#!/usr/bin/env python3
"""Google Contacts (vCard) importer.

Parses .vcf files from Google Takeout Contacts export and imports them
into the archive database.

Usage:
    python contacts_importer.py /path/to/Takeout/Contacts
"""

import json
import os
import re
import sys
import time
from pathlib import Path

from database import get_connection, init_db
from config import ensure_dirs


def decode_quoted_printable(value):
    """Decode quoted-printable encoded string."""
    try:
        import quopri
        return quopri.decodestring(value.encode('ascii', errors='replace')).decode('utf-8', errors='replace')
    except Exception:
        return value


def parse_vcard_file(vcf_path):
    """Parse a .vcf file and yield individual contact dicts."""
    with open(vcf_path, 'r', encoding='utf-8', errors='replace') as f:
        raw = f.read()

    # Split into individual vCards
    cards = re.split(r'(?m)^BEGIN:VCARD\s*$', raw)

    for card_text in cards:
        if not card_text.strip():
            continue

        # Remove trailing END:VCARD
        card_text = re.sub(r'(?m)^END:VCARD\s*$', '', card_text).strip()
        if not card_text:
            continue

        # Unfold continuation lines (lines starting with space/tab are continuations)
        card_text = re.sub(r'\r?\n[ \t]', '', card_text)

        contact = {
            'name': '',
            'given_name': '',
            'family_name': '',
            'emails': [],
            'phones': [],
            'organization': '',
            'title': '',
            'notes': '',
            'photo_path': '',
            'groups': [],
        }

        for line in card_text.split('\n'):
            line = line.strip()
            if not line or line.startswith('VERSION:'):
                continue

            # Parse property name and value
            # Handle properties with parameters: PROP;PARAM=VAL:value
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

            # Handle item1.EMAIL style properties
            if '.' in prop_name:
                prop_name = prop_name.split('.', 1)[1]

            if prop_name == 'FN':
                contact['name'] = value.strip()

            elif prop_name == 'N':
                # N:family;given;additional;prefix;suffix
                parts = value.split(';')
                if len(parts) >= 2:
                    contact['family_name'] = parts[0].replace('\\:', ':').replace('\\,', ',').strip()
                    contact['given_name'] = parts[1].replace('\\:', ':').replace('\\,', ',').strip()

            elif prop_name == 'EMAIL':
                email_type = params.get('TYPE', 'other')
                if value.strip():
                    contact['emails'].append({
                        'type': email_type.lower(),
                        'address': value.strip()
                    })

            elif prop_name == 'TEL':
                phone_type = params.get('TYPE', 'other')
                if value.strip():
                    contact['phones'].append({
                        'type': phone_type.lower(),
                        'number': value.strip()
                    })

            elif prop_name == 'ORG':
                contact['organization'] = value.replace(';', ', ').strip().rstrip(',')

            elif prop_name == 'TITLE':
                contact['title'] = value.strip()

            elif prop_name == 'NOTE':
                contact['notes'] = value.replace('\\n', '\n').replace('\\,', ',').strip()

            elif prop_name == 'CATEGORIES':
                groups = [g.strip() for g in value.split(',') if g.strip()]
                contact['groups'].extend(groups)

            elif prop_name == 'X-ABLABEL':
                pass  # Apple address book label, skip

        # If no FN, build from given/family
        if not contact['name']:
            parts = [contact['given_name'], contact['family_name']]
            contact['name'] = ' '.join(p for p in parts if p).strip()

        # Skip completely empty contacts (no name, no email, no phone)
        if not contact['name'] and not contact['emails'] and not contact['phones']:
            continue

        yield contact


def import_contacts(contacts_path):
    """Import contacts from a Takeout Contacts directory."""
    contacts_dir = Path(contacts_path)
    if not contacts_dir.exists():
        print(f"Error: Contacts directory not found: {contacts_dir}")
        sys.exit(1)

    ensure_dirs()
    init_db(skip_fts=True)

    # Find all .vcf files (check subfolders too)
    vcf_files = []
    for vcf in contacts_dir.rglob('*.vcf'):
        vcf_files.append(vcf)

    if not vcf_files:
        print(f"No .vcf files found in {contacts_dir}")
        sys.exit(1)

    print(f"Found {len(vcf_files)} vCard files:")
    for v in vcf_files:
        print(f"  {v.name}")

    conn = get_connection()
    cursor = conn.cursor()

    # Load existing contacts for dedup
    existing = set()
    try:
        for row in cursor.execute("SELECT name, emails FROM contacts"):
            existing.add((row[0], row[1]))
    except Exception:
        pass

    start_time = time.time()
    imported = 0
    skipped = 0
    errors = 0
    total_parsed = 0

    for vcf_path in vcf_files:
        group_name = vcf_path.parent.name  # e.g. "My Contacts", "All Contacts"
        print(f"\nProcessing: {vcf_path.name} (group: {group_name})")

        try:
            for contact in parse_vcard_file(str(vcf_path)):
                total_parsed += 1

                emails_json = json.dumps(contact['emails'])
                phones_json = json.dumps(contact['phones'])
                groups = contact['groups']
                if group_name and group_name not in groups:
                    groups.append(group_name)
                groups_json = json.dumps(groups)

                dedup_key = (contact['name'], emails_json)
                if dedup_key in existing:
                    skipped += 1
                    continue

                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO contacts
                        (name, given_name, family_name, emails, phones,
                         organization, title, notes, photo_path, groups, source_file)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        contact['name'],
                        contact['given_name'],
                        contact['family_name'],
                        emails_json,
                        phones_json,
                        contact['organization'],
                        contact['title'],
                        contact['notes'],
                        contact['photo_path'],
                        groups_json,
                        str(vcf_path),
                    ))

                    if cursor.rowcount > 0:
                        imported += 1
                        existing.add(dedup_key)
                    else:
                        skipped += 1

                except Exception as e:
                    errors += 1
                    if errors <= 20:
                        print(f"  Error inserting contact '{contact['name']}': {e}")

                if total_parsed % 200 == 0:
                    conn.commit()
                    elapsed = time.time() - start_time
                    rate = total_parsed / elapsed if elapsed > 0 else 0
                    print(f"\r  Parsed: {total_parsed:,} | Imported: {imported:,} | "
                          f"Skipped: {skipped:,} | Errors: {errors:,} | {rate:.0f}/sec",
                          end="", flush=True)

        except Exception as e:
            errors += 1
            print(f"  Error parsing {vcf_path.name}: {e}")

    conn.commit()

    elapsed = time.time() - start_time
    print(f"\n\n{'='*60}")
    print(f"CONTACTS IMPORT COMPLETE! Time: {elapsed:.1f}s")
    print(f"  Parsed:   {total_parsed:,}")
    print(f"  Imported: {imported:,}")
    print(f"  Skipped:  {skipped:,} (duplicates)")
    print(f"  Errors:   {errors:,}")

    total_db = cursor.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    print(f"  Total contacts in DB: {total_db:,}")
    print(f"{'='*60}")

    conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = "/Volumes/backup Plus/TakeOut/other product takeouts/Takeout 2/Contacts"

    import_contacts(path)
