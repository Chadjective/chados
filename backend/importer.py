#!/usr/bin/env python3
"""
Gmail mbox importer with progress reporting.
Streams a Google Takeout .mbox file line-by-line for immediate processing
without needing to index the entire file first.
"""

import email
import email.utils
import email.header
import email.policy
import hashlib
import json
import os
import sys
import time
import re
from pathlib import Path
from datetime import timezone
from email import message_from_bytes
from email.utils import parseaddr, getaddresses, parsedate_to_datetime

from database import init_db, get_connection, build_fts
from config import ATTACHMENTS_DIR, ensure_dirs


MAX_FILENAME_LENGTH = 200  # macOS limit is 255 bytes; leave room for prefix


def decode_header_value(value):
    """Decode an email header value that may contain encoded words."""
    if not value:
        return ""
    try:
        parts = email.header.decode_header(value)
        decoded = []
        for part, charset in parts:
            if isinstance(part, bytes):
                charset = charset or "utf-8"
                try:
                    decoded.append(part.decode(charset, errors="replace"))
                except (LookupError, UnicodeDecodeError):
                    decoded.append(part.decode("utf-8", errors="replace"))
            else:
                decoded.append(part)
        return " ".join(decoded)
    except Exception:
        return str(value)


def parse_addresses(header_value):
    """Parse an address header into a list of {name, address} dicts."""
    if not header_value:
        return []
    try:
        decoded = decode_header_value(header_value)
        pairs = getaddresses([decoded])
        result = []
        for name, addr in pairs:
            if addr:
                result.append({"name": name, "address": addr})
        return result
    except Exception:
        return []


def parse_date(msg):
    """Parse the Date header into ISO format and unix timestamp."""
    date_str = msg.get("Date", "")
    if not date_str:
        return None, None
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat(), int(dt.timestamp())
    except Exception:
        return None, None


def get_gmail_labels(msg):
    """Extract Gmail labels from X-Gmail-Labels header."""
    labels_header = msg.get("X-Gmail-Labels", "")
    if not labels_header:
        return []
    decoded = decode_header_value(labels_header)
    labels = [l.strip() for l in decoded.split(",") if l.strip()]
    return labels


def get_body(msg):
    """Extract plain text and HTML body from the message."""
    body_text = ""
    body_html = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))

            if "attachment" in disposition:
                continue

            if content_type == "text/plain" and not body_text:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_text = payload.decode(charset, errors="replace")
                except Exception:
                    pass
            elif content_type == "text/html" and not body_html:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_html = payload.decode(charset, errors="replace")
                except Exception:
                    pass
    else:
        content_type = msg.get_content_type()
        try:
            charset = msg.get_content_charset() or "utf-8"
            payload = msg.get_payload(decode=True)
            if payload:
                text = payload.decode(charset, errors="replace")
                if content_type == "text/html":
                    body_html = text
                else:
                    body_text = text
        except Exception:
            pass

    return body_text, body_html


def safe_filename(filename, email_id):
    """Create a safe, length-limited filename for attachments."""
    # Remove illegal characters
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)

    # If the filename is already short enough, use it as-is
    prefix = f"{email_id}_"
    max_name_len = MAX_FILENAME_LENGTH - len(prefix)

    if len(filename.encode('utf-8')) <= max_name_len:
        return filename

    # Truncate: keep extension, hash the middle for uniqueness
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    if len(suffix) > 20:
        suffix = suffix[:20]

    name_hash = hashlib.md5(filename.encode()).hexdigest()[:8]
    max_stem = max_name_len - len(suffix) - len(name_hash) - 1
    if max_stem < 10:
        max_stem = 10
    truncated_stem = stem[:max_stem]
    return f"{truncated_stem}_{name_hash}{suffix}"


def extract_attachments(msg, email_id, cursor):
    """Extract attachments from the message and save to disk."""
    if not msg.is_multipart():
        return False

    has_attachments = False

    for part in msg.walk():
        disposition = str(part.get("Content-Disposition", ""))
        filename = part.get_filename()

        if not filename and "attachment" not in disposition:
            continue

        if not filename:
            ext = part.get_content_type().split("/")[-1]
            filename = f"attachment.{ext}"

        filename = decode_header_value(filename)
        filename = safe_filename(filename, email_id)

        try:
            payload = part.get_payload(decode=True)
            if not payload:
                continue
        except Exception:
            continue

        has_attachments = True
        size_bytes = len(payload)

        subdir = ATTACHMENTS_DIR / str(email_id // 1000)
        subdir.mkdir(parents=True, exist_ok=True)
        file_path = subdir / f"{email_id}_{filename}"

        counter = 1
        while file_path.exists():
            stem = Path(filename).stem
            suffix = Path(filename).suffix
            file_path = subdir / f"{email_id}_{stem}_{counter}{suffix}"
            counter += 1

        try:
            with open(file_path, "wb") as f:
                f.write(payload)
        except OSError as e:
            print(f"\n  Warning: Could not save attachment {filename}: {e}")
            continue

        cursor.execute(
            """INSERT INTO attachments (email_id, filename, content_type, size_bytes, file_path)
               VALUES (?, ?, ?, ?, ?)""",
            (email_id, filename, part.get_content_type(), size_bytes, str(file_path)),
        )

    return has_attachments


def compute_thread_id(msg):
    """Compute a thread ID from References and In-Reply-To headers."""
    refs = msg.get("References", "")
    in_reply_to = msg.get("In-Reply-To", "")
    message_id = msg.get("Message-ID", "")

    if refs:
        first_ref = refs.strip().split()[0].strip("<>")
        return first_ref
    if in_reply_to:
        return in_reply_to.strip().strip("<>")
    if message_id:
        return message_id.strip().strip("<>")
    return None


def stream_mbox_messages(mbox_path):
    """Stream individual email messages from an mbox file without loading
    the entire file into memory. Yields raw bytes for each message."""
    current_message = []
    bytes_read = 0

    with open(mbox_path, "rb") as f:
        for line in f:
            bytes_read += len(line)
            # mbox "From " separator line
            if line.startswith(b"From ") and current_message:
                yield b"".join(current_message), bytes_read
                current_message = []
            else:
                current_message.append(line)

        # Don't forget the last message
        if current_message:
            yield b"".join(current_message), bytes_read


def import_mbox(mbox_path, batch_size=1000):
    """Import an mbox file into the database using streaming.
    FTS index is built after all emails are imported for speed and safety."""
    print(f"Importing: {mbox_path}")
    file_size = os.path.getsize(mbox_path)
    print(f"File size: {file_size / (1024**3):.2f} GB")

    ensure_dirs()
    # Skip FTS during bulk import — we'll build it after
    init_db(skip_fts=True)
    conn = get_connection()
    cursor = conn.cursor()

    # Optimize for bulk import
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA locking_mode=EXCLUSIVE")

    # Check existing
    cursor.execute("SELECT COUNT(*) FROM emails")
    existing_count = cursor.fetchone()[0]
    if existing_count > 0:
        print(f"Database already has {existing_count:,} emails.")
        print("Importing will skip duplicates based on Message-ID.")

    # Cache known message IDs for fast duplicate checking
    print("Loading existing message IDs...")
    cursor.execute("SELECT message_id FROM emails WHERE message_id IS NOT NULL")
    known_ids = set(row[0] for row in cursor.fetchall())
    print(f"  {len(known_ids):,} known message IDs cached.")

    # Cache label name -> id mapping
    label_cache = {}
    for row in cursor.execute("SELECT id, name FROM labels").fetchall():
        label_cache[row[1]] = row[0]

    start_time = time.time()
    processed = 0
    imported = 0
    skipped = 0
    errors = 0
    last_report = start_time

    print(f"Streaming mbox file...\n")

    for raw_bytes, bytes_read in stream_mbox_messages(mbox_path):
        try:
            processed += 1

            # Parse the raw bytes into an email message
            msg = message_from_bytes(raw_bytes)

            # Extract message ID
            message_id = msg.get("Message-ID", "")
            if message_id:
                message_id = message_id.strip().strip("<>")

            # Skip duplicates using in-memory set (much faster than DB lookup)
            if message_id and message_id in known_ids:
                skipped += 1
                if time.time() - last_report >= 2.0:
                    _print_progress(processed, imported, skipped, errors, start_time,
                                    bytes_read, file_size)
                    last_report = time.time()
                continue

            # Parse the email
            from_name, from_address = parseaddr(decode_header_value(msg.get("From", "")))
            subject = decode_header_value(msg.get("Subject", ""))
            date_iso, date_unix = parse_date(msg)
            to_addresses = parse_addresses(msg.get("To", ""))
            cc_addresses = parse_addresses(msg.get("Cc", ""))
            bcc_addresses = parse_addresses(msg.get("Bcc", ""))
            labels = get_gmail_labels(msg)
            body_text, body_html = get_body(msg)
            thread_id = compute_thread_id(msg)

            is_read = "Unread" not in labels
            is_starred = "Starred" in labels
            raw_size = len(raw_bytes)

            # Insert email
            cursor.execute(
                """INSERT OR IGNORE INTO emails
                   (message_id, thread_id, from_address, from_name, to_addresses, cc_addresses,
                    bcc_addresses, subject, date, date_unix, body_text, body_html, labels,
                    has_attachments, is_read, is_starred, raw_size_bytes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)""",
                (
                    message_id or None,
                    thread_id,
                    from_address,
                    from_name,
                    json.dumps(to_addresses),
                    json.dumps(cc_addresses),
                    json.dumps(bcc_addresses),
                    subject,
                    date_iso,
                    date_unix,
                    body_text,
                    body_html,
                    json.dumps(labels),
                    is_read,
                    is_starred,
                    raw_size,
                ),
            )

            if cursor.rowcount > 0:
                email_id = cursor.lastrowid
                imported += 1

                if message_id:
                    known_ids.add(message_id)

                # Extract attachments
                has_att = extract_attachments(msg, email_id, cursor)
                if has_att:
                    cursor.execute("UPDATE emails SET has_attachments = 1 WHERE id = ?", (email_id,))

                # Insert labels
                for label_name in labels:
                    if label_name not in label_cache:
                        cursor.execute(
                            "INSERT OR IGNORE INTO labels (name, email_count) VALUES (?, 0)",
                            (label_name,),
                        )
                        cursor.execute("SELECT id FROM labels WHERE name = ?", (label_name,))
                        label_row = cursor.fetchone()
                        if label_row:
                            label_cache[label_name] = label_row[0]

                    if label_name in label_cache:
                        cursor.execute(
                            "INSERT OR IGNORE INTO email_labels (email_id, label_id) VALUES (?, ?)",
                            (email_id, label_cache[label_name]),
                        )

            # Commit in batches
            if imported % batch_size == 0 and imported > 0:
                conn.commit()

            # Progress reporting
            now = time.time()
            if now - last_report >= 2.0:
                _print_progress(processed, imported, skipped, errors, start_time,
                                bytes_read, file_size)
                last_report = now

        except Exception as e:
            errors += 1
            if errors <= 20:
                print(f"\n  Error on message {processed}: {e}")
            elif errors == 21:
                print(f"\n  (Suppressing further error messages...)")

    # Final commit of remaining batch
    conn.commit()

    elapsed = time.time() - start_time
    print(f"\n\n{'='*60}")
    print(f"Bulk import complete!")
    print(f"  Processed: {processed:,}")
    print(f"  Imported:  {imported:,}")
    print(f"  Skipped:   {skipped:,} (duplicates)")
    print(f"  Errors:    {errors:,}")
    print(f"  Time:      {_format_time(elapsed)}")
    if imported > 0:
        print(f"  Speed:     {imported / elapsed:.0f} emails/sec")
    print(f"{'='*60}\n")

    # Update label counts
    print("Updating label counts...")
    cursor.execute("""
        UPDATE labels SET email_count = (
            SELECT COUNT(*) FROM email_labels WHERE email_labels.label_id = labels.id
        )
    """)
    conn.commit()
    print("  Done.\n")

    conn.close()

    # Build FTS index as a separate step (after all data is in)
    print("Building full-text search index...")
    fts_start = time.time()
    build_fts()
    print(f"  Total FTS build time: {time.time() - fts_start:.1f}s\n")

    total_time = time.time() - start_time
    print(f"{'='*60}")
    print(f"ALL DONE! Total time: {_format_time(total_time)}")
    print(f"{'='*60}")


def _print_progress(processed, imported, skipped, errors, start_time, bytes_read, file_size):
    elapsed = time.time() - start_time
    rate = processed / elapsed if elapsed > 0 else 0
    pct = min(bytes_read / file_size * 100, 99.9) if file_size > 0 else 0
    bytes_rate = bytes_read / elapsed if elapsed > 0 else 0

    if bytes_rate > 0 and file_size > bytes_read:
        remaining = (file_size - bytes_read) / bytes_rate
        eta = _format_time(remaining)
    else:
        eta = "unknown"

    sys.stdout.write(
        f"\r  [{pct:5.1f}%] Processed: {processed:>9,} | "
        f"Imported: {imported:>9,} | Skipped: {skipped:>7,} | "
        f"Errors: {errors:>5,} | {rate:,.0f}/sec | ETA: {eta}  "
    )
    sys.stdout.flush()


def _format_time(seconds):
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}h {m}m"


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = input("Enter path to .mbox file: ").strip()

    if not os.path.exists(path):
        print(f"Error: File not found: {path}")
        sys.exit(1)

    import_mbox(path)
