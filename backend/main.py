import sqlite3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db, get_connection
from config import DB_PATH

app = FastAPI(title="Personal Archive", version="2.0.0")

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os

from routers import emails, labels, attachments, photos  # noqa: E402
from routers import contacts, calendar, chat, drive, notes, search, analytics  # noqa: E402
from routers import related  # noqa: E402

app.include_router(emails.router)
app.include_router(labels.router)
app.include_router(attachments.router)
app.include_router(photos.router)
app.include_router(contacts.router)
app.include_router(calendar.router)
app.include_router(chat.router)
app.include_router(drive.router)
app.include_router(notes.router)
app.include_router(search.router)
app.include_router(analytics.router)
app.include_router(related.router)

# AI features are optional — only load if not explicitly disabled
ENABLE_AI = os.environ.get("ARCHIVE_ENABLE_AI", "auto")
if ENABLE_AI != "false":
    try:
        from routers import ai_chat, semantic  # noqa: E402
        app.include_router(ai_chat.router)
        app.include_router(semantic.router)
        _ai_loaded = True
    except ImportError:
        _ai_loaded = False
else:
    _ai_loaded = False


@app.on_event("startup")
async def startup():
    try:
        init_db()
    except Exception:
        # Database may be locked by import process — that's OK,
        # schema already exists if import is running.
        pass


def _safe_count(cursor, table: str) -> int:
    """Get row count for a table, returning 0 if it doesn't exist."""
    try:
        return cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except sqlite3.OperationalError:
        return 0


@app.get("/api/health")
async def health():
    """Health check — reports server status and basic DB availability."""
    status = {"status": "ok", "database": str(DB_PATH)}
    try:
        conn = get_connection(readonly=True)
        cursor = conn.cursor()
        fts_exists = cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='emails_fts'"
        ).fetchone() is not None

        status["fts_ready"] = fts_exists
        status["counts"] = {
            "emails": _safe_count(cursor, "emails"),
            "photos": _safe_count(cursor, "photos"),
            "albums": _safe_count(cursor, "albums"),
            "contacts": _safe_count(cursor, "contacts"),
            "calendar_events": _safe_count(cursor, "calendar_events"),
            "chat_conversations": _safe_count(cursor, "chat_conversations"),
            "chat_messages": _safe_count(cursor, "chat_messages"),
            "drive_files": _safe_count(cursor, "drive_files"),
            "notes": _safe_count(cursor, "notes"),
        }
        # Keep legacy fields for backward compatibility
        status["email_count"] = status["counts"]["emails"]
        status["photo_count"] = status["counts"]["photos"]
        status["album_count"] = status["counts"]["albums"]
        status["ai_enabled"] = _ai_loaded
        conn.close()
    except sqlite3.OperationalError:
        status["email_count"] = 0
        status["fts_ready"] = False
        status["counts"] = {}
        status["note"] = "Database tables may not exist yet (import in progress)"
    except Exception as exc:
        status["status"] = "degraded"
        status["error"] = str(exc)
    return status


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
