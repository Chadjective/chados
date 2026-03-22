import sqlite3
from typing import List
from fastapi import APIRouter, HTTPException
from database import get_connection
from models import LabelInfo

router = APIRouter(prefix="/api/labels", tags=["labels"])


# Standard Gmail system labels in display order
SYSTEM_LABELS_ORDER = [
    "Inbox",
    "Sent",
    "Starred",
    "Important",
    "Drafts",
    "Spam",
    "Trash",
    "Chats",
]


@router.get("", response_model=List[LabelInfo])
async def list_labels():
    """List all labels with email counts.

    System labels appear first in a fixed order (Inbox, Sent, Starred, ...),
    followed by custom/user labels sorted alphabetically.
    """
    conn = get_connection(readonly=True)
    try:
        cursor = conn.cursor()

        # Get labels with live email counts from the join table
        rows = cursor.execute(
            """
            SELECT l.id, l.name,
                   COALESCE(counts.cnt, l.email_count) AS email_count
            FROM labels l
            LEFT JOIN (
                SELECT label_id, COUNT(*) AS cnt
                FROM email_labels
                GROUP BY label_id
            ) counts ON counts.label_id = l.id
            ORDER BY l.name
            """
        ).fetchall()

        labels = [
            LabelInfo(id=r["id"], name=r["name"], email_count=r["email_count"])
            for r in rows
        ]

        # Sort: system labels first (in fixed order), then custom labels alphabetically
        system = []
        custom = []
        for label in labels:
            if label.name in SYSTEM_LABELS_ORDER:
                system.append(label)
            else:
                custom.append(label)

        system.sort(key=lambda l: SYSTEM_LABELS_ORDER.index(l.name))
        custom.sort(key=lambda l: l.name.lower())

        return system + custom
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
    finally:
        conn.close()
