#!/usr/bin/env python3
"""Google Calendar (iCalendar) importer.

Parses .ics files from Google Takeout Calendar export and imports events
into the archive database.

Usage:
    python calendar_importer.py /path/to/Takeout/Calendar
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from database import get_connection, init_db
from config import ensure_dirs


# Common timezone offset mappings for fallback
TZ_OFFSETS = {
    'US/Eastern': -5, 'America/New_York': -5, 'America/Toronto': -5,
    'US/Central': -6, 'America/Chicago': -6,
    'US/Mountain': -7, 'America/Denver': -7,
    'US/Pacific': -8, 'America/Los_Angeles': -8, 'America/Vancouver': -8,
    'UTC': 0, 'GMT': 0,
    'Europe/London': 0, 'Europe/Paris': 1, 'Europe/Berlin': 1,
    'Asia/Tokyo': 9, 'Asia/Shanghai': 8,
    'Australia/Sydney': 11,
}


def parse_ics_datetime(dtstr, default_tz=None):
    """Parse an iCalendar datetime string into (iso_string, unix_timestamp, is_all_day).

    Handles:
    - DATE: 20090129 (all-day)
    - DATETIME: 20090126T220000Z (UTC)
    - DATETIME: 20090126T170000 (floating, use default_tz)
    - TZID parameter handled by caller
    """
    dtstr = dtstr.strip()

    # All-day date: YYYYMMDD
    if len(dtstr) == 8 and dtstr.isdigit():
        try:
            dt = datetime.strptime(dtstr, '%Y%m%d')
            dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat(), int(dt.timestamp()), True
        except ValueError:
            return None, None, False

    # UTC datetime: YYYYMMDDTHHMMSSz
    if dtstr.endswith('Z'):
        try:
            dt = datetime.strptime(dtstr, '%Y%m%dT%H%M%SZ')
            dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat(), int(dt.timestamp()), False
        except ValueError:
            return None, None, False

    # Floating datetime: YYYYMMDDTHHMMSS
    if 'T' in dtstr:
        try:
            dt = datetime.strptime(dtstr, '%Y%m%dT%H%M%S')
            # Apply default timezone offset
            if default_tz and default_tz in TZ_OFFSETS:
                offset = timedelta(hours=TZ_OFFSETS[default_tz])
                dt = dt.replace(tzinfo=timezone(offset))
            else:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat(), int(dt.timestamp()), False
        except ValueError:
            return None, None, False

    return None, None, False


def unfold_ics(text):
    """Unfold long lines in iCalendar format (RFC 5545 line folding)."""
    return re.sub(r'\r?\n[ \t]', '', text)


def parse_attendees(lines):
    """Parse ATTENDEE lines into a list of {name, email, status} dicts."""
    attendees = []
    for line in lines:
        attendee = {}
        # Extract CN (common name)
        cn_match = re.search(r'CN=([^;:]+)', line)
        if cn_match:
            attendee['name'] = cn_match.group(1).strip()

        # Extract email from mailto:
        email_match = re.search(r'mailto:([^\s;]+)', line, re.IGNORECASE)
        if email_match:
            attendee['email'] = email_match.group(1).strip()

        # Extract participation status
        status_match = re.search(r'PARTSTAT=([^;:]+)', line)
        if status_match:
            attendee['status'] = status_match.group(1).strip()

        if attendee.get('email') or attendee.get('name'):
            attendees.append(attendee)

    return attendees


def parse_ics_file(ics_path):
    """Parse an .ics file and yield event dicts."""
    with open(ics_path, 'r', encoding='utf-8', errors='replace') as f:
        raw = f.read()

    raw = unfold_ics(raw)

    # Get calendar-level timezone
    tz_match = re.search(r'X-WR-TIMEZONE:(.+)', raw)
    default_tz = tz_match.group(1).strip() if tz_match else None

    # Get calendar name
    calname_match = re.search(r'X-WR-CALNAME:(.+)', raw)
    calendar_name = calname_match.group(1).strip() if calname_match else Path(ics_path).stem

    # Split into VEVENT blocks
    events = re.findall(r'BEGIN:VEVENT\s*\n(.*?)END:VEVENT', raw, re.DOTALL)

    for event_text in events:
        event = {
            'calendar_name': calendar_name,
            'uid': '',
            'summary': '',
            'description': '',
            'location': '',
            'start_time': None,
            'end_time': None,
            'start_unix': None,
            'end_unix': None,
            'is_all_day': 0,
            'recurrence': '',
            'organizer': '',
            'attendees': [],
            'status': '',
        }

        attendee_lines = []

        for line in event_text.split('\n'):
            line = line.strip()
            if not line:
                continue

            if ':' not in line:
                continue

            prop_part, _, value = line.partition(':')
            prop_parts = prop_part.split(';')
            prop_name = prop_parts[0].upper()
            params = {}
            for p in prop_parts[1:]:
                if '=' in p:
                    pk, _, pv = p.partition('=')
                    params[pk.upper()] = pv

            if prop_name == 'UID':
                event['uid'] = value.strip()

            elif prop_name == 'SUMMARY':
                event['summary'] = value.replace('\\n', '\n').replace('\\,', ',').strip()

            elif prop_name == 'DESCRIPTION':
                event['description'] = value.replace('\\n', '\n').replace('\\,', ',').strip()

            elif prop_name == 'LOCATION':
                event['location'] = value.replace('\\n', '\n').replace('\\,', ',').strip()

            elif prop_name == 'STATUS':
                event['status'] = value.strip()

            elif prop_name == 'RRULE':
                event['recurrence'] = value.strip()

            elif prop_name in ('DTSTART', 'DTEND'):
                # Check for VALUE=DATE (all-day)
                tz_for_parse = params.get('TZID', default_tz)
                if params.get('VALUE') == 'DATE':
                    iso, unix, is_all_day = parse_ics_datetime(value, tz_for_parse)
                    if is_all_day:
                        event['is_all_day'] = 1
                else:
                    iso, unix, is_all_day = parse_ics_datetime(value, tz_for_parse)
                    if is_all_day:
                        event['is_all_day'] = 1

                if prop_name == 'DTSTART':
                    event['start_time'] = iso
                    event['start_unix'] = unix
                else:
                    event['end_time'] = iso
                    event['end_unix'] = unix

            elif prop_name == 'ORGANIZER':
                org_cn = re.search(r'CN=([^;:]+)', line)
                org_email = re.search(r'mailto:([^\s;]+)', line, re.IGNORECASE)
                parts = []
                if org_cn:
                    parts.append(org_cn.group(1).strip())
                if org_email:
                    parts.append(f"<{org_email.group(1).strip()}>")
                event['organizer'] = ' '.join(parts) if parts else value.strip()

            elif prop_name == 'ATTENDEE':
                attendee_lines.append(line)

        if attendee_lines:
            event['attendees'] = parse_attendees(attendee_lines)

        # Skip events with no UID
        if not event['uid']:
            continue

        yield event


def import_calendar(calendar_path):
    """Import calendar events from a Takeout Calendar directory."""
    cal_dir = Path(calendar_path)
    if not cal_dir.exists():
        print(f"Error: Calendar directory not found: {cal_dir}")
        sys.exit(1)

    ensure_dirs()
    init_db(skip_fts=True)

    # Find all .ics files
    ics_files = sorted(cal_dir.glob('*.ics'))
    if not ics_files:
        print(f"No .ics files found in {cal_dir}")
        sys.exit(1)

    print(f"Found {len(ics_files)} calendar files:")
    for f in ics_files:
        print(f"  {f.name}")

    conn = get_connection()
    cursor = conn.cursor()

    # Load existing UIDs for dedup
    existing = set()
    try:
        for row in cursor.execute("SELECT uid, calendar_name FROM calendar_events"):
            existing.add((row[0], row[1]))
    except Exception:
        pass

    start_time = time.time()
    imported = 0
    skipped = 0
    errors = 0
    total_parsed = 0

    for ics_path in ics_files:
        print(f"\nProcessing: {ics_path.name}")

        try:
            for event in parse_ics_file(str(ics_path)):
                total_parsed += 1

                dedup_key = (event['uid'], event['calendar_name'])
                if dedup_key in existing:
                    skipped += 1
                    continue

                try:
                    attendees_json = json.dumps(event['attendees']) if event['attendees'] else None

                    cursor.execute("""
                        INSERT OR IGNORE INTO calendar_events
                        (calendar_name, uid, summary, description, location,
                         start_time, end_time, start_unix, end_unix, is_all_day,
                         recurrence, organizer, attendees, status, source_file)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        event['calendar_name'],
                        event['uid'],
                        event['summary'],
                        event['description'],
                        event['location'],
                        event['start_time'],
                        event['end_time'],
                        event['start_unix'],
                        event['end_unix'],
                        event['is_all_day'],
                        event['recurrence'],
                        event['organizer'],
                        attendees_json,
                        event['status'],
                        str(ics_path),
                    ))

                    if cursor.rowcount > 0:
                        imported += 1
                        existing.add(dedup_key)
                    else:
                        skipped += 1

                except Exception as e:
                    errors += 1
                    if errors <= 20:
                        print(f"  Error inserting event '{event['summary'][:50]}': {e}")

                if total_parsed % 100 == 0:
                    conn.commit()

        except Exception as e:
            errors += 1
            print(f"  Error parsing {ics_path.name}: {e}")

        elapsed = time.time() - start_time
        rate = total_parsed / elapsed if elapsed > 0 else 0
        print(f"  Parsed: {total_parsed:,} | Imported: {imported:,} | "
              f"Skipped: {skipped:,} | Errors: {errors:,} | {rate:.0f}/sec")

    conn.commit()

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"CALENDAR IMPORT COMPLETE! Time: {elapsed:.1f}s")
    print(f"  Parsed:   {total_parsed:,}")
    print(f"  Imported: {imported:,}")
    print(f"  Skipped:  {skipped:,} (duplicates)")
    print(f"  Errors:   {errors:,}")

    # Per-calendar stats
    cursor.execute("""
        SELECT calendar_name, COUNT(*) as cnt
        FROM calendar_events GROUP BY calendar_name ORDER BY cnt DESC
    """)
    print(f"\n  Events per calendar:")
    for row in cursor.fetchall():
        print(f"    {row[0]}: {row[1]:,}")

    total_db = cursor.execute("SELECT COUNT(*) FROM calendar_events").fetchone()[0]
    print(f"\n  Total events in DB: {total_db:,}")
    print(f"{'='*60}")

    conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = "/Volumes/backup Plus/TakeOut/other product takeouts/Takeout 2/Calendar"

    import_calendar(path)
