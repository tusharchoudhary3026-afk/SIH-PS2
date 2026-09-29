"""Deterministic, explainable sonar-image evidence features (heuristics only)."""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from .schemas import Detection


def _gray_float(image: Any) -> np.ndarray:
    array = np.asarray(image)
    if array.ndim == 3:
        if array.shape[2] >= 3:
            array = 0.299 * array[..., 0] + 0.587 * array[..., 1] + 0.114 * array[..., 2]
        else:
            array = array[..., 0]
    if array.ndim != 2 or not array.size:
        raise ValueError("image must be a non-empty grayscale or color array")
    values = array.astype(np.float64)
    finite = np.isfinite(values)
    if not finite.any():
        raise ValueError("image has no finite pixels")
    lo, hi = np.percentile(values[finite], [1, 99])
    if hi <= lo:
        out = np.zeros_like(values)
    else:
        out = np.clip((values - lo) / (hi - lo), 0.0, 1.0)
    out[~finite] = 0.0
    return out


def _regions(gray: np.ndarray, detection: Detection, context_scale: float = 1.8):
    h, w = gray.shape
    b = detection.bbox
    x1, y1 = max(0, int(math.floor(b.x1))), max(0, int(math.floor(b.y1)))
    x2, y2 = min(w, int(math.ceil(b.x2))), min(h, int(math.ceil(b.y2)))
    if x2 - x1 < 2 or y2 - y1 < 2:
        return None, None, {"valid": False, "reason": "bbox_empty_or_smaller_than_2px", "clipped_bbox": [x1, y1, x2, y2]}
    obj = gray[y1:y2, x1:x2]
    margin_x = max(2, int((x2 - x1) * context_scale))
    margin_y = max(2, int((y2 - y1) * context_scale))
    rx1, ry1, rx2, ry2 = max(0, x1 - margin_x), max(0, y1 - margin_y), min(w, x2 + margin_x), min(h, y2 + margin_y)
    context = gray[ry1:ry2, rx1:rx2].copy()
    context[y1 - ry1:y2 - ry1, x1 - rx1:x2 - rx1] = np.nan
    bg = context[np.isfinite(context)]
    info = {"valid": True, "clipped_bbox": [x1, y1, x2, y2], "context_bbox": [rx1, ry1, rx2, ry2],
            "object_pixels": int(obj.size), "background_pixels": int(bg.size)}
    return obj, bg, info


def extract_evidence(image: Any, detection: Detection) -> dict[str, Any]:
    """Return normalized shadow/contrast and geometric evidence plus diagnostics.

    Shadow score estimates whether a dark patch occurs immediately beyond the
    bbox along image y+. Its orientation is a heuristic, not physical sonar
    reconstruction; callers must retain these diagnostic caveats.
    """
    gray = _gray_float(image)
    if gray.shape != (detection.image_height, detection.image_width):
        raise ValueError("detector image dimensions do not match supplied image")
    obj, bg, region_info = _regions(gray, detection)
    b = detection.bbox
    width, height = max(0.0, b.x2 - b.x1), max(0.0, b.y2 - b.y1)
    area = width * height
    ratio = width / height if height > 0 else 0.0
    geometry = {
        "bbox_width": width, "bbox_height": height, "bbox_area": area,
        "aspect_ratio": ratio, "normalized_area": area / (detection.image_width * detection.image_height),
        "normalized_width": width / detection.image_width, "normalized_height": height / detection.image_height,
    }
    if obj is None or bg is None or not bg.size:
        return {**geometry, "shadow_consistency": None, "shadow_diagnostics": {**region_info, "method": "darkness in image-y+ strip versus local background", "available": False},
                "local_contrast": None, "contrast_diagnostics": {**region_info, "available": False},
                "object_mean_intensity": None, "background_mean_intensity": None, "contrast_difference": None}
    object_mean, background_mean = float(np.mean(obj)), float(np.mean(bg))
    difference = object_mean - background_mean
    local_contrast = float(np.clip(abs(difference) / max(float(np.std(bg)), 0.05), 0.0, 1.0))
    x1, y1, x2, y2 = region_info["clipped_bbox"]
    gray_h, gray_w = gray.shape
    depth = max(2, y2 - y1)
    strip_y1, strip_y2 = y2, min(gray_h, y2 + depth)
    if strip_y2 > strip_y1:
        strip = gray[strip_y1:strip_y2, max(0, x1 - (x2-x1)//2):min(gray_w, x2 + (x2-x1)//2)]
        shadow_mean = float(np.mean(strip)) if strip.size else None
    else:
        shadow_mean = None
    shadow_score = float(np.clip((background_mean - shadow_mean) / max(background_mean, 0.05), 0.0, 1.0)) if shadow_mean is not None else None
    return {
        **geometry,
        "shadow_consistency": shadow_score,
        "shadow_diagnostics": {**region_info, "available": shadow_score is not None, "method": "mean darkness in image-y+ strip relative to local background; heuristic only", "strip_mean_intensity": shadow_mean, "background_mean_intensity": background_mean},
        "local_contrast": local_contrast,
        "contrast_diagnostics": {**region_info, "available": True, "normalization": "abs(object mean - background mean) / max(background std, 0.05), clipped to [0,1]", "object_std": float(np.std(obj))},
        "object_mean_intensity": object_mean, "background_mean_intensity": background_mean, "contrast_difference": difference,
    }
