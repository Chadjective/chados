#!/usr/bin/env python3
"""Local-folder / external-drive photo importer (ChadOS v4).

A source-agnostic counterpart to ``photo_importer.py`` (the Takeout importer).
It walks an arbitrary folder — e.g. an external drive — reads metadata from
EXIF only (no Google JSON sidecar), generates local thumbnails, dedups by file
hash, and indexes photos *in place*: ``file_path`` points at the original on the
drive, so nothing is copied. ``import_source`` is ``'local_folder'``.

Reuses the existing import core from ``photo_importer`` (hashing, EXIF date/GPS,
dimensions, video probe, thumbnailing, mime guessing) so the two sources stay
consistent.
"""

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from config import THUMBNAILS_DIR, get_ffmpeg_path, ensure_dirs
from database import get_connection
from photo_importer import (
    IMAGE_EXTS, VIDEO_EXTS, MEDIA_EXTS,
    file_hash, get_exif_date, get_exif_gps,
    get_image_dimensions, get_video_info,
    generate_thumbnail, guess_mime_type,
)

# Directories we never descend into (OS/backup cruft).
SKIP_DIRS = {
    '.Trashes', '.Spotlight-V100', '.fseventsd', '.DocumentRevisions-V100',
    '.TemporaryItems', '.PKInstallSandboxManager', '.HFS+ Private Directory Data',
    '#recycle', '$RECYCLE.BIN', 'System Volume Information',
    '.git', 'node_modules', 'Library', 'Caches', 'tmp',
}


def scan_folder(root: str, recursive: bool = True):
    """Yield absolute paths of media files under ``root``.

    Skips macOS resource forks (``._*``), ``.DS_Store``, and the system/backup
    directories in ``SKIP_DIRS``.
    """
    root_path = Path(root)
    if not root_path.exists():
        return

    if not recursive:
        for f in sorted(root_path.iterdir()):
            if f.is_file() and _is_media(f):
                yield str(f)
        return

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Prune skip dirs and hidden dirs in place so os.walk won't descend.
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith('._')
        ]
        for name in sorted(filenames):
            f = Path(dirpath) / name
            if _is_media(f):
                yield str(f)


def _is_media(f: Path) -> bool:
    name = f.name
    if name.startswith('._') or name == '.DS_Store':
        return False
    return f.suffix.lower() in MEDIA_EXTS


def import_folder(
    root: str,
    recursive: bool = True,
    source_label: Optional[str] = None,
    on_progress: Optional[Callable[[dict], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> dict:
    """Import every media file under ``root`` into the photos table.

    Photos are indexed in place (``file_path`` = original location) with
    ``import_source='local_folder'`` and ``location_source='exif'`` when GPS is
    present in the EXIF. Dedups against existing rows by ``file_path`` (resume)
    and by ``file_hash`` (the same photo living on another drive / backup).

    ``on_progress`` is called periodically with a stats dict; ``should_cancel``
    is polled cooperatively so a job can be cancelled mid-run.
    """
    ensure_dirs()
    ffmpeg_path = get_ffmpeg_path()
    if source_label is None:
        source_label = Path(root).name or root

    stats = {
        "total": 0, "processed": 0, "imported": 0,
        "skipped": 0, "errors": 0, "geotagged": 0,
        "phase": "scanning",
    }

    # --- Phase 1: discover files (so we have a meaningful total / ETA) ---
    media_files = []
    for fp in scan_folder(root, recursive=recursive):
        media_files.append(fp)
        if len(media_files) % 500 == 0:
            stats["total"] = len(media_files)
            if on_progress:
                on_progress(stats)
            if should_cancel and should_cancel():
                stats["phase"] = "cancelled"
                return stats
    stats["total"] = len(media_files)
    stats["phase"] = "importing"
    if on_progress:
        on_progress(stats)

    if not media_files:
        stats["phase"] = "done"
        return stats

    conn = get_connection()
    cursor = conn.cursor()

    # Existing file paths → resume / re-run safety.
    existing_paths = set()
    for row in cursor.execute("SELECT file_path FROM photos"):
        existing_paths.add(row[0])

    batch_count = 0
    BATCH_SIZE = 100
    last_report = time.time()

    for fp in media_files:
        stats["processed"] += 1

        if should_cancel and should_cancel():
            conn.commit()
            stats["phase"] = "cancelled"
            if on_progress:
                on_progress(stats)
            conn.close()
            return stats

        if fp in existing_paths:
            stats["skipped"] += 1
        else:
            try:
                _import_one(cursor, fp, source_label, ffmpeg_path, stats)
                batch_count += 1
                if batch_count >= BATCH_SIZE:
                    conn.commit()
                    batch_count = 0
            except Exception as exc:  # never let one bad file kill the job
                stats["errors"] += 1
                stats.setdefault("last_error", str(exc))

        # Throttle progress reporting to ~2/sec.
        now = time.time()
        if on_progress and (now - last_report > 0.5 or stats["processed"] == stats["total"]):
            on_progress(stats)
            last_report = now

    conn.commit()
    conn.close()
    stats["phase"] = "done"
    if on_progress:
        on_progress(stats)
    return stats


def _import_one(cursor, filepath, source_label, ffmpeg_path, stats):
    """Index a single media file (already known not to be a path-duplicate)."""
    stat = os.stat(filepath)
    ext = Path(filepath).suffix.lower()
    is_video = ext in VIDEO_EXTS
    filename = Path(filepath).name
    mime = guess_mime_type(filepath)
    fhash = file_hash(filepath)

    # Content duplicate (same photo on another drive / backup) → skip.
    dup = cursor.execute(
        "SELECT id FROM photos WHERE file_hash = ?", (fhash,)
    ).fetchone()
    if dup:
        stats["skipped"] += 1
        return

    # Dimensions / duration
    width = height = duration = None
    if is_video:
        width, height, duration = get_video_info(filepath, ffmpeg_path)
    else:
        dims = get_image_dimensions(filepath)
        if dims:
            width, height = dims

    # Date: EXIF DateTimeOriginal, else file mtime.
    date_taken = date_taken_unix = None
    if not is_video:
        date_taken, date_taken_unix = get_exif_date(filepath)
    if not date_taken_unix:
        date_taken_unix = int(stat.st_mtime)
        date_taken = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

    # GPS straight from EXIF (Takeout strips this; phone/camera photos keep it).
    latitude = longitude = altitude = None
    location_source = None
    if not is_video:
        latitude, longitude, altitude = get_exif_gps(filepath)
        if latitude is not None:
            location_source = 'exif'
            stats["geotagged"] += 1

    # Thumbnail (local cache, keyed by hash so it dedups too).
    thumb_path_str = None
    dt = datetime.fromtimestamp(date_taken_unix, tz=timezone.utc)
    thumb_full = THUMBNAILS_DIR / f"{dt.year}" / f"{dt.month:02d}" / f"{fhash}.jpg"
    if thumb_full.exists():
        thumb_path_str = str(thumb_full)
    elif generate_thumbnail(filepath, thumb_full, is_video=is_video, ffmpeg_path=ffmpeg_path):
        thumb_path_str = str(thumb_full)

    cursor.execute(
        """
        INSERT INTO photos (
            file_path, filename, title, description, mime_type,
            width, height, size_bytes, date_taken, date_taken_unix,
            latitude, longitude, altitude, is_video, duration_seconds,
            thumbnail_path, source_album, file_hash,
            import_source, location_source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            filepath, filename, filename, '', mime,
            width, height, stat.st_size, date_taken, date_taken_unix,
            latitude, longitude, altitude, 1 if is_video else 0,
            duration if is_video else None,
            thumb_path_str, source_label, fhash,
            'local_folder', location_source,
        ),
    )
    stats["imported"] += 1
