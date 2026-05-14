"""
Pipeline REST API — called by n8n.

Endpoints:
  GET  /api/pipeline/scan         → Scan Drive tree + return status of every file
  POST /api/pipeline/process      → Start processing one Drive file
  GET  /api/pipeline/jobs/{id}    → Poll job status
  GET  /api/pipeline/files        → List all tracked files from DB
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from ..services.pipeline_service import pipeline_service
from ..config import settings

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


# ------------------------------------------------------------------ schemas

class ProcessRequest(BaseModel):
    drive_file_id: str
    filename: str
    categoria_name: str
    tema_name: str


class ProcessResponse(BaseModel):
    job_id: str
    drive_file_id: str
    filename: str
    status: str
    cdn_url: Optional[str] = None
    message: str = ""


class JobStatusResponse(BaseModel):
    job_id: str
    drive_file_id: str
    filename: str
    status: str
    progress: float
    cdn_url: Optional[str] = None
    error: Optional[str] = None
    categoria_name: str
    tema_name: str


# ------------------------------------------------------------------ endpoints

@router.get("/scan")
async def scan_drive(
    root_folder_id: str = Query(..., description="Google Drive folder ID of the root course folder"),
):
    """
    Traverse the Drive tree (root → Categorias → Temas → Files) and
    return every target file enriched with its current pipeline status.

    n8n uses this to decide which files still need processing.
    """
    try:
        from ..services.drive_service import scan_drive_tree
        drive_records = scan_drive_tree(root_folder_id)
    except Exception as exc:
        raise HTTPException(502, f"Drive API error: {exc}")

    enriched = pipeline_service.merge_scan_results(drive_records)
    return {
        "total": len(enriched),
        "files": enriched,
    }


@router.post("/process", response_model=ProcessResponse)
async def process_file(req: ProcessRequest):
    """
    Submit a single Drive file for the full pipeline.

    If the file was already processed successfully, returns the existing
    CDN URL immediately (idempotent — safe to call multiple times).
    """
    try:
        job = await pipeline_service.start_pipeline(
            drive_file_id=req.drive_file_id,
            filename=req.filename,
            categoria_name=req.categoria_name,
            tema_name=req.tema_name,
        )
    except Exception as exc:
        raise HTTPException(500, f"Failed to start pipeline: {exc}")

    already_done = job.status == "completed" and job.progress == 100.0
    return ProcessResponse(
        job_id=job.job_id,
        drive_file_id=job.drive_file_id,
        filename=job.filename,
        status=job.status,
        cdn_url=job.cdn_url,
        message="already_processed" if already_done else "started",
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Poll the status of a running pipeline job.

    n8n polls this endpoint until status is 'completed' or 'failed'.
    """
    job = pipeline_service.get_job(job_id)
    if not job:
        # Try to recover from DB
        all_records = pipeline_service.list_records()
        record = next((r for r in all_records if r.get("job_id") == job_id), None)
        if not record:
            raise HTTPException(404, "Job not found")
        return JobStatusResponse(
            job_id=job_id,
            drive_file_id=record["drive_file_id"],
            filename=record["filename"],
            status=record["status"],
            progress=100.0 if record["status"] == "completed" else 0.0,
            cdn_url=record["cdn_url"],
            error=record["error"],
            categoria_name=record["categoria_name"],
            tema_name=record["tema_name"],
        )

    return JobStatusResponse(
        job_id=job.job_id,
        drive_file_id=job.drive_file_id,
        filename=job.filename,
        status=job.status,
        progress=job.progress,
        cdn_url=job.cdn_url,
        error=job.error,
        categoria_name=job.categoria_name,
        tema_name=job.tema_name,
    )


@router.get("/files")
async def list_processed_files():
    """Return all files tracked in the SQLite pipeline database."""
    records = pipeline_service.list_records()
    return {
        "total": len(records),
        "files": records,
    }


@router.delete("/files/{drive_file_id}")
async def reset_file(drive_file_id: str):
    """
    Reset a file's pipeline state so it gets reprocessed on next scan.
    Useful when the source file changes or processing failed.
    """
    import sqlite3
    from pathlib import Path

    db_path = Path("data/pipeline.db")
    if not db_path.exists():
        raise HTTPException(404, "No pipeline database found")

    with sqlite3.connect(db_path) as conn:
        result = conn.execute(
            "DELETE FROM pipeline_files WHERE drive_file_id = ?",
            (drive_file_id,)
        )
        if result.rowcount == 0:
            raise HTTPException(404, "File record not found")

    return {"status": "reset", "drive_file_id": drive_file_id}


@router.get("/health")
async def pipeline_health():
    """Quick health check for n8n to verify the service is up."""
    return {
        "status": "ok",
        "root_folder_id": settings.drive_root_folder_id or "not_set",
        "bunny_zone": settings.bunny_storage_zone or "not_set",
    }
