from __future__ import annotations
from dataclasses import asdict,dataclass
import csv
from pathlib import Path
from typing import Any


@dataclass
class DatasetRecord:
    image_id: str
    image_path: str
    annotation_path: str | None
    source_dataset: str
    classes: list[str]
    original_image_id: str | None = None
    tile_id: str | None = None
    acquisition_group: str | None = None
    survey: str | None = None
    sequence: str | None = None
    site: str | None = None
    split: str | None = None
    provenance: dict[str,Any] | None = None

    def to_dict(self): return asdict(self)


GROUP_KEYS=("acquisition_group","survey","sequence","site","source_dataset")


def choose_group_key(records: list[dict]) -> tuple[str | None,str]:
    for key in GROUP_KEYS:
        if records and all(r.get(key) not in (None,"") for r in records) and len({str(r.get(key)) for r in records}) > 1: return key,key
    return None,"No complete acquisition/survey/sequence/site/source grouping is available; image-level deterministic split only."


def split_records(records: list[dict], *, seed: int = 0, fractions=(0.7,0.15,0.15)) -> tuple[list[dict],dict]:
    if not records: return [],{"group_key":None,"limitation":"Not available with current metadata"}
    if len(fractions)!=3 or any(f<0 for f in fractions) or abs(sum(fractions)-1)>1e-8: raise ValueError("fractions must be three non-negative values summing to 1")
    import hashlib
    group_key,limitation=choose_group_key(records)
    groups={}
    for row in records:
        key=str(row.get(group_key)) if group_key else str(row.get("image_id"))
        groups.setdefault(key,[]).append(row)
    # Seeded stable hashing makes assignment repeatable without relying on record order.
    keys=sorted(groups,key=lambda k:hashlib.sha256(f"{seed}:{k}".encode()).hexdigest())
    result=[]; cumulative=(fractions[0],fractions[0]+fractions[1])
    for i,key in enumerate(keys):
        position=(i+0.5)/max(1,len(keys)); split="train" if position<cumulative[0] else "val" if position<cumulative[1] else "test"
        result.extend({**row,"split":split,"split_group_key":group_key or "image_id","split_group":key} for row in groups[key])
    return result,{"group_key":group_key or "image_id","limitation":limitation if group_key else "Not available with current metadata; deterministic image-level split cannot guarantee acquisition independence."}


def load_tile_manifest(manifest_path: str | Path, *, tile_size: int = 640, image_root: str | Path | None = None, label_root: str | Path | None = None) -> list[dict]:
    """Adapt build_dataset.py's actual CSV fields; x/y become source-space tile bounds.

    Group fields are copied only when present in the supplied CSV. The script's
    current manifest lacks acquisition metadata, so none is inferred here.
    """
    if tile_size < 1: raise ValueError("tile_size must be positive")
    manifest_path=Path(manifest_path); rows=[]
    with manifest_path.open(newline="",encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            tile=row.get("tile",""); split=row.get("split",""); source=row.get("source",row.get("source_dataset","UNKNOWN"))
            x,y=int(row["x"]),int(row["y"]); original=row.get("orig_image") or row.get("original_image_id") or None
            image_path=""
            if image_root:
                folder=Path(image_root)/split
                image_path=next((str(path) for path in folder.glob(tile+".*") if path.is_file()),"")
            annotation_path=str(Path(label_root)/split/(tile+".txt")) if label_root else None
            class_ids=[]
            if annotation_path and Path(annotation_path).is_file():
                for line in Path(annotation_path).read_text(encoding="utf-8").splitlines():
                    fields=line.split()
                    if fields:
                        try: class_ids.append(int(fields[0]))
                        except ValueError: continue
            output={"image_id":tile,"image_path":image_path,"annotation_path":annotation_path,"source_dataset":source,
                    "classes":[],"class_ids":sorted(set(class_ids)),"original_image_id":f"{source}:{original}" if original else None,"tile_id":tile,
                    "split":split,"tile_bbox":[x,y,x+tile_size,y+tile_size],
                    "provenance":{"dataset_manifest":str(manifest_path.resolve()),"original_image":original,"source_tile_x":x,"source_tile_y":y}}
            for key in ("acquisition_group","survey","sequence","site"):
                if row.get(key): output[key]=row[key]
            rows.append(output)
    return rows
