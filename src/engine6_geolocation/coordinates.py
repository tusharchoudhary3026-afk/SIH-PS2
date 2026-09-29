from __future__ import annotations
import math


def validate_coordinates(latitude, longitude) -> tuple[float, float]:
    try: lat, lon=float(latitude),float(longitude)
    except (TypeError,ValueError): raise ValueError("coordinates must be numeric and non-null")
    if not math.isfinite(lat) or not math.isfinite(lon): raise ValueError("coordinates must be finite")
    if not -90 <= lat <= 90: raise ValueError("latitude must be between -90 and 90")
    if not -180 <= lon <= 180: raise ValueError("longitude must be between -180 and 180")
    return lat,lon
