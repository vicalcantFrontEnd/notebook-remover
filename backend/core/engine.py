"""
Core video watermark removal engine.
Uses FFmpeg for I/O and OpenCV inpainting for watermark removal.

Supports three removal methods:
  - "pixel":  Detects only the actual watermark text/logo pixels within the
              region and inpaints just those. Minimal visual impact.
  - "box":    Inpaints the entire rectangular region (original behaviour).
  - "crop":   Crops/zooms the video to exclude the watermark corner entirely.
"""

import subprocess
import json
import shutil
import glob
import os
import platform
import numpy as np
import cv2
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Pre-configured watermark regions for NotebookLM as fractions of (width, height).
# Format: (x_frac, y_frac, w_frac, h_frac)
NOTEBOOKLM_PRESETS = {
    "bottom_right": (0.75, 0.89, 0.23, 0.09),
}

REMOVAL_METHODS = ["pixel", "box", "crop", "lama"]

FFMPEG_BIN = None
FFPROBE_BIN = None


# ------------------------------------------------------------------ FFmpeg
def _find_ffmpeg():
    """Locate ffmpeg and ffprobe binaries (PATH or common install locations)."""
    global FFMPEG_BIN, FFPROBE_BIN
    if FFMPEG_BIN:
        return

    FFMPEG_BIN = shutil.which("ffmpeg")
    FFPROBE_BIN = shutil.which("ffprobe")

    if not FFMPEG_BIN:
        search_patterns = [
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\*ffmpeg*\*\bin\ffmpeg.exe"),
            r"C:\ffmpeg\bin\ffmpeg.exe",
            os.path.expandvars(r"%USERPROFILE%\scoop\apps\ffmpeg\current\bin\ffmpeg.exe"),
            r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
            # Linux / macOS common paths
            "/usr/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            "/snap/bin/ffmpeg",
        ]
        for pattern in search_patterns:
            matches = glob.glob(pattern)
            if matches:
                bin_dir = str(Path(matches[0]).parent)
                if platform.system() == "Windows":
                    FFMPEG_BIN = os.path.join(bin_dir, "ffmpeg.exe")
                    FFPROBE_BIN = os.path.join(bin_dir, "ffprobe.exe")
                else:
                    FFMPEG_BIN = os.path.join(bin_dir, "ffmpeg")
                    FFPROBE_BIN = os.path.join(bin_dir, "ffprobe")
                if os.path.isfile(FFMPEG_BIN) and os.path.isfile(FFPROBE_BIN):
                    break
                FFMPEG_BIN = FFPROBE_BIN = None
            elif not pattern.startswith(("%", "C:", "/")):
                continue
            else:
                # Direct path (non-glob), check if it exists
                if os.path.isfile(pattern):
                    bin_dir = str(Path(pattern).parent)
                    FFMPEG_BIN = pattern
                    FFPROBE_BIN = os.path.join(bin_dir, "ffprobe")
                    if platform.system() == "Windows":
                        FFPROBE_BIN = os.path.join(bin_dir, "ffprobe.exe")
                    if os.path.isfile(FFMPEG_BIN) and os.path.isfile(FFPROBE_BIN):
                        break
                    FFMPEG_BIN = FFPROBE_BIN = None

    if not FFMPEG_BIN:
        raise FileNotFoundError(
            "FFmpeg not found. Install it with:  winget install ffmpeg  (Windows) "
            "or  apt install ffmpeg  (Linux)\n"
            "Then restart this application."
        )
    if not FFPROBE_BIN:
        raise FileNotFoundError("FFprobe not found. It should come bundled with FFmpeg.")


def _no_window():
    if platform.system() == "Windows" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        return subprocess.CREATE_NO_WINDOW
    return 0


# ------------------------------------------------------------------ Video I/O
def get_video_info(video_path: str) -> dict:
    """Return video metadata via ffprobe."""
    _find_ffmpeg()
    cmd = [
        FFPROBE_BIN, "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, creationflags=_no_window())
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    data = json.loads(result.stdout)
    video_stream = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    if not video_stream:
        raise ValueError("No video stream found in file.")

    width = int(video_stream["width"])
    height = int(video_stream["height"])
    fps_str = video_stream.get("r_frame_rate", "30/1")
    num, den = map(int, fps_str.split("/"))
    fps = num / den if den else 30.0
    duration = float(data["format"].get("duration", 0))
    has_audio = any(s["codec_type"] == "audio" for s in data["streams"])

    return {
        "width": width, "height": height, "fps": fps,
        "duration": duration, "total_frames": int(duration * fps),
        "has_audio": has_audio,
    }


def extract_first_frame(video_path: str) -> tuple[np.ndarray, dict]:
    """Extract the first frame as a BGR numpy array, plus video info."""
    _find_ffmpeg()
    info = get_video_info(video_path)
    w, h = info["width"], info["height"]

    cmd = [
        FFMPEG_BIN, "-i", str(video_path),
        "-vframes", "1", "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-v", "quiet", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, creationflags=_no_window())
    if result.returncode != 0 or len(result.stdout) < w * h * 3:
        raise RuntimeError("Failed to extract first frame.")

    frame = np.frombuffer(result.stdout, dtype=np.uint8).reshape((h, w, 3))
    return frame.copy(), info


# ---------------------------------------------------------- Detection
def detect_watermark_region(frame: np.ndarray) -> tuple[int, int, int, int]:
    """
    Auto-detect the watermark region in a video frame.
    Returns a tight (x, y, w, h) in pixels.
    """
    h, w = frame.shape[:2]

    roi_x_start = int(w * 0.60)
    roi_y_start = int(h * 0.75)
    roi = frame[roi_y_start:, roi_x_start:]

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 40, 120)

    kernel = np.ones((5, 5), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=3)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        roi_h, roi_w = roi.shape[:2]
        candidates = [
            c for c in contours
            if cv2.boundingRect(c)[0] + cv2.boundingRect(c)[2] > roi_w * 0.3
            and cv2.boundingRect(c)[1] + cv2.boundingRect(c)[3] > roi_h * 0.3
        ]
        if candidates:
            all_pts = np.vstack(candidates)
            cx, cy, cw, ch = cv2.boundingRect(all_pts)
            pad = 10
            fx = max(0, roi_x_start + cx - pad)
            fy = max(0, roi_y_start + cy - pad)
            fw = min(w - fx, cw + 2 * pad)
            fh = min(h - fy, ch + 2 * pad)
            if 30 < fw < w * 0.40 and 15 < fh < h * 0.30:
                return (fx, fy, fw, fh)

    preset = NOTEBOOKLM_PRESETS["bottom_right"]
    return (int(w * preset[0]), int(h * preset[1]),
            int(w * preset[2]), int(h * preset[3]))


# ---------------------------------------------------------- Masks
def create_pixel_mask(
    frame: np.ndarray,
    region: tuple[int, int, int, int],
    sensitivity: int = 30,
    dilate_px: int = 2,
) -> np.ndarray:
    """
    Create a mask that covers ONLY the watermark text/logo pixels within
    *region*, leaving the background untouched.

    Works by detecting pixels in the ROI whose luminance deviates from the
    local median, which is characteristic of semi-transparent overlays.
    """
    h, w = frame.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    rx, ry, rw, rh = region

    roi = frame[ry : ry + rh, rx : rx + rw]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.float32)

    # Local median via heavy blur gives us the "expected" background
    bg = cv2.medianBlur(gray.astype(np.uint8), max(rw | 1, rh | 1) // 2 * 2 + 1)
    bg = bg.astype(np.float32)

    diff = np.abs(gray - bg)

    # Pixels that deviate enough from the background are watermark candidates
    roi_mask = (diff > sensitivity).astype(np.uint8) * 255

    # Improved morphology: close to connect strokes, then dilate for coverage
    if dilate_px > 0:
        k_close = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (dilate_px * 2 + 1, dilate_px * 2 + 1)
        )
        roi_mask = cv2.morphologyEx(roi_mask, cv2.MORPH_CLOSE, k_close)
        k_dilate = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (dilate_px + 1, dilate_px + 1)
        )
        roi_mask = cv2.dilate(roi_mask, k_dilate, iterations=1)

    mask[ry : ry + rh, rx : rx + rw] = roi_mask
    return mask


def create_box_mask(
    frame_shape: tuple,
    region: tuple[int, int, int, int],
) -> np.ndarray:
    """Create a solid rectangular mask (original behaviour)."""
    h, w = frame_shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    x, y, rw, rh = region
    mask[y : y + rh, x : x + rw] = 255
    return mask


# keep backwards compat
def create_mask(frame_shape, region, feather=3):
    return create_box_mask(frame_shape, region)


def _feather_mask(mask: np.ndarray, radius: int = 4) -> np.ndarray:
    """Create soft edges on a binary mask for seamless blending.

    Returns a float32 mask (0.0–1.0) where the watermark core stays ~1.0
    and edges transition smoothly to 0.0 over *radius* pixels.
    """
    if radius <= 0:
        return mask.astype(np.float32) / 255.0
    ksize = radius * 2 + 1
    soft = cv2.GaussianBlur(mask.astype(np.float32), (ksize, ksize), 0)
    return soft / 255.0


# ---------------------------------------------------------- Single-frame helpers
def inpaint_frame(frame: np.ndarray, mask: np.ndarray, radius: int = 3) -> np.ndarray:
    """Inpaint a single frame with professional feathered blending.

    Uses Navier-Stokes inpainting (smoother than Telea for text/logos)
    combined with a feathered mask to produce seamless transitions.
    """
    if mask.max() == 0:
        return frame

    # Navier-Stokes produces smoother fills for text and small logos
    inpainted = cv2.inpaint(frame, mask, radius, cv2.INPAINT_NS)

    # Feathered blend: core = fully inpainted, edges = smooth transition
    alpha = _feather_mask(mask, radius=4)
    alpha_3ch = np.stack([alpha] * 3, axis=-1)
    blended = (inpainted.astype(np.float32) * alpha_3ch +
               frame.astype(np.float32) * (1.0 - alpha_3ch))
    return np.clip(blended, 0, 255).astype(np.uint8)


def crop_frame(frame: np.ndarray, region: tuple[int, int, int, int]) -> np.ndarray:
    """
    Crop/zoom the frame to exclude the watermark corner.
    Determines which corner the region is in and removes it by cropping,
    then scales back to the original dimensions.
    """
    h, w = frame.shape[:2]
    rx, ry, rw, rh = region

    # Determine how much to crop from each edge
    crop_right = max(0, (rx + rw) - w + rw) if rx + rw > w * 0.5 else 0
    crop_bottom = max(0, (ry + rh) - h + rh) if ry + rh > h * 0.5 else 0
    crop_left = rw if rx < w * 0.3 else 0
    crop_top = rh if ry < h * 0.3 else 0

    # Simpler: just trim enough from the edge that contains the watermark
    # and rescale to original size
    if rx > w * 0.5:
        # watermark on the right side
        new_w = rx
    else:
        new_w = w
    if ry > h * 0.5:
        # watermark on the bottom side
        new_h = ry
    else:
        new_h = h

    cropped = frame[crop_top:new_h, crop_left:new_w]
    return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LANCZOS4)


# ---------------------------------------------------------- ROI inpaint helper
def _inpaint_roi(
    frame: np.ndarray,
    mask: np.ndarray,
    region: tuple[int, int, int, int],
    inpaint_radius: int,
    pad: int = 30,
) -> np.ndarray:
    """
    Inpaint only the watermark ROI (+ padding) with professional blending.

    Uses Navier-Stokes inpainting + feathered mask edges for seamless
    results.  Gives 10-50x speedup over full-frame inpaint.
    """
    h, w = frame.shape[:2]
    rx, ry, rw, rh = region
    x1 = max(0, rx - pad)
    y1 = max(0, ry - pad)
    x2 = min(w, rx + rw + pad)
    y2 = min(h, ry + rh + pad)

    roi = frame[y1:y2, x1:x2].copy()
    roi_mask = mask[y1:y2, x1:x2]

    if roi_mask.max() == 0:
        return frame

    # NS inpainting: smoother than Telea for text/logos
    inpainted = cv2.inpaint(roi, roi_mask, inpaint_radius, cv2.INPAINT_NS)

    # Feathered blending for invisible transitions
    alpha = _feather_mask(roi_mask, radius=4)
    alpha_3ch = np.stack([alpha] * 3, axis=-1)
    blended = (inpainted.astype(np.float32) * alpha_3ch +
               roi.astype(np.float32) * (1.0 - alpha_3ch))

    result = frame.copy()
    result[y1:y2, x1:x2] = np.clip(blended, 0, 255).astype(np.uint8)
    return result


# ---------------------------------------------------------- LaMa ROI inpaint
def _inpaint_roi_lama(
    frame: np.ndarray,
    mask: np.ndarray,
    region: tuple[int, int, int, int],
    pad: int = 30,
) -> np.ndarray:
    """
    Inpaint the watermark ROI using LaMa (AI) with feathered blending.

    Extracts the ROI + padding, runs LaMa inference on the crop,
    then blends it back into the original frame.
    """
    from .lama_inpainter import lama_inpaint

    h, w = frame.shape[:2]
    rx, ry, rw, rh = region
    x1 = max(0, rx - pad)
    y1 = max(0, ry - pad)
    x2 = min(w, rx + rw + pad)
    y2 = min(h, ry + rh + pad)

    roi = frame[y1:y2, x1:x2].copy()
    roi_mask = mask[y1:y2, x1:x2]

    if roi_mask.max() == 0:
        return frame

    inpainted = lama_inpaint(roi, roi_mask)

    # Feathered blending for invisible transitions
    alpha = _feather_mask(roi_mask, radius=4)
    alpha_3ch = np.stack([alpha] * 3, axis=-1)
    blended = (inpainted.astype(np.float32) * alpha_3ch +
               roi.astype(np.float32) * (1.0 - alpha_3ch))

    result = frame.copy()
    result[y1:y2, x1:x2] = np.clip(blended, 0, 255).astype(np.uint8)
    return result


# ---------------------------------------------------------- Video processing
def process_video(
    input_path: str,
    output_path: str,
    region: tuple[int, int, int, int],
    trim_end_seconds: float = 0.0,
    inpaint_radius: int = 3,
    method: str = "pixel",
    sensitivity: int = 30,
    progress_callback=None,
    cancel_flag=None,
):
    """
    Remove watermark and optionally trim end of video.

    Args:
        method: "pixel" | "box" | "crop"
        sensitivity: For pixel method, how aggressively to detect watermark
                     pixels (lower = more aggressive). Range 10-80.
    """
    _find_ffmpeg()
    info = get_video_info(input_path)
    w, h = info["width"], info["height"]
    fps = info["fps"]
    duration = info["duration"]

    effective_duration = max(0.1, duration - trim_end_seconds)
    total_frames = int(effective_duration * fps)

    # Pre-compute mask for pixel/box methods (same for every frame)
    mask = None
    if method == "pixel":
        # Multi-frame consensus mask: sample several frames for a more
        # accurate and stable watermark mask across the whole video.
        from .engine_extensions import multi_frame_pixel_mask
        mask = multi_frame_pixel_mask(
            input_path, region, sensitivity=sensitivity,
            num_samples=5, duration=effective_duration,
        )
        # If pixel detection found almost nothing, fall back to a thin box
        if mask.sum() < 100:
            mask = create_box_mask((h, w), region)
    elif method == "box":
        mask = create_box_mask((h, w), region)
    elif method == "lama":
        mask = create_box_mask((h, w), region)

    nw = _no_window()

    # --- Reader ---
    read_cmd = [FFMPEG_BIN, "-v", "quiet"]
    if trim_end_seconds > 0:
        read_cmd += ["-t", f"{effective_duration:.3f}"]
    read_cmd += ["-i", str(input_path), "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]

    # --- Writer ---
    write_cmd = [
        FFMPEG_BIN, "-y", "-v", "quiet",
        "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-s", f"{w}x{h}", "-r", str(fps), "-i", "pipe:0",
    ]
    if info["has_audio"]:
        if trim_end_seconds > 0:
            write_cmd += ["-t", f"{effective_duration:.3f}"]
        write_cmd += ["-i", str(input_path), "-map", "0:v", "-map", "1:a", "-c:a", "copy"]
    write_cmd += [
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-pix_fmt", "yuv420p", str(output_path),
    ]

    reader = subprocess.Popen(read_cmd, stdout=subprocess.PIPE, creationflags=nw)
    writer = subprocess.Popen(write_cmd, stdin=subprocess.PIPE, creationflags=nw)

    frame_size = w * h * 3
    frame_count = 0

    # Number of parallel workers — leave 1 core for I/O
    num_workers = max(2, min(8, (os.cpu_count() or 4) - 1))
    # Buffer: keep up to 2× workers frames in-flight to overlap I/O and compute
    buffer_size = num_workers * 2

    def _process(frame_bytes: bytes):
        frame = np.frombuffer(frame_bytes, dtype=np.uint8).reshape((h, w, 3)).copy()
        if method in ("pixel", "box"):
            return _inpaint_roi(frame, mask, region, inpaint_radius)
        if method == "lama":
            return _inpaint_roi_lama(frame, mask, region, pad=30)
        return crop_frame(frame, region)

    try:
        with ThreadPoolExecutor(max_workers=num_workers) as pool:
            pending = []  # list of Future, kept in submission order

            while True:
                if cancel_flag and cancel_flag():
                    break

                raw = reader.stdout.read(frame_size)
                if len(raw) < frame_size:
                    break

                pending.append(pool.submit(_process, raw))

                # When buffer is full, drain the oldest frame first (keeps order)
                while len(pending) >= buffer_size:
                    cleaned = pending.pop(0).result()
                    writer.stdin.write(cleaned.tobytes())
                    frame_count += 1
                    if progress_callback and frame_count % 3 == 0:
                        progress_callback(frame_count, total_frames)

            # Drain remaining in-flight frames
            for fut in pending:
                cleaned = fut.result()
                writer.stdin.write(cleaned.tobytes())
                frame_count += 1

    finally:
        try:
            writer.stdin.close()
        except Exception:
            pass
        writer.wait()
        reader.terminate()
        reader.wait()

    if progress_callback:
        progress_callback(total_frames, total_frames)

    return frame_count
