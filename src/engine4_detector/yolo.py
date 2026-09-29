"""Ultralytics YOLO inference adapter with overlap-aware full-image tiling.

Ultralytics is an optional dependency. The adapter loads a caller-supplied
checkpoint and never downloads weights or claims that an untrained model is
project-validated.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from engine5_confidence.schemas import BBox, Detection

CORE_CLASS_NAMES = ("Pipe", "Shipwreck", "Mine-like Contact", "Crab Pot")
_CLASS_ALIASES = {
    "pipe": 0,
    "shipwreck": 1,
    "mine_like": 2,
    "mine-like": 2,
    "mine_like_contact": 2,
    "mine-like_contact": 2,
    "mine-like contact": 2,
    "crab_pot": 3,
    "crab pot": 3,
}


def _tile_starts(length: int, tile: int, overlap: int) -> list[int]:
    if length <= tile:
        return [0]
    stride = tile - overlap
    starts = list(range(0, length - tile + 1, stride))
    if starts[-1] != length - tile:
        starts.append(length - tile)
    return starts


def _box_iou(left: list[float], right: list[float]) -> float:
    x1, y1 = max(left[0], right[0]), max(left[1], right[1])
    x2, y2 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union > 0 else 0.0


class YOLODetector:
    """Adapt a four-class Ultralytics checkpoint to the stable Detection schema."""

    mode = "REAL"

    def __init__(self, weights: str | Path, *, confidence: float = 0.25,
                 tile_size: int = 640, overlap: int = 160, merge_iou: float = 0.5,
                 device: str | int | None = None, model: Any | None = None):
        self.weights = Path(weights).expanduser().resolve()
        if model is None and not self.weights.is_file():
            raise FileNotFoundError(f"YOLO weights not found: {self.weights}")
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be in [0, 1]")
        if tile_size < 1 or overlap < 0 or overlap >= tile_size:
            raise ValueError("overlap must be non-negative and smaller than tile_size")
        if not 0 < merge_iou <= 1:
            raise ValueError("merge_iou must be in (0, 1]")
        if model is None:
            try:
                from ultralytics import YOLO
            except ImportError as exc:
                raise RuntimeError("Install requirements-engine4.txt to use a real YOLO detector") from exc
            model = YOLO(str(self.weights))
        self.model = model
        self.confidence = confidence
        self.tile_size = tile_size
        self.overlap = overlap
        self.merge_iou = merge_iou
        self.device = device
        self.class_ids = self._validate_model_classes(getattr(model, "names", None))

    @staticmethod
    def _validate_model_classes(names: Any) -> dict[int, int]:
        if isinstance(names, dict):
            source_names = {int(key): str(value) for key, value in names.items()}
        elif isinstance(names, (list, tuple)):
            source_names = dict(enumerate(map(str, names)))
        else:
            raise ValueError("YOLO checkpoint must expose four named classes")
        mapped: dict[int, int] = {}
        for source_id, name in source_names.items():
            key = name.strip().lower().replace(" ", "_")
            if key not in _CLASS_ALIASES:
                raise ValueError(f"Unexpected detector class {name!r}; expected the four SIH core classes")
            mapped[source_id] = _CLASS_ALIASES[key]
        if set(mapped.values()) != set(range(len(CORE_CLASS_NAMES))) or len(mapped) != 4:
            raise ValueError("YOLO checkpoint class names must map exactly to Pipe, Shipwreck, Mine-like Contact, Crab Pot")
        return mapped

    def _tiles(self, image: np.ndarray):
        height, width = image.shape[:2]
        if width <= self.tile_size and height <= self.tile_size:
            yield 0, 0, image
            return
        for top in _tile_starts(height, self.tile_size, self.overlap):
            for left in _tile_starts(width, self.tile_size, self.overlap):
                yield left, top, image[top:min(top + self.tile_size, height), left:min(left + self.tile_size, width)]

    def analyze(self, image: Any, *, image_id: str, source_dataset: str) -> list[Detection]:
        pixels = np.asarray(image)
        if pixels.ndim not in (2, 3) or pixels.shape[0] < 1 or pixels.shape[1] < 1:
            raise ValueError("image must be a non-empty HxW or HxWxC array")
        height, width = pixels.shape[:2]
        raw: list[dict[str, Any]] = []
        for left, top, tile in self._tiles(pixels):
            pil_tile = Image.fromarray(tile.astype(np.uint8, copy=False))
            kwargs = {"source": pil_tile, "conf": self.confidence, "verbose": False}
            if self.device is not None:
                kwargs["device"] = self.device
            result = self.model.predict(**kwargs)[0]
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            xyxys = boxes.xyxy.cpu().tolist()
            class_ids = boxes.cls.cpu().tolist()
            scores = boxes.conf.cpu().tolist()
            for local_box, source_id, score in zip(xyxys, class_ids, scores):
                original_class_id = int(source_id)
                if original_class_id not in self.class_ids:
                    raise ValueError(f"Prediction used undeclared class id {original_class_id}")
                box = [float(local_box[0]) + left, float(local_box[1]) + top,
                       float(local_box[2]) + left, float(local_box[3]) + top]
                box[0], box[2] = max(0.0, min(width, box[0])), max(0.0, min(width, box[2]))
                box[1], box[3] = max(0.0, min(height, box[1])), max(0.0, min(height, box[3]))
                if box[2] <= box[0] or box[3] <= box[1]:
                    continue
                raw.append({"class_id": self.class_ids[original_class_id], "bbox": box,
                            "confidence": float(score), "tile_origin": [left, top]})

        merged: list[dict[str, Any]] = []
        for item in sorted(raw, key=lambda row: row["confidence"], reverse=True):
            match = next((prior for prior in merged
                          if prior["class_id"] == item["class_id"]
                          and _box_iou(prior["bbox"], item["bbox"]) >= self.merge_iou), None)
            if match is None:
                merged.append({**item, "tile_origins": [item["tile_origin"]]})
            else:
                # Keep the highest-confidence box (raw is sorted descending).
                # Unioning tile-local boxes systematically inflates object size
                # and corrupts localization/evidence measurements.
                match["tile_origins"].append(item["tile_origin"])

        detections = []
        for index, item in enumerate(merged, start=1):
            class_id = item["class_id"]
            detections.append(Detection.from_dict({
                "detection_id": f"{image_id}-yolo-{index:04d}",
                "image_id": image_id,
                "class_id": class_id,
                "class_name": CORE_CLASS_NAMES[class_id],
                "bbox": item["bbox"],
                "raw_confidence": item["confidence"],
                "image_width": width,
                "image_height": height,
                "source_dataset": source_dataset,
                "provenance": {"detector": "ultralytics-yolo", "weights": str(self.weights),
                               "tile_origins": item["tile_origins"], "synthetic": False},
            }))
        return detections
