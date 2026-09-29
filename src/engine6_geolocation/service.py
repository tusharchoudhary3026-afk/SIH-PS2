from __future__ import annotations
from .association import associate_timestamp
from .schemas import GeolocationResult


class GeolocationService:
    def __init__(self, navigation_adapter=None, timestamp_tolerance_seconds: float = 1.0):
        self.navigation_adapter=navigation_adapter; self.tolerance=timestamp_tolerance_seconds

    def locate(self, *, image_id: str, object_class: str, bbox: list[float], confidence: float | None, source_dataset: str,
               image_timestamp: str | None = None) -> GeolocationResult:
        fix=None; reason="navigation metadata unavailable"; source=None
        if self.navigation_adapter is not None:
            fixes=self.navigation_adapter.load_fixes(); source=str(getattr(self.navigation_adapter,"csv_path",None)) if fixes else None
            fix,reason=associate_timestamp(image_timestamp,fixes,tolerance_seconds=self.tolerance,image_id=image_id)
        if fix:
            return GeolocationResult(image_id,object_class,bbox,confidence,fix["latitude"],fix["longitude"],source_dataset,"Real","Verified image-to-navigation association",fix["metadata_source"])
        return GeolocationResult(image_id,object_class,bbox,confidence,None,None,source_dataset,"Unavailable",reason,source)
