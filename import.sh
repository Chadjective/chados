#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PATH="$HOME/.local/node/bin:$HOME/.local/bin:$PATH"

# Load .env if it exists
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

TAKEOUT_PATH="${1:-}"

echo "╔══════════════════════════════════════════╗"
echo "║    Personal Google Archive — Import      ║"
echo "╚══════════════════════════════════════════╝"
echo ""

if [ -z "$TAKEOUT_PATH" ]; then
    echo "Usage: ./import.sh /path/to/Takeout"
    echo ""
    echo "Point this at your Google Takeout folder."
    echo "It can contain any of: Mail/, Google Photos/,"
    echo "Calendar/, Contacts/, Google Chat/, Drive/, Keep/"
    echo ""
    echo "If your Takeout is split across multiple folders"
    echo "(Takeout, Takeout 2, etc.), run this script for each."
    echo ""
    echo "If your Takeout is still in zip files, this script"
    echo "can extract them first."
    exit 1
fi

# Check if pointing at a directory of zip files
ZIP_COUNT=$(find "$TAKEOUT_PATH" -maxdepth 1 -name "*.zip" 2>/dev/null | wc -l | tr -d ' ')

if [ "$ZIP_COUNT" -gt 0 ]; then
    echo "Found $ZIP_COUNT zip files in $TAKEOUT_PATH"
    echo "Extracting Takeout data from zips..."
    echo ""

    count=0
    for zipfile in "$TAKEOUT_PATH"/*.zip; do
        count=$((count + 1))
        basename=$(basename "$zipfile" .zip)
        targetdir="$TAKEOUT_PATH/extracted_$basename"

        if [ -d "$targetdir" ]; then
            echo "[$count/$ZIP_COUNT] Already extracted: $basename"
            continue
        fi

        echo "[$count/$ZIP_COUNT] Extracting $basename..."
        mkdir -p "$targetdir"
        unzip -q -o "$zipfile" -d "$targetdir" 2>/dev/null || true
    done

    echo ""
    echo "Extraction complete. Now importing from extracted folders..."
    echo ""

    # Import from each extracted folder
    for dir in "$TAKEOUT_PATH"/extracted_*/Takeout; do
        if [ -d "$dir" ]; then
            echo "━━━ Importing from $(basename "$(dirname "$dir")") ━━━"
            "$0" "$dir"
            echo ""
        fi
    done
    exit 0
fi

# ── Set up Python environment ──
if [ ! -d "$SCRIPT_DIR/backend/venv" ]; then
    echo "Setting up Python environment first..."
    python3 -m venv "$SCRIPT_DIR/backend/venv"
    source "$SCRIPT_DIR/backend/venv/bin/activate"
    pip install -q -r "$SCRIPT_DIR/backend/requirements.txt"
else
    source "$SCRIPT_DIR/backend/venv/bin/activate"
fi

cd "$SCRIPT_DIR/backend"

# ── Discover what's available ──
echo "Scanning: $TAKEOUT_PATH"
echo ""

# Email (.mbox files)
MBOX_FILES=$(find "$TAKEOUT_PATH" -maxdepth 3 -name "*.mbox" -type f 2>/dev/null)
if [ -n "$MBOX_FILES" ]; then
    MBOX_COUNT=$(echo "$MBOX_FILES" | wc -l | tr -d ' ')
    echo "📧 Email: Found $MBOX_COUNT .mbox file(s)"
    while IFS= read -r mbox; do
        SIZE=$(du -h "$mbox" | cut -f1)
        echo "   → $mbox ($SIZE)"
        echo "   Importing emails..."
        python importer.py "$mbox" || true
        echo ""
    done <<< "$MBOX_FILES"
fi

# Google Photos
PHOTOS_DIR=""
if [ -d "$TAKEOUT_PATH/Google Photos" ]; then
    PHOTOS_DIR="$TAKEOUT_PATH"
fi
if [ -n "$PHOTOS_DIR" ]; then
    PHOTO_COUNT=$(find "$PHOTOS_DIR/Google Photos" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.heic" -o -iname "*.mp4" -o -iname "*.mov" -o -iname "*.gif" \) 2>/dev/null | wc -l | tr -d ' ')
    echo "📸 Photos: Found ~$PHOTO_COUNT media files"
    echo "   Importing photos..."
    python photo_importer.py "$PHOTOS_DIR" || true
    echo ""
fi

# Calendar
if [ -d "$TAKEOUT_PATH/Calendar" ]; then
    ICS_COUNT=$(find "$TAKEOUT_PATH/Calendar" -name "*.ics" 2>/dev/null | wc -l | tr -d ' ')
    echo "📅 Calendar: Found $ICS_COUNT .ics file(s)"
    echo "   Importing calendar events..."
    python calendar_importer.py "$TAKEOUT_PATH/Calendar" || true
    echo ""
fi

# Contacts
if [ -d "$TAKEOUT_PATH/Contacts" ]; then
    VCF_COUNT=$(find "$TAKEOUT_PATH/Contacts" -name "*.vcf" 2>/dev/null | wc -l | tr -d ' ')
    echo "👥 Contacts: Found $VCF_COUNT .vcf file(s)"
    echo "   Importing contacts..."
    python contacts_importer.py "$TAKEOUT_PATH" || true
    echo ""
fi

# Google Chat
if [ -d "$TAKEOUT_PATH/Google Chat" ]; then
    echo "💬 Chat: Found Google Chat data"
    echo "   Importing chat messages..."
    python chat_importer.py "$TAKEOUT_PATH" || true
    echo ""
fi

# Drive
if [ -d "$TAKEOUT_PATH/Drive" ]; then
    DRIVE_COUNT=$(find "$TAKEOUT_PATH/Drive" -type f 2>/dev/null | wc -l | tr -d ' ')
    echo "💾 Drive: Found $DRIVE_COUNT files"
    echo "   Importing drive files..."
    python drive_importer.py "$TAKEOUT_PATH" || true
    echo ""
fi

# Keep Notes
if [ -d "$TAKEOUT_PATH/Keep" ]; then
    echo "📝 Notes: Found Google Keep data"
    echo "   Importing notes..."
    python notes_importer.py "$TAKEOUT_PATH" || true
    echo ""
fi

# ── Summary ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 -c "
import sqlite3, os
db = os.environ.get('ARCHIVE_DB_DIR', os.path.expanduser('~/personal-archive-data'))
conn = sqlite3.connect(f'{db}/archive.db')
tables = {
    'emails': '📧 Emails',
    'photos': '📸 Photos',
    'calendar_events': '📅 Calendar Events',
    'contacts': '👥 Contacts',
    'chat_messages': '💬 Chat Messages',
    'drive_files': '💾 Drive Files',
    'notes': '📝 Notes',
}
print()
print('  Import Summary')
print('  ─────────────────────────')
for table, label in tables.items():
    try:
        count = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        if count > 0:
            print(f'  {label}: {count:,}')
    except:
        pass
print()
conn.close()
" 2>/dev/null || true

echo "Done! Run ./start.sh to launch the app."
echo ""
