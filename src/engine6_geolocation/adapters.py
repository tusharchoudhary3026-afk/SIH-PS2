"""Metadata adapters. No adapter invents coordinates or SubPipe records."""
from __future__ import annotations
import csv
from datetime import datetime, timezone
from pathlib import Path

from .coordinates import validate_coordinates
from .schemas import NavigationFix


def parse_timestamp(value: str) -> float:
    text=str(value).strip()
    try: return float(text)
    except ValueError: pass
    parsed=datetime.fromisoformat(text.replace("Z","+00:00"))
    if parsed.tzinfo is None: parsed=parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


class NavigationAdapter:
    """Loads only explicit timestamp/latitude/longitude columns in a supplied CSV."""
    def __init__(self, csv_path: str | Path | None): self.csv_path=Path(csv_path) if csv_path else None

    @property
    def available(self): return bool(self.csv_path and self.csv_path.is_file())

    def load_fixes(self) -> list[NavigationFix]:
        if not self.available: return []
        with self.csv_path.open(newline="",encoding="utf-8-sig") as stream:
            reader=csv.DictReader(stream); names={str(k).strip().lower():k for k in (reader.fieldnames or [])}
            time_col=next((names[k] for k in ("timestamp","time","datetime","utc") if k in names),None)
            lat_col=next((names[k] for k in ("latitude","lat") if k in names),None)
            lon_col=next((names[k] for k in ("longitude","lon","long") if k in names),None)
            id_col=next((names[k] for k in ("image_id","image","filename","id") if k in names),None)
            if not time_col or not lat_col or not lon_col: return []
            fixes=[]
            for row in reader:
                try: lat,lon=validate_coordinates(row[lat_col],row[lon_col]); parse_timestamp(row[time_col])
                except (ValueError,TypeError): continue
                fixes.append(NavigationFix(row[time_col],lat,lon,str(self.csv_path),row.get(id_col) if id_col else None))
            return fixes


class SubPipeAdapter(NavigationAdapter):
    """Future adapter for caller-supplied EstimatedState.csv; absent means no fixes."""
    def __init__(self, dataset_root: str | Path | None):
        root=Path(dataset_root) if dataset_root else None
        candidates=[root/"EstimatedState.csv",root/"estimatedstate.csv"] if root else []
        super().__init__(next((p for p in candidates if p.is_file()),None))


class SimulatedLocationAdapter:
    """Marks caller-provided demonstration coordinates as simulated."""
    def locate(self, latitude, longitude):
        lat,lon=validate_coordinates(latitude,longitude)
        return {"latitude":lat,"longitude":lon,"geolocation_type":"Simulated","geolocation_status":"Caller-provided simulation; not a real position","metadata_source":"explicit simulation input"}
