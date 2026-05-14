import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from ..services.job_service import job_service
from ..api.schemas import JobStatus


async def job_progress_ws(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time job progress."""
    await websocket.accept()

    job = job_service.get_job(job_id)
    if not job:
        await websocket.send_json({"type": "error", "message": "Job not found"})
        await websocket.close()
        return

    # Send initial status
    await websocket.send_json({
        "type": "status",
        "job_id": job_id,
        "status": job.status.value,
        "progress": job.progress,
    })

    if job.status in (JobStatus.completed, JobStatus.failed, JobStatus.cancelled):
        await websocket.send_json({
            "type": "done",
            "job_id": job_id,
            "status": job.status.value,
            "error": job.error,
        })
        await websocket.close()
        return

    # Stream progress updates
    try:
        while True:
            if not job.progress_queue:
                await asyncio.sleep(0.5)
                continue

            try:
                msg = await asyncio.wait_for(job.progress_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                # Send heartbeat / current status
                if job.status in (JobStatus.completed, JobStatus.failed, JobStatus.cancelled):
                    break
                continue

            if msg is None:  # sentinel - job finished
                break

            await websocket.send_json({
                "type": "progress",
                "job_id": job_id,
                "status": job.status.value,
                "progress": msg.get("progress", 0),
                "current_frame": msg.get("current_frame", 0),
                "total_frames": msg.get("total_frames", 0),
                "eta_seconds": msg.get("eta_seconds"),
            })
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        # Send final status
        try:
            await websocket.send_json({
                "type": "done",
                "job_id": job_id,
                "status": job.status.value,
                "error": job.error,
            })
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass
