#!/usr/bin/env python3
"""Google Chat / Hangouts importer.

Parses Google Chat Takeout JSON data (Groups/ and Users/ directories)
and imports conversations and messages into the archive database.

Usage:
    python chat_importer.py /path/to/Takeout/Google Chat
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


# Google Chat date format: "Saturday, November 20, 2021 at 10:09:35 PM UTC"
CHAT_DATE_RE = re.compile(
    r'\w+,\s+'                      # Day of week
    r'(\w+)\s+'                     # Month
    r'(\d{1,2}),\s+'               # Day
    r'(\d{4})\s+'                  # Year
    r'at\s+'                        # literal "at"
    r'(\d{1,2}):(\d{2}):(\d{2})\s*' # H:M:S
    r'(AM|PM)\s+'                  # AM/PM
    r'(\w+)'                       # Timezone
)

MONTH_MAP = {
    'January': 1, 'February': 2, 'March': 3, 'April': 4,
    'May': 5, 'June': 6, 'July': 7, 'August': 8,
    'September': 9, 'October': 10, 'November': 11, 'December': 12,
}


def parse_chat_date(date_str):
    """Parse Google Chat's date format into (iso_string, unix_timestamp)."""
    if not date_str:
        return None, None

    m = CHAT_DATE_RE.match(date_str.strip())
    if not m:
        return None, None

    month_name, day, year, hour, minute, second, ampm, tz_name = m.groups()
    month = MONTH_MAP.get(month_name)
    if not month:
        return None, None

    hour = int(hour)
    if ampm == 'PM' and hour != 12:
        hour += 12
    elif ampm == 'AM' and hour == 12:
        hour = 0

    try:
        dt = datetime(int(year), month, int(day), hour, int(minute), int(second),
                      tzinfo=timezone.utc)
        return dt.isoformat(), int(dt.timestamp())
    except (ValueError, OverflowError):
        return None, None


def determine_conversation_type(folder_name):
    """Determine conversation type from folder name."""
    if folder_name.startswith('DM '):
        return 'DM'
    elif folder_name.startswith('Space '):
        return 'Space'
    else:
        return 'Group'


def parse_group_info(group_info_path):
    """Parse group_info.json for conversation metadata."""
    try:
        with open(group_info_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return None, []

    name = data.get('name', '')
    members = data.get('members', [])

    participants = []
    for member in members:
        p = {}
        if member.get('name'):
            p['name'] = member['name']
        if member.get('email'):
            p['email'] = member['email']
        if p:
            participants.append(p)

    return name, participants


def parse_messages(messages_path):
    """Parse messages.json and yield message dicts."""
    try:
        with open(messages_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return

    messages = data.get('messages', [])

    for msg in messages:
        creator = msg.get('creator', {})
        text = msg.get('text', '')

        # Some messages have attached files but no text
        if not text:
            attached = msg.get('attached_files', [])
            if attached:
                filenames = [a.get('export_name', 'file') for a in attached]
                text = f"[Attached: {', '.join(filenames)}]"

        if not text:
            continue

        timestamp_iso, timestamp_unix = parse_chat_date(msg.get('created_date', ''))

        # Determine message type
        msg_type = 'text'
        if msg.get('attached_files'):
            msg_type = 'attachment'
        elif msg.get('annotations'):
            for ann in msg.get('annotations', []):
                if 'video_call_metadata' in ann:
                    msg_type = 'video_call'
                    break

        yield {
            'sender_name': creator.get('name', ''),
            'sender_email': creator.get('email', ''),
            'content': text,
            'timestamp': timestamp_iso,
            'timestamp_unix': timestamp_unix,
            'message_type': msg_type,
        }


def import_chat(chat_path):
    """Import Google Chat data from Takeout directory."""
    chat_dir = Path(chat_path)
    if not chat_dir.exists():
        print(f"Error: Google Chat directory not found: {chat_dir}")
        sys.exit(1)

    ensure_dirs()
    init_db(skip_fts=True)

    # Find conversation directories in Groups/ and Users/
    conversation_dirs = []

    groups_dir = chat_dir / 'Groups'
    if groups_dir.exists():
        for d in sorted(groups_dir.iterdir()):
            if d.is_dir():
                conversation_dirs.append(d)

    users_dir = chat_dir / 'Users'
    if users_dir.exists():
        for d in sorted(users_dir.iterdir()):
            if d.is_dir():
                conversation_dirs.append(d)

    if not conversation_dirs:
        print(f"No conversation directories found in {chat_dir}")
        sys.exit(1)

    print(f"Found {len(conversation_dirs)} conversations")

    conn = get_connection()
    cursor = conn.cursor()

    # Load existing conversations for dedup
    existing_convos = set()
    try:
        for row in cursor.execute("SELECT source_folder FROM chat_conversations"):
            existing_convos.add(row[0])
    except Exception:
        pass

    start_time = time.time()
    convos_imported = 0
    convos_skipped = 0
    messages_imported = 0
    errors = 0

    for i, conv_dir in enumerate(conversation_dirs):
        folder_name = conv_dir.name
        source_folder = str(conv_dir)

        # Skip already imported conversations
        if source_folder in existing_convos:
            convos_skipped += 1
            continue

        try:
            conv_type = determine_conversation_type(folder_name)

            # Parse group info if available
            group_info_path = conv_dir / 'group_info.json'
            conv_name = ''
            participants = []

            if group_info_path.exists():
                conv_name, participants = parse_group_info(str(group_info_path))

            # If no name from group_info, use folder name
            if not conv_name:
                conv_name = folder_name

            # For user folders (Users/), parse user_info.json
            user_info_path = conv_dir / 'user_info.json'
            if user_info_path.exists() and not participants:
                try:
                    with open(user_info_path, 'r', encoding='utf-8') as f:
                        user_data = json.load(f)
                    user = user_data.get('user', {})
                    if user:
                        participants = [{'name': user.get('name', ''), 'email': user.get('email', '')}]
                except Exception:
                    pass

            # Insert conversation
            participants_json = json.dumps(participants) if participants else '[]'
            cursor.execute("""
                INSERT OR IGNORE INTO chat_conversations
                (name, participants, type, source_folder)
                VALUES (?, ?, ?, ?)
            """, (conv_name, participants_json, conv_type, source_folder))

            if cursor.rowcount == 0:
                convos_skipped += 1
                continue

            conversation_id = cursor.lastrowid
            convos_imported += 1
            existing_convos.add(source_folder)

            # Parse and insert messages
            messages_path = conv_dir / 'messages.json'
            if messages_path.exists():
                msg_count = 0
                for msg in parse_messages(str(messages_path)):
                    try:
                        cursor.execute("""
                            INSERT INTO chat_messages
                            (conversation_id, sender_name, sender_email, content,
                             timestamp, timestamp_unix, message_type)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            conversation_id,
                            msg['sender_name'],
                            msg['sender_email'],
                            msg['content'],
                            msg['timestamp'],
                            msg['timestamp_unix'],
                            msg['message_type'],
                        ))
                        messages_imported += 1
                        msg_count += 1
                    except Exception as e:
                        errors += 1
                        if errors <= 20:
                            print(f"  Error inserting message in {folder_name}: {e}")

            # Commit every 10 conversations
            if convos_imported % 10 == 0:
                conn.commit()

        except Exception as e:
            errors += 1
            if errors <= 20:
                print(f"  Error processing {folder_name}: {e}")

        # Progress
        processed = i + 1
        if processed % 20 == 0 or processed == len(conversation_dirs):
            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 else 0
            pct = processed / len(conversation_dirs) * 100
            print(f"\r  [{pct:5.1f}%] Convos: {convos_imported:,} | "
                  f"Messages: {messages_imported:,} | "
                  f"Skipped: {convos_skipped:,} | Errors: {errors:,} | "
                  f"{rate:.0f} convos/sec",
                  end="", flush=True)

    conn.commit()

    elapsed = time.time() - start_time
    print(f"\n\n{'='*60}")
    print(f"CHAT IMPORT COMPLETE! Time: {elapsed:.1f}s")
    print(f"  Conversations imported: {convos_imported:,}")
    print(f"  Conversations skipped:  {convos_skipped:,}")
    print(f"  Messages imported:      {messages_imported:,}")
    print(f"  Errors:                 {errors:,}")

    # Stats by type
    cursor.execute("""
        SELECT type, COUNT(*) as cnt FROM chat_conversations GROUP BY type ORDER BY cnt DESC
    """)
    print(f"\n  Conversations by type:")
    for row in cursor.fetchall():
        print(f"    {row[0]}: {row[1]:,}")

    total_msgs = cursor.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]
    print(f"\n  Total messages in DB: {total_msgs:,}")
    print(f"{'='*60}")

    conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = "/Volumes/backup Plus/TakeOut/other product takeouts/Takeout 2/Google Chat"

    import_chat(path)
