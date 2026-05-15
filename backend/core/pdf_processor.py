"""
PDF watermark removal processor.
Uses PyMuPDF redaction to remove only the watermark region,
preserving the original PDF content and keeping file size minimal.
"""

import numpy as np
import cv2
import fitz  # PyMuPDF
from pathlib import Path

from .engine import create_pixel_mask, create_box_mask, inpaint_frame


def get_pdf_info(path: str) -> dict:
    """Return width, height (of first page), and page count."""
    doc = fitz.open(str(Path(path).resolve()))
    page = doc[0]
    rect = page.rect
    page_count = len(doc)
    doc.close()
    return {
        "width": int(rect.width),
        "height": int(rect.height),
        "page_count": page_count,
    }


def extract_first_page_image(path: str) -> np.ndarray:
    """Render the first page of a PDF as a BGR numpy array."""
    doc = fitz.open(str(Path(path).resolve()))
    page = doc[0]
    # Render at 2x for good quality
    mat = fitz.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=mat)
    # Convert pixmap to numpy array (RGB)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
    if pix.n == 4:  # RGBA
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    else:  # RGB
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    doc.close()
    return img


def _render_page(page: fitz.Page, scale: float = 2.0) -> np.ndarray:
    """Render a single PDF page to a BGR numpy array."""
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
    if pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    else:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    return img


def process_pdf(
    input_path: str,
    output_path: str,
    region: tuple[int, int, int, int],
    method: str = "pixel",
    sensitivity: int = 30,
    inpaint_radius: int = 3,
    progress_callback=None,
    cancel_flag=None,
) -> None:
    """
    Remove watermark from all pages of a PDF.

    Uses a hybrid approach:
    1. Renders only the watermark region at 2x scale
    2. Inpaints just that region
    3. Pastes the cleaned region back as a small image overlay
    4. Original PDF content is preserved — file size stays close to original
    """
    doc = fitz.open(str(input_path))
    total_pages = len(doc)
    scale = 2.0

    # Region coordinates are at 2x scale, convert to PDF coordinates (1x)
    rx, ry, rw, rh = region
    pdf_x = rx / scale
    pdf_y = ry / scale
    pdf_w = rw / scale
    pdf_h = rh / scale

    for i in range(total_pages):
        if cancel_flag and cancel_flag():
            doc.close()
            return

        page = doc[i]
        page_rect = page.rect

        # Clip the region to the page bounds
        clip_x = min(pdf_x, page_rect.width)
        clip_y = min(pdf_y, page_rect.height)
        clip_x2 = min(pdf_x + pdf_w, page_rect.width)
        clip_y2 = min(pdf_y + pdf_h, page_rect.height)

        if clip_x2 <= clip_x or clip_y2 <= clip_y:
            if progress_callback:
                progress_callback(i + 1, total_pages)
            continue

        clip_rect = fitz.Rect(clip_x, clip_y, clip_x2, clip_y2)

        # Render only the watermark region at 2x scale
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, clip=clip_rect)
        roi_img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        if pix.n == 4:
            roi_img = cv2.cvtColor(roi_img, cv2.COLOR_RGBA2BGR)
        else:
            roi_img = cv2.cvtColor(roi_img, cv2.COLOR_RGB2BGR)

        # Create mask for the ROI
        roi_h, roi_w = roi_img.shape[:2]
        if method == "pixel":
            # For pixel method, detect watermark pixels within the ROI
            full_region = (0, 0, roi_w, roi_h)
            roi_mask = create_pixel_mask(roi_img, full_region, sensitivity=sensitivity)
            if roi_mask.sum() < 100:
                roi_mask = create_box_mask(roi_img.shape, full_region)
        else:  # box
            roi_mask = create_box_mask(roi_img.shape, (0, 0, roi_w, roi_h))

        # Inpaint just the watermark region
        cleaned_roi = inpaint_frame(roi_img, roi_mask, inpaint_radius)

        # Encode the cleaned region as JPEG
        _, jpg_buf = cv2.imencode(".jpg", cleaned_roi, [cv2.IMWRITE_JPEG_QUALITY, 92])
        img_bytes = jpg_buf.tobytes()

        # Paste the cleaned region back over the original page
        page.insert_image(clip_rect, stream=img_bytes, overlay=True)

        if progress_callback:
            progress_callback(i + 1, total_pages)

    # Save with incremental-style compression
    doc.save(str(Path(output_path).resolve()), garbage=4, deflate=True)
    doc.close()
