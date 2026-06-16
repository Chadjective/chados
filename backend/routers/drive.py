import sqlite3
from typing import Optional, List
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse
from database import get_connection

router = APIRouter(prefix="/api/drive", tags=["drive"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _file_summary(row) -> dict:
    """Build a file summary dict from a sqlite3.Row."""
    return {
        "id": row["id"],
        "filename": row["filename"],
        "path": row["path"],
        "parent_path": row["parent_path"],
        "mime_type": row["mime_type"],
        "size_bytes": row["size_bytes"],
        "modified_time": row["modified_time"],
        "is_folder": bool(row["is_folder"]),
    }


def _file_detail(row) -> dict:
    """Build a full file detail dict from a sqlite3.Row."""
    result = _file_summary(row)
    result["extracted_text"] = row["extracted_text"]
    result["source_file"] = row["source_file"]
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/search")
async def search_files(
    q: str = Query("", description="Search query"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Search filenames and extracted text."""
    if not q.strip():
        raise HTTPException(status_code=400, detail="Search query 'q' is required")

    conn = get_connection(readonly=True)
    try:
        c = conn.cursor()
        like = f"%{q}%"
        where = "deleted_at IS NULL AND (filename LIKE ? OR extracted_text LIKE ? OR path LIKE ?)"

        count = c.execute(
            f"SELECT COUNT(*) FROM drive_files WHERE {where}",
            (like, like, like),
        ).fetchone()[0]
        rows = c.execute(
            f"SELECT * FROM drive_files WHERE {where} "
            f"ORDER BY modified_unix DESC LIMIT ? OFFSET ?",
            (like, like, like, limit, offset),
        ).fetchall()

        return {"files": [_file_summary(r) for r in rows], "total": count}
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()


@router.get("/folders")
async def list_folders():
    """List all unique folder paths for tree navigation."""
    conn = get_connection(readonly=True)
    try:
        c = conn.cursor()
        rows = c.execute(
            "SELECT DISTINCT parent_path FROM drive_files "
            "WHERE parent_path IS NOT NULL AND parent_path != '' AND deleted_at IS NULL "
            "ORDER BY parent_path ASC"
        ).fetchall()

        folders = [r["parent_path"] for r in rows]

        # Also include folders that are actual entries
        folder_rows = c.execute(
            "SELECT path FROM drive_files WHERE is_folder = 1 AND deleted_at IS NULL ORDER BY path ASC"
        ).fetchall()
        folder_entries = [r["path"] for r in folder_rows]

        # Merge unique folder paths
        all_folders = sorted(set(folders + folder_entries))

        return {"folders": all_folders, "total": len(all_folders)}
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()


@router.get("/files/{file_id}/preview")
async def preview_file(file_id: int):
    """Serve the actual file for inline preview."""
    conn = get_connection(readonly=True)
    try:
        row = conn.execute(
            "SELECT source_file, mime_type, filename FROM drive_files WHERE id = ?",
            (file_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="File not found")
        if not row["source_file"]:
            raise HTTPException(status_code=404, detail="No source file available")

        fp = Path(row["source_file"])
        if not fp.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")

        return FileResponse(
            str(fp),
            media_type=row["mime_type"] or "application/octet-stream",
            filename=row["filename"],
        )
    except HTTPException:
        raise
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()


@router.get("/files/{file_id}")
async def get_file(file_id: int):
    """Get full file detail including extracted text."""
    conn = get_connection(readonly=True)
    try:
        row = conn.execute(
            "SELECT * FROM drive_files WHERE id = ? AND deleted_at IS NULL", (file_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="File not found")
        return _file_detail(row)
    except HTTPException:
        raise
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()


@router.get("/files")
async def list_files(
    parent_path: Optional[str] = Query(None, description="Filter by parent folder path"),
    mime_type: Optional[str] = Query(None, description="Filter by MIME type"),
    q: Optional[str] = Query(None, description="Filter by filename"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """List files with optional folder browsing via parent_path filter."""
    conn = get_connection(readonly=True)
    try:
        c = conn.cursor()
        conditions: List[str] = ["deleted_at IS NULL"]
        params: list = []

        if parent_path is not None:
            conditions.append("parent_path = ?")
            params.append(parent_path)

        if mime_type:
            conditions.append("mime_type = ?")
            params.append(mime_type)

        if q:
            like = f"%{q}%"
            conditions.append("filename LIKE ?")
            params.append(like)

        where = " AND ".join(conditions) if conditions else "1=1"

        count = c.execute(
            f"SELECT COUNT(*) FROM drive_files WHERE {where}", params
        ).fetchone()[0]

        # Folders first, then files, both sorted by name
        rows = c.execute(
            f"SELECT * FROM drive_files WHERE {where} "
            f"ORDER BY is_folder DESC, filename ASC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

        return {"files": [_file_summary(r) for r in rows], "total": count}
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()
