#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PATH="$HOME/.local/node/bin:$HOME/.local/bin:$PATH"

PHOTOS_PATH="${1:-/Volumes/backup Plus/TakeOut/Zip Files}"

echo "=================================="
echo "  Google Photos Archive Importer"
echo "=================================="
echo ""

# Set up Python environment
if [ ! -d "$SCRIPT_DIR/backend/venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv "$SCRIPT_DIR/backend/venv"
    source "$SCRIPT_DIR/backend/venv/bin/activate"
    pip install -r "$SCRIPT_DIR/backend/requirements.txt"
else
    source "$SCRIPT_DIR/backend/venv/bin/activate"
fi

# Step 1: Extract Google Photos from zip files (if any)
echo "Step 1: Checking for unextracted zip files..."
ZIP_COUNT=$(ls -1 "$PHOTOS_PATH"/takeout-*.zip 2>/dev/null | wc -l | tr -d ' ')
EXTRACTED_COUNT=$(ls -d "$PHOTOS_PATH/Takeout"*/Google\ Photos 2>/dev/null | wc -l | tr -d ' ')

echo "  Zip files found: $ZIP_COUNT"
echo "  Already extracted: $EXTRACTED_COUNT Google Photos folders"

if [ "$ZIP_COUNT" -gt 0 ]; then
    echo ""
    echo "  Extracting Google Photos from zip files..."
    echo "  (This extracts only Google Photos content, not other Takeout data)"
    echo ""
    bash "$SCRIPT_DIR/extract_photos.sh"
    echo ""
else
    echo "  No zip files to extract."
fi

# Step 2: Import photos into database
echo ""
echo "Step 2: Importing photos into database..."
echo "  Source: $PHOTOS_PATH"
echo "  Database: ~/personal-archive-data/archive.db"
echo "  Thumbnails: ~/personal-archive-data/thumbnails/"
echo ""
cd "$SCRIPT_DIR/backend"
python photo_importer.py "$PHOTOS_PATH"
