import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_connection
from config import ATTACHMENTS_DIR

router = APIRouter(prefix="/api", tags=["actions"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class DeleteRequest(BaseModel):
    item_type: str
    item_ids: List[int]
    permanent: bool = False


class RestoreRequest(BaseModel):
    item_type: str
    item_ids: List[int]


class StarRequest(BaseModel):
    item_ids: List[int]
    starred: bool


class MarkReadRequest(BaseModel):
    item_ids: List[int]
    read: bool


class LabelRequest(BaseModel):
    item_ids: List[int]
    add_labels: List[str] = []
    remove_labels: List[str] = []


class TagItemRequest(BaseModel):
    item_type: str
    item_ids: List[int]
    tag_id: int


class EmptyTrashRequest(BaseModel):
    item_type: str = "all"


class TagCreateRequest(BaseModel):
    name: str
    color: str = "#1a73e8"


class TagUpdateRequest(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_ITEM_TYPES = {"email", "photo", "calendar_event", "chat_message", "drive_file", "contact"}

TABLE_MAP = {
    "email": "emails",
    "photo": "photos",
    "calendar_event": "calendar_events",
    "chat_message": "chat_messages",
    "drive_file": "drive_files",
    "contact": "contacts",
}


def _validate_item_type(item_type: str) -> str:
    if item_type not in VALID_ITEM_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid item_type: {item_type}")
    return TABLE_MAP[item_type]


def _log_action(cursor, action: str, item_type: str, item_ids: List[int], detail: dict = None):
    now = datetime.utcnow().isoformat()
    for item_id in item_ids:
        cursor.execute(
            "INSERT INTO user_actions (action, item_type, item_id, detail, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (action, item_type, item_id, json.dumps(detail) if detail else None, now),
        )


# ---------------------------------------------------------------------------
# Delete / Restore
# ---------------------------------------------------------------------------

@router.post("/actions/delete")
async def soft_delete(req: DeleteRequest):
    table = _validate_item_type(req.item_type)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        now = datetime.utcnow().isoformat()

        if req.permanent:
            # Permanent delete: remove rows and files
            space_freed = 0
            files_removed = 0

            if req.item_type == "email":
                # Get attachment file paths first
                placeholders = ",".join("?" * len(req.item_ids))
                att_rows = cursor.execute(
                    f"SELECT file_path, size_bytes FROM attachments WHERE email_id IN ({placeholders})",
                    req.item_ids,
                ).fetchall()
                for att in att_rows:
                    if att["file_path"] and os.path.exists(att["file_path"]):
                        try:
                            os.remove(att["file_path"])
                            files_removed += 1
                        except OSError:
                            pass
                    space_freed += att["size_bytes"] or 0
                # Get email sizes
                sizes = cursor.execute(
                    f"SELECT COALESCE(SUM(raw_size_bytes), 0) FROM emails WHERE id IN ({placeholders})",
                    req.item_ids,
                ).fetchone()[0]
                space_freed += sizes
                # Delete attachments then emails
                cursor.execute(
                    f"DELETE FROM attachments WHERE email_id IN ({placeholders})",
                    req.item_ids,
                )

            elif req.item_type == "photo":
                placeholders = ",".join("?" * len(req.item_ids))
                photo_rows = cursor.execute(
                    f"SELECT file_path, thumbnail_path, size_bytes FROM photos WHERE id IN ({placeholders})",
                    req.item_ids,
                ).fetchall()
                for p in photo_rows:
                    for path_key in ["file_path", "thumbnail_path"]:
                        path = p[path_key]
                        if path and os.path.exists(path):
                            try:
                                os.remove(path)
                                files_removed += 1
                            except OSError:
                                pass
                    space_freed += p["size_bytes"] or 0

            placeholders = ",".join("?" * len(req.item_ids))
            cursor.execute(
                f"DELETE FROM {table} WHERE id IN ({placeholders})",
                req.item_ids,
            )
            # Clean up item_tags
            cursor.execute(
                f"DELETE FROM item_tags WHERE item_type = ? AND item_id IN ({placeholders})",
                [req.item_type] + req.item_ids,
            )
            _log_action(cursor, "permanent_delete", req.item_type, req.item_ids)
            conn.commit()
            return {"deleted": len(req.item_ids), "space_freed_bytes": space_freed, "files_removed": files_removed}
        else:
            # Soft delete
            placeholders = ",".join("?" * len(req.item_ids))
            cursor.execute(
                f"UPDATE {table} SET deleted_at = ? WHERE id IN ({placeholders}) AND deleted_at IS NULL",
                [now] + req.item_ids,
            )
            deleted = cursor.rowcount
            _log_action(cursor, "delete", req.item_type, req.item_ids)
            conn.commit()
            return {"deleted": deleted}
    finally:
        conn.close()


@router.post("/actions/restore")
async def restore(req: RestoreRequest):
    table = _validate_item_type(req.item_type)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(req.item_ids))
        cursor.execute(
            f"UPDATE {table} SET deleted_at = NULL WHERE id IN ({placeholders}) AND deleted_at IS NOT NULL",
            req.item_ids,
        )
        restored = cursor.rowcount
        _log_action(cursor, "restore", req.item_type, req.item_ids)
        conn.commit()
        return {"restored": restored}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Star / Mark Read
# ---------------------------------------------------------------------------

@router.post("/actions/star")
async def toggle_star(req: StarRequest):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(req.item_ids))
        cursor.execute(
            f"UPDATE emails SET is_starred = ? WHERE id IN ({placeholders}) AND deleted_at IS NULL",
            [1 if req.starred else 0] + req.item_ids,
        )
        updated = cursor.rowcount
        _log_action(cursor, "star" if req.starred else "unstar", "email", req.item_ids)
        conn.commit()
        return {"updated": updated}
    finally:
        conn.close()


@router.post("/actions/mark-read")
async def mark_read(req: MarkReadRequest):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(req.item_ids))
        cursor.execute(
            f"UPDATE emails SET is_read = ? WHERE id IN ({placeholders}) AND deleted_at IS NULL",
            [1 if req.read else 0] + req.item_ids,
        )
        updated = cursor.rowcount
        _log_action(cursor, "mark_read" if req.read else "mark_unread", "email", req.item_ids)
        conn.commit()
        return {"updated": updated}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Label management (Gmail labels on emails)
# ---------------------------------------------------------------------------

@router.post("/actions/label")
async def modify_labels(req: LabelRequest):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        updated = 0

        for email_id in req.item_ids:
            for label_name in req.add_labels:
                # Ensure label exists
                cursor.execute(
                    "INSERT OR IGNORE INTO labels (name, email_count) VALUES (?, 0)",
                    (label_name,),
                )
                label_row = cursor.execute(
                    "SELECT id FROM labels WHERE name = ?", (label_name,)
                ).fetchone()
                if label_row:
                    cursor.execute(
                        "INSERT OR IGNORE INTO email_labels (email_id, label_id) VALUES (?, ?)",
                        (email_id, label_row["id"]),
                    )
                    if cursor.rowcount > 0:
                        cursor.execute(
                            "UPDATE labels SET email_count = email_count + 1 WHERE id = ?",
                            (label_row["id"],),
                        )

            for label_name in req.remove_labels:
                label_row = cursor.execute(
                    "SELECT id FROM labels WHERE name = ?", (label_name,)
                ).fetchone()
                if label_row:
                    cursor.execute(
                        "DELETE FROM email_labels WHERE email_id = ? AND label_id = ?",
                        (email_id, label_row["id"]),
                    )
                    if cursor.rowcount > 0:
                        cursor.execute(
                            "UPDATE labels SET email_count = MAX(email_count - 1, 0) WHERE id = ?",
                            (label_row["id"],),
                        )
            updated += 1

        _log_action(
            cursor, "label", "email", req.item_ids,
            {"add": req.add_labels, "remove": req.remove_labels},
        )
        conn.commit()
        return {"updated": updated}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tag management (user-created tags on any item type)
# ---------------------------------------------------------------------------

@router.post("/actions/tag")
async def tag_items(req: TagItemRequest):
    table = _validate_item_type(req.item_type)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        tagged = 0
        for item_id in req.item_ids:
            try:
                cursor.execute(
                    "INSERT INTO item_tags (tag_id, item_type, item_id) VALUES (?, ?, ?)",
                    (req.tag_id, req.item_type, item_id),
                )
                tagged += 1
            except sqlite3.IntegrityError:
                pass  # Already tagged
        _log_action(cursor, "tag", req.item_type, req.item_ids, {"tag_id": req.tag_id})
        conn.commit()
        return {"tagged": tagged}
    finally:
        conn.close()


@router.post("/actions/untag")
async def untag_items(req: TagItemRequest):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(req.item_ids))
        cursor.execute(
            f"DELETE FROM item_tags WHERE tag_id = ? AND item_type = ? AND item_id IN ({placeholders})",
            [req.tag_id, req.item_type] + req.item_ids,
        )
        untagged = cursor.rowcount
        _log_action(cursor, "untag", req.item_type, req.item_ids, {"tag_id": req.tag_id})
        conn.commit()
        return {"untagged": untagged}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Trash view
# ---------------------------------------------------------------------------

@router.get("/actions/trash")
async def view_trash(
    item_type: str = "email",
    offset: int = 0,
    limit: int = 50,
):
    table = _validate_item_type(item_type)
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()
        total = cursor.execute(
            f"SELECT COUNT(*) FROM {table} WHERE deleted_at IS NOT NULL"
        ).fetchone()[0]

        if item_type == "email":
            rows = cursor.execute(
                f"SELECT id, message_id, thread_id, from_address, from_name, subject, date, "
                f"body_text, labels, has_attachments, is_read, is_starred, raw_size_bytes, deleted_at "
                f"FROM {table} WHERE deleted_at IS NOT NULL "
                f"ORDER BY deleted_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            items = []
            for r in rows:
                labels = []
                if r["labels"]:
                    try:
                        labels = json.loads(r["labels"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                items.append({
                    "id": r["id"],
                    "from_name": r["from_name"],
                    "from_address": r["from_address"],
                    "subject": r["subject"],
                    "date": r["date"],
                    "snippet": (r["body_text"] or "")[:200].replace("\n", " ").strip(),
                    "labels": labels,
                    "has_attachments": bool(r["has_attachments"]),
                    "is_read": bool(r["is_read"]),
                    "is_starred": bool(r["is_starred"]),
                    "raw_size_bytes": r["raw_size_bytes"] or 0,
                    "deleted_at": r["deleted_at"],
                })
        else:
            rows = cursor.execute(
                f"SELECT * FROM {table} WHERE deleted_at IS NOT NULL "
                f"ORDER BY deleted_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            items = [dict(r) for r in rows]

        total_size = cursor.execute(
            f"SELECT COALESCE(SUM({'raw_size_bytes' if item_type == 'email' else 'size_bytes'}), 0) "
            f"FROM {table} WHERE deleted_at IS NOT NULL"
        ).fetchone()[0]

        return {"items": items, "total": total, "total_size_bytes": total_size}
    finally:
        conn.close()


@router.post("/actions/empty-trash")
async def empty_trash(req: EmptyTrashRequest):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        total_deleted = 0
        space_freed = 0

        types_to_empty = list(VALID_ITEM_TYPES) if req.item_type == "all" else [req.item_type]

        for item_type in types_to_empty:
            table = TABLE_MAP.get(item_type)
            if not table:
                continue

            # Count items in trash
            count = cursor.execute(
                f"SELECT COUNT(*) FROM {table} WHERE deleted_at IS NOT NULL"
            ).fetchone()[0]
            if count == 0:
                continue

            size_col = "raw_size_bytes" if item_type == "email" else "size_bytes"
            try:
                size = cursor.execute(
                    f"SELECT COALESCE(SUM({size_col}), 0) FROM {table} WHERE deleted_at IS NOT NULL"
                ).fetchone()[0]
            except sqlite3.OperationalError:
                size = 0

            # Handle file cleanup for emails and photos
            if item_type == "email":
                att_rows = cursor.execute(
                    "SELECT a.file_path FROM attachments a "
                    "JOIN emails e ON a.email_id = e.id WHERE e.deleted_at IS NOT NULL"
                ).fetchall()
                for att in att_rows:
                    if att["file_path"] and os.path.exists(att["file_path"]):
                        try:
                            os.remove(att["file_path"])
                        except OSError:
                            pass
                cursor.execute(
                    "DELETE FROM attachments WHERE email_id IN "
                    "(SELECT id FROM emails WHERE deleted_at IS NOT NULL)"
                )

            elif item_type == "photo":
                photo_rows = cursor.execute(
                    f"SELECT file_path, thumbnail_path FROM {table} WHERE deleted_at IS NOT NULL"
                ).fetchall()
                for p in photo_rows:
                    for key in ["file_path", "thumbnail_path"]:
                        path = p[key]
                        if path and os.path.exists(path):
                            try:
                                os.remove(path)
                            except OSError:
                                pass

            # Delete item_tags
            cursor.execute(
                f"DELETE FROM item_tags WHERE item_type = ? AND item_id IN "
                f"(SELECT id FROM {table} WHERE deleted_at IS NOT NULL)",
                (item_type,),
            )

            cursor.execute(f"DELETE FROM {table} WHERE deleted_at IS NOT NULL")
            total_deleted += count
            space_freed += size

        conn.commit()
        return {"permanently_deleted": total_deleted, "space_freed_bytes": space_freed}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Space analysis
# ---------------------------------------------------------------------------

@router.get("/actions/space-analysis")
async def space_analysis():
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()
        by_type = {}

        # Email space
        try:
            r = cursor.execute(
                "SELECT COUNT(*) as count, COALESCE(SUM(raw_size_bytes), 0) as bytes "
                "FROM emails WHERE deleted_at IS NULL"
            ).fetchone()
            by_type["email"] = {"count": r["count"], "bytes": r["bytes"]}
        except sqlite3.OperationalError:
            by_type["email"] = {"count": 0, "bytes": 0}

        # Photo space
        try:
            r = cursor.execute(
                "SELECT COUNT(*) as count, COALESCE(SUM(size_bytes), 0) as bytes "
                "FROM photos WHERE deleted_at IS NULL"
            ).fetchone()
            by_type["photos"] = {"count": r["count"], "bytes": r["bytes"]}
        except sqlite3.OperationalError:
            by_type["photos"] = {"count": 0, "bytes": 0}

        # Attachment space
        try:
            r = cursor.execute(
                "SELECT COUNT(*) as count, COALESCE(SUM(a.size_bytes), 0) as bytes "
                "FROM attachments a JOIN emails e ON a.email_id = e.id WHERE e.deleted_at IS NULL"
            ).fetchone()
            by_type["attachments"] = {"count": r["count"], "bytes": r["bytes"]}
        except sqlite3.OperationalError:
            by_type["attachments"] = {"count": 0, "bytes": 0}

        # Drive space
        try:
            r = cursor.execute(
                "SELECT COUNT(*) as count, COALESCE(SUM(size_bytes), 0) as bytes "
                "FROM drive_files WHERE deleted_at IS NULL"
            ).fetchone()
            by_type["drive"] = {"count": r["count"], "bytes": r["bytes"]}
        except sqlite3.OperationalError:
            by_type["drive"] = {"count": 0, "bytes": 0}

        total_bytes = sum(t["bytes"] for t in by_type.values())

        # Top space consumers (emails with large attachments)
        try:
            top_rows = cursor.execute(
                "SELECT e.id, e.subject, e.from_name, e.date, e.raw_size_bytes, "
                "COUNT(a.id) as attachment_count "
                "FROM emails e LEFT JOIN attachments a ON a.email_id = e.id "
                "WHERE e.deleted_at IS NULL "
                "GROUP BY e.id "
                "ORDER BY e.raw_size_bytes DESC LIMIT 20"
            ).fetchall()
            top_consumers = [
                {
                    "type": "email",
                    "id": r["id"],
                    "subject": r["subject"],
                    "from_name": r["from_name"],
                    "date": r["date"],
                    "bytes": r["raw_size_bytes"] or 0,
                    "attachments": r["attachment_count"],
                }
                for r in top_rows
            ]
        except sqlite3.OperationalError:
            top_consumers = []

        # Potential savings
        potential_savings = {}

        # Spam
        try:
            r = cursor.execute(
                "SELECT COUNT(*) as count, COALESCE(SUM(e.raw_size_bytes), 0) as bytes "
                "FROM emails e "
                "JOIN email_labels el ON el.email_id = e.id "
                "JOIN labels l ON l.id = el.label_id "
                "WHERE l.name = 'Spam' AND e.deleted_at IS NULL"
            ).fetchone()
            potential_savings["spam"] = {"count": r["count"], "bytes": r["bytes"]}
        except sqlite3.OperationalError:
            potential_savings["spam"] = {"count": 0, "bytes": 0}

        # Newsletters (from addresses with >20 emails and unsubscribe-like patterns)
        try:
            r = cursor.execute(
                "SELECT COUNT(*) as count, COALESCE(SUM(raw_size_bytes), 0) as bytes "
                "FROM emails WHERE deleted_at IS NULL AND ("
                "from_address LIKE '%noreply%' OR from_address LIKE '%no-reply%' "
                "OR from_address LIKE '%newsletter%' OR from_address LIKE '%marketing%' "
                "OR from_address LIKE '%notifications%' OR from_address LIKE '%updates@%' "
                "OR body_text LIKE '%unsubscribe%')"
            ).fetchone()
            potential_savings["newsletters"] = {"count": r["count"], "bytes": r["bytes"]}
        except sqlite3.OperationalError:
            potential_savings["newsletters"] = {"count": 0, "bytes": 0}

        # Large emails (>5MB)
        try:
            r = cursor.execute(
                "SELECT COUNT(*) as count, COALESCE(SUM(raw_size_bytes), 0) as bytes "
                "FROM emails WHERE raw_size_bytes > 5242880 AND deleted_at IS NULL"
            ).fetchone()
            potential_savings["large_emails"] = {"count": r["count"], "bytes": r["bytes"]}
        except sqlite3.OperationalError:
            potential_savings["large_emails"] = {"count": 0, "bytes": 0}

        # Promotions
        try:
            r = cursor.execute(
                "SELECT COUNT(*) as count, COALESCE(SUM(e.raw_size_bytes), 0) as bytes "
                "FROM emails e "
                "JOIN email_labels el ON el.email_id = e.id "
                "JOIN labels l ON l.id = el.label_id "
                "WHERE l.name = 'Category Promotions' AND e.deleted_at IS NULL"
            ).fetchone()
            potential_savings["promotions"] = {"count": r["count"], "bytes": r["bytes"]}
        except sqlite3.OperationalError:
            potential_savings["promotions"] = {"count": 0, "bytes": 0}

        return {
            "total_bytes": total_bytes,
            "by_type": by_type,
            "top_space_consumers": top_consumers,
            "potential_savings": potential_savings,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tags CRUD
# ---------------------------------------------------------------------------

@router.get("/tags")
async def list_tags():
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT t.*, "
            "(SELECT COUNT(*) FROM item_tags it WHERE it.tag_id = t.id) as item_count "
            "FROM user_tags t ORDER BY t.name"
        ).fetchall()
        return {
            "tags": [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "color": r["color"],
                    "item_count": r["item_count"],
                }
                for r in rows
            ]
        }
    finally:
        conn.close()


@router.post("/tags")
async def create_tag(req: TagCreateRequest):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO user_tags (name, color) VALUES (?, ?)",
            (req.name, req.color),
        )
        tag_id = cursor.lastrowid
        conn.commit()
        return {"id": tag_id, "name": req.name, "color": req.color}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail=f"Tag '{req.name}' already exists")
    finally:
        conn.close()


@router.put("/tags/{tag_id}")
async def update_tag(tag_id: int, req: TagUpdateRequest):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        existing = cursor.execute("SELECT * FROM user_tags WHERE id = ?", (tag_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Tag not found")

        if req.name is not None:
            cursor.execute("UPDATE user_tags SET name = ? WHERE id = ?", (req.name, tag_id))
        if req.color is not None:
            cursor.execute("UPDATE user_tags SET color = ? WHERE id = ?", (req.color, tag_id))
        conn.commit()

        updated = cursor.execute("SELECT * FROM user_tags WHERE id = ?", (tag_id,)).fetchone()
        return {"id": updated["id"], "name": updated["name"], "color": updated["color"]}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail=f"Tag name already exists")
    finally:
        conn.close()


@router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM item_tags WHERE tag_id = ?", (tag_id,))
        cursor.execute("DELETE FROM user_tags WHERE id = ?", (tag_id,))
        conn.commit()
        return {"deleted": True}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Smart filters
# ---------------------------------------------------------------------------

@router.get("/smart-filters")
async def smart_filters():
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()
        filters = []

        def _safe(sql, params=()):
            try:
                return cursor.execute(sql, params).fetchone()
            except sqlite3.OperationalError:
                return None

        # Newsletters
        r = _safe(
            "SELECT COUNT(*) as count, COALESCE(SUM(raw_size_bytes), 0) as bytes "
            "FROM emails WHERE deleted_at IS NULL AND ("
            "from_address LIKE '%noreply%' OR from_address LIKE '%no-reply%' "
            "OR from_address LIKE '%newsletter%' OR from_address LIKE '%marketing%' "
            "OR body_text LIKE '%unsubscribe%')"
        )
        if r and r["count"] > 0:
            filters.append({
                "name": "Newsletters",
                "query": "unsubscribe:true",
                "count": r["count"],
                "size_bytes": r["bytes"],
            })

        # Spam
        r = _safe(
            "SELECT COUNT(*) as count, COALESCE(SUM(e.raw_size_bytes), 0) as bytes "
            "FROM emails e JOIN email_labels el ON el.email_id = e.id "
            "JOIN labels l ON l.id = el.label_id "
            "WHERE l.name = 'Spam' AND e.deleted_at IS NULL"
        )
        if r and r["count"] > 0:
            filters.append({
                "name": "Spam",
                "query": "label:Spam",
                "count": r["count"],
                "size_bytes": r["bytes"],
            })

        # Promotions
        r = _safe(
            "SELECT COUNT(*) as count, COALESCE(SUM(e.raw_size_bytes), 0) as bytes "
            "FROM emails e JOIN email_labels el ON el.email_id = e.id "
            "JOIN labels l ON l.id = el.label_id "
            "WHERE l.name = 'Category Promotions' AND e.deleted_at IS NULL"
        )
        if r and r["count"] > 0:
            filters.append({
                "name": "Promotions",
                "query": 'label:"Category Promotions"',
                "count": r["count"],
                "size_bytes": r["bytes"],
            })

        # Large emails (>5MB)
        r = _safe(
            "SELECT COUNT(*) as count, COALESCE(SUM(raw_size_bytes), 0) as bytes "
            "FROM emails WHERE raw_size_bytes > 5242880 AND deleted_at IS NULL"
        )
        if r and r["count"] > 0:
            filters.append({
                "name": "Large emails (>5MB)",
                "query": "larger:5mb",
                "count": r["count"],
                "size_bytes": r["bytes"],
            })

        # Old & unread (>3 years)
        three_years_ago = (datetime.utcnow() - timedelta(days=3 * 365)).isoformat()
        r = _safe(
            "SELECT COUNT(*) as count, COALESCE(SUM(raw_size_bytes), 0) as bytes "
            "FROM emails WHERE is_read = 0 AND date < ? AND deleted_at IS NULL",
            (three_years_ago,),
        )
        if r and r["count"] > 0:
            filters.append({
                "name": "Old & unread (3+ years)",
                "query": "is:unread older_than:3y",
                "count": r["count"],
                "size_bytes": r["bytes"],
            })

        # Social notifications
        r = _safe(
            "SELECT COUNT(*) as count, COALESCE(SUM(e.raw_size_bytes), 0) as bytes "
            "FROM emails e JOIN email_labels el ON el.email_id = e.id "
            "JOIN labels l ON l.id = el.label_id "
            "WHERE l.name = 'Category Social' AND e.deleted_at IS NULL"
        )
        if r and r["count"] > 0:
            filters.append({
                "name": "Social notifications",
                "query": 'label:"Category Social"',
                "count": r["count"],
                "size_bytes": r["bytes"],
            })

        # No-reply senders
        r = _safe(
            "SELECT COUNT(*) as count, COALESCE(SUM(raw_size_bytes), 0) as bytes "
            "FROM emails WHERE deleted_at IS NULL AND "
            "(from_address LIKE '%noreply%' OR from_address LIKE '%no-reply%')"
        )
        if r and r["count"] > 0:
            filters.append({
                "name": "No-reply senders",
                "query": "from:noreply OR from:no-reply",
                "count": r["count"],
                "size_bytes": r["bytes"],
            })

        return {"filters": filters}
    finally:
        conn.close()
