"""Related items endpoint — finds contextually related items across data types."""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from database import get_connection
from models import (
    RelatedResponse,
    RelatedSource,
    RelatedEmail,
    RelatedPhoto,
    RelatedEvent,
    RelatedContact,
    RelatedChat,
    RelatedDrive,
)

router = APIRouter(prefix="/api", tags=["related"])

# 3 days in seconds
THREE_DAYS = 3 * 24 * 60 * 60


def _get_source_date_unix(conn, item_type: str, item_id: int) -> Optional[int]:
    """Get the unix timestamp for a source item."""
    cursor = conn.cursor()
    if item_type == "email":
        row = cursor.execute(
            "SELECT date_unix, date, from_address, from_name FROM emails WHERE id = ?",
            (item_id,),
        ).fetchone()
        if not row:
            return None
        return row["date_unix"]
    elif item_type == "photo":
        row = cursor.execute(
            "SELECT date_taken_unix FROM photos WHERE id = ?", (item_id,)
        ).fetchone()
        return row["date_taken_unix"] if row else None
    elif item_type == "event":
        row = cursor.execute(
            "SELECT start_unix FROM calendar_events WHERE id = ?", (item_id,)
        ).fetchone()
        return row["start_unix"] if row else None
    elif item_type == "chat":
        row = cursor.execute(
            "SELECT timestamp_unix FROM chat_messages WHERE id = ?", (item_id,)
        ).fetchone()
        return row["timestamp_unix"] if row else None
    return None


def _find_related_emails(cursor, source_unix: int, exclude_type: str, limit: int = 5):
    """Find emails within +/-3 days of source date."""
    if exclude_type == "email":
        return []
    lo = source_unix - THREE_DAYS
    hi = source_unix + THREE_DAYS
    rows = cursor.execute(
        """SELECT id, subject, from_name, date, date_unix
           FROM emails
           WHERE date_unix BETWEEN ? AND ?
           ORDER BY ABS(date_unix - ?) ASC
           LIMIT ?""",
        (lo, hi, source_unix, limit),
    ).fetchall()
    return [
        RelatedEmail(
            id=r["id"],
            subject=r["subject"],
            from_name=r["from_name"],
            date=r["date"],
        )
        for r in rows
    ]


def _find_related_photos(cursor, source_unix: int, exclude_type: str, limit: int = 5):
    """Find photos within +/-3 days of source date."""
    if exclude_type == "photo":
        return []
    lo = source_unix - THREE_DAYS
    hi = source_unix + THREE_DAYS
    rows = cursor.execute(
        """SELECT id, filename, date_taken, date_taken_unix, thumbnail_path
           FROM photos
           WHERE date_taken_unix BETWEEN ? AND ?
           ORDER BY ABS(date_taken_unix - ?) ASC
           LIMIT ?""",
        (lo, hi, source_unix, limit),
    ).fetchall()
    return [
        RelatedPhoto(
            id=r["id"],
            filename=r["filename"],
            date_taken=r["date_taken"],
            thumbnail_path=r["thumbnail_path"],
        )
        for r in rows
    ]


def _find_related_events(cursor, source_unix: int, exclude_type: str, limit: int = 5):
    """Find calendar events within +/-3 days of source date."""
    if exclude_type == "event":
        return []
    lo = source_unix - THREE_DAYS
    hi = source_unix + THREE_DAYS
    rows = cursor.execute(
        """SELECT id, summary, start_time, start_unix, location
           FROM calendar_events
           WHERE start_unix BETWEEN ? AND ?
           ORDER BY ABS(start_unix - ?) ASC
           LIMIT ?""",
        (lo, hi, source_unix, limit),
    ).fetchall()
    return [
        RelatedEvent(
            id=r["id"],
            summary=r["summary"],
            start_time=r["start_time"],
            location=r["location"],
        )
        for r in rows
    ]


def _find_related_chats(cursor, source_unix: int, exclude_type: str, limit: int = 5):
    """Find chat messages within +/-3 days of source date."""
    if exclude_type == "chat":
        return []
    lo = source_unix - THREE_DAYS
    hi = source_unix + THREE_DAYS
    rows = cursor.execute(
        """SELECT id, conversation_id, sender_name, content, timestamp, timestamp_unix
           FROM chat_messages
           WHERE timestamp_unix BETWEEN ? AND ?
           ORDER BY ABS(timestamp_unix - ?) ASC
           LIMIT ?""",
        (lo, hi, source_unix, limit),
    ).fetchall()
    return [
        RelatedChat(
            id=r["id"],
            conversation_id=r["conversation_id"],
            sender_name=r["sender_name"],
            content=(r["content"] or "")[:200],
            timestamp=r["timestamp"],
        )
        for r in rows
    ]


def _find_related_drive(cursor, source_unix: int, exclude_type: str, limit: int = 5):
    """Find drive files modified within +/-3 days of source date."""
    lo = source_unix - THREE_DAYS
    hi = source_unix + THREE_DAYS
    rows = cursor.execute(
        """SELECT id, filename, path, mime_type, modified_unix
           FROM drive_files
           WHERE modified_unix BETWEEN ? AND ?
             AND is_folder = 0
           ORDER BY ABS(modified_unix - ?) ASC
           LIMIT ?""",
        (lo, hi, source_unix, limit),
    ).fetchall()
    return [
        RelatedDrive(
            id=r["id"],
            filename=r["filename"],
            path=r["path"],
            mime_type=r["mime_type"],
        )
        for r in rows
    ]


def _find_contact_related(cursor, from_address: str):
    """Find contact-based related items for an email address."""
    contacts = []
    emails_from_person = []
    chats_from_person = []

    if not from_address:
        return contacts, emails_from_person, chats_from_person

    # Find matching contact record
    rows = cursor.execute(
        "SELECT id, name, emails FROM contacts"
    ).fetchall()
    for r in rows:
        try:
            contact_emails = json.loads(r["emails"]) if r["emails"] else []
        except (json.JSONDecodeError, TypeError):
            contact_emails = []
        for ce in contact_emails:
            addr = ce.get("address", "") if isinstance(ce, dict) else str(ce)
            if addr.lower() == from_address.lower():
                contacts.append(
                    RelatedContact(
                        id=r["id"],
                        name=r["name"],
                        emails=[ce] if isinstance(ce, dict) else [{"address": addr}],
                    )
                )
                break
        if len(contacts) >= 2:
            break

    # Recent emails from/to same person
    rows = cursor.execute(
        """SELECT id, subject, from_name, date
           FROM emails
           WHERE from_address = ? OR to_addresses LIKE ?
           ORDER BY date_unix DESC
           LIMIT 5""",
        (from_address, f"%{from_address}%"),
    ).fetchall()
    emails_from_person = [
        RelatedEmail(
            id=r["id"],
            subject=r["subject"],
            from_name=r["from_name"],
            date=r["date"],
        )
        for r in rows
    ]

    # Chat messages involving this person (match by email in sender_email)
    rows = cursor.execute(
        """SELECT id, conversation_id, sender_name, content, timestamp
           FROM chat_messages
           WHERE sender_email = ?
           ORDER BY timestamp_unix DESC
           LIMIT 5""",
        (from_address,),
    ).fetchall()
    chats_from_person = [
        RelatedChat(
            id=r["id"],
            conversation_id=r["conversation_id"],
            sender_name=r["sender_name"],
            content=(r["content"] or "")[:200],
            timestamp=r["timestamp"],
        )
        for r in rows
    ]

    return contacts, emails_from_person, chats_from_person


@router.get("/related")
async def get_related(
    type: str = Query(..., description="Source item type: email, photo, event, chat"),
    id: int = Query(..., description="Source item ID"),
):
    """Find related items across all data types for a given source item."""
    valid_types = ("email", "photo", "event", "chat")
    if type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid type '{type}'. Must be one of: {', '.join(valid_types)}",
        )

    conn = get_connection(readonly=True)
    cursor = conn.cursor()

    try:
        # Get source item date
        source_unix = _get_source_date_unix(conn, type, id)
        if source_unix is None:
            raise HTTPException(status_code=404, detail=f"{type} with id={id} not found")

        # Get source date string for response
        source_date = None
        if type == "email":
            row = cursor.execute("SELECT date FROM emails WHERE id = ?", (id,)).fetchone()
            source_date = row["date"] if row else None
        elif type == "photo":
            row = cursor.execute("SELECT date_taken FROM photos WHERE id = ?", (id,)).fetchone()
            source_date = row["date_taken"] if row else None
        elif type == "event":
            row = cursor.execute("SELECT start_time FROM calendar_events WHERE id = ?", (id,)).fetchone()
            source_date = row["start_time"] if row else None
        elif type == "chat":
            row = cursor.execute("SELECT timestamp FROM chat_messages WHERE id = ?", (id,)).fetchone()
            source_date = row["timestamp"] if row else None

        # Time-based related items
        emails = _find_related_emails(cursor, source_unix, type)
        photos = _find_related_photos(cursor, source_unix, type)
        events = _find_related_events(cursor, source_unix, type)
        chats = _find_related_chats(cursor, source_unix, type)
        drive = _find_related_drive(cursor, source_unix, type)
        contacts = []

        # Contact-based related items for emails
        if type == "email":
            row = cursor.execute(
                "SELECT from_address FROM emails WHERE id = ?", (id,)
            ).fetchone()
            if row and row["from_address"]:
                contact_matches, contact_emails, contact_chats = _find_contact_related(
                    cursor, row["from_address"]
                )
                contacts = contact_matches

                # Merge contact-based emails (deduplicate by id)
                existing_ids = {e.id for e in emails}
                for ce in contact_emails:
                    if ce.id not in existing_ids and ce.id != id:
                        emails.append(ce)
                        existing_ids.add(ce.id)
                emails = emails[:5]

                # Merge contact-based chats (deduplicate by id)
                existing_chat_ids = {c.id for c in chats}
                for cc in contact_chats:
                    if cc.id not in existing_chat_ids:
                        chats.append(cc)
                        existing_chat_ids.add(cc.id)
                chats = chats[:5]

        # Remove the source item from its own results
        if type == "email":
            emails = [e for e in emails if e.id != id]
        elif type == "photo":
            photos = [p for p in photos if p.id != id]
        elif type == "event":
            events = [e for e in events if e.id != id]
        elif type == "chat":
            chats = [c for c in chats if c.id != id]

        return RelatedResponse(
            source=RelatedSource(type=type, id=id, date=source_date),
            related={
                "emails": emails[:5],
                "photos": photos[:5],
                "events": events[:5],
                "contacts": contacts[:5],
                "chats": chats[:5],
                "drive": drive[:5],
            },
        )
    finally:
        conn.close()
