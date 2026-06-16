"""Photo import API (ChadOS v4): index photos from local folders / external
drives in the background, with progress and cancellation."""

import os
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from jobs import create_job, get_job, list_jobs, cancel_job

router = APIRouter(prefix="/api/photos/import", tags=["photo-import"])


class FolderImportRequest(BaseModel):
    path: str
    recursive: bool = True
    label: Optional[str] = None


@router.get("/drives")
async def list_drives():
    """List mounted volumes under /Volumes so the UI can offer drive shortcuts."""
    volumes = Path("/Volumes")
    drives = []
    if volumes.exists():
        for entry in sorted(volumes.iterdir()):
            try:
                if not entry.is_dir():
                    continue
                usage = shutil.disk_usage(entry)
                drives.append({
                    "name": entry.name,
                    "path": str(entry),
                    "total_bytes": usage.total,
                    "used_bytes": usage.used,
                    "free_bytes": usage.free,
                })
            except (PermissionError, OSError):
                continue
    return {"drives": drives}


@router.post("/folder")
async def import_folder(req: FolderImportRequest):
    """Queue a background import of every photo/video under ``path``."""
    path = os.path.expanduser(req.path.strip())
    if not path:
        raise HTTPException(status_code=400, detail="A folder path is required.")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"Not a folder: {path}")

    label = req.label or Path(path).name or path
    job_id = create_job(
        "photo_import",
        label=label,
        scope={"path": path, "recursive": req.recursive, "label": label},
    )
    return {"job_id": job_id}


@router.get("/jobs")
async def get_jobs():
    return {"jobs": list_jobs(limit=50)}


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: int):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/{job_id}/cancel")
async def cancel_import(job_id: int):
    if not cancel_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"cancelled": True}
