"""Stable Engine 4 -> Engine 5 and Engine 5 result contracts.

Bounding boxes are pixel coordinates in ``xyxy`` order, relative to the
original image. Detector confidence is a raw score in [0, 1], never a
calibrated probability by implication.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any


@dataclass(frozen=True)
class BBox:
    x1: float
    y1: float
    x2: float
    y2: float

    def to_list(self) -> list[float]:
        return [self.x1, self.y1, self.x2, self.y2]


@dataclass(frozen=True)
class Detection:
    detection_id: str
    image_id: str
    class_id: int
    class_name: str
    bbox: BBox
    raw_confidence: float
    image_width: int
    image_height: int
    source_dataset: str = "UNKNOWN"
    provenance: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Detection":
        box = value["bbox"]
        if isinstance(box, dict):
            bbox = BBox(**{key: float(box[key]) for key in ("x1", "y1", "x2", "y2")})
        else:
            if len(box) != 4:
                raise ValueError("bbox must contain x1,y1,x2,y2 pixel coordinates")
            bbox = BBox(*map(float, box))
        result = cls(
            detection_id=str(value["detection_id"]), image_id=str(value["image_id"]),
            class_id=int(value["class_id"]), class_name=str(value["class_name"]), bbox=bbox,
            raw_confidence=float(value["raw_confidence"]), image_width=int(value["image_width"]),
            image_height=int(value["image_height"]), source_dataset=str(value.get("source_dataset") or "UNKNOWN"),
            provenance=dict(value.get("provenance") or {}),
        )
        if not result.detection_id or not result.image_id or not result.class_name:
            raise ValueError("detection_id, image_id, and class_name are required")
        if result.image_width <= 0 or result.image_height <= 0:
            raise ValueError("image dimensions must be positive")
        if not all(math.isfinite(v) for v in bbox.to_list()):
            raise ValueError("bbox coordinates must be finite")
        if bbox.x2 <= bbox.x1 or bbox.y2 <= bbox.y1:
            raise ValueError("bbox must have positive width and height")
        if not 0 <= result.raw_confidence <= 1:
            raise ValueError("raw_confidence must be in [0, 1]")
        return result


@dataclass
class ScoredDetection:
    detection_id: str
    image_id: str
    class_id: int
    class_name: str
    bbox: list[float]
    raw_confidence: float
    shadow_consistency: float | None
    shadow_diagnostics: dict[str, Any]
    local_contrast: float | None
    contrast_diagnostics: dict[str, Any]
    object_mean_intensity: float | None
    background_mean_intensity: float | None
    contrast_difference: float | None
    bbox_width: float
    bbox_height: float
    bbox_area: float
    aspect_ratio: float
    normalized_area: float
    normalized_width: float
    normalized_height: float
    fusion_score: float | None
    calibrated_confidence: float | None
    confidence_status: str
    false_positive_status: str
    reason_codes: list[str]
    evidence_scores: dict[str, float | None]
    source_dataset: str
    provenance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
