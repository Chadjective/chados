#!/usr/bin/env python3
"""Google Drive file catalog importer.

Catalogs all files from the Google Takeout Drive export, extracts text
from supported formats (.txt, .html, .csv), and stores metadata for others.

Usage:
    python drive_importer.py /path/to/Takeout/Drive
"""

import csv
import io
import json
import mimetypes
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from database import get_connection, init_db
from config import ensure_dirs


# MIME type mapping for common extensions
EXTRA_MIME = {
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.mov': 'video/quicktime',
    '.heic': 'image/heic',
}

# Extensions for which we extract text content
TEXT_EXTRACTABLE = {'.txt', '.text', '.md', '.markdown', '.rst', '.log', '.csv', '.tsv',
                     '.json', '.xml', '.yaml', '.yml', '.ini', '.cfg', '.conf',
                     '.py', '.js', '.ts', '.html', '.htm', '.css', '.sql', '.sh', '.bat'}

# Maximum text to extract per file (100KB)
MAX_TEXT_EXTRACT = 100_000


def guess_mime(filepath):
    """Guess MIME type from file extension."""
    ext = Path(filepath).suffix.lower()
    if ext in EXTRA_MIME:
        return EXTRA_MIME[ext]
    mime, _ = mimetypes.guess_type(str(filepath))
    return mime or 'application/octet-stream'


def extract_text_from_html(filepath):
    """Extract readable text from an HTML file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read(MAX_TEXT_EXTRACT * 2)

        # Strip HTML tags
        text = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)

        # Decode HTML entities
        try:
            import html
            text = html.unescape(text)
        except ImportError:
            pass

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:MAX_TEXT_EXTRACT]

    except Exception:
        return None


def extract_text_from_csv(filepath):
    """Extract text content from a CSV file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.reader(f)
            rows = []
            for i, row in enumerate(reader):
                if i > 500:  # Cap at 500 rows
                    rows.append('... (truncated)')
                    break
                rows.append(' | '.join(row))
            text = '\n'.join(rows)
            return text[:MAX_TEXT_EXTRACT]
    except Exception:
        return None


def extract_text(filepath):
    """Extract text content from a file if possible."""
    ext = Path(filepath).suffix.lower()

    if ext not in TEXT_EXTRACTABLE:
        return None

    if ext in ('.html', '.htm'):
        return extract_text_from_html(filepath)

    if ext in ('.csv', '.tsv'):
        return extract_text_from_csv(filepath)

    # Plain text files
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read(MAX_TEXT_EXTRACT)
        return text.strip() if text.strip() else None
    except Exception:
        return None


def scan_drive_files(drive_dir):
    """Recursively scan the Drive directory and yield (filepath, rel_path, parent_rel) tuples."""
    drive_path = Path(drive_dir)

    for root, dirs, files in os.walk(drive_path):
        # Skip macOS junk
        dirs[:] = [d for d in dirs if not d.startswith('.')]

        root_path = Path(root)
        rel_root = root_path.relative_to(drive_path)

        # Yield folders
        for d in sorted(dirs):
            folder_path = root_path / d
            rel_path = str(folder_path.relative_to(drive_path))
            parent_rel = str(rel_root) if str(rel_root) != '.' else ''
            yield str(folder_path), rel_path, parent_rel, True

        # Yield files
        for fname in sorted(files):
            if fname.startswith('.') or fname == '.DS_Store':
                continue
            filepath = root_path / fname
            rel_path = str(filepath.relative_to(drive_path))
            parent_rel = str(rel_root) if str(rel_root) != '.' else ''
            yield str(filepath), rel_path, parent_rel, False


def import_drive(drive_path):
    """Import Google Drive files from Takeout directory."""
    drive_dir = Path(drive_path)
    if not drive_dir.exists():
        print(f"Error: Drive directory not found: {drive_dir}")
        sys.exit(1)

    ensure_dirs()
    init_db(skip_fts=True)

    print(f"Scanning Drive files in: {drive_dir}")

    # Count files first
    print("Counting files...")
    all_items = list(scan_drive_files(drive_dir))
    total = len(all_items)
    file_count = sum(1 for _, _, _, is_folder in all_items if not is_folder)
    folder_count = sum(1 for _, _, _, is_folder in all_items if is_folder)
    print(f"Found {file_count:,} files and {folder_count:,} folders")

    if total == 0:
        print("Nothing to import.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    # Load existing paths for dedup
    existing = set()
    try:
        for row in cursor.execute("SELECT path FROM drive_files"):
            existing.add(row[0])
    except Exception:
        pass
    print(f"  {len(existing):,} items already in database")

    start_time = time.time()
    imported = 0
    skipped = 0
    errors = 0
    text_extracted = 0

    for i, (filepath, rel_path, parent_path, is_folder) in enumerate(all_items):
        # Skip already imported
        if rel_path in existing:
            skipped += 1
            continue

        try:
            filename = Path(filepath).name

            if is_folder:
                cursor.execute("""
                    INSERT OR IGNORE INTO drive_files
                    (filename, path, parent_path, mime_type, size_bytes,
                     modified_time, modified_unix, is_folder, source_file)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                """, (
                    filename, rel_path, parent_path,
                    'inode/directory', 0, None, None, str(filepath),
                ))
            else:
                try:
                    stat = os.stat(filepath)
                    size = stat.st_size
                    mtime = stat.st_mtime
                    mtime_iso = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
                    mtime_unix = int(mtime)
                except OSError:
                    size = 0
                    mtime_iso = None
                    mtime_unix = None

                mime = guess_mime(filepath)

                # Extract text if possible
                extracted = extract_text(filepath)
                if extracted:
                    text_extracted += 1

                cursor.execute("""
                    INSERT OR IGNORE INTO drive_files
                    (filename, path, parent_path, mime_type, size_bytes,
                     modified_time, modified_unix, is_folder, extracted_text, source_file)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """, (
                    filename, rel_path, parent_path,
                    mime, size, mtime_iso, mtime_unix,
                    extracted, str(filepath),
                ))

            if cursor.rowcount > 0:
                imported += 1
                existing.add(rel_path)
            else:
                skipped += 1

        except Exception as e:
            errors += 1
            if errors <= 20:
                print(f"\n  Error on {Path(filepath).name}: {e}")
            elif errors == 21:
                print("\n  (Suppressing further error messages...)")

        # Commit and report progress
        processed = i + 1
        if processed % 50 == 0:
            conn.commit()

        if processed % 50 == 0 or processed == total:
            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 else 0
            pct = processed / total * 100
            print(f"\r  [{pct:5.1f}%] Processed: {processed:>6,} | "
                  f"Imported: {imported:>6,} | Skipped: {skipped:>5,} | "
                  f"Text: {text_extracted:>4,} | Errors: {errors:>4,} | "
                  f"{rate:.0f}/sec",
                  end="", flush=True)

    conn.commit()

    elapsed = time.time() - start_time
    print(f"\n\n{'='*60}")
    print(f"DRIVE IMPORT COMPLETE! Time: {elapsed:.1f}s")
    print(f"  Imported:       {imported:,}")
    print(f"  Skipped:        {skipped:,} (duplicates)")
    print(f"  Text extracted: {text_extracted:,}")
    print(f"  Errors:         {errors:,}")

    # Stats by type
    cursor.execute("""
        SELECT mime_type, COUNT(*) as cnt
        FROM drive_files WHERE is_folder = 0
        GROUP BY mime_type ORDER BY cnt DESC LIMIT 15
    """)
    print(f"\n  Files by type:")
    for row in cursor.fetchall():
        print(f"    {row[0]}: {row[1]:,}")

    total_db = cursor.execute("SELECT COUNT(*) FROM drive_files").fetchone()[0]
    total_size = cursor.execute("SELECT SUM(size_bytes) FROM drive_files WHERE is_folder = 0").fetchone()[0] or 0
    print(f"\n  Total items in DB: {total_db:,}")
    print(f"  Total size: {total_size / (1024**2):.1f} MB")
    print(f"{'='*60}")

    conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = "/Volumes/backup Plus/TakeOut/other product takeouts/Takeout 2/Drive"

    import_drive(path)
