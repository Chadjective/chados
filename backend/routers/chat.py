import json
import sqlite3
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from database import get_connection

router = APIRouter(prefix="/api/chat", tags=["chat"])


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


def _conversation_summary(row, last_message=None) -> dict:
    """Build a conversation summary dict."""
    result = {
        "id": row["id"],
        "name": row["name"],
        "participants": _parse_json_col(row["participants"]),
        "type": row["type"],
    }
    if last_message:
        result["last_message"] = {
            "sender_name": last_message["sender_name"],
            "content": (last_message["content"] or "")[:200],
            "timestamp": last_message["timestamp"],
        }
    return result


def _message_dict(row) -> dict:
    """Build a message dict from a sqlite3.Row."""
    return {
        "id": row["id"],
        "conversation_id": row["conversation_id"],
        "sender_name": row["sender_name"],
        "sender_email": row["sender_email"],
        "content": row["content"],
        "timestamp": row["timestamp"],
        "message_type": row["message_type"],
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/search")
async def search_chat(
    q: str = Query("", description="Search query"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Search message content across all conversations."""
    if not q.strip():
        raise HTTPException(status_code=400, detail="Search query 'q' is required")

    conn = get_connection(readonly=True)
    try:
        c = conn.cursor()
        like = f"%{q}%"

        count = c.execute(
            "SELECT COUNT(*) FROM chat_messages WHERE content LIKE ?",
            (like,),
        ).fetchone()[0]

        rows = c.execute(
            "SELECT m.*, cc.name as conversation_name "
            "FROM chat_messages m "
            "JOIN chat_conversations cc ON cc.id = m.conversation_id "
            "WHERE m.content LIKE ? "
            "ORDER BY m.timestamp_unix DESC LIMIT ? OFFSET ?",
            (like, limit, offset),
        ).fetchall()

        messages = []
        for r in rows:
            msg = _message_dict(r)
            msg["conversation_name"] = r["conversation_name"]
            messages.append(msg)

        return {"messages": messages, "total": count}
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """Get a conversation with its messages, paginated."""
    conn = get_connection(readonly=True)
    try:
        c = conn.cursor()

        conv = c.execute(
            "SELECT * FROM chat_conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        msg_count = c.execute(
            "SELECT COUNT(*) FROM chat_messages WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()[0]

        messages = c.execute(
            "SELECT * FROM chat_messages WHERE conversation_id = ? "
            "ORDER BY timestamp_unix ASC LIMIT ? OFFSET ?",
            (conversation_id, limit, offset),
        ).fetchall()

        return {
            "conversation": {
                "id": conv["id"],
                "name": conv["name"],
                "participants": _parse_json_col(conv["participants"]),
                "type": conv["type"],
                "message_count": msg_count,
            },
            "messages": [_message_dict(m) for m in messages],
            "total": msg_count,
        }
    except HTTPException:
        raise
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()


@router.get("/conversations")
async def list_conversations(
    type_filter: Optional[str] = Query(None, alias="type", description="Filter by type: DM, Space, Group"),
    q: Optional[str] = Query(None, description="Search conversation names"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """List conversations with last message preview, sorted by most recent activity."""
    conn = get_connection(readonly=True)
    try:
        c = conn.cursor()
        conditions = []  # type: List[str]
        params = []  # type: list

        if type_filter:
            conditions.append("cc.type = ?")
            params.append(type_filter)

        if q:
            like = f"%{q}%"
            conditions.append("cc.name LIKE ?")
            params.append(like)

        where = " AND ".join(conditions) if conditions else "1=1"

        count = c.execute(
            f"SELECT COUNT(*) FROM chat_conversations cc WHERE {where}",
            params,
        ).fetchone()[0]

        # Get conversations ordered by their most recent message, with message count
        rows = c.execute(
            f"SELECT cc.*, "
            f"(SELECT MAX(timestamp_unix) FROM chat_messages WHERE conversation_id = cc.id) as last_activity, "
            f"(SELECT COUNT(*) FROM chat_messages WHERE conversation_id = cc.id) as msg_count "
            f"FROM chat_conversations cc "
            f"WHERE {where} "
            f"ORDER BY last_activity DESC NULLS LAST "
            f"LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

        conversations = []
        for row in rows:
            # Get last message for preview
            last_msg = c.execute(
                "SELECT sender_name, content, timestamp FROM chat_messages "
                "WHERE conversation_id = ? ORDER BY timestamp_unix DESC LIMIT 1",
                (row["id"],),
            ).fetchone()
            summary = _conversation_summary(row, last_msg)
            summary["message_count"] = row["msg_count"]
            conversations.append(summary)

        return {"conversations": conversations, "total": count}
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()
