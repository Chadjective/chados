#!/usr/bin/env bash
#
# Master import script for Google Takeout Archive Viewer
# Runs all Phase 1-3 importers in sequence.
#
# Usage:
#   ./import-all.sh [TAKEOUT_BASE_PATH]
#
# Default Takeout path: /Volumes/backup Plus/TakeOut/other product takeouts

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"

# Default paths
TAKEOUT_BASE="${1:-/Volumes/backup Plus/TakeOut/other product takeouts}"
TAKEOUT2="$TAKEOUT_BASE/Takeout 2"
MBOX_PATH="$TAKEOUT_BASE/All mail Including Spam and Trash-002.mbox"
PHOTOS_PATH="/Volumes/backup Plus/TakeOut/Zip Files"

echo "============================================================"
echo "  Google Archive Importer - All Phases"
echo "============================================================"
echo ""
echo "  Takeout base: $TAKEOUT_BASE"
echo "  Backend dir:  $BACKEND_DIR"
echo ""

cd "$BACKEND_DIR"

# Track overall timing
OVERALL_START=$SECONDS

run_importer() {
    local name="$1"
    local script="$2"
    shift 2
    local args=("$@")

    echo ""
    echo "------------------------------------------------------------"
    echo "  [$name] Starting..."
    echo "------------------------------------------------------------"

    local start=$SECONDS

    if python3 "$script" "${args[@]}"; then
        local elapsed=$(( SECONDS - start ))
        echo "  [$name] Completed in ${elapsed}s"
    else
        local elapsed=$(( SECONDS - start ))
        echo "  [$name] FAILED after ${elapsed}s (exit code: $?)"
        echo "  Continuing with next importer..."
    fi
}

# ============================================================
# Phase 1: Email (skip if no mbox file)
# ============================================================
if [ -f "$MBOX_PATH" ]; then
    run_importer "EMAIL" "importer.py" "$MBOX_PATH"
else
    echo ""
    echo "  [EMAIL] Skipping - mbox file not found: $MBOX_PATH"
fi

# ============================================================
# Phase 2: Photos (skip if no photos dir)
# ============================================================
if [ -d "$PHOTOS_PATH" ]; then
    run_importer "PHOTOS" "photo_importer.py" "$PHOTOS_PATH"
else
    echo ""
    echo "  [PHOTOS] Skipping - photos dir not found: $PHOTOS_PATH"
fi

# ============================================================
# Phase 3: Contacts
# ============================================================
CONTACTS_DIR="$TAKEOUT2/Contacts"
if [ -d "$CONTACTS_DIR" ]; then
    run_importer "CONTACTS" "contacts_importer.py" "$CONTACTS_DIR"
else
    echo ""
    echo "  [CONTACTS] Skipping - not found: $CONTACTS_DIR"
fi

# ============================================================
# Phase 3: Calendar
# ============================================================
CALENDAR_DIR="$TAKEOUT2/Calendar"
if [ -d "$CALENDAR_DIR" ]; then
    run_importer "CALENDAR" "calendar_importer.py" "$CALENDAR_DIR"
else
    echo ""
    echo "  [CALENDAR] Skipping - not found: $CALENDAR_DIR"
fi

# ============================================================
# Phase 3: Google Chat
# ============================================================
CHAT_DIR="$TAKEOUT2/Google Chat"
if [ -d "$CHAT_DIR" ]; then
    run_importer "CHAT" "chat_importer.py" "$CHAT_DIR"
else
    echo ""
    echo "  [CHAT] Skipping - not found: $CHAT_DIR"
fi

# ============================================================
# Phase 3: Drive
# ============================================================
DRIVE_DIR="$TAKEOUT2/Drive"
if [ -d "$DRIVE_DIR" ]; then
    run_importer "DRIVE" "drive_importer.py" "$DRIVE_DIR"
else
    echo ""
    echo "  [DRIVE] Skipping - not found: $DRIVE_DIR"
fi

# ============================================================
# Phase 3: Notes (Google Keep) - may not exist
# ============================================================
KEEP_DIR="$TAKEOUT2/Keep"
if [ -d "$KEEP_DIR" ]; then
    run_importer "NOTES" "notes_importer.py" "$KEEP_DIR"
else
    # Try alternate name
    KEEP_DIR="$TAKEOUT2/Google Keep"
    if [ -d "$KEEP_DIR" ]; then
        run_importer "NOTES" "notes_importer.py" "$KEEP_DIR"
    else
        echo ""
        echo "  [NOTES] Skipping - no Google Keep data found"
    fi
fi

# ============================================================
# Summary
# ============================================================
TOTAL_ELAPSED=$(( SECONDS - OVERALL_START ))
MINUTES=$(( TOTAL_ELAPSED / 60 ))
SECS=$(( TOTAL_ELAPSED % 60 ))

echo ""
echo "============================================================"
echo "  ALL IMPORTS COMPLETE!"
echo "  Total time: ${MINUTES}m ${SECS}s"
echo "============================================================"
