import sqlite3
from typing import Optional, List
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse
from database import get_connection

router = APIRouter(prefix="/api/photos", tags=["photos"])


def _photo_dict(row):
    """Convert a sqlite3.Row to a dict for a photo."""
    return {
        "id": row["id"],
        "filename": row["filename"],
        "title": row["title"],
        "description": row["description"],
        "mime_type": row["mime_type"],
        "width": row["width"],
        "height": row["height"],
        "size_bytes": row["size_bytes"],
        "date_taken": row["date_taken"],
        "date_taken_unix": row["date_taken_unix"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "camera_make": row["camera_make"],
        "camera_model": row["camera_model"],
        "device_type": row["device_type"],
        "is_video": bool(row["is_video"]),
        "duration_seconds": row["duration_seconds"],
        "is_favorite": bool(row["is_favorite"]),
        "source_album": row["source_album"],
        "has_thumbnail": bool(row["thumbnail_path"]),
    }


@router.get("/stats")
async def photo_stats():
    """Basic stats about the photo archive."""
    conn = get_connection(readonly=True)
    try:
        c = conn.cursor()
        total_photos = c.execute("SELECT COUNT(*) FROM photos WHERE is_video = 0").fetchone()[0]
        total_videos = c.execute("SELECT COUNT(*) FROM photos WHERE is_video = 1").fetchone()[0]
        total_albums = c.execute("SELECT COUNT(*) FROM albums").fetchone()[0]
        date_range = c.execute(
            "SELECT MIN(date_taken) as earliest, MAX(date_taken) as latest FROM photos"
        ).fetchone()
        total_size = c.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM photos").fetchone()[0]
        return {
            "total_photos": total_photos,
            "total_videos": total_videos,
            "total_albums": total_albums,
            "earliest_date": date_range["earliest"],
            "latest_date": date_range["latest"],
            "total_size_bytes": total_size,
        }
    except sqlite3.OperationalError:
        return {"total_photos": 0, "total_videos": 0, "total_albums": 0,
                "earliest_date": None, "latest_date": None, "total_size_bytes": 0}
    finally:
        conn.close()


@router.get("/timeline")
async def photo_timeline():
    """Get photo counts grouped by year and month for timeline navigation."""
    conn = get_connection(readonly=True)
    try:
        c = conn.cursor()
        rows = c.execute("""
            SELECT
                CAST(strftime('%Y', date_taken) AS INTEGER) as year,
                CAST(strftime('%m', date_taken) AS INTEGER) as month,
                COUNT(*) as count
            FROM photos
            WHERE date_taken IS NOT NULL
            GROUP BY year, month
            ORDER BY year DESC, month DESC
        """).fetchall()
        return [{"year": r["year"], "month": r["month"], "count": r["count"]} for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


@router.get("/search")
async def search_photos(
    q: str = Query("", description="Search query"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Search photos by filename, title, description, or album."""
    if not q.strip():
        raise HTTPException(status_code=400, detail="Search query required")

    conn = get_connection(readonly=True)
    try:
        c = conn.cursor()
        like = f"%{q}%"
        count = c.execute(
            "SELECT COUNT(*) FROM photos WHERE title LIKE ? OR description LIKE ? OR filename LIKE ? OR source_album LIKE ?",
            (like, like, like, like)
        ).fetchone()[0]
        rows = c.execute(
            "SELECT * FROM photos WHERE title LIKE ? OR description LIKE ? OR filename LIKE ? OR source_album LIKE ? "
            "ORDER BY date_taken_unix DESC LIMIT ? OFFSET ?",
            (like, like, like, like, limit, offset)
        ).fetchall()
        return {"photos": [_photo_dict(r) for r in rows], "total": count}
    finally:
        conn.close()


@router.get("/albums")
async def list_albums():
    """List all albums with counts and cover photos."""
    conn = get_connection(readonly=True)
    try:
        c = conn.cursor()
        rows = c.execute("""
            SELECT a.id, a.name, a.photo_count, a.cover_photo_id,
                   p.thumbnail_path as cover_thumbnail
            FROM albums a
            LEFT JOIN photos p ON p.id = a.cover_photo_id
            WHERE a.photo_count > 0
            ORDER BY a.name
        """).fetchall()
        return [{
            "id": r["id"],
            "name": r["name"],
            "photo_count": r["photo_count"],
            "cover_photo_id": r["cover_photo_id"],
            "has_cover_thumbnail": bool(r["cover_thumbnail"]),
        } for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


@router.get("/albums/{album_id}")
async def get_album_photos(
    album_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Get photos in an album."""
    conn = get_connection(readonly=True)
    try:
        c = conn.cursor()
        album = c.execute("SELECT * FROM albums WHERE id = ?", (album_id,)).fetchone()
        if not album:
            raise HTTPException(status_code=404, detail="Album not found")

        count = c.execute(
            "SELECT COUNT(*) FROM photo_albums WHERE album_id = ?", (album_id,)
        ).fetchone()[0]

        rows = c.execute("""
            SELECT p.* FROM photos p
            JOIN photo_albums pa ON pa.photo_id = p.id
            WHERE pa.album_id = ?
            ORDER BY p.date_taken_unix DESC
            LIMIT ? OFFSET ?
        """, (album_id, limit, offset)).fetchall()

        return {
            "album": {"id": album["id"], "name": album["name"], "photo_count": album["photo_count"]},
            "photos": [_photo_dict(r) for r in rows],
            "total": count,
        }
    finally:
        conn.close()


@router.get("/{photo_id}")
async def get_photo(photo_id: int):
    """Get full photo metadata."""
    conn = get_connection(readonly=True)
    try:
        row = conn.execute("SELECT * FROM photos WHERE id = ?", (photo_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Photo not found")

        # Get albums this photo belongs to
        albums = conn.execute("""
            SELECT a.id, a.name FROM albums a
            JOIN photo_albums pa ON pa.album_id = a.id
            WHERE pa.photo_id = ?
        """, (photo_id,)).fetchall()

        result = _photo_dict(row)
        result["albums"] = [{"id": a["id"], "name": a["name"]} for a in albums]
        return result
    finally:
        conn.close()


@router.get("/{photo_id}/thumbnail")
async def get_thumbnail(photo_id: int):
    """Serve the thumbnail for a photo."""
    conn = get_connection(readonly=True)
    try:
        row = conn.execute(
            "SELECT thumbnail_path FROM photos WHERE id = ?", (photo_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Photo not found")
        if not row["thumbnail_path"]:
            raise HTTPException(status_code=404, detail="No thumbnail available")

        thumb = Path(row["thumbnail_path"])
        if not thumb.exists():
            raise HTTPException(status_code=404, detail="Thumbnail file missing")

        return FileResponse(str(thumb), media_type="image/jpeg")
    finally:
        conn.close()


@router.get("/{photo_id}/full")
async def get_full_photo(photo_id: int):
    """Serve the full-resolution photo/video."""
    conn = get_connection(readonly=True)
    try:
        row = conn.execute(
            "SELECT file_path, mime_type, filename FROM photos WHERE id = ?", (photo_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Photo not found")

        fp = Path(row["file_path"])
        if not fp.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")

        return FileResponse(
            str(fp),
            media_type=row["mime_type"],
            filename=row["filename"],
        )
    finally:
        conn.close()


@router.get("")
async def list_photos(
    year: Optional[int] = Query(None, description="Filter by year"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Filter by month"),
    media_type: Optional[str] = Query(None, description="'photo' or 'video'"),
    favorite: Optional[bool] = Query(None, description="Filter favorites"),
    album: Optional[str] = Query(None, description="Filter by album name"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Paginated photo list with filters."""
    conn = get_connection(readonly=True)
    try:
        c = conn.cursor()
        conditions = []  # type: List[str]
        params = []  # type: list

        if year:
            conditions.append("CAST(strftime('%Y', date_taken) AS INTEGER) = ?")
            params.append(year)
        if month:
            conditions.append("CAST(strftime('%m', date_taken) AS INTEGER) = ?")
            params.append(month)
        if media_type == 'photo':
            conditions.append("is_video = 0")
        elif media_type == 'video':
            conditions.append("is_video = 1")
        if favorite:
            conditions.append("is_favorite = 1")
        if album:
            conditions.append(
                "EXISTS (SELECT 1 FROM photo_albums pa JOIN albums a ON a.id = pa.album_id "
                "WHERE pa.photo_id = photos.id AND a.name = ?)"
            )
            params.append(album)

        where = " AND ".join(conditions) if conditions else "1=1"

        count = c.execute(f"SELECT COUNT(*) FROM photos WHERE {where}", params).fetchone()[0]
        rows = c.execute(
            f"SELECT * FROM photos WHERE {where} ORDER BY date_taken_unix DESC LIMIT ? OFFSET ?",
            params + [limit, offset]
        ).fetchall()

        return {"photos": [_photo_dict(r) for r in rows], "total": count}
    except sqlite3.OperationalError:
        return {"photos": [], "total": 0}
    finally:
        conn.close()
