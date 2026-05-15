import base64
import os
import cv2
import numpy as np
from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pathlib import Path

from .schemas import (
    VideoInfo, FileInfo, FileType, DetectResponse, Region,
    PreviewRequest, PreviewResponse,
    JobCreate, JobInfo, JobListResponse,
)
from ..services.upload_service import upload_service
from ..services.job_service import job_service
from ..core.engine import (
    extract_first_frame, detect_watermark_region, get_video_info,
    create_pixel_mask, create_box_mask, inpaint_frame, crop_frame,
)

router = APIRouter(prefix="/api")

# Extension → FileType mapping
_VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm"}
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
_PDF_EXTS = {".pdf"}
_PPTX_EXTS = {".pptx"}


def _detect_file_type(filename: str) -> FileType:
    """Detect file type from extension."""
    ext = Path(filename).suffix.lower()
    if ext in _VIDEO_EXTS:
        return FileType.video
    if ext in _IMAGE_EXTS:
        return FileType.image
    if ext in _PDF_EXTS:
        return FileType.pdf
    if ext in _PPTX_EXTS:
        return FileType.pptx
    return FileType.video  # fallback


def _get_mime_type(file_path: str) -> str:
    """Get MIME type from file extension."""
    ext = Path(file_path).suffix.lower()
    mime_map = {
        ".mp4": "video/mp4", ".webm": "video/webm", ".mkv": "video/x-matroska",
        ".avi": "video/x-msvideo", ".mov": "video/quicktime",
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
        ".pdf": "application/pdf",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    return mime_map.get(ext, "application/octet-stream")


def _frame_to_base64(frame_bgr: np.ndarray, quality: int = 85) -> str:
    """Encode a BGR frame as base64 JPEG."""
    _, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(buf.tobytes()).decode("utf-8")


# ---- Upload ----
@router.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    result = await upload_service.save_upload(file)
    return result


# ---- Video Info (legacy, kept for compatibility) ----
@router.get("/video/{file_id}/info", response_model=VideoInfo)
async def video_info(file_id: str):
    file_path = upload_service.get_file_path(file_id)
    frame, info = extract_first_frame(file_path)
    frame_b64 = _frame_to_base64(frame)
    filename = upload_service.get_filename(file_id)
    return VideoInfo(
        file_id=file_id,
        filename=filename,
        width=info["width"],
        height=info["height"],
        fps=info["fps"],
        duration=info["duration"],
        total_frames=info["total_frames"],
        has_audio=info["has_audio"],
        first_frame_base64=frame_b64,
    )


# ---- Generic File Info ----
@router.get("/file/{file_id}/info", response_model=FileInfo)
async def file_info(file_id: str):
    """Get info for any supported file type."""
    import traceback as _tb
    try:
        return await _file_info_inner(file_id)
    except HTTPException:
        raise
    except Exception as e:
        _tb.print_exc()
        raise HTTPException(500, str(e))

async def _file_info_inner(file_id: str):
    file_path = upload_service.get_file_path(file_id)
    filename = upload_service.get_filename(file_id)
    file_type = _detect_file_type(filename)

    if file_type == FileType.video:
        frame, info = extract_first_frame(file_path)
        return FileInfo(
            file_id=file_id, filename=filename, file_type=file_type,
            width=info["width"], height=info["height"],
            fps=info["fps"], duration=info["duration"],
            total_frames=info["total_frames"], has_audio=info["has_audio"],
            first_frame_base64=_frame_to_base64(frame),
        )

    if file_type == FileType.image:
        from ..core.image_processor import load_image
        img = load_image(file_path)
        h, w = img.shape[:2]
        return FileInfo(
            file_id=file_id, filename=filename, file_type=file_type,
            width=w, height=h,
            first_frame_base64=_frame_to_base64(img),
        )

    if file_type == FileType.pdf:
        from ..core.pdf_processor import get_pdf_info, extract_first_page_image
        info = get_pdf_info(file_path)
        page_img = extract_first_page_image(file_path)
        return FileInfo(
            file_id=file_id, filename=filename, file_type=file_type,
            width=page_img.shape[1], height=page_img.shape[0],
            page_count=info["page_count"],
            first_frame_base64=_frame_to_base64(page_img),
        )

    if file_type == FileType.pptx:
        from ..core.pptx_processor import get_pptx_info, extract_first_slide_image
        info = get_pptx_info(file_path)
        slide_img = extract_first_slide_image(file_path)
        return FileInfo(
            file_id=file_id, filename=filename, file_type=file_type,
            width=info["width"], height=info["height"],
            page_count=info["slide_count"],
            first_frame_base64=_frame_to_base64(slide_img),
        )

    raise HTTPException(400, f"Unsupported file type: {file_type}")


# ---- Page image (PDF/PPTX page navigation) ----
@router.get("/file/{file_id}/page/{page_index}")
async def get_page_image(file_id: str, page_index: int):
    """Return a base64 JPEG of a specific page (0-indexed) for PDF/PPTX files."""
    file_path = upload_service.get_file_path(file_id)
    filename = upload_service.get_filename(file_id)
    file_type = _detect_file_type(filename)

    if file_type == FileType.pdf:
        import fitz
        doc = fitz.open(str(file_path))
        if page_index < 0 or page_index >= len(doc):
            doc.close()
            raise HTTPException(400, f"Page {page_index} out of range (0-{len(doc)-1})")
        page = doc[page_index]
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        doc.close()
        return {"page_index": page_index, "image_base64": _frame_to_base64(img)}

    if file_type == FileType.pptx:
        from ..core.pptx_processor import extract_slide_image
        img = extract_slide_image(file_path, page_index)
        return {"page_index": page_index, "image_base64": _frame_to_base64(img)}

    raise HTTPException(400, "Page navigation only supported for PDF and PPTX files")


# ---- Stream (video playback / file serving) ----
@router.get("/video/{file_id}/stream")
async def stream_video(file_id: str, request: Request):
    """Serve the uploaded video file with range request support for seeking."""
    file_path = upload_service.get_file_path(file_id)
    file_size = os.path.getsize(file_path)

    media_type = _get_mime_type(file_path)

    range_header = request.headers.get("range")
    if range_header:
        range_str = range_header.replace("bytes=", "")
        parts = range_str.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else file_size - 1
        end = min(end, file_size - 1)
        content_length = end - start + 1

        def iter_range():
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    chunk_size = min(1024 * 1024, remaining)
                    data = f.read(chunk_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return StreamingResponse(
            iter_range(),
            status_code=206,
            media_type=media_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
            },
        )

    return FileResponse(file_path, media_type=media_type, headers={"Accept-Ranges": "bytes"})


# ---- Generic file stream ----
@router.get("/file/{file_id}/stream")
async def stream_file(file_id: str, request: Request):
    """Serve any uploaded file (image, PDF, etc.)."""
    return await stream_video(file_id, request)


# ---- Detect ----
@router.post("/video/{file_id}/detect", response_model=DetectResponse)
async def detect_region(file_id: str):
    file_path = upload_service.get_file_path(file_id)
    frame, _ = extract_first_frame(file_path)
    x, y, w, h = detect_watermark_region(frame)
    return DetectResponse(region=Region(x=x, y=y, w=w, h=h))


@router.post("/file/{file_id}/detect", response_model=DetectResponse)
async def detect_file_region(file_id: str):
    """Auto-detect watermark region for any file type."""
    file_path = upload_service.get_file_path(file_id)
    filename = upload_service.get_filename(file_id)
    file_type = _detect_file_type(filename)

    if file_type == FileType.video:
        frame, _ = extract_first_frame(file_path)
    elif file_type == FileType.image:
        from ..core.image_processor import load_image
        frame = load_image(file_path)
    elif file_type == FileType.pdf:
        from ..core.pdf_processor import extract_first_page_image
        frame = extract_first_page_image(file_path)
    elif file_type == FileType.pptx:
        from ..core.pptx_processor import extract_first_slide_image
        frame = extract_first_slide_image(file_path)
    else:
        raise HTTPException(400, "Cannot detect region for this file type")

    x, y, w, h = detect_watermark_region(frame)
    return DetectResponse(region=Region(x=x, y=y, w=w, h=h))


# ---- Preview ----
@router.post("/video/{file_id}/preview", response_model=PreviewResponse)
async def preview_removal(file_id: str, req: PreviewRequest):
    file_path = upload_service.get_file_path(file_id)
    frame, _ = extract_first_frame(file_path)
    region = (req.region.x, req.region.y, req.region.w, req.region.h)

    if req.method.value == "pixel":
        mask = create_pixel_mask(frame, region, sensitivity=req.sensitivity)
        cleaned = inpaint_frame(frame, mask, req.inpaint_radius)
    elif req.method.value == "box":
        mask = create_box_mask(frame.shape, region)
        cleaned = inpaint_frame(frame, mask, req.inpaint_radius)
    else:
        cleaned = crop_frame(frame, region)

    return PreviewResponse(
        preview_base64=_frame_to_base64(cleaned),
        method=req.method.value,
    )


@router.post("/file/{file_id}/preview", response_model=PreviewResponse)
async def preview_file_removal(file_id: str, req: PreviewRequest):
    """Preview watermark removal for any file type."""
    file_path = upload_service.get_file_path(file_id)
    filename = upload_service.get_filename(file_id)
    file_type = _detect_file_type(filename)

    # For PPTX with delete_shapes, no visual preview is available
    if file_type == FileType.pptx and req.method.value == "delete_shapes":
        from ..core.pptx_processor import extract_first_slide_image
        frame = extract_first_slide_image(file_path)
        # Draw a translucent overlay on the region to show what will be removed
        region = (req.region.x, req.region.y, req.region.w, req.region.h)
        preview = frame.copy()
        overlay = preview.copy()
        cv2.rectangle(overlay, (region[0], region[1]),
                      (region[0] + region[2], region[1] + region[3]),
                      (0, 0, 255), -1)
        cv2.addWeighted(overlay, 0.3, preview, 0.7, 0, preview)
        return PreviewResponse(
            preview_base64=_frame_to_base64(preview),
            method=req.method.value,
        )

    # Get the frame/image for the file type
    if file_type == FileType.video:
        frame, _ = extract_first_frame(file_path)
    elif file_type == FileType.image:
        from ..core.image_processor import load_image
        frame = load_image(file_path)
    elif file_type == FileType.pdf:
        from ..core.pdf_processor import extract_first_page_image
        frame = extract_first_page_image(file_path)
    elif file_type == FileType.pptx:
        from ..core.pptx_processor import extract_first_slide_image
        frame = extract_first_slide_image(file_path)
    else:
        raise HTTPException(400, "Cannot preview this file type")

    region = (req.region.x, req.region.y, req.region.w, req.region.h)

    if req.method.value == "pixel":
        mask = create_pixel_mask(frame, region, sensitivity=req.sensitivity)
        cleaned = inpaint_frame(frame, mask, req.inpaint_radius)
    elif req.method.value == "box":
        mask = create_box_mask(frame.shape, region)
        cleaned = inpaint_frame(frame, mask, req.inpaint_radius)
    else:
        cleaned = crop_frame(frame, region)

    return PreviewResponse(
        preview_base64=_frame_to_base64(cleaned),
        method=req.method.value,
    )


# ---- Jobs ----
@router.post("/jobs", status_code=202, response_model=JobInfo)
async def create_job(req: JobCreate):
    file_path = upload_service.get_file_path(req.file_id)
    filename = upload_service.get_filename(req.file_id)
    job = await job_service.create_job(req, file_path, filename)
    return job.to_info()


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs():
    return JobListResponse(jobs=job_service.list_jobs())


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    success = job_service.cancel_job(job_id)
    if not success:
        raise HTTPException(404, "Job not found or already finished")
    return {"status": "cancelled"}


@router.get("/jobs/{job_id}/download")
async def download_job(job_id: str):
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status.value != "completed":
        raise HTTPException(400, "Job not completed yet")
    if not job.output_path or not Path(job.output_path).exists():
        raise HTTPException(404, "Output file not found")

    media_type = _get_mime_type(job.output_path)
    return FileResponse(
        job.output_path,
        media_type=media_type,
        filename=Path(job.output_path).name,
    )


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    job_service.delete_job(job_id)
    return {"status": "deleted"}
