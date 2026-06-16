import json
import re
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from database import get_connection
from models import EmailSummary, EmailDetail, SearchResult, ThreadDetail, AttachmentInfo

router = APIRouter(prefix="/api/emails", tags=["emails"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fts_table_exists(cursor) -> bool:
    """Check if the FTS table exists (import may still be running)."""
    try:
        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='emails_fts'"
        )
        return cursor.fetchone() is not None
    except Exception:
        return False


def _snippet(body_text: Optional[str], length: int = 200) -> str:
    if not body_text:
        return ""
    return body_text[:length].replace("\n", " ").strip()


def _parse_json_col(val) -> list:
    if not val:
        return []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []


def _build_email_summary(row) -> dict:
    """Build an EmailSummary dict from a sqlite3.Row."""
    return EmailSummary(
        id=row["id"],
        message_id=row["message_id"],
        thread_id=row["thread_id"],
        from_address=row["from_address"],
        from_name=row["from_name"],
        subject=row["subject"],
        date=row["date"],
        snippet=_snippet(row["body_text"]),
        labels=_parse_json_col(row["labels"]),
        has_attachments=bool(row["has_attachments"]),
        is_read=bool(row["is_read"]),
        is_starred=bool(row["is_starred"]),
    )


def parse_search_query(q: str) -> dict:
    """Parse Gmail-style search operators from a query string.

    Supports: from:, to:, subject:, label:, has:attachment,
              before:, after:, is:starred, is:unread, is:read,
              larger:, smaller:, older_than:, newer_than:, unsubscribe:
    Returns a dict with extracted operators and remaining free text.
    """
    filters: dict = {}
    remaining = q

    # Patterns that can appear multiple times — collect all matches
    multi_patterns = {
        "from": r'from:("[^"]+"|[\S]+)',
        "to": r'to:("[^"]+"|[\S]+)',
        "subject": r'subject:("[^"]+"|[\S]+)',
        "label": r'label:("[^"]+"|[\S]+)',
        "before": r'before:(\S+)',
        "after": r'after:(\S+)',
        "has": r'has:(\S+)',
        "is": r'is:(\S+)',
        "larger": r'larger:(\S+)',
        "smaller": r'smaller:(\S+)',
        "older_than": r'older_than:(\S+)',
        "newer_than": r'newer_than:(\S+)',
        "unsubscribe": r'unsubscribe:(\S+)',
    }

    for key, pattern in multi_patterns.items():
        while True:
            match = re.search(pattern, remaining, re.IGNORECASE)
            if not match:
                break
            value = match.group(1).strip('"')
            if key in filters:
                if isinstance(filters[key], list):
                    filters[key].append(value)
                else:
                    filters[key] = [filters[key], value]
            else:
                filters[key] = value
            remaining = remaining[: match.start()] + remaining[match.end() :]

    filters["text"] = remaining.strip()
    return filters


def _apply_filters(filters: dict, conditions: list, params: list) -> None:
    """Append SQL conditions and params based on parsed search filters."""
    if filters.get("from"):
        val = filters["from"]
        if isinstance(val, list):
            val = val[0]
        conditions.append("(e.from_address LIKE ? OR e.from_name LIKE ?)")
        params.extend([f"%{val}%", f"%{val}%"])

    if filters.get("to"):
        val = filters["to"]
        if isinstance(val, list):
            val = val[0]
        conditions.append("e.to_addresses LIKE ?")
        params.append(f"%{val}%")

    if filters.get("subject"):
        val = filters["subject"]
        if isinstance(val, list):
            val = val[0]
        conditions.append("e.subject LIKE ?")
        params.append(f"%{val}%")

    if filters.get("label"):
        val = filters["label"]
        if isinstance(val, list):
            val = val[0]
        conditions.append(
            "EXISTS (SELECT 1 FROM email_labels el "
            "JOIN labels l ON el.label_id = l.id "
            "WHERE el.email_id = e.id AND l.name = ?)"
        )
        params.append(val)

    has_val = filters.get("has")
    if has_val:
        if isinstance(has_val, list):
            has_val = has_val
        else:
            has_val = [has_val]
        for h in has_val:
            if h == "attachment":
                conditions.append("e.has_attachments = 1")

    is_val = filters.get("is")
    if is_val:
        if isinstance(is_val, str):
            is_val = [is_val]
        for v in is_val:
            if v == "starred":
                conditions.append("e.is_starred = 1")
            elif v == "unread":
                conditions.append("e.is_read = 0")
            elif v == "read":
                conditions.append("e.is_read = 1")

    if filters.get("before"):
        val = filters["before"]
        if isinstance(val, list):
            val = val[0]
        conditions.append("e.date < ?")
        params.append(val)

    if filters.get("after"):
        val = filters["after"]
        if isinstance(val, list):
            val = val[0]
        conditions.append("e.date > ?")
        params.append(val)

    # --- Advanced search operators ---

    def _parse_size(s: str) -> int:
        """Parse size string like '5mb', '100kb', '1gb' to bytes."""
        s = s.lower().strip()
        multipliers = {"b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3}
        for suffix, mult in sorted(multipliers.items(), key=lambda x: -len(x[0])):
            if s.endswith(suffix):
                return int(float(s[:-len(suffix)]) * mult)
        return int(s)

    def _parse_age(s: str) -> str:
        """Parse age string like '2y', '6m', '30d' to ISO date."""
        s = s.lower().strip()
        now = datetime.utcnow()
        if s.endswith("y"):
            dt = now - timedelta(days=int(s[:-1]) * 365)
        elif s.endswith("m"):
            dt = now - timedelta(days=int(s[:-1]) * 30)
        elif s.endswith("d"):
            dt = now - timedelta(days=int(s[:-1]))
        else:
            dt = now - timedelta(days=int(s))
        return dt.isoformat()

    if filters.get("larger"):
        val = filters["larger"]
        if isinstance(val, list):
            val = val[0]
        conditions.append("e.raw_size_bytes > ?")
        params.append(_parse_size(val))

    if filters.get("smaller"):
        val = filters["smaller"]
        if isinstance(val, list):
            val = val[0]
        conditions.append("e.raw_size_bytes < ?")
        params.append(_parse_size(val))

    if filters.get("older_than"):
        val = filters["older_than"]
        if isinstance(val, list):
            val = val[0]
        conditions.append("e.date < ?")
        params.append(_parse_age(val))

    if filters.get("newer_than"):
        val = filters["newer_than"]
        if isinstance(val, list):
            val = val[0]
        conditions.append("e.date > ?")
        params.append(_parse_age(val))

    if filters.get("unsubscribe"):
        val = filters["unsubscribe"]
        if isinstance(val, list):
            val = val[0]
        if val.lower() == "true":
            conditions.append("(e.body_text LIKE '%unsubscribe%' OR e.body_html LIKE '%unsubscribe%')")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/stats")
async def email_stats():
    """Basic statistics about the email archive."""
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()

        total = cursor.execute("SELECT COUNT(*) FROM emails WHERE deleted_at IS NULL").fetchone()[0]

        date_range = cursor.execute(
            "SELECT MIN(date) AS earliest, MAX(date) AS latest FROM emails WHERE deleted_at IS NULL"
        ).fetchone()

        total_attachments = cursor.execute(
            "SELECT COUNT(*) FROM attachments"
        ).fetchone()[0]

        starred = cursor.execute(
            "SELECT COUNT(*) FROM emails WHERE is_starred = 1 AND deleted_at IS NULL"
        ).fetchone()[0]

        unread = cursor.execute(
            "SELECT COUNT(*) FROM emails WHERE is_read = 0 AND deleted_at IS NULL"
        ).fetchone()[0]

        return {
            "total_emails": total,
            "earliest_date": date_range["earliest"] if date_range else None,
            "latest_date": date_range["latest"] if date_range else None,
            "total_attachments": total_attachments,
            "starred": starred,
            "unread": unread,
        }
    except sqlite3.OperationalError as exc:
        # Tables may not exist yet during import
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()


@router.get("/search")
async def search_emails(
    q: str = Query("", description="Search query with Gmail-style operators"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
    count_only: bool = Query(False, description="Return only count and total size"),
):
    """Full-text search with Gmail-like operator parsing.

    Supports operators: from:, to:, subject:, label:, has:attachment,
    before:YYYY-MM-DD, after:YYYY-MM-DD, is:starred, is:unread, is:read.
    Free text is matched via FTS5 (if available) or LIKE fallback.
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Search query 'q' is required")

    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()
        filters = parse_search_query(q)

        conditions: List[str] = ["e.deleted_at IS NULL"]
        params: List = []
        _apply_filters(filters, conditions, params)

        free_text = filters.get("text", "").strip()
        has_fts = _fts_table_exists(cursor)

        order = "e.date_unix DESC"

        if free_text and has_fts:
            # Sanitize free text for FTS5: quote each word so special chars
            # (dots, @, hyphens) don't cause syntax errors.
            fts_terms = []
            for word in free_text.split():
                safe = word.replace('"', '""')
                fts_terms.append(f'"{safe}"')
            fts_query = " ".join(fts_terms)

            like_pat = f"%{free_text}%"

            # Use UNION to combine FTS results with LIKE matches on address columns.
            # FTS tokenizer splits emails on @ and . so direct address search needs LIKE.
            # Operator filters (from:, to:, etc.) are applied on the outer query to avoid
            # alias mismatches inside the UNION subqueries.
            id_union = (
                "SELECT e_inner.id FROM emails e_inner "
                "INNER JOIN emails_fts ON emails_fts.rowid = e_inner.id "
                "WHERE emails_fts MATCH ? AND e_inner.deleted_at IS NULL "
                "UNION "
                "SELECT e_like.id FROM emails e_like "
                "WHERE e_like.deleted_at IS NULL AND "
                "(e_like.from_address LIKE ? OR e_like.to_addresses LIKE ? "
                "OR e_like.cc_addresses LIKE ?)"
            )

            # Operator filters applied on the outer query (uses alias 'e')
            outer_conditions = ["e.id IN ({})".format(id_union)] + conditions
            outer_where = " AND ".join(outer_conditions)

            count_sql = f"SELECT COUNT(*) FROM emails e WHERE {outer_where}"
            query_sql = (
                f"SELECT e.* FROM emails e WHERE {outer_where} "
                f"ORDER BY {order} LIMIT ? OFFSET ?"
            )
            # params: fts_query + 3 like_pats (for the UNION) + operator filter params
            union_params = [fts_query, like_pat, like_pat, like_pat]
            count_params = union_params + params
            query_params = union_params + params + [limit, offset]
        elif free_text:
            # No FTS available — full LIKE fallback
            like_pat = f"%{free_text}%"
            conditions.append(
                "(e.subject LIKE ? OR e.from_name LIKE ? OR e.from_address LIKE ? "
                "OR e.to_addresses LIKE ? OR e.cc_addresses LIKE ? OR e.body_text LIKE ?)"
            )
            params.extend([like_pat, like_pat, like_pat, like_pat, like_pat, like_pat])
            where = " AND ".join(conditions)
            count_sql = f"SELECT COUNT(*) FROM emails e WHERE {where}"
            query_sql = (
                f"SELECT e.* FROM emails e WHERE {where} "
                f"ORDER BY {order} LIMIT ? OFFSET ?"
            )
            count_params = params
            query_params = params + [limit, offset]
        else:
            # Only operator filters, no free text
            where = " AND ".join(conditions) if conditions else "1=1"
            count_sql = f"SELECT COUNT(*) FROM emails e WHERE {where}"
            query_sql = (
                f"SELECT e.* FROM emails e WHERE {where} "
                f"ORDER BY {order} LIMIT ? OFFSET ?"
            )
            count_params = params
            query_params = params + [limit, offset]

        total = cursor.execute(count_sql, count_params).fetchone()[0]

        if count_only:
            # Also compute total size for "preview before delete"
            size_sql = count_sql.replace("SELECT COUNT(*)", "SELECT COALESCE(SUM(e.raw_size_bytes), 0)")
            total_size = cursor.execute(size_sql, count_params).fetchone()[0]
            return {"total": total, "total_size_bytes": total_size}

        rows = cursor.execute(query_sql, query_params).fetchall()
        emails = [_build_email_summary(row) for row in rows]

        return SearchResult(
            emails=emails,
            total=total,
            page=(offset // limit) + 1,
            page_size=limit,
        )
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Search error: {exc}")
    finally:
        conn.close()


@router.get("/{email_id}/thread", response_model=ThreadDetail)
async def get_email_thread(email_id: int):
    """Get all emails in the same thread as the given email, ordered by date."""
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()

        # First get the thread_id for this email
        row = cursor.execute(
            "SELECT thread_id FROM emails WHERE id = ? AND deleted_at IS NULL", (email_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Email not found")

        thread_id = row["thread_id"]
        if not thread_id:
            # No thread — just return the single email
            email_row = cursor.execute(
                "SELECT * FROM emails WHERE id = ?", (email_id,)
            ).fetchone()
            attachments = cursor.execute(
                "SELECT id, email_id, filename, content_type, size_bytes "
                "FROM attachments WHERE email_id = ?",
                (email_id,),
            ).fetchall()
            att_list = [
                dict(
                    id=a["id"], email_id=a["email_id"], filename=a["filename"],
                    content_type=a["content_type"], size_bytes=a["size_bytes"],
                )
                for a in attachments
            ]
            detail = EmailDetail.from_row(email_row, att_list)
            return ThreadDetail(
                thread_id=str(email_id),
                subject=detail.subject,
                messages=[detail],
                message_count=1,
            )

        rows = cursor.execute(
            "SELECT * FROM emails WHERE thread_id = ? AND deleted_at IS NULL ORDER BY date_unix ASC",
            (thread_id,),
        ).fetchall()

        messages = []
        for r in rows:
            attachments = cursor.execute(
                "SELECT id, email_id, filename, content_type, size_bytes "
                "FROM attachments WHERE email_id = ?",
                (r["id"],),
            ).fetchall()
            att_list = [
                dict(
                    id=a["id"], email_id=a["email_id"], filename=a["filename"],
                    content_type=a["content_type"], size_bytes=a["size_bytes"],
                )
                for a in attachments
            ]
            messages.append(EmailDetail.from_row(r, att_list))

        subject = messages[0].subject if messages else None

        return ThreadDetail(
            thread_id=thread_id,
            subject=subject,
            messages=messages,
            message_count=len(messages),
        )
    except HTTPException:
        raise
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()


@router.get("/{email_id}", response_model=EmailDetail)
async def get_email(email_id: int):
    """Full email detail including body, attachments, and thread info."""
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()

        row = cursor.execute(
            "SELECT * FROM emails WHERE id = ? AND deleted_at IS NULL", (email_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Email not found")

        attachments = cursor.execute(
            "SELECT id, email_id, filename, content_type, size_bytes "
            "FROM attachments WHERE email_id = ?",
            (email_id,),
        ).fetchall()

        att_list = [
            dict(
                id=a["id"],
                email_id=a["email_id"],
                filename=a["filename"],
                content_type=a["content_type"],
                size_bytes=a["size_bytes"],
            )
            for a in attachments
        ]

        return EmailDetail.from_row(row, att_list)
    except HTTPException:
        raise
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()


@router.get("", response_model=SearchResult)
async def list_emails(
    label: str = Query("", description="Filter by label name"),
    has_attachment: bool = Query(False, alias="has:attachment", description="Filter emails with attachments"),
    is_starred: bool = Query(False, alias="is:starred", description="Filter starred emails"),
    is_read: Optional[bool] = Query(None, alias="is:read", description="Filter by read status"),
    date_from: str = Query("", alias="after", description="Emails after this date (ISO or YYYY-MM-DD)"),
    date_to: str = Query("", alias="before", description="Emails before this date (ISO or YYYY-MM-DD)"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
    sort: str = Query("date_desc", description="Sort order: date_desc or date_asc"),
):
    """Paginated email list with optional filters."""
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()

        conditions: List[str] = ["e.deleted_at IS NULL"]
        params: List = []

        if label:
            conditions.append(
                "EXISTS (SELECT 1 FROM email_labels el "
                "JOIN labels l ON el.label_id = l.id "
                "WHERE el.email_id = e.id AND l.name = ?)"
            )
            params.append(label)

        if has_attachment:
            conditions.append("e.has_attachments = 1")

        if is_starred:
            conditions.append("e.is_starred = 1")

        if is_read is not None:
            conditions.append("e.is_read = ?")
            params.append(1 if is_read else 0)

        if date_from:
            conditions.append("e.date >= ?")
            params.append(date_from)

        if date_to:
            conditions.append("e.date <= ?")
            params.append(date_to)

        where = " AND ".join(conditions) if conditions else "1=1"
        order = "e.date_unix DESC" if sort == "date_desc" else "e.date_unix ASC"

        count_sql = f"SELECT COUNT(*) FROM emails e WHERE {where}"
        query_sql = (
            f"SELECT e.* FROM emails e WHERE {where} "
            f"ORDER BY {order} LIMIT ? OFFSET ?"
        )

        total = cursor.execute(count_sql, params).fetchone()[0]
        rows = cursor.execute(query_sql, params + [limit, offset]).fetchall()
        emails = [_build_email_summary(row) for row in rows]

        return SearchResult(
            emails=emails,
            total=total,
            page=(offset // limit) + 1,
            page_size=limit,
        )
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()
