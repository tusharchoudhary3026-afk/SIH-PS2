"""Engine 5: explainable evidence, score fusion, calibration, and review rules."""

from .pipeline import ConfidencePipeline
from .schemas import BBox, Detection, ScoredDetection

__all__ = ["BBox", "ConfidencePipeline", "Detection", "ScoredDetection"]
