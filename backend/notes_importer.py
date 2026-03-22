#!/usr/bin/env python3
"""Google Keep notes importer.

Parses Google Keep notes from Google Takeout export. Supports both
JSON format (newer exports) and HTML format (older exports).

Usage:
    python notes_importer.py /path/to/Takeout/Keep

If no Keep data is found in the Takeout, the importer exits gracefully.
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from database import get_connection, init_db
from config import ensure_dirs


def extract_text_from_html(html_content):
    """Strip HTML tags and extract plain text."""
    text = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<br\s*/?\s*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<li[^>]*>', '\n- ', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)

    try:
        import html
        text = html.unescape(text)
    except ImportError:
        pass

    # Clean up whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def parse_keep_json(json_path):
    """Parse a Google Keep JSON export file."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return None

    note = {
        'title': data.get('title', ''),
        'content': '',
        'color': data.get('color', ''),
        'labels': [],
        'is_archived': 1 if data.get('isArchived') else 0,
        'is_pinned': 1 if data.get('isPinned') else 0,
        'is_trashed': 1 if data.get('isTrashed') else 0,
        'created_time': None,
        'modified_time': None,
        'source_file': str(json_path),
    }

    # Content: either textContent or listContent
    if data.get('textContent'):
        note['content'] = data['textContent']
    elif data.get('listContent'):
        items = []
        for item in data['listContent']:
            text = item.get('text', '')
            checked = item.get('isChecked', False)
            prefix = '[x]' if checked else '[ ]'
            items.append(f"{prefix} {text}")
        note['content'] = '\n'.join(items)

    # Labels
    for label in data.get('labels', []):
        if label.get('name'):
            note['labels'].append(label['name'])

    # Timestamps (microseconds)
    if data.get('createdTimestampUsec'):
        ts = int(data['createdTimestampUsec']) / 1_000_000
        note['created_time'] = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    if data.get('userEditedTimestampUsec'):
        ts = int(data['userEditedTimestampUsec']) / 1_000_000
        note['modified_time'] = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

    return note


def parse_keep_html(html_path):
    """Parse a Google Keep HTML export file (older format)."""
    try:
        with open(html_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except FileNotFoundError:
        return None

    note = {
        'title': '',
        'content': '',
        'color': '',
        'labels': [],
        'is_archived': 0,
        'is_pinned': 0,
        'is_trashed': 0,
        'created_time': None,
        'modified_time': None,
        'source_file': str(html_path),
    }

    # Extract title from <title> or first heading
    title_match = re.search(r'<title>(.+?)</title>', content, re.IGNORECASE)
    if title_match:
        note['title'] = extract_text_from_html(title_match.group(1))

    # Extract heading if no title
    if not note['title']:
        h_match = re.search(r'<h[1-6][^>]*>(.+?)</h[1-6]>', content, re.IGNORECASE)
        if h_match:
            note['title'] = extract_text_from_html(h_match.group(1))

    # Extract body content
    body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
    if body_match:
        note['content'] = extract_text_from_html(body_match.group(1))
    else:
        note['content'] = extract_text_from_html(content)

    # Extract color from background-color style
    color_match = re.search(r'background-color:\s*([^;"]+)', content, re.IGNORECASE)
    if color_match:
        note['color'] = color_match.group(1).strip()

    # Extract labels from class names or data attributes
    label_matches = re.findall(r'class="label[^"]*"[^>]*>([^<]+)', content, re.IGNORECASE)
    note['labels'] = [l.strip() for l in label_matches if l.strip()]

    # Try to get archived/pinned status from class names
    if 'archived' in content.lower():
        note['is_archived'] = 1
    if 'pinned' in content.lower():
        note['is_pinned'] = 1

    return note


def import_notes(notes_path):
    """Import Google Keep notes from Takeout directory."""
    notes_dir = Path(notes_path)

    if not notes_dir.exists():
        print(f"No Keep/Notes directory found at: {notes_dir}")
        print("This Takeout may not include Google Keep data. Skipping.")
        return

    ensure_dirs()
    init_db(skip_fts=True)

    # Find note files (JSON preferred, fall back to HTML)
    json_files = sorted(notes_dir.glob('*.json'))
    html_files = sorted(notes_dir.glob('*.html'))

    # Filter out non-note JSON files
    json_files = [f for f in json_files if f.name not in ('labels.json', 'trash.json')]

    total_files = len(json_files) + len(html_files)
    if total_files == 0:
        print(f"No note files found in {notes_dir}")
        print("Skipping notes import.")
        return

    print(f"Found {len(json_files)} JSON notes and {len(html_files)} HTML notes")

    conn = get_connection()
    cursor = conn.cursor()

    # Load existing for dedup
    existing = set()
    try:
        for row in cursor.execute("SELECT source_file FROM notes"):
            existing.add(row[0])
    except Exception:
        pass

    start_time = time.time()
    imported = 0
    skipped = 0
    errors = 0

    # Process JSON files first (preferred format)
    for f in json_files:
        source = str(f)
        if source in existing:
            skipped += 1
            continue

        try:
            note = parse_keep_json(f)
            if not note:
                errors += 1
                continue

            labels_json = json.dumps(note['labels']) if note['labels'] else None

            cursor.execute("""
                INSERT OR IGNORE INTO notes
                (title, content, color, labels, is_archived, is_pinned,
                 is_trashed, created_time, modified_time, source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                note['title'], note['content'], note['color'],
                labels_json, note['is_archived'], note['is_pinned'],
                note['is_trashed'], note['created_time'], note['modified_time'],
                source,
            ))

            if cursor.rowcount > 0:
                imported += 1
                existing.add(source)
            else:
                skipped += 1

        except Exception as e:
            errors += 1
            if errors <= 20:
                print(f"  Error on {f.name}: {e}")

    # Process HTML files (only if not already covered by JSON)
    for f in html_files:
        source = str(f)
        if source in existing:
            skipped += 1
            continue

        try:
            note = parse_keep_html(f)
            if not note:
                errors += 1
                continue

            labels_json = json.dumps(note['labels']) if note['labels'] else None

            cursor.execute("""
                INSERT OR IGNORE INTO notes
                (title, content, color, labels, is_archived, is_pinned,
                 is_trashed, created_time, modified_time, source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                note['title'], note['content'], note['color'],
                labels_json, note['is_archived'], note['is_pinned'],
                note['is_trashed'], note['created_time'], note['modified_time'],
                source,
            ))

            if cursor.rowcount > 0:
                imported += 1
                existing.add(source)
            else:
                skipped += 1

        except Exception as e:
            errors += 1
            if errors <= 20:
                print(f"  Error on {f.name}: {e}")

    conn.commit()

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"NOTES IMPORT COMPLETE! Time: {elapsed:.1f}s")
    print(f"  Imported: {imported:,}")
    print(f"  Skipped:  {skipped:,}")
    print(f"  Errors:   {errors:,}")

    total_db = cursor.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    print(f"  Total notes in DB: {total_db:,}")
    print(f"{'='*60}")

    conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        # Try common Keep locations in Takeout
        candidates = [
            "/Volumes/backup Plus/TakeOut/other product takeouts/Takeout 2/Keep",
            "/Volumes/backup Plus/TakeOut/other product takeouts/Takeout 2/Google Keep",
        ]
        path = None
        for c in candidates:
            if os.path.exists(c):
                path = c
                break

        if not path:
            print("No Google Keep directory found in Takeout.")
            print("Usage: python notes_importer.py /path/to/Takeout/Keep")
            sys.exit(0)

    import_notes(path)
