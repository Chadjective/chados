#!/usr/bin/env python3
"""Google Photos Takeout importer.

Scans extracted Takeout folders for photos/videos, reads JSON sidecar metadata,
generates thumbnails, and imports everything into the archive database.

Usage:
    python photo_importer.py [/path/to/Takeout/Zip/Files]

It will find all "Takeout*/Google Photos/" folders under the given path.
"""

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from config import DB_PATH, THUMBNAILS_DIR, get_ffmpeg_path, ensure_dirs
from database import get_connection, init_db

# Media file extensions we care about
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif', '.bmp', '.tiff', '.tif', '.nef', '.cr2', '.arw', '.dng', '.raw'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.mpg', '.mpeg'}
MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS

# Thumbnail settings
THUMB_SIZE = (400, 400)
THUMB_QUALITY = 80


def file_hash(filepath, chunk_size=65536):
    """Compute a fast hash of file (first 64KB + size) for dedup."""
    h = hashlib.md5()
    size = os.path.getsize(filepath)
    h.update(str(size).encode())
    with open(filepath, 'rb') as f:
        chunk = f.read(chunk_size)
        h.update(chunk)
    return h.hexdigest()


def find_json_sidecar(media_path):
    """Find the JSON metadata sidecar for a media file.

    Google Takeout uses several naming conventions:
    - photo.jpg.json (most common)
    - photo.json (older format)
    - photo(1).jpg.json (for duplicates)
    """
    p = Path(media_path)

    # Try: photo.jpg.json
    sidecar = p.parent / (p.name + '.json')
    if sidecar.exists():
        return sidecar

    # Try: photo.json (without the media extension)
    sidecar = p.parent / (p.stem + '.json')
    if sidecar.exists():
        return sidecar

    # Try with edited suffix: photo-edited.jpg -> photo.jpg.json
    edited_match = re.match(r'^(.+)-edited(\.\w+)$', p.name, re.IGNORECASE)
    if edited_match:
        original_name = edited_match.group(1) + edited_match.group(2)
        sidecar = p.parent / (original_name + '.json')
        if sidecar.exists():
            return sidecar

    # Try truncated name (Google truncates long filenames at 46 chars)
    if len(p.stem) >= 46:
        for json_file in p.parent.glob('*.json'):
            if json_file.stem.startswith(p.stem[:46]):
                return json_file

    return None


def parse_json_metadata(json_path):
    """Parse Google Photos JSON sidecar metadata."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}

    meta = {}

    meta['title'] = data.get('title', '')
    meta['description'] = data.get('description', '')
    meta['google_photos_url'] = data.get('url', '')

    # Photo taken time
    taken = data.get('photoTakenTime', {})
    if taken.get('timestamp'):
        ts = int(taken['timestamp'])
        meta['date_taken_unix'] = ts
        meta['date_taken'] = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

    # Creation time
    created = data.get('creationTime', {})
    if created.get('timestamp'):
        ts = int(created['timestamp'])
        meta['creation_unix'] = ts
        meta['date_created'] = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

    # Geo data
    geo = data.get('geoData', {})
    if geo.get('latitude', 0) != 0 or geo.get('longitude', 0) != 0:
        meta['latitude'] = geo.get('latitude')
        meta['longitude'] = geo.get('longitude')
        meta['altitude'] = geo.get('altitude')

    # Fall back to EXIF geo
    if 'latitude' not in meta:
        geo_exif = data.get('geoDataExif', {})
        if geo_exif.get('latitude', 0) != 0 or geo_exif.get('longitude', 0) != 0:
            meta['latitude'] = geo_exif.get('latitude')
            meta['longitude'] = geo_exif.get('longitude')
            meta['altitude'] = geo_exif.get('altitude')

    # Device type
    origin = data.get('googlePhotosOrigin', {})
    if 'mobileUpload' in origin:
        meta['device_type'] = origin['mobileUpload'].get('deviceType', '')

    # Favorite
    if data.get('favorited'):
        meta['is_favorite'] = 1

    return meta


def get_exif_date(filepath):
    """Extract date taken from image EXIF data using Pillow.

    Returns (iso_string, unix_timestamp) or (None, None) if not available.
    """
    try:
        from PIL import Image
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            pass

        with Image.open(filepath) as img:
            exif_data = img.getexif()
            if not exif_data:
                return None, None

            # Try DateTimeOriginal (36867), then DateTimeDigitized (36868), then DateTime (306)
            date_str = None
            for tag_id in (36867, 36868, 306):
                val = exif_data.get(tag_id)
                if val and isinstance(val, str) and val.strip() and val.strip() != '0000:00:00 00:00:00':
                    date_str = val.strip()
                    break

            if not date_str:
                return None, None

            # EXIF date format: "YYYY:MM:DD HH:MM:SS"
            dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat(), int(dt.timestamp())
    except Exception:
        return None, None


def get_image_dimensions(filepath):
    """Get image width and height using Pillow."""
    try:
        from PIL import Image
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            pass

        with Image.open(filepath) as img:
            return img.size  # (width, height)
    except Exception:
        return None, None


def get_video_info(filepath, ffmpeg_path):
    """Get video dimensions and duration using ffprobe."""
    try:
        ffprobe = ffmpeg_path.replace('ffmpeg', 'ffprobe') if 'ffmpeg' in ffmpeg_path else 'ffprobe'
        # If ffprobe doesn't exist, try ffmpeg -i approach
        result = subprocess.run(
            [ffmpeg_path, '-i', str(filepath), '-hide_banner'],
            capture_output=True, text=True, timeout=10
        )
        output = result.stderr

        # Parse duration
        duration_match = re.search(r'Duration:\s*(\d+):(\d+):(\d+)\.(\d+)', output)
        duration = None
        if duration_match:
            h, m, s, cs = duration_match.groups()
            duration = int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100

        # Parse video dimensions
        dim_match = re.search(r'(\d{2,5})x(\d{2,5})', output)
        width, height = None, None
        if dim_match:
            width, height = int(dim_match.group(1)), int(dim_match.group(2))

        return width, height, duration
    except Exception:
        return None, None, None


def generate_thumbnail(filepath, thumb_path, is_video=False, ffmpeg_path='ffmpeg'):
    """Generate a thumbnail for an image or video."""
    try:
        thumb_path = Path(thumb_path)
        thumb_path.parent.mkdir(parents=True, exist_ok=True)

        if is_video:
            # Extract a frame at 1 second (or 0 for very short videos)
            subprocess.run(
                [ffmpeg_path, '-y', '-i', str(filepath),
                 '-ss', '1', '-vframes', '1',
                 '-vf', f'scale={THUMB_SIZE[0]}:{THUMB_SIZE[1]}:force_original_aspect_ratio=decrease',
                 '-q:v', '5', str(thumb_path)],
                capture_output=True, timeout=30
            )
            return thumb_path.exists()
        else:
            from PIL import Image
            try:
                import pillow_heif
                pillow_heif.register_heif_opener()
            except ImportError:
                pass

            with Image.open(filepath) as img:
                # Handle EXIF orientation
                try:
                    from PIL import ImageOps
                    img = ImageOps.exif_transpose(img)
                except Exception:
                    pass

                img.thumbnail(THUMB_SIZE, Image.LANCZOS)
                # Convert to RGB if necessary (for RGBA, P mode, etc.)
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                img.save(str(thumb_path), 'JPEG', quality=THUMB_QUALITY)
                return True
    except Exception as e:
        # Silently skip thumbnail failures
        return False


def guess_mime_type(filepath):
    """Guess MIME type from extension."""
    ext = Path(filepath).suffix.lower()
    mime_map = {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.png': 'image/png', '.gif': 'image/gif',
        '.webp': 'image/webp', '.heic': 'image/heic',
        '.heif': 'image/heif', '.bmp': 'image/bmp',
        '.tiff': 'image/tiff', '.tif': 'image/tiff',
        '.nef': 'image/x-nikon-nef', '.cr2': 'image/x-canon-cr2',
        '.arw': 'image/x-sony-arw', '.dng': 'image/x-adobe-dng',
        '.raw': 'image/raw',
        '.mp4': 'video/mp4', '.mov': 'video/quicktime',
        '.avi': 'video/x-msvideo', '.mkv': 'video/x-matroska',
        '.wmv': 'video/x-ms-wmv', '.flv': 'video/x-flv',
        '.webm': 'video/webm', '.m4v': 'video/x-m4v',
        '.3gp': 'video/3gpp', '.mpg': 'video/mpeg', '.mpeg': 'video/mpeg',
    }
    return mime_map.get(ext, 'application/octet-stream')


def find_google_photos_dirs(base_path):
    """Find all Google Photos directories under the base path."""
    base = Path(base_path)
    dirs = []
    for d in sorted(base.rglob('Google Photos')):
        if d.is_dir():
            dirs.append(d)
    return dirs


def scan_media_files(photos_dirs):
    """Scan all Google Photos directories and return (media_path, album_name) tuples."""
    files = []
    for gp_dir in photos_dirs:
        for album_dir in sorted(gp_dir.iterdir()):
            if not album_dir.is_dir():
                continue
            album_name = album_dir.name
            for f in sorted(album_dir.iterdir()):
                if not f.is_file():
                    continue
                # Skip macOS resource fork files and other junk
                if f.name.startswith('._') or f.name == '.DS_Store':
                    continue
                if f.suffix.lower() in MEDIA_EXTS:
                    files.append((str(f), album_name))
    return files


def import_photos(base_path, skip_thumbnails=False):
    """Main import function for Google Photos Takeout data."""
    ensure_dirs()
    init_db(skip_fts=True)

    ffmpeg_path = get_ffmpeg_path()

    print(f"Scanning for Google Photos in: {base_path}")
    photos_dirs = find_google_photos_dirs(base_path)
    if not photos_dirs:
        print("No Google Photos directories found!")
        sys.exit(1)

    print(f"Found {len(photos_dirs)} Google Photos directories:")
    for d in photos_dirs:
        print(f"  {d}")

    print("\nScanning for media files...")
    media_files = scan_media_files(photos_dirs)
    total = len(media_files)
    print(f"Found {total:,} media files")

    if total == 0:
        print("Nothing to import.")
        return

    conn = get_connection()
    # DB is on internal SSD (APFS) so WAL mode is safe and allows concurrent reads
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")
    cursor = conn.cursor()

    # Load existing file paths for skip/resume
    existing = set()
    try:
        for row in cursor.execute("SELECT file_path FROM photos"):
            existing.add(row[0])
    except sqlite3.OperationalError:
        pass
    print(f"  {len(existing):,} photos already in database")

    # Cache album IDs
    album_cache = {}
    try:
        for row in cursor.execute("SELECT id, name FROM albums"):
            album_cache[row['name']] = row['id']
    except sqlite3.OperationalError:
        pass

    imported = 0
    skipped = 0
    errors = 0
    thumb_generated = 0
    start_time = time.time()
    batch_count = 0
    BATCH_SIZE = 100

    for i, (filepath, album_name) in enumerate(media_files):
        # Skip already imported
        if filepath in existing:
            skipped += 1
            continue

        try:
            stat = os.stat(filepath)
            ext = Path(filepath).suffix.lower()
            is_video = ext in VIDEO_EXTS
            filename = Path(filepath).name
            mime = guess_mime_type(filepath)
            fhash = file_hash(filepath)

            # Check for duplicate by hash
            dup = cursor.execute(
                "SELECT id FROM photos WHERE file_hash = ?", (fhash,)
            ).fetchone()

            if dup:
                # Link to existing album but don't re-import
                photo_id = dup['id']
                skipped += 1
            else:
                # Parse JSON sidecar
                meta = {}
                sidecar = find_json_sidecar(filepath)
                if sidecar:
                    meta = parse_json_metadata(sidecar)

                # Get dimensions
                width, height, duration = None, None, None
                if is_video:
                    width, height, duration = get_video_info(filepath, ffmpeg_path)
                else:
                    dims = get_image_dimensions(filepath)
                    if dims:
                        width, height = dims

                # Date priority: JSON photoTakenTime > JSON creationTime > EXIF > file mtime
                date_taken_unix = meta.get('date_taken_unix')
                date_taken = meta.get('date_taken')
                if not date_taken_unix and meta.get('creation_unix'):
                    # Use JSON creationTime as fallback
                    date_taken_unix = meta['creation_unix']
                    date_taken = meta['date_created']
                if not date_taken_unix and not is_video:
                    # Try EXIF data from image file
                    exif_date, exif_unix = get_exif_date(filepath)
                    if exif_unix:
                        date_taken_unix = exif_unix
                        date_taken = exif_date
                if not date_taken_unix:
                    # Last resort: file modification time
                    date_taken_unix = int(stat.st_mtime)
                    date_taken = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

                # Generate thumbnail
                thumb_path_str = None
                if not skip_thumbnails:
                    # Organize thumbnails by date: YYYY/MM/
                    dt = datetime.fromtimestamp(date_taken_unix, tz=timezone.utc)
                    thumb_dir = THUMBNAILS_DIR / f"{dt.year}" / f"{dt.month:02d}"
                    thumb_filename = f"{fhash}.jpg"
                    thumb_full = thumb_dir / thumb_filename

                    if not thumb_full.exists():
                        if generate_thumbnail(filepath, thumb_full, is_video=is_video, ffmpeg_path=ffmpeg_path):
                            thumb_generated += 1
                            thumb_path_str = str(thumb_full)
                    else:
                        thumb_path_str = str(thumb_full)

                cursor.execute("""
                    INSERT INTO photos (
                        file_path, filename, title, description, mime_type,
                        width, height, size_bytes, date_taken, date_taken_unix,
                        date_created, creation_unix, latitude, longitude, altitude,
                        camera_make, camera_model, device_type, is_video,
                        duration_seconds, thumbnail_path, google_photos_url,
                        is_favorite, source_album, file_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    filepath, filename,
                    meta.get('title', filename),
                    meta.get('description', ''),
                    mime,
                    width, height, stat.st_size,
                    date_taken, date_taken_unix,
                    meta.get('date_created'), meta.get('creation_unix'),
                    meta.get('latitude'), meta.get('longitude'), meta.get('altitude'),
                    meta.get('camera_make'), meta.get('camera_model'),
                    meta.get('device_type'),
                    1 if is_video else 0,
                    duration if is_video else None,
                    thumb_path_str,
                    meta.get('google_photos_url', ''),
                    meta.get('is_favorite', 0),
                    album_name,
                    fhash,
                ))
                photo_id = cursor.lastrowid
                imported += 1

            # Link to album
            if album_name and not album_name.startswith('.'):
                if album_name not in album_cache:
                    cursor.execute(
                        "INSERT OR IGNORE INTO albums (name) VALUES (?)",
                        (album_name,)
                    )
                    aid = cursor.execute(
                        "SELECT id FROM albums WHERE name = ?", (album_name,)
                    ).fetchone()['id']
                    album_cache[album_name] = aid

                cursor.execute(
                    "INSERT OR IGNORE INTO photo_albums (photo_id, album_id) VALUES (?, ?)",
                    (photo_id, album_cache[album_name])
                )

            batch_count += 1
            if batch_count >= BATCH_SIZE:
                conn.commit()
                batch_count = 0

        except Exception as e:
            errors += 1
            if errors <= 20:
                print(f"\n  Error on {Path(filepath).name}: {e}")
            elif errors == 21:
                print("\n  (Suppressing further error messages...)")

        # Progress
        processed = i + 1
        if processed % 50 == 0 or processed == total:
            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 else 0
            pct = processed / total * 100
            eta = (total - processed) / rate / 60 if rate > 0 else 0
            print(
                f"\r  [{pct:5.1f}%] Processed: {processed:>8,} | "
                f"Imported: {imported:>8,} | Skipped: {skipped:>7,} | "
                f"Errors: {errors:>5,} | Thumbs: {thumb_generated:>6,} | "
                f"{rate:.0f}/sec | ETA: {eta:.1f}m",
                end="", flush=True
            )

    # Final commit
    if batch_count > 0:
        conn.commit()

    # Update album counts and cover photos
    print("\n\nUpdating album counts and covers...")
    cursor.execute("""
        UPDATE albums SET
            photo_count = (
                SELECT COUNT(*) FROM photo_albums WHERE album_id = albums.id
            ),
            cover_photo_id = (
                SELECT pa.photo_id FROM photo_albums pa
                JOIN photos p ON p.id = pa.photo_id
                WHERE pa.album_id = albums.id
                ORDER BY p.date_taken_unix DESC
                LIMIT 1
            )
    """)
    conn.commit()

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"PHOTO IMPORT COMPLETE! Total time: {elapsed/60:.1f}m")
    print(f"  Imported: {imported:,}")
    print(f"  Skipped (already imported or duplicate): {skipped:,}")
    print(f"  Errors: {errors:,}")
    print(f"  Thumbnails generated: {thumb_generated:,}")

    # Stats
    total_photos = cursor.execute("SELECT COUNT(*) FROM photos WHERE is_video = 0").fetchone()[0]
    total_videos = cursor.execute("SELECT COUNT(*) FROM photos WHERE is_video = 1").fetchone()[0]
    total_albums = cursor.execute("SELECT COUNT(*) FROM albums").fetchone()[0]
    print(f"\n  Total photos in DB: {total_photos:,}")
    print(f"  Total videos in DB: {total_videos:,}")
    print(f"  Total albums: {total_albums:,}")
    print(f"{'='*60}")

    conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        from config import PHOTOS_TAKEOUT_BASE
        path = PHOTOS_TAKEOUT_BASE

    import_photos(path)
