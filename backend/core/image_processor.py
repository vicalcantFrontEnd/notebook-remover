"""
Image watermark removal processor.
Loads an image, applies inpainting using the same engine functions as video,
and saves the result.
"""

import cv2
import numpy as np
from pathlib import Path

from .engine import create_pixel_mask, create_box_mask, inpaint_frame, crop_frame, _inpaint_roi_lama


def load_image(path: str) -> np.ndarray:
    """Load an image file as a BGR numpy array (handles Unicode paths on Windows)."""
    buf = np.fromfile(str(Path(path).resolve()), dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Cannot load image: {path}")
    return img


def get_image_info(path: str) -> dict:
    """Return width and height of an image."""
    img = load_image(path)
    h, w = img.shape[:2]
    return {"width": w, "height": h}


def process_image(
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
    Remove watermark from a single image.

    Args:
        method: "pixel" | "box" | "crop"
        sensitivity: For pixel method, detection aggressiveness (5-80).
    """
    if cancel_flag and cancel_flag():
        return

    frame = load_image(input_path)

    if progress_callback:
        progress_callback(0, 1)

    if method == "pixel":
        mask = create_pixel_mask(frame, region, sensitivity=sensitivity)
        if mask.sum() < 100:
            mask = create_box_mask(frame.shape, region)
        cleaned = inpaint_frame(frame, mask, inpaint_radius)
    elif method == "box":
        mask = create_box_mask(frame.shape, region)
        cleaned = inpaint_frame(frame, mask, inpaint_radius)
    elif method == "lama":
        rx, ry, rw, rh = region
        mask = create_box_mask(frame.shape[:2], (rx, ry, rw, rh))
        cleaned = _inpaint_roi_lama(frame, mask, (rx, ry, rw, rh))
    else:  # crop
        cleaned = crop_frame(frame, region)

    if cancel_flag and cancel_flag():
        return

    # Determine output format from extension
    ext = Path(output_path).suffix.lower()
    params = []
    if ext in (".jpg", ".jpeg"):
        params = [cv2.IMWRITE_JPEG_QUALITY, 95]
    elif ext == ".webp":
        params = [cv2.IMWRITE_WEBP_QUALITY, 95]
    elif ext == ".png":
        params = [cv2.IMWRITE_PNG_COMPRESSION, 3]

    # Use imencode + tofile for Unicode path support on Windows
    _, buf = cv2.imencode(ext, cleaned, params)
    buf.tofile(str(Path(output_path).resolve()))

    if progress_callback:
        progress_callback(1, 1)
