"""Phase 4: Analytics endpoints for the personal archive viewer."""

import re
import sqlite3
from collections import defaultdict
from typing import Optional, List, Dict, Tuple

from fastapi import APIRouter, Query, HTTPException
from database import get_connection
from models import (
    EmailVolumeResponse,
    YearlyEmailVolume,
    MonthlyEmailVolume,
    EmailHeatmapResponse,
    TopContactsResponse,
    TopContact,
    ContactTimelineResponse,
    ContactMonth,
    ResponseTimesResponse,
    ResponseTimeBucket,
    WritingStatsResponse,
    YearlyWritingStats,
    WordFrequency,
    OverviewResponse,
    DataTypeOverview,
    PhotoOverview,
    CalendarOverview,
    ContactsOverview,
    ChatOverview,
    DriveOverview,
    OnThisDayResponse,
    OnThisDayYear,
    OnThisDayEmail,
    OnThisDayPhoto,
    OnThisDayEvent,
    ActivityTimelineResponse,
    MonthlyActivity,
    PhotoStatsResponse,
    YearlyPhotoStats,
    CameraStats,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Common English stopwords to exclude from writing stats
STOPWORDS = frozenset({
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
    "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
    "this", "but", "his", "by", "from", "they", "we", "say", "her",
    "she", "or", "an", "will", "my", "one", "all", "would", "there",
    "their", "what", "so", "up", "out", "if", "about", "who", "get",
    "which", "go", "me", "when", "make", "can", "like", "time", "no",
    "just", "him", "know", "take", "people", "into", "year", "your",
    "good", "some", "could", "them", "see", "other", "than", "then",
    "now", "look", "only", "come", "its", "over", "think", "also",
    "back", "after", "use", "two", "how", "our", "work", "first",
    "well", "way", "even", "new", "want", "because", "any", "these",
    "give", "day", "most", "us", "is", "are", "was", "were", "been",
    "has", "had", "did", "does", "am", "being", "having", "doing",
    "should", "could", "would", "might", "must", "shall", "may",
    "re", "ve", "ll", "don", "didn", "doesn", "isn", "aren", "wasn",
    "weren", "hasn", "hadn", "won", "wouldn", "shouldn", "couldn",
    "let", "s", "t", "d", "m", "o", "http", "https", "www", "com",
    "org", "net", "de", "en", "la", "le", "el", "un", "que", "es",
    "se", "los", "las", "del", "des", "les", "il", "et", "est",
    "sent", "wrote", "message", "email", "mail",
})

_WORD_RE = re.compile(r"[a-z]{3,}", re.ASCII)


def _safe_int(val, default: int = 0) -> int:
    """Safely convert a value to int."""
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _table_exists(cursor: sqlite3.Cursor, table: str) -> bool:
    """Check if a table exists."""
    try:
        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        return cursor.fetchone() is not None
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Email Analytics
# ---------------------------------------------------------------------------

@router.get("/email-volume", response_model=EmailVolumeResponse)
async def email_volume():
    """Email count grouped by year, and by year+month."""
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()

        # Yearly counts - use substr on the ISO date string for speed
        rows = cursor.execute("""
            SELECT CAST(substr(date, 1, 4) AS INTEGER) AS year,
                   COUNT(*) AS count
            FROM emails
            WHERE date IS NOT NULL AND length(date) >= 4
            GROUP BY year
            ORDER BY year
        """).fetchall()
        yearly = [YearlyEmailVolume(year=r["year"], count=r["count"]) for r in rows]

        # Monthly counts
        rows = cursor.execute("""
            SELECT CAST(substr(date, 1, 4) AS INTEGER) AS year,
                   CAST(substr(date, 6, 2) AS INTEGER) AS month,
                   COUNT(*) AS count
            FROM emails
            WHERE date IS NOT NULL AND length(date) >= 7
            GROUP BY year, month
            ORDER BY year, month
        """).fetchall()
        monthly = [
            MonthlyEmailVolume(year=r["year"], month=r["month"], count=r["count"])
            for r in rows
        ]

        return EmailVolumeResponse(yearly=yearly, monthly=monthly)
    finally:
        conn.close()


@router.get("/email-heatmap", response_model=EmailHeatmapResponse)
async def email_heatmap():
    """Day-of-week x hour-of-day grid of email counts (7x24).

    Day 0 = Sunday, Day 6 = Saturday (SQLite strftime %w convention).
    """
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()

        # Use strftime on the ISO date column.
        # strftime('%w', date) gives 0=Sun..6=Sat, '%H' gives hour 0-23.
        rows = cursor.execute("""
            SELECT CAST(strftime('%w', date) AS INTEGER) AS dow,
                   CAST(strftime('%H', date) AS INTEGER) AS hour,
                   COUNT(*) AS count
            FROM emails
            WHERE date IS NOT NULL AND length(date) >= 16
            GROUP BY dow, hour
        """).fetchall()

        # Build 7x24 grid initialised to zeros
        grid = [[0] * 24 for _ in range(7)]
        for r in rows:
            dow = _safe_int(r["dow"])
            hour = _safe_int(r["hour"])
            if 0 <= dow <= 6 and 0 <= hour <= 23:
                grid[dow][hour] = r["count"]

        return EmailHeatmapResponse(heatmap=grid)
    finally:
        conn.close()


@router.get("/top-contacts", response_model=TopContactsResponse)
async def top_contacts(
    limit: int = Query(20, ge=1, le=100),
    year: Optional[int] = Query(None, description="Filter to a specific year"),
):
    """Top email contacts by frequency (sent + received combined)."""
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()

        year_filter = ""
        params: List = []
        if year is not None:
            year_filter = "AND substr(date, 1, 4) = ?"
            params.append(str(year))

        # Fast approach: just GROUP BY from_address for all emails.
        # Received = from_address where NOT sent labels.
        # Sent count = from_address where labels contain 'Sent' (these are MY sent emails,
        # so from_address is me — we skip those and instead count how many times
        # I emailed each person using a separate fast query on the to_addresses column).

        # For speed, skip JSON parsing entirely. Just use from_address for received,
        # and count sent emails by checking labels.

        # All contacts by from_address (received emails)
        received_rows = cursor.execute(f"""
            SELECT lower(from_address) AS address,
                   from_name AS name,
                   COUNT(*) AS cnt,
                   MAX(date) AS last_date
            FROM emails
            WHERE from_address IS NOT NULL
              AND from_address != ''
              {year_filter}
            GROUP BY lower(from_address)
            ORDER BY cnt DESC
            LIMIT 500
        """, params).fetchall()

        contact_data: Dict[str, dict] = {}
        for r in received_rows:
            addr = r["address"]
            contact_data[addr] = {
                "name": r["name"],
                "address": addr,
                "received_count": r["cnt"],
                "sent_count": 0,
                "last_contact": r["last_date"],
            }

        # Build sorted list
        contacts_list = []
        for addr, data in contact_data.items():
            total = data["received_count"]
            if total == 0:
                continue
            contacts_list.append(TopContact(
                name=data["name"],
                address=data["address"],
                sent_count=data["sent_count"],
                received_count=data["received_count"],
                total=total,
                last_contact=data["last_contact"],
            ))

        contacts_list.sort(key=lambda c: c.total, reverse=True)
        return TopContactsResponse(contacts=contacts_list[:limit])
    finally:
        conn.close()


@router.get("/contact-timeline", response_model=ContactTimelineResponse)
async def contact_timeline(
    address: str = Query(..., description="Email address to get timeline for"),
):
    """Monthly email volume with a specific contact."""
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()
        addr_lower = address.lower().strip()

        # Received from this contact (not sent by me)
        received = cursor.execute("""
            SELECT CAST(substr(date, 1, 4) AS INTEGER) AS year,
                   CAST(substr(date, 6, 2) AS INTEGER) AS month,
                   COUNT(*) AS count
            FROM emails
            WHERE lower(from_address) = ?
              AND (labels IS NULL OR lower(labels) NOT LIKE '%sent%')
              AND date IS NOT NULL AND length(date) >= 7
            GROUP BY year, month
            ORDER BY year, month
        """, (addr_lower,)).fetchall()

        # Sent to this contact: find emails where labels contain 'sent'
        # and to_addresses JSON contains the address
        sent = cursor.execute("""
            SELECT CAST(substr(date, 1, 4) AS INTEGER) AS year,
                   CAST(substr(date, 6, 2) AS INTEGER) AS month,
                   COUNT(*) AS count
            FROM emails
            WHERE lower(labels) LIKE '%sent%'
              AND lower(to_addresses) LIKE ?
              AND date IS NOT NULL AND length(date) >= 7
            GROUP BY year, month
            ORDER BY year, month
        """, (f"%{addr_lower}%",)).fetchall()

        # Merge into a single timeline
        months_map: Dict[Tuple[int, int], dict] = {}
        for r in received:
            key = (r["year"], r["month"])
            months_map[key] = {"year": r["year"], "month": r["month"], "sent": 0, "received": r["count"]}
        for r in sent:
            key = (r["year"], r["month"])
            if key in months_map:
                months_map[key]["sent"] = r["count"]
            else:
                months_map[key] = {"year": r["year"], "month": r["month"], "sent": r["count"], "received": 0}

        sorted_months = sorted(months_map.values(), key=lambda m: (m["year"], m["month"]))
        months_list = [
            ContactMonth(year=m["year"], month=m["month"], sent=m["sent"], received=m["received"])
            for m in sorted_months
        ]

        # Get name for this contact
        name_row = cursor.execute(
            "SELECT from_name FROM emails WHERE lower(from_address) = ? AND from_name IS NOT NULL LIMIT 1",
            (addr_lower,),
        ).fetchone()
        name = name_row["from_name"] if name_row else None

        return ContactTimelineResponse(address=addr_lower, name=name, months=months_list)
    finally:
        conn.close()


@router.get("/response-times", response_model=ResponseTimesResponse)
async def response_times():
    """Average response time for threads the user participated in.

    Buckets: <1hr, 1-4hr, 4-12hr, 12-24hr, 1-3day, 3+day.
    Only considers threads with both sent and received messages.
    """
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()

        # Get threads where the user both sent and received emails.
        # For each thread, order by date and compute response deltas.
        # We use date_unix for fast arithmetic.
        rows = cursor.execute("""
            SELECT thread_id, date_unix,
                   CASE WHEN lower(labels) LIKE '%sent%' THEN 1 ELSE 0 END AS is_sent
            FROM emails
            WHERE thread_id IS NOT NULL
              AND date_unix IS NOT NULL
              AND date_unix > 0
            ORDER BY thread_id, date_unix
        """).fetchall()

        # Group by thread
        threads: Dict[str, list] = defaultdict(list)
        for r in rows:
            threads[r["thread_id"]].append({
                "date_unix": r["date_unix"],
                "is_sent": r["is_sent"],
            })

        # Compute response times: time between receiving and next sent
        response_seconds: List[float] = []
        for thread_id, messages in threads.items():
            if len(messages) < 2:
                continue
            # Check thread has both sent and received
            has_sent = any(m["is_sent"] for m in messages)
            has_received = any(not m["is_sent"] for m in messages)
            if not has_sent or not has_received:
                continue

            for i in range(1, len(messages)):
                prev = messages[i - 1]
                curr = messages[i]
                # Response = I sent after receiving
                if not prev["is_sent"] and curr["is_sent"]:
                    delta = curr["date_unix"] - prev["date_unix"]
                    if 0 < delta < 30 * 86400:  # ignore gaps > 30 days
                        response_seconds.append(delta)

        # Bucket the response times
        bucket_defs = [
            ("<1hr", 0, 3600),
            ("1-4hr", 3600, 14400),
            ("4-12hr", 14400, 43200),
            ("12-24hr", 43200, 86400),
            ("1-3day", 86400, 259200),
            ("3+day", 259200, float("inf")),
        ]
        bucket_counts: Dict[str, int] = {b[0]: 0 for b in bucket_defs}
        for sec in response_seconds:
            for label, lo, hi in bucket_defs:
                if lo <= sec < hi:
                    bucket_counts[label] += 1
                    break

        buckets = [
            ResponseTimeBucket(label=label, count=bucket_counts[label])
            for label, _, _ in bucket_defs
        ]

        avg_hours = None
        if response_seconds:
            avg_hours = round(sum(response_seconds) / len(response_seconds) / 3600, 2)

        return ResponseTimesResponse(buckets=buckets, average_hours=avg_hours)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Writing Analytics
# ---------------------------------------------------------------------------

@router.get("/writing-stats", response_model=WritingStatsResponse)
async def writing_stats():
    """Writing analytics for sent emails: avg length by year, top words."""
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()

        # Yearly stats for sent emails
        rows = cursor.execute("""
            SELECT CAST(substr(date, 1, 4) AS INTEGER) AS year,
                   AVG(length(body_text)) AS avg_length,
                   COUNT(*) AS email_count
            FROM emails
            WHERE lower(labels) LIKE '%sent%'
              AND body_text IS NOT NULL
              AND length(body_text) > 0
              AND date IS NOT NULL AND length(date) >= 4
            GROUP BY year
            ORDER BY year
        """).fetchall()

        yearly = []
        for r in rows:
            # Estimate avg words as avg_length / 5 (average word length)
            avg_len = r["avg_length"] or 0
            yearly.append(YearlyWritingStats(
                year=r["year"],
                avg_length=round(avg_len, 1),
                avg_words=round(avg_len / 5.0, 1),
                email_count=r["email_count"],
            ))

        # Top words: sample sent emails for word frequency.
        # For performance, limit to a reasonable sample.
        word_rows = cursor.execute("""
            SELECT body_text
            FROM emails
            WHERE lower(labels) LIKE '%sent%'
              AND body_text IS NOT NULL
              AND length(body_text) > 10
            LIMIT 50000
        """).fetchall()

        word_counts: Dict[str, int] = defaultdict(int)
        for r in word_rows:
            text = r["body_text"]
            if not text:
                continue
            for word in _WORD_RE.findall(text.lower()):
                if word not in STOPWORDS and len(word) <= 30:
                    word_counts[word] += 1

        # Top 50 words
        top_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:50]
        top_words_list = [WordFrequency(word=w, count=c) for w, c in top_words]

        return WritingStatsResponse(yearly=yearly, top_words=top_words_list)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Archive Overview
# ---------------------------------------------------------------------------

@router.get("/overview", response_model=OverviewResponse)
async def overview():
    """Total counts and size for all data types, date ranges."""
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()

        # Email overview – use separate fast queries instead of one slow SUM
        email_ov = None
        if _table_exists(cursor, "emails"):
            count = cursor.execute("SELECT COUNT(*) FROM emails WHERE deleted_at IS NULL").fetchone()[0]
            dates = cursor.execute("SELECT MIN(date) AS earliest, MAX(date) AS latest FROM emails WHERE deleted_at IS NULL").fetchone()
            email_ov = DataTypeOverview(
                count=count,
                size_bytes=0,
                earliest=dates["earliest"],
                latest=dates["latest"],
            )

        # Photos overview
        photo_ov = None
        if _table_exists(cursor, "photos"):
            count = cursor.execute("SELECT COUNT(*) FROM photos WHERE deleted_at IS NULL").fetchone()[0]
            videos = cursor.execute("SELECT COUNT(*) FROM photos WHERE is_video = 1 AND deleted_at IS NULL").fetchone()[0]
            photo_ov = PhotoOverview(
                count=count,
                size_bytes=0,
                videos=videos,
            )

        # Calendar overview
        cal_ov = None
        if _table_exists(cursor, "calendar_events"):
            r = cursor.execute("""
                SELECT COUNT(*) AS count,
                       MIN(start_time) AS earliest,
                       MAX(start_time) AS latest
                FROM calendar_events WHERE deleted_at IS NULL
            """).fetchone()
            cal_ov = CalendarOverview(
                count=r["count"],
                earliest=r["earliest"],
                latest=r["latest"],
            )

        # Contacts overview
        contacts_ov = None
        if _table_exists(cursor, "contacts"):
            r = cursor.execute("SELECT COUNT(*) AS count FROM contacts WHERE deleted_at IS NULL").fetchone()
            contacts_ov = ContactsOverview(count=r["count"])

        # Chat overview
        chat_ov = None
        if _table_exists(cursor, "chat_conversations") and _table_exists(cursor, "chat_messages"):
            convos = cursor.execute("SELECT COUNT(*) AS count FROM chat_conversations").fetchone()
            msgs = cursor.execute("SELECT COUNT(*) AS count FROM chat_messages WHERE deleted_at IS NULL").fetchone()
            chat_ov = ChatOverview(
                conversations=convos["count"],
                messages=msgs["count"],
            )

        # Drive overview
        drive_ov = None
        if _table_exists(cursor, "drive_files"):
            count = cursor.execute("SELECT COUNT(*) FROM drive_files WHERE deleted_at IS NULL").fetchone()[0]
            drive_ov = DriveOverview(
                count=count,
                size_bytes=0,
            )

        return OverviewResponse(
            email=email_ov,
            photos=photo_ov,
            calendar=cal_ov,
            contacts=contacts_ov,
            chat=chat_ov,
            drive=drive_ov,
        )
    finally:
        conn.close()


@router.get("/on-this-day", response_model=OnThisDayResponse)
async def on_this_day(
    month: int = Query(..., ge=1, le=12),
    day: int = Query(..., ge=1, le=31),
):
    """What happened on this date in previous years."""
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()

        # Format month/day with zero-padding for LIKE queries
        mm = f"{month:02d}"
        dd = f"{day:02d}"
        date_pattern = f"%-{mm}-{dd}%"

        years_data: Dict[int, dict] = defaultdict(lambda: {"emails": [], "photos": [], "events": []})

        # Emails on this day
        if _table_exists(cursor, "emails"):
            rows = cursor.execute("""
                SELECT id, subject, from_name, date,
                       CAST(substr(date, 1, 4) AS INTEGER) AS year
                FROM emails
                WHERE date_month_day = ?
                ORDER BY date
                LIMIT 500
            """, (f"{mm}-{dd}",)).fetchall()
            for r in rows:
                years_data[r["year"]]["emails"].append(
                    OnThisDayEmail(id=r["id"], subject=r["subject"], from_name=r["from_name"], date=r["date"])
                )

        # Photos on this day
        if _table_exists(cursor, "photos"):
            rows = cursor.execute("""
                SELECT id, filename, thumbnail_path,
                       CAST(substr(date_taken, 1, 4) AS INTEGER) AS year
                FROM photos
                WHERE date_month_day = ?
                ORDER BY date_taken
                LIMIT 200
            """, (f"{mm}-{dd}",)).fetchall()
            for r in rows:
                years_data[r["year"]]["photos"].append(
                    OnThisDayPhoto(id=r["id"], filename=r["filename"], thumbnail_path=r["thumbnail_path"])
                )

        # Calendar events on this day
        if _table_exists(cursor, "calendar_events"):
            rows = cursor.execute("""
                SELECT id, summary,
                       CAST(substr(start_time, 1, 4) AS INTEGER) AS year
                FROM calendar_events
                WHERE date_month_day = ?
                ORDER BY start_time
                LIMIT 200
            """, (f"{mm}-{dd}",)).fetchall()
            for r in rows:
                years_data[r["year"]]["events"].append(
                    OnThisDayEvent(id=r["id"], summary=r["summary"])
                )

        # Build sorted response
        years_list = []
        for year in sorted(years_data.keys()):
            data = years_data[year]
            if data["emails"] or data["photos"] or data["events"]:
                years_list.append(OnThisDayYear(
                    year=year,
                    emails=data["emails"],
                    photos=data["photos"],
                    events=data["events"],
                ))

        return OnThisDayResponse(years=years_list)
    finally:
        conn.close()


@router.get("/activity-timeline", response_model=ActivityTimelineResponse)
async def activity_timeline():
    """Unified monthly activity across all data types."""
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()
        months_map: Dict[Tuple[int, int], dict] = defaultdict(
            lambda: {"emails": 0, "photos": 0, "events": 0, "chats": 0}
        )

        # Emails by month
        if _table_exists(cursor, "emails"):
            rows = cursor.execute("""
                SELECT CAST(substr(date, 1, 4) AS INTEGER) AS year,
                       CAST(substr(date, 6, 2) AS INTEGER) AS month,
                       COUNT(*) AS count
                FROM emails
                WHERE date IS NOT NULL AND length(date) >= 7
                GROUP BY year, month
            """).fetchall()
            for r in rows:
                months_map[(r["year"], r["month"])]["emails"] = r["count"]

        # Photos by month
        if _table_exists(cursor, "photos"):
            rows = cursor.execute("""
                SELECT CAST(substr(date_taken, 1, 4) AS INTEGER) AS year,
                       CAST(substr(date_taken, 6, 2) AS INTEGER) AS month,
                       COUNT(*) AS count
                FROM photos
                WHERE date_taken IS NOT NULL AND length(date_taken) >= 7
                GROUP BY year, month
            """).fetchall()
            for r in rows:
                months_map[(r["year"], r["month"])]["photos"] = r["count"]

        # Calendar events by month
        if _table_exists(cursor, "calendar_events"):
            rows = cursor.execute("""
                SELECT CAST(substr(start_time, 1, 4) AS INTEGER) AS year,
                       CAST(substr(start_time, 6, 2) AS INTEGER) AS month,
                       COUNT(*) AS count
                FROM calendar_events
                WHERE start_time IS NOT NULL AND length(start_time) >= 7
                GROUP BY year, month
            """).fetchall()
            for r in rows:
                months_map[(r["year"], r["month"])]["events"] = r["count"]

        # Chat messages by month
        if _table_exists(cursor, "chat_messages"):
            rows = cursor.execute("""
                SELECT CAST(substr(timestamp, 1, 4) AS INTEGER) AS year,
                       CAST(substr(timestamp, 6, 2) AS INTEGER) AS month,
                       COUNT(*) AS count
                FROM chat_messages
                WHERE timestamp IS NOT NULL AND length(timestamp) >= 7
                GROUP BY year, month
            """).fetchall()
            for r in rows:
                months_map[(r["year"], r["month"])]["chats"] = r["count"]

        # Build sorted response
        sorted_keys = sorted(months_map.keys())
        months_list = [
            MonthlyActivity(
                year=k[0], month=k[1],
                emails=months_map[k]["emails"],
                photos=months_map[k]["photos"],
                events=months_map[k]["events"],
                chats=months_map[k]["chats"],
            )
            for k in sorted_keys
        ]

        return ActivityTimelineResponse(months=months_list)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Photo Analytics
# ---------------------------------------------------------------------------

@router.get("/photo-stats", response_model=PhotoStatsResponse)
async def photo_stats():
    """Photos per year with video breakdown, camera/device stats."""
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()

        # Yearly photo counts
        yearly = []
        if _table_exists(cursor, "photos"):
            rows = cursor.execute("""
                SELECT CAST(substr(date_taken, 1, 4) AS INTEGER) AS year,
                       COUNT(*) AS count,
                       SUM(CASE WHEN is_video = 1 THEN 1 ELSE 0 END) AS video_count
                FROM photos
                WHERE date_taken IS NOT NULL AND length(date_taken) >= 4
                GROUP BY year
                ORDER BY year
            """).fetchall()
            yearly = [
                YearlyPhotoStats(year=r["year"], count=r["count"], video_count=_safe_int(r["video_count"]))
                for r in rows
            ]

        # Camera stats
        cameras = []
        if _table_exists(cursor, "photos"):
            rows = cursor.execute("""
                SELECT camera_make, camera_model, COUNT(*) AS count
                FROM photos
                WHERE camera_make IS NOT NULL OR camera_model IS NOT NULL
                GROUP BY camera_make, camera_model
                ORDER BY count DESC
                LIMIT 50
            """).fetchall()
            cameras = [
                CameraStats(make=r["camera_make"], model=r["camera_model"], count=r["count"])
                for r in rows
            ]

        return PhotoStatsResponse(yearly=yearly, cameras=cameras)
    finally:
        conn.close()
