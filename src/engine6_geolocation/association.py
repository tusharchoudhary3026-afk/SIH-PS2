from __future__ import annotations
from .adapters import parse_timestamp
from .coordinates import validate_coordinates


def associate_timestamp(image_timestamp: str | None, fixes, *, tolerance_seconds: float = 1.0, image_id: str | None = None):
    if not image_timestamp: return None,"image timestamp unavailable"
    if tolerance_seconds < 0: raise ValueError("tolerance_seconds must be non-negative")
    try: target=parse_timestamp(image_timestamp)
    except (ValueError,TypeError): return None,"image timestamp invalid"
    eligible=[]
    for fix in fixes:
        if fix.image_id and image_id and fix.image_id == image_id:
            eligible.append((0.0,fix)); continue
        try: delta=abs(parse_timestamp(fix.timestamp)-target)
        except (ValueError,TypeError): continue
        if delta<=tolerance_seconds: eligible.append((delta,fix))
    if not eligible: return None,"no navigation fix within configured timestamp tolerance"
    delta,fix=min(eligible,key=lambda pair: pair[0])
    try: coords=validate_coordinates(fix.latitude,fix.longitude)
    except ValueError: return None,"matched navigation coordinates invalid"
    return {"latitude":coords[0],"longitude":coords[1],"metadata_source":fix.metadata_source,"time_delta_seconds":delta},"verified timestamp association"
