"""Extended watermark detection using multiple frames for better accuracy."""
import numpy as np
import cv2
from .engine import _find_ffmpeg, FFMPEG_BIN, _no_window, create_pixel_mask
import subprocess


def extract_frame_at(video_path: str, timestamp: float, width: int, height: int) -> np.ndarray | None:
    """Extract a single frame at a given timestamp."""
    _find_ffmpeg()
    cmd = [FFMPEG_BIN, "-ss", str(timestamp), "-i", str(video_path),
           "-vframes", "1", "-f", "rawvideo", "-pix_fmt", "bgr24", "-v", "quiet", "-"]
    result = subprocess.run(cmd, capture_output=True, creationflags=_no_window())
    if result.returncode != 0 or len(result.stdout) < width * height * 3:
        return None
    return np.frombuffer(result.stdout, dtype=np.uint8).reshape((height, width, 3)).copy()


def multi_frame_pixel_mask(video_path: str, region: tuple, sensitivity: int = 30,
                           num_samples: int = 5, duration: float = 0) -> np.ndarray:
    """Build a consensus pixel mask from multiple frames."""
    from .engine import get_video_info
    info = get_video_info(video_path)
    w, h = info["width"], info["height"]
    dur = duration or info["duration"]

    timestamps = [dur * (i + 1) / (num_samples + 1) for i in range(num_samples)]
    masks = []
    for ts in timestamps:
        frame = extract_frame_at(video_path, ts, w, h)
        if frame is not None:
            mask = create_pixel_mask(frame, region, sensitivity=sensitivity)
            masks.append(mask)

    if not masks:
        from .engine import extract_first_frame
        frame, _ = extract_first_frame(video_path)
        return create_pixel_mask(frame, region, sensitivity=sensitivity)

    # Consensus: pixel must appear in at least 60% of samples
    stacked = np.stack(masks, axis=0)
    consensus = (stacked > 0).sum(axis=0) >= max(1, len(masks) * 0.6)
    result = np.zeros((h, w), dtype=np.uint8)
    result[consensus] = 255

    # Light morphological close to fill gaps
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    result = cv2.morphologyEx(result, cv2.MORPH_CLOSE, kernel)
    return result
