"""
Pipeline Service: Drive → Watermark Removal → Bunny CDN

Tracks processing state in SQLite so files are never processed twice.
Each pipeline job runs in a background thread (heavy CPU work).
"""

import sqlite3
import uuid
import tempfile
import shutil
import asyncio
import threading
import os
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..config import settings


# ------------------------------------------------------------------ data classes

@dataclass
class PipelineJob:
    job_id: str
    drive_file_id: str
    filename: str
    categoria_name: str
    tema_name: str
    status: str        # pending | downloading | processing | uploading | completed | failed
    cdn_url: Optional[str] = None
    error: Optional[str] = None
    progress: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "drive_file_id": self.drive_file_id,
            "filename": self.filename,
            "categoria_name": self.categoria_name,
            "tema_name": self.tema_name,
            "status": self.status,
            "cdn_url": self.cdn_url,
            "error": self.error,
            "progress": self.progress,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ------------------------------------------------------------------ service

class PipelineService:
    _DB_SCHEMA = """
        CREATE TABLE IF NOT EXISTS pipeline_files (
            drive_file_id   TEXT PRIMARY KEY,
            filename        TEXT NOT NULL,
            categoria_name  TEXT NOT NULL,
            tema_name       TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'pending',
            cdn_url         TEXT,
            error           TEXT,
            job_id          TEXT,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );
    """

    def __init__(self):
        self._db_path = Path("data/pipeline.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._jobs: dict[str, PipelineJob] = {}
        self._lock = threading.Lock()

    # ---- DB helpers --------------------------------------------------

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript(self._DB_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _upsert(self, job: PipelineJob):
        job.updated_at = datetime.utcnow().isoformat()
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO pipeline_files
                    (drive_file_id, filename, categoria_name, tema_name,
                     status, cdn_url, error, job_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(drive_file_id) DO UPDATE SET
                    status      = excluded.status,
                    cdn_url     = excluded.cdn_url,
                    error       = excluded.error,
                    job_id      = excluded.job_id,
                    updated_at  = excluded.updated_at
            """, (
                job.drive_file_id, job.filename,
                job.categoria_name, job.tema_name,
                job.status, job.cdn_url, job.error,
                job.job_id, job.created_at, job.updated_at,
            ))

    def get_record(self, drive_file_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM pipeline_files WHERE drive_file_id = ?",
                (drive_file_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_records(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM pipeline_files ORDER BY updated_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    # ---- Job management ----------------------------------------------

    def get_job(self, job_id: str) -> Optional[PipelineJob]:
        with self._lock:
            return self._jobs.get(job_id)

    async def start_pipeline(
        self,
        drive_file_id: str,
        filename: str,
        categoria_name: str,
        tema_name: str,
    ) -> PipelineJob:
        """
        Start a pipeline job for a single Drive file.

        If the file was already successfully processed, returns the existing
        record immediately without re-processing.
        """
        # Check DB for existing completed record
        record = self.get_record(drive_file_id)
        if record and record["status"] == "completed":
            # Already done — reconstruct a finished job
            job = PipelineJob(
                job_id=record["job_id"] or uuid.uuid4().hex[:12],
                drive_file_id=drive_file_id,
                filename=filename,
                categoria_name=categoria_name,
                tema_name=tema_name,
                status="completed",
                cdn_url=record["cdn_url"],
                progress=100.0,
                created_at=record["created_at"],
                updated_at=record["updated_at"],
            )
            with self._lock:
                self._jobs[job.job_id] = job
            return job

        # Check if already in progress (in-memory)
        if record and record.get("job_id"):
            with self._lock:
                existing = self._jobs.get(record["job_id"])
                if existing and existing.status not in ("completed", "failed"):
                    return existing

        # Create new job
        job = PipelineJob(
            job_id=uuid.uuid4().hex[:12],
            drive_file_id=drive_file_id,
            filename=filename,
            categoria_name=categoria_name,
            tema_name=tema_name,
            status="pending",
        )
        with self._lock:
            self._jobs[job.job_id] = job

        self._upsert(job)

        # Run in thread pool (CPU/IO bound)
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, self._run_sync, job)

        return job

    # ---- Pipeline execution (runs in thread) -------------------------

    def _run_sync(self, job: PipelineJob):
        """Full pipeline: download → process → upload to CDN."""
        tmp_dir = Path(tempfile.mkdtemp(prefix="pipeline_"))
        try:
            self._step_download(job, tmp_dir)
            self._step_process(job, tmp_dir)
            self._step_upload(job, tmp_dir)

            job.status = "completed"
            job.progress = 100.0
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            import traceback
            traceback.print_exc()
        finally:
            self._upsert(job)
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _step_download(self, job: PipelineJob, tmp_dir: Path):
        from .drive_service import download_file
        job.status = "downloading"
        job.progress = 5.0
        self._upsert(job)

        content = download_file(job.drive_file_id)
        input_path = tmp_dir / job.filename
        input_path.write_bytes(content)
        job._input_path = str(input_path)

    def _step_process(self, job: PipelineJob, tmp_dir: Path):
        job.status = "processing"
        job.progress = 15.0
        self._upsert(job)

        input_path = job._input_path
        ext = Path(job.filename).suffix.lower()
        stem = Path(job.filename).stem
        clean_filename = f"{stem}_clean{ext}"
        output_path = str(tmp_dir / clean_filename)
        job._output_path = output_path
        job._clean_filename = clean_filename

        def progress_cb(current, total):
            if total > 0:
                job.progress = 15.0 + (current / total) * 70.0

        if ext in {".mp4", ".mkv", ".avi", ".mov", ".webm"}:
            self._process_video(input_path, output_path, progress_cb)

        elif ext in {".jpg", ".jpeg", ".png", ".webp"}:
            self._process_image(input_path, output_path, progress_cb)

        elif ext == ".pdf":
            self._process_pdf(input_path, output_path, progress_cb)

        elif ext in {".m4a", ".mp3", ".aac", ".wav"}:
            self._process_audio(input_path, output_path, ext)

        else:
            # Unknown type — pass through
            shutil.copy2(input_path, output_path)

    def _step_upload(self, job: PipelineJob, tmp_dir: Path):
        from .bunny_service import upload_file
        job.status = "uploading"
        job.progress = 88.0
        self._upsert(job)

        content = Path(job._output_path).read_bytes()
        cdn_path = f"{job.categoria_name}/{job.tema_name}"
        cdn_url = upload_file(content, cdn_path, job._clean_filename)
        job.cdn_url = cdn_url

    # ---- Processors --------------------------------------------------

    def _process_video(self, input_path: str, output_path: str, progress_cb):
        from ..core.engine import (
            extract_first_frame, detect_watermark_region, process_video,
        )
        frame, _ = extract_first_frame(input_path)
        region = detect_watermark_region(frame)
        process_video(
            input_path=input_path,
            output_path=output_path,
            region=region,
            method=settings.pipeline_video_method,
            sensitivity=settings.pipeline_sensitivity,
            inpaint_radius=settings.pipeline_inpaint_radius,
            trim_end_seconds=settings.pipeline_trim_end_seconds,
            progress_callback=progress_cb,
        )

    def _process_image(self, input_path: str, output_path: str, progress_cb):
        from ..core.image_processor import load_image, process_image
        from ..core.engine import detect_watermark_region
        frame = load_image(input_path)
        region = detect_watermark_region(frame)
        process_image(
            input_path=input_path,
            output_path=output_path,
            region=region,
            method=settings.pipeline_image_method,
            sensitivity=settings.pipeline_sensitivity,
            inpaint_radius=settings.pipeline_inpaint_radius,
            progress_callback=progress_cb,
        )

    def _process_pdf(self, input_path: str, output_path: str, progress_cb):
        from ..core.pdf_processor import extract_first_page_image, process_pdf
        from ..core.engine import detect_watermark_region
        frame = extract_first_page_image(input_path)
        region = detect_watermark_region(frame)
        process_pdf(
            input_path=input_path,
            output_path=output_path,
            region=region,
            method=settings.pipeline_pdf_method,
            sensitivity=settings.pipeline_sensitivity,
            inpaint_radius=settings.pipeline_inpaint_radius,
            progress_callback=progress_cb,
        )

    def _process_audio(self, input_path: str, output_path: str, ext: str):
        """Re-encode audio with FFmpeg, optionally trimming the end."""
        from ..core.engine import _find_ffmpeg, FFMPEG_BIN, _no_window
        import subprocess
        import json

        _find_ffmpeg()

        trim_end = settings.audio_trim_end_seconds
        cmd = [FFMPEG_BIN, "-y", "-v", "quiet", "-i", input_path]

        if trim_end > 0:
            # Get duration first
            probe_cmd = [
                FFMPEG_BIN.replace("ffmpeg", "ffprobe"),
                "-v", "quiet", "-print_format", "json",
                "-show_format", input_path,
            ]
            result = subprocess.run(
                probe_cmd, capture_output=True, text=True,
                creationflags=_no_window(),
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                duration = float(data.get("format", {}).get("duration", 0))
                effective = max(1.0, duration - trim_end)
                cmd += ["-t", f"{effective:.3f}"]

        # Re-encode to same format
        if ext == ".m4a":
            cmd += ["-c:a", "aac", "-q:a", "2"]
        else:
            cmd += ["-c:a", "copy"]
        cmd.append(output_path)

        subprocess.run(cmd, check=True, creationflags=_no_window())

    # ---- Bulk scan ---------------------------------------------------

    def merge_scan_results(
        self, drive_records: list[dict]
    ) -> list[dict]:
        """
        Merge a list of Drive scan records with their DB status.
        Returns enriched records with 'pipeline_status' and 'cdn_url'.
        """
        enriched = []
        for rec in drive_records:
            db_rec = self.get_record(rec["drive_file_id"])
            enriched.append({
                **rec,
                "pipeline_status": db_rec["status"] if db_rec else "not_started",
                "cdn_url": db_rec["cdn_url"] if db_rec else None,
                "job_id": db_rec["job_id"] if db_rec else None,
            })
        return enriched


pipeline_service = PipelineService()
