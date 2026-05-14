"""
LaMa (Large Mask Inpainting) via ONNX Runtime.

Singleton module: downloads the model on first use (~208 MB) from
Carve/LaMa-ONNX on Hugging Face, then keeps a single ONNX session
alive for all subsequent calls.
"""

import numpy as np
import cv2
import onnxruntime as ort

_session: ort.InferenceSession | None = None
_MODEL_SIZE = 512


def _get_session() -> ort.InferenceSession:
    """Lazy-load the ONNX model. Downloads ~208 MB on first use."""
    global _session
    if _session is None:
        from huggingface_hub import hf_hub_download

        model_path = hf_hub_download("Carve/LaMa-ONNX", "lama_fp32.onnx")
        _session = ort.InferenceSession(
            model_path, providers=["CPUExecutionProvider"]
        )
    return _session


def lama_inpaint(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    Run LaMa inpainting on an arbitrary-sized BGR image + binary mask.

    Args:
        image: BGR uint8 array (H, W, 3).
        mask:  Single-channel uint8 array (H, W) where 255 = area to inpaint.

    Returns:
        BGR uint8 array with the masked region filled in.
    """
    orig_h, orig_w = image.shape[:2]

    # Resize to model input size
    img_rs = cv2.resize(image, (_MODEL_SIZE, _MODEL_SIZE), interpolation=cv2.INTER_LANCZOS4)
    mask_rs = cv2.resize(mask, (_MODEL_SIZE, _MODEL_SIZE), interpolation=cv2.INTER_NEAREST)

    # Normalize image: BGR -> RGB, [0,1], CHW, add batch dim
    img_rgb = cv2.cvtColor(img_rs, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    img_chw = np.transpose(img_rgb, (2, 0, 1))  # (3, 512, 512)
    img_batch = np.expand_dims(img_chw, axis=0)  # (1, 3, 512, 512)

    # Normalize mask: binarize -> [0,1], 1HW, add batch dim
    mask_bin = (mask_rs > 127).astype(np.float32)
    mask_batch = mask_bin[np.newaxis, np.newaxis, :, :]  # (1, 1, 512, 512)

    # Run inference
    session = _get_session()
    input_name_img = session.get_inputs()[0].name
    input_name_mask = session.get_inputs()[1].name
    output_name = session.get_outputs()[0].name

    result = session.run(
        [output_name],
        {input_name_img: img_batch, input_name_mask: mask_batch},
    )[0]  # (1, 3, 512, 512)

    # Denormalize: CHW -> HWC, [0,1] -> [0,255], RGB -> BGR
    out_chw = result[0]  # (3, 512, 512)
    out_hwc = np.transpose(out_chw, (1, 2, 0))  # (512, 512, 3)
    out_hwc = np.clip(out_hwc * 255.0, 0, 255).astype(np.uint8)
    out_bgr = cv2.cvtColor(out_hwc, cv2.COLOR_RGB2BGR)

    # Resize back to original dimensions
    if (orig_h, orig_w) != (_MODEL_SIZE, _MODEL_SIZE):
        out_bgr = cv2.resize(out_bgr, (orig_w, orig_h), interpolation=cv2.INTER_LANCZOS4)

    return out_bgr
