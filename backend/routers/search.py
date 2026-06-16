import json
import sqlite3
from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from database import get_connection

router = APIRouter(prefix="/api/search", tags=["search"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json_col(val) -> list:
    if not val:
        return []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []


def _safe_count(cursor, sql, params) -> int:
    """Execute a count query, returning 0 if the table doesn't exist."""
    try:
        return cursor.execute(sql, params).fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def _safe_query(cursor, sql, params) -> list:
    """Execute a query, returning [] if the table doesn't exist."""
    try:
        return cursor.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.get("")
async def global_search(
    q: str = Query("", description="Search query across all data types"),
    limit_per_type: int = Query(5, ge=1, le=20, description="Max results per type"),
):
    """Search across ALL data types. Returns results grouped by type with counts.

    Searches: emails, photos, contacts, calendar events, chat messages,
    drive files, and notes. Returns top results per type plus total counts.
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Search query 'q' is required")

    conn = get_connection(readonly=True)
    try:
        c = conn.cursor()
        like = f"%{q}%"
        results = {}

        # --- Emails ---
        email_count = _safe_count(
            c,
            "SELECT COUNT(*) FROM emails "
            "WHERE deleted_at IS NULL AND (subject LIKE ? OR from_name LIKE ? OR from_address LIKE ? OR body_text LIKE ?)",
            (like, like, like, like),
        )
        email_rows = _safe_query(
            c,
            "SELECT id, subject, from_name, from_address, date, "
            "SUBSTR(body_text, 1, 200) as snippet "
            "FROM emails "
            "WHERE deleted_at IS NULL AND (subject LIKE ? OR from_name LIKE ? OR from_address LIKE ? OR body_text LIKE ?) "
            "ORDER BY date_unix DESC LIMIT ?",
            (like, like, like, like, limit_per_type),
        )
        results["emails"] = {
            "total": email_count,
            "items": [
                {
                    "id": r["id"],
                    "title": r["subject"],
                    "subtitle": r["from_name"] or r["from_address"],
                    "date": r["date"],
                    "snippet": (r["snippet"] or "").replace("\n", " ").strip(),
                    "type": "email",
                }
                for r in email_rows
            ],
        }

        # --- Photos ---
        photo_count = _safe_count(
            c,
            "SELECT COUNT(*) FROM photos "
            "WHERE deleted_at IS NULL AND (title LIKE ? OR description LIKE ? OR filename LIKE ?)",
            (like, like, like),
        )
        photo_rows = _safe_query(
            c,
            "SELECT id, title, filename, description, date_taken "
            "FROM photos "
            "WHERE deleted_at IS NULL AND (title LIKE ? OR description LIKE ? OR filename LIKE ?) "
            "ORDER BY date_taken_unix DESC LIMIT ?",
            (like, like, like, limit_per_type),
        )
        results["photos"] = {
            "total": photo_count,
            "items": [
                {
                    "id": r["id"],
                    "title": r["title"] or r["filename"],
                    "subtitle": r["description"],
                    "date": r["date_taken"],
                    "type": "photo",
                }
                for r in photo_rows
            ],
        }

        # --- Contacts ---
        contact_count = _safe_count(
            c,
            "SELECT COUNT(*) FROM contacts "
            "WHERE deleted_at IS NULL AND (name LIKE ? OR emails LIKE ? OR phones LIKE ? OR organization LIKE ?)",
            (like, like, like, like),
        )
        contact_rows = _safe_query(
            c,
            "SELECT id, name, organization, emails as email_json "
            "FROM contacts "
            "WHERE deleted_at IS NULL AND (name LIKE ? OR emails LIKE ? OR phones LIKE ? OR organization LIKE ?) "
            "ORDER BY name ASC LIMIT ?",
            (like, like, like, like, limit_per_type),
        )
        results["contacts"] = {
            "total": contact_count,
            "items": [
                {
                    "id": r["id"],
                    "title": r["name"],
                    "subtitle": r["organization"],
                    "type": "contact",
                }
                for r in contact_rows
            ],
        }

        # --- Calendar Events ---
        event_count = _safe_count(
            c,
            "SELECT COUNT(*) FROM calendar_events "
            "WHERE deleted_at IS NULL AND (summary LIKE ? OR description LIKE ? OR location LIKE ?)",
            (like, like, like),
        )
        event_rows = _safe_query(
            c,
            "SELECT id, summary, location, start_time, calendar_name "
            "FROM calendar_events "
            "WHERE deleted_at IS NULL AND (summary LIKE ? OR description LIKE ? OR location LIKE ?) "
            "ORDER BY start_unix DESC LIMIT ?",
            (like, like, like, limit_per_type),
        )
        results["calendar"] = {
            "total": event_count,
            "items": [
                {
                    "id": r["id"],
                    "title": r["summary"],
                    "subtitle": r["location"] or r["calendar_name"],
                    "date": r["start_time"],
                    "type": "calendar_event",
                }
                for r in event_rows
            ],
        }

        # --- Chat Messages ---
        chat_count = _safe_count(
            c,
            "SELECT COUNT(*) FROM chat_messages WHERE content LIKE ? AND deleted_at IS NULL",
            (like,),
        )
        chat_rows = _safe_query(
            c,
            "SELECT m.id, m.content, m.sender_name, m.timestamp, "
            "m.conversation_id, cc.name as conversation_name "
            "FROM chat_messages m "
            "JOIN chat_conversations cc ON cc.id = m.conversation_id "
            "WHERE m.content LIKE ? AND m.deleted_at IS NULL "
            "ORDER BY m.timestamp_unix DESC LIMIT ?",
            (like, limit_per_type),
        )
        results["chat"] = {
            "total": chat_count,
            "items": [
                {
                    "id": r["id"],
                    "title": r["conversation_name"],
                    "subtitle": r["sender_name"],
                    "date": r["timestamp"],
                    "snippet": (r["content"] or "")[:200].replace("\n", " ").strip(),
                    "conversation_id": r["conversation_id"],
                    "type": "chat_message",
                }
                for r in chat_rows
            ],
        }

        # --- Drive Files ---
        drive_count = _safe_count(
            c,
            "SELECT COUNT(*) FROM drive_files "
            "WHERE deleted_at IS NULL AND (filename LIKE ? OR extracted_text LIKE ? OR path LIKE ?)",
            (like, like, like),
        )
        drive_rows = _safe_query(
            c,
            "SELECT id, filename, path, mime_type, modified_time, "
            "SUBSTR(extracted_text, 1, 200) as snippet "
            "FROM drive_files "
            "WHERE deleted_at IS NULL AND (filename LIKE ? OR extracted_text LIKE ? OR path LIKE ?) "
            "ORDER BY modified_unix DESC LIMIT ?",
            (like, like, like, limit_per_type),
        )
        results["drive"] = {
            "total": drive_count,
            "items": [
                {
                    "id": r["id"],
                    "title": r["filename"],
                    "subtitle": r["path"],
                    "date": r["modified_time"],
                    "snippet": (r["snippet"] or "").replace("\n", " ").strip(),
                    "type": "drive_file",
                }
                for r in drive_rows
            ],
        }

        # --- Notes ---
        note_count = _safe_count(
            c,
            "SELECT COUNT(*) FROM notes "
            "WHERE (title LIKE ? OR content LIKE ?) AND is_trashed = 0",
            (like, like),
        )
        note_rows = _safe_query(
            c,
            "SELECT id, title, SUBSTR(content, 1, 200) as snippet, "
            "color, modified_time "
            "FROM notes "
            "WHERE (title LIKE ? OR content LIKE ?) AND is_trashed = 0 "
            "ORDER BY modified_time DESC LIMIT ?",
            (like, like, limit_per_type),
        )
        results["notes"] = {
            "total": note_count,
            "items": [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "date": r["modified_time"],
                    "snippet": (r["snippet"] or "").replace("\n", " ").strip(),
                    "color": r["color"],
                    "type": "note",
                }
                for r in note_rows
            ],
        }

        # Compute grand total
        grand_total = sum(section["total"] for section in results.values())

        return {
            "query": q,
            "total_results": grand_total,
            "results": results,
        }
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()
