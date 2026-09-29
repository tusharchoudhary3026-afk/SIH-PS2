from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class NavigationFix:
    timestamp: str
    latitude: float
    longitude: float
    metadata_source: str
    image_id: str | None = None


@dataclass
class GeolocationResult:
    image_id: str
    object_class: str
    bbox: list[float]
    confidence: float | None
    latitude: float | None
    longitude: float | None
    source_dataset: str
    geolocation_type: str
    geolocation_status: str
    metadata_source: str | None

    def to_dict(self) -> dict[str, Any]: return asdict(self)
