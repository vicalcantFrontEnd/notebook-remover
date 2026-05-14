import uuid
import asyncio
import time
import threading
from datetime import datetime
from pathlib import Path
from ..config import settings
from ..api.schemas import JobStatus, JobCreate, JobInfo, FileType


# Extension → output extension mapping
_OUTPUT_EXT = {
    FileType.video: ".mp4",
    FileType.image: None,  # preserve original extension
    FileType.pdf: ".pdf",
    FileType.pptx: ".pptx",
}


class Job:
    def __init__(self, job_id: str, file_id: str, filename: str, params: JobCreate):
        self.job_id = job_id
        self.file_id = file_id
        self.filename = filename
        self.params = params
        self.status = JobStatus.queued
        self.progress = 0.0
        self.current_frame = 0
        self.total_frames = 0
        self.eta_seconds: float | None = None
        self.created_at = datetime.now()
        self.completed_at: datetime | None = None
        self.error: str | None = None
        self.output_path: str | None = None
        self.cancel_event = threading.Event()
        self.progress_queue: asyncio.Queue | None = None
        self._start_time: float | None = None

    def to_info(self) -> JobInfo:
        return JobInfo(
            job_id=self.job_id,
            file_id=self.file_id,
            filename=self.filename,
            status=self.status,
            progress=self.progress,
            current_frame=self.current_frame,
            total_frames=self.total_frames,
            eta_seconds=self.eta_seconds,
            created_at=self.created_at,
            completed_at=self.completed_at,
            error=self.error,
            method=self.params.method.value,
        )


class JobService:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._consumer_task: asyncio.Task | None = None

    def start(self):
        """Start the job consumer loop."""
        self._consumer_task = asyncio.create_task(self._consumer_loop())

    async def stop(self):
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

    async def create_job(self, params: JobCreate, file_path: str, filename: str) -> Job:
        job_id = uuid.uuid4().hex[:12]
        job = Job(job_id, params.file_id, filename, params)
        job.progress_queue = asyncio.Queue()

        # Create output directory
        output_dir = settings.output_dir / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(filename).stem

        # Determine output extension based on file type
        file_type = params.file_type
        out_ext = _OUTPUT_EXT.get(file_type)
        if out_ext is None:
            # Preserve original extension (for images)
            out_ext = Path(filename).suffix.lower()
        job.output_path = str(output_dir / f"{stem}_clean{out_ext}")

        self._jobs[job_id] = job
        await self._queue.put(job_id)
        return job

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[JobInfo]:
        return [j.to_info() for j in self._jobs.values()]

    def cancel_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.status in (JobStatus.queued, JobStatus.processing):
            job.cancel_event.set()
            job.status = JobStatus.cancelled
            return True
        return False

    def delete_job(self, job_id: str):
        job = self._jobs.pop(job_id, None)
        if job and job.output_path:
            import shutil
            parent = Path(job.output_path).parent
            if parent.exists():
                shutil.rmtree(parent, ignore_errors=True)

    async def _consumer_loop(self):
        """Pull jobs from queue and process one at a time."""
        while True:
            job_id = await self._queue.get()
            job = self._jobs.get(job_id)
            if not job or job.cancel_event.is_set():
                continue

            job.status = JobStatus.processing
            job._start_time = time.time()

            try:
                from .upload_service import upload_service
                file_path = upload_service.get_file_path(job.file_id)

                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self._process_job, job, file_path, loop)

                if job.cancel_event.is_set():
                    job.status = JobStatus.cancelled
                else:
                    job.status = JobStatus.completed
                    job.progress = 100.0
                    job.completed_at = datetime.now()
            except Exception as e:
                job.status = JobStatus.failed
                job.error = str(e)
                job.completed_at = datetime.now()
            finally:
                # Send final status update
                if job.progress_queue:
                    await job.progress_queue.put(None)  # sentinel

    def _process_job(self, job: Job, file_path: str, loop: asyncio.AbstractEventLoop):
        """Run in thread pool - dispatches to the appropriate processor."""
        region = (job.params.region.x, job.params.region.y,
                  job.params.region.w, job.params.region.h)

        def progress_cb(current, total):
            job.current_frame = current
            job.total_frames = total
            if total > 0:
                job.progress = round(current / total * 100, 1)
            if job._start_time and current > 0 and total > 0:
                elapsed = time.time() - job._start_time
                rate = current / elapsed
                remaining = (total - current) / rate if rate > 0 else 0
                job.eta_seconds = round(remaining, 1)
            # Push to async queue (thread-safe via call_soon_threadsafe)
            if job.progress_queue:
                try:
                    loop.call_soon_threadsafe(job.progress_queue.put_nowait, {
                        "progress": job.progress,
                        "current_frame": current,
                        "total_frames": total,
                        "eta_seconds": job.eta_seconds,
                    })
                except Exception:
                    pass

        file_type = job.params.file_type

        if file_type == FileType.video:
            from backend.core.engine import process_video
            process_video(
                input_path=file_path,
                output_path=job.output_path,
                region=region,
                trim_end_seconds=job.params.trim_end_seconds,
                inpaint_radius=job.params.inpaint_radius,
                method=job.params.method.value,
                sensitivity=job.params.sensitivity,
                progress_callback=progress_cb,
                cancel_flag=lambda: job.cancel_event.is_set(),
            )

        elif file_type == FileType.image:
            from backend.core.image_processor import process_image
            process_image(
                input_path=file_path,
                output_path=job.output_path,
                region=region,
                method=job.params.method.value,
                sensitivity=job.params.sensitivity,
                inpaint_radius=job.params.inpaint_radius,
                progress_callback=progress_cb,
                cancel_flag=lambda: job.cancel_event.is_set(),
            )

        elif file_type == FileType.pdf:
            from backend.core.pdf_processor import process_pdf
            process_pdf(
                input_path=file_path,
                output_path=job.output_path,
                region=region,
                method=job.params.method.value,
                sensitivity=job.params.sensitivity,
                inpaint_radius=job.params.inpaint_radius,
                progress_callback=progress_cb,
                cancel_flag=lambda: job.cancel_event.is_set(),
            )

        elif file_type == FileType.pptx:
            from backend.core.pptx_processor import process_pptx
            process_pptx(
                input_path=file_path,
                output_path=job.output_path,
                region=region,
                progress_callback=progress_cb,
                cancel_flag=lambda: job.cancel_event.is_set(),
            )

        else:
            raise ValueError(f"Unsupported file type: {file_type}")


job_service = JobService()
