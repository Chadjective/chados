import json
import sqlite3
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from database import get_connection

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


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


def _contact_summary(row) -> dict:
    """Build a contact summary dict from a sqlite3.Row."""
    return {
        "id": row["id"],
        "name": row["name"],
        "given_name": row["given_name"],
        "family_name": row["family_name"],
        "emails": _parse_json_col(row["emails"]),
        "phones": _parse_json_col(row["phones"]),
        "organization": row["organization"],
        "title": row["title"],
        "notes": row["notes"],
        "groups": _parse_json_col(row["groups"]),
        "has_photo": bool(row["photo_path"]),
    }


def _contact_detail(row) -> dict:
    """Build a full contact detail dict from a sqlite3.Row."""
    result = _contact_summary(row)
    result["notes"] = row["notes"]
    result["photo_path"] = row["photo_path"]
    result["source_file"] = row["source_file"]
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/search")
async def search_contacts(
    q: str = Query("", description="Search query"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=2000),
):
    """Search contacts by name, email, phone, or organization."""
    if not q.strip():
        raise HTTPException(status_code=400, detail="Search query 'q' is required")

    conn = get_connection(readonly=True)
    try:
        c = conn.cursor()
        like = f"%{q}%"
        where = (
            "name LIKE ? OR given_name LIKE ? OR family_name LIKE ? "
            "OR emails LIKE ? OR phones LIKE ? OR organization LIKE ?"
        )
        count = c.execute(
            f"SELECT COUNT(*) FROM contacts WHERE {where}",
            (like, like, like, like, like, like),
        ).fetchone()[0]
        rows = c.execute(
            f"SELECT * FROM contacts WHERE {where} ORDER BY name ASC LIMIT ? OFFSET ?",
            (like, like, like, like, like, like, limit, offset),
        ).fetchall()
        return {
            "contacts": [_contact_summary(r) for r in rows],
            "total": count,
        }
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()


@router.get("/groups")
async def list_contact_groups():
    """List contact groups with member counts."""
    conn = get_connection(readonly=True)
    try:
        c = conn.cursor()
        rows = c.execute("SELECT groups FROM contacts WHERE groups IS NOT NULL").fetchall()
        group_counts = {}  # type: dict
        for row in rows:
            groups = _parse_json_col(row["groups"])
            for g in groups:
                if g:
                    group_counts[g] = group_counts.get(g, 0) + 1
        result = [
            {"name": name, "count": count}
            for name, count in sorted(group_counts.items())
        ]
        return {"groups": result, "total": len(result)}
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()


@router.get("/{contact_id}")
async def get_contact(contact_id: int):
    """Get full contact detail."""
    conn = get_connection(readonly=True)
    try:
        row = conn.execute(
            "SELECT * FROM contacts WHERE id = ?", (contact_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Contact not found")
        return _contact_detail(row)
    except HTTPException:
        raise
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()


@router.get("")
async def list_contacts(
    q: Optional[str] = Query(None, description="Search by name/email/phone/org"),
    group: Optional[str] = Query(None, description="Filter by group name"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=2000),
):
    """Paginated contact list, searchable and sortable alphabetically."""
    conn = get_connection(readonly=True)
    try:
        c = conn.cursor()
        conditions = []  # type: List[str]
        params = []  # type: list

        if q:
            like = f"%{q}%"
            conditions.append(
                "(name LIKE ? OR given_name LIKE ? OR family_name LIKE ? "
                "OR emails LIKE ? OR phones LIKE ? OR organization LIKE ?)"
            )
            params.extend([like, like, like, like, like, like])

        if group:
            # groups is stored as JSON array, use LIKE for matching
            conditions.append("groups LIKE ?")
            params.append(f'%"{group}"%')

        where = " AND ".join(conditions) if conditions else "1=1"

        count = c.execute(
            f"SELECT COUNT(*) FROM contacts WHERE {where}", params
        ).fetchone()[0]
        rows = c.execute(
            f"SELECT * FROM contacts WHERE {where} ORDER BY name ASC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

        return {
            "contacts": [_contact_summary(r) for r in rows],
            "total": count,
        }
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()
