import json
import sqlite3
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from database import get_connection

router = APIRouter(prefix="/api/notes", tags=["notes"])


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


def _note_summary(row) -> dict:
    """Build a note summary dict from a sqlite3.Row."""
    content = row["content"] or ""
    return {
        "id": row["id"],
        "title": row["title"],
        "snippet": content[:200].replace("\n", " ").strip(),
        "color": row["color"],
        "labels": _parse_json_col(row["labels"]),
        "is_archived": bool(row["is_archived"]),
        "is_pinned": bool(row["is_pinned"]),
        "is_trashed": bool(row["is_trashed"]),
        "created_time": row["created_time"],
        "modified_time": row["modified_time"],
    }


def _note_detail(row) -> dict:
    """Build a full note detail dict from a sqlite3.Row."""
    return {
        "id": row["id"],
        "title": row["title"],
        "content": row["content"],
        "color": row["color"],
        "labels": _parse_json_col(row["labels"]),
        "is_archived": bool(row["is_archived"]),
        "is_pinned": bool(row["is_pinned"]),
        "is_trashed": bool(row["is_trashed"]),
        "created_time": row["created_time"],
        "modified_time": row["modified_time"],
        "source_file": row["source_file"],
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/labels")
async def list_note_labels():
    """List note labels with counts."""
    conn = get_connection(readonly=True)
    try:
        c = conn.cursor()
        rows = c.execute(
            "SELECT labels FROM notes WHERE labels IS NOT NULL AND is_trashed = 0"
        ).fetchall()

        label_counts = {}  # type: dict
        for row in rows:
            labels = _parse_json_col(row["labels"])
            for label in labels:
                if label:
                    label_counts[label] = label_counts.get(label, 0) + 1

        result = [
            {"name": name, "count": count}
            for name, count in sorted(label_counts.items())
        ]
        return {"labels": result, "total": len(result)}
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()


@router.get("/{note_id}")
async def get_note(note_id: int):
    """Get a single note detail."""
    conn = get_connection(readonly=True)
    try:
        row = conn.execute(
            "SELECT * FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Note not found")
        return _note_detail(row)
    except HTTPException:
        raise
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()


@router.get("")
async def list_notes(
    label: Optional[str] = Query(None, description="Filter by label"),
    color: Optional[str] = Query(None, description="Filter by color"),
    archived: Optional[bool] = Query(None, description="Filter by archived status"),
    pinned: Optional[bool] = Query(None, description="Filter pinned notes"),
    q: Optional[str] = Query(None, description="Search title/content"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Paginated note list, filterable by label, color, and archived status."""
    conn = get_connection(readonly=True)
    try:
        c = conn.cursor()
        conditions = ["is_trashed = 0"]  # type: List[str]
        params = []  # type: list

        if label:
            conditions.append("labels LIKE ?")
            params.append(f'%"{label}"%')

        if color:
            conditions.append("color = ?")
            params.append(color)

        if archived is not None:
            conditions.append("is_archived = ?")
            params.append(1 if archived else 0)

        if pinned is not None:
            conditions.append("is_pinned = ?")
            params.append(1 if pinned else 0)

        if q:
            like = f"%{q}%"
            conditions.append("(title LIKE ? OR content LIKE ?)")
            params.extend([like, like])

        where = " AND ".join(conditions)

        count = c.execute(
            f"SELECT COUNT(*) FROM notes WHERE {where}", params
        ).fetchone()[0]

        # Pinned first, then by modified_time desc
        rows = c.execute(
            f"SELECT * FROM notes WHERE {where} "
            f"ORDER BY is_pinned DESC, modified_time DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

        return {"notes": [_note_summary(r) for r in rows], "total": count}
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()
