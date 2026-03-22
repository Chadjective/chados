import json
import sqlite3
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from database import get_connection

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


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


def _event_summary(row) -> dict:
    """Build an event summary dict from a sqlite3.Row."""
    return {
        "id": row["id"],
        "calendar_name": row["calendar_name"],
        "summary": row["summary"],
        "description": row["description"],
        "location": row["location"],
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "is_all_day": bool(row["is_all_day"]),
        "recurrence": row["recurrence"],
        "organizer": row["organizer"],
        "attendees": _parse_json_col(row["attendees"]),
        "status": row["status"],
    }


def _event_detail(row) -> dict:
    """Build a full event detail dict from a sqlite3.Row."""
    return {
        "id": row["id"],
        "calendar_name": row["calendar_name"],
        "uid": row["uid"],
        "summary": row["summary"],
        "description": row["description"],
        "location": row["location"],
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "start_unix": row["start_unix"],
        "end_unix": row["end_unix"],
        "is_all_day": bool(row["is_all_day"]),
        "recurrence": row["recurrence"],
        "organizer": row["organizer"],
        "attendees": _parse_json_col(row["attendees"]),
        "status": row["status"],
        "source_file": row["source_file"],
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/calendars")
async def list_calendars():
    """List calendar names with event counts."""
    conn = get_connection(readonly=True)
    try:
        c = conn.cursor()
        rows = c.execute(
            "SELECT calendar_name, COUNT(*) as event_count "
            "FROM calendar_events "
            "GROUP BY calendar_name "
            "ORDER BY event_count DESC"
        ).fetchall()
        return {
            "calendars": [
                {"name": r["calendar_name"], "event_count": r["event_count"]}
                for r in rows
            ],
            "total": len(rows),
        }
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()


@router.get("/month/{year}/{month}")
async def events_by_month(year: int, month: int):
    """Get all events for a specific month."""
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12")

    conn = get_connection(readonly=True)
    try:
        c = conn.cursor()
        # Build date range for the month
        start_date = f"{year:04d}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1:04d}-01-01"
        else:
            end_date = f"{year:04d}-{month + 1:02d}-01"

        rows = c.execute(
            "SELECT * FROM calendar_events "
            "WHERE start_time >= ? AND start_time < ? "
            "ORDER BY start_unix ASC",
            (start_date, end_date),
        ).fetchall()

        return {
            "year": year,
            "month": month,
            "events": [_event_summary(r) for r in rows],
            "total": len(rows),
        }
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()


@router.get("/events/{event_id}")
async def get_event(event_id: int):
    """Get a single event detail."""
    conn = get_connection(readonly=True)
    try:
        row = conn.execute(
            "SELECT * FROM calendar_events WHERE id = ?", (event_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Event not found")
        return _event_detail(row)
    except HTTPException:
        raise
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()


@router.get("/events")
async def list_events(
    calendar: Optional[str] = Query(None, description="Filter by calendar name"),
    start_after: Optional[str] = Query(None, description="Events starting after this ISO date"),
    start_before: Optional[str] = Query(None, description="Events starting before this ISO date"),
    q: Optional[str] = Query(None, description="Search summary/description"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Paginated event list with date range filtering."""
    conn = get_connection(readonly=True)
    try:
        c = conn.cursor()
        conditions = []  # type: List[str]
        params = []  # type: list

        if calendar:
            conditions.append("calendar_name = ?")
            params.append(calendar)

        if start_after:
            conditions.append("start_time >= ?")
            params.append(start_after)

        if start_before:
            conditions.append("start_time <= ?")
            params.append(start_before)

        if q:
            like = f"%{q}%"
            conditions.append("(summary LIKE ? OR description LIKE ? OR location LIKE ?)")
            params.extend([like, like, like])

        where = " AND ".join(conditions) if conditions else "1=1"

        count = c.execute(
            f"SELECT COUNT(*) FROM calendar_events WHERE {where}", params
        ).fetchone()[0]
        rows = c.execute(
            f"SELECT * FROM calendar_events WHERE {where} "
            f"ORDER BY start_unix DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

        return {
            "events": [_event_summary(r) for r in rows],
            "total": count,
        }
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()
