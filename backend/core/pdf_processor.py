"""
PDF watermark removal processor.
Renders each page as an image, applies inpainting, and reassembles into a new PDF.
Uses PyMuPDF (fitz) for PDF I/O.
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

    The region coordinates are relative to the first page rendered at 2x scale.
    Each page is rendered, inpainted, then inserted back into a new PDF.
    """
    doc = fitz.open(str(input_path))
    total_pages = len(doc)
    scale = 2.0

    # Pre-compute mask from first page
    first_page_img = _render_page(doc[0], scale)
    if method == "pixel":
        mask = create_pixel_mask(first_page_img, region, sensitivity=sensitivity)
        if mask.sum() < 100:
            mask = create_box_mask(first_page_img.shape, region)
    else:  # box
        mask = create_box_mask(first_page_img.shape, region)

    # Create new PDF with inpainted pages
    out_doc = fitz.open()

    for i in range(total_pages):
        if cancel_flag and cancel_flag():
            out_doc.close()
            doc.close()
            return

        page = doc[i]
        page_img = _render_page(page, scale)

        # Resize mask if page dimensions differ from first page
        if page_img.shape[:2] != mask.shape[:2]:
            page_mask = cv2.resize(mask, (page_img.shape[1], page_img.shape[0]),
                                   interpolation=cv2.INTER_NEAREST)
        else:
            page_mask = mask

        cleaned = inpaint_frame(page_img, page_mask, inpaint_radius)

        # Create new page with same dimensions as original
        rect = page.rect
        new_page = out_doc.new_page(width=rect.width, height=rect.height)

        # Encode cleaned image as JPEG (much smaller than PNG)
        _, jpg_buf = cv2.imencode(".jpg", cleaned, [cv2.IMWRITE_JPEG_QUALITY, 90])
        img_bytes = jpg_buf.tobytes()
        new_page.insert_image(rect, stream=img_bytes)

        if progress_callback:
            progress_callback(i + 1, total_pages)

    # Save with compression and garbage collection to minimize file size
    out_doc.save(str(Path(output_path).resolve()), garbage=4, deflate=True)
    out_doc.close()
    doc.close()

