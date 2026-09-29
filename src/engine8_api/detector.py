"""DetectorInterface and a visibly synthetic development adapter."""
from __future__ import annotations
import re
from typing import Protocol,Any
from engine5_confidence.schemas import BBox, Detection


class DetectorInterface(Protocol):
    mode: str
    def analyze(self, image: Any, *, image_id: str, source_dataset: str) -> list[Detection]: ...


class MockDetector:
    mode="MOCK"
    def analyze(self, image, *, image_id: str, source_dataset: str) -> list[Detection]:
        """Return one deterministic, explicitly synthetic sample per dataset run."""
        height, width = image.shape[:2]
        datasets = {
            "AI4Shipwrecks": (1, "Shipwreck", 0.24, 0.28, 0.92),
            "MILCO/NOMBO": (2, "Mine-like Contact", 0.54, 0.48, 0.84),
            "SubPipe": (0, "Pipe", 0.72, 0.68, 0.78),
            "PINGEcosystem": (3, "Crab Pot", 0.38, 0.72, 0.81),
        }
        class_id, class_name, center_x, center_y, score = datasets.get(
            source_dataset, (3, "Unknown Object", 0.48, 0.54, 0.70)
        )
        box_width = max(1.0, width * 0.16)
        box_height = max(1.0, height * 0.14)
        x1 = min(max(0.0, width - box_width), max(0.0, width * center_x - box_width / 2))
        y1 = min(max(0.0, height - box_height), max(0.0, height * center_y - box_height / 2))
        x2 = min(float(width), x1 + box_width)
        y2 = min(float(height), y1 + box_height)
        dataset_key = re.sub(r"[^a-z0-9]+", "-", source_dataset.lower()).strip("-") or "unknown"
        return [Detection(
            detection_id=f"{image_id}-{dataset_key}-mock-01",
            image_id=image_id,
            class_id=class_id,
            class_name=class_name,
            bbox=BBox(x1, y1, x2, y2),
            raw_confidence=score,
            image_width=width,
            image_height=height,
            source_dataset=source_dataset,
            provenance={"detector": "development-mock", "synthetic": True, "note": "Not a real model prediction."},
        )]


class UnavailableDetector:
    mode="UNAVAILABLE"
    def analyze(self, image, *, image_id: str, source_dataset: str) -> list[Detection]:
        raise RuntimeError("No detector adapter is configured")
