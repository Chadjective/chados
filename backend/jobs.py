#!/usr/bin/env python3
"""Background job runner for ChadOS enrichment/import work (v4).

A single worker thread drains a FIFO queue of jobs persisted in the
``enrichment_jobs`` table. One job runs at a time (disk- and Ollama-bound work
serialises anyway). Jobs are:

* **resumable**  — importers skip rows already present, so re-queuing is safe;
* **cancellable** — a cooperative in-memory flag the job polls;
* **observable**  — coarse status transitions (queued→running→done/…) are
  persisted, while fast-moving progress counters live in memory and are
  overlaid by :func:`get_job`. Keeping the hot loop out of the DB avoids
  write-lock contention with the importer's own connection.

This is the shared foundation for photo import now, and geo-backfill / vision
enrichment later (just add a branch in ``_run_job``).
"""

# Backend runs on Python 3.9; defer annotation eval so `X | None` is legal.
from __future__ import annotations

import json
import queue
import threading
from datetime import datetime, timezone

from database import get_connection

_job_queue: "queue.Queue[int]" = queue.Queue()
_worker: threading.Thread | None = None
_worker_lock = threading.Lock()

_cancelled: set[int] = set()          # job ids asked to stop
_live: dict[int, dict] = {}           # job id -> live progress (hot path)
_live_lock = threading.Lock()

# Columns _set_status is allowed to write.
_STATUS_COLUMNS = {
    "status", "total", "processed", "imported", "skipped", "errors",
    "error", "started_at", "finished_at",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_worker() -> None:
    global _worker
    with _worker_lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_worker_loop, name="job-worker", daemon=True)
            _worker.start()


def create_job(job_type: str, label: str | None = None, scope: dict | None = None) -> int:
    """Persist a queued job, enqueue it, and make sure the worker is running."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO enrichment_jobs (job_type, label, scope_json, status) "
        "VALUES (?, ?, ?, 'queued')",
        (job_type, label, json.dumps(scope or {})),
    )
    job_id = cur.lastrowid
    conn.commit()
    conn.close()
    _job_queue.put(job_id)
    _ensure_worker()
    return job_id


def cancel_job(job_id: int) -> bool:
    """Request cancellation. Queued jobs are marked cancelled immediately;
    running jobs stop at their next cooperative check."""
    _cancelled.add(job_id)
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("SELECT status FROM enrichment_jobs WHERE id = ?", (job_id,)).fetchone()
    if row and row["status"] == "queued":
        cur.execute(
            "UPDATE enrichment_jobs SET status='cancelled', finished_at=? WHERE id=?",
            (_now(), job_id),
        )
        conn.commit()
    conn.close()
    return bool(row)


def get_job(job_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM enrichment_jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if not row:
        return None
    data = dict(row)
    with _live_lock:
        if job_id in _live:
            data.update(_live[job_id])   # overlay fresher in-memory counters
    return data


def list_jobs(limit: int = 50) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM enrichment_jobs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    out = []
    with _live_lock:
        for row in rows:
            data = dict(row)
            if data["id"] in _live:
                data.update(_live[data["id"]])
            out.append(data)
    return out


def _set_status(job_id: int, **fields) -> None:
    fields = {k: v for k, v in fields.items() if k in _STATUS_COLUMNS}
    if not fields:
        return
    assignments = ", ".join(f"{k} = ?" for k in fields)
    conn = get_connection()
    conn.execute(
        f"UPDATE enrichment_jobs SET {assignments} WHERE id = ?",
        (*fields.values(), job_id),
    )
    conn.commit()
    conn.close()


def _worker_loop() -> None:
    while True:
        job_id = _job_queue.get()
        try:
            _run_job(job_id)
        except Exception as exc:  # noqa: BLE001 - worker must never die
            _set_status(job_id, status="error", error=str(exc), finished_at=_now())
        finally:
            with _live_lock:
                _live.pop(job_id, None)
            _cancelled.discard(job_id)
            _job_queue.task_done()


def _run_job(job_id: int) -> None:
    conn = get_connection()
    row = conn.execute(
        "SELECT job_type, scope_json, status FROM enrichment_jobs WHERE id = ?", (job_id,)
    ).fetchone()
    conn.close()
    if not row:
        return
    if row["status"] == "cancelled" or job_id in _cancelled:
        _set_status(job_id, status="cancelled", finished_at=_now())
        return

    scope = json.loads(row["scope_json"] or "{}")
    _set_status(job_id, status="running", started_at=_now())

    if row["job_type"] == "photo_import":
        _run_photo_import(job_id, scope)
    else:
        _set_status(
            job_id, status="error",
            error=f"unknown job_type: {row['job_type']}", finished_at=_now(),
        )


def _run_photo_import(job_id: int, scope: dict) -> None:
    from local_folder_importer import import_folder

    def on_progress(stats: dict) -> None:
        with _live_lock:
            _live[job_id] = {
                "total": stats.get("total", 0),
                "processed": stats.get("processed", 0),
                "imported": stats.get("imported", 0),
                "skipped": stats.get("skipped", 0),
                "errors": stats.get("errors", 0),
                "geotagged": stats.get("geotagged", 0),
                "phase": stats.get("phase"),
            }

    def should_cancel() -> bool:
        return job_id in _cancelled

    final = import_folder(
        scope["path"],
        recursive=scope.get("recursive", True),
        source_label=scope.get("label"),
        on_progress=on_progress,
        should_cancel=should_cancel,
    )

    status = "cancelled" if final.get("phase") == "cancelled" else "done"
    _set_status(
        job_id,
        status=status,
        total=final.get("total", 0),
        processed=final.get("processed", 0),
        imported=final.get("imported", 0),
        skipped=final.get("skipped", 0),
        errors=final.get("errors", 0),
        finished_at=_now(),
    )
