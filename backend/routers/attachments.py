import sqlite3
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from database import get_connection
from models import AttachmentInfo

router = APIRouter(prefix="/api/attachments", tags=["attachments"])


def _get_attachment_row(attachment_id: int):
    """Fetch an attachment row by ID. Raises HTTPException if not found."""
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT id, email_id, filename, content_type, size_bytes, file_path "
            "FROM attachments WHERE id = ?",
            (attachment_id,),
        ).fetchone()
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return row


@router.get("/{attachment_id}/info", response_model=AttachmentInfo)
async def attachment_info(attachment_id: int):
    """Return attachment metadata without streaming the file."""
    row = _get_attachment_row(attachment_id)
    return AttachmentInfo(
        id=row["id"],
        email_id=row["email_id"],
        filename=row["filename"],
        content_type=row["content_type"],
        size_bytes=row["size_bytes"],
    )


@router.get("/{attachment_id}")
async def get_attachment(attachment_id: int):
    """Stream an attachment file from disk.

    Sets Content-Disposition to attachment so the browser triggers a download.
    """
    row = _get_attachment_row(attachment_id)

    file_path = Path(row["file_path"]) if row["file_path"] else None
    if not file_path or not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Attachment file not found on disk",
        )

    media_type = row["content_type"] or "application/octet-stream"
    filename = row["filename"] or f"attachment_{attachment_id}"

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=media_type,
    )


@router.get("/{attachment_id}/preview")
async def preview_attachment(attachment_id: int):
    """Serve attachment inline for preview (images, PDFs, text)."""
    row = _get_attachment_row(attachment_id)

    file_path = Path(row["file_path"]) if row["file_path"] else None
    if not file_path or not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Attachment file not found on disk",
        )

    content_type = row["content_type"] or "application/octet-stream"

    previewable = (
        content_type.startswith("image/")
        or content_type == "application/pdf"
        or content_type.startswith("text/")
    )
    if not previewable:
        raise HTTPException(
            status_code=415, detail="This file type cannot be previewed inline"
        )

    return FileResponse(
        path=str(file_path),
        media_type=content_type,
        headers={"Content-Disposition": "inline"},
    )
