from __future__ import annotations
import hashlib
from collections import defaultdict
from pathlib import Path
from PIL import Image


def _sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()


def _ahash(path):
    with Image.open(path) as im:
        pixels=list(im.convert("L").resize((8,8)).getdata()); mean=sum(pixels)/64
        return sum((1<<i) for i,p in enumerate(pixels) if p>=mean)


def check_leakage(records: list[dict]) -> dict:
    issues=[]; ids=defaultdict(list); exact=defaultdict(list); original=defaultdict(set); hashes=[]
    for i,row in enumerate(records):
        ids[str(row.get("image_id"))].append(i)
        path=row.get("image_path")
        if path and Path(path).is_file():
            digest=_sha(path); exact[digest].append(i)
            try: hashes.append((i,_ahash(path)))
            except Exception: pass
        original[str(row.get("original_image_id") or row.get("image_id"))].add(str(row.get("split") or ""))
    for key,indices in ids.items():
        if len(indices)>1: issues.append({"type":"duplicate_image_id","image_id":key,"record_indices":indices})
    for digest,indices in exact.items():
        if len(indices)>1:
            splits=sorted({str(records[i].get("split") or "unspecified") for i in indices})
            issues.append({"type":"duplicate_file","sha256":digest,"record_indices":indices,"splits":splits,"crosses_splits":len(splits)>1})
    for image,splits in original.items():
        named={s for s in splits if s}
        if len(named)>1: issues.append({"type":"original_image_tiles_cross_splits","original_image_id":image,"splits":sorted(named)})
    near=[]; buckets=defaultdict(list)
    for i,a in hashes:
        # With distance <=2, at least one of three 21-bit chunks is unchanged.
        chunks=(a&0x1fffff,(a>>21)&0x1fffff,(a>>42)&0x3fffff)
        candidates=set()
        for chunk_index,chunk in enumerate(chunks): candidates.update(buckets[(chunk_index,chunk)])
        for j,b in candidates:
            if records[i].get("split") and records[j].get("split") and records[i].get("split")!=records[j].get("split"):
                distance=(a^b).bit_count()
                if distance<=2: near.append({"record_indices":[j,i],"ahash_distance":distance})
        for chunk_index,chunk in enumerate(chunks): buckets[(chunk_index,chunk)].append((i,a))
    if near: issues.append({"type":"near_duplicate_image_across_splits","pairs":near})
    # Tile overlap: compare source-coordinate tile boxes when callers supply them.
    by_original=defaultdict(list)
    for i,row in enumerate(records):
        box=row.get("tile_bbox")
        if box and len(box)==4: by_original[str(row.get("original_image_id") or row.get("image_id"))].append((i,row,box))
    for original_id,tiles in by_original.items():
        for pos,(i,left,a) in enumerate(tiles):
            for j,right,b in tiles[pos+1:]:
                if left.get("split")==right.get("split"): continue
                if min(a[2],b[2])>max(a[0],b[0]) and min(a[3],b[3])>max(a[1],b[1]):
                    issues.append({"type":"overlapping_tiles_cross_splits","original_image_id":original_id,"record_indices":[i,j]})
    return {"status":"issues_found" if issues else "no_issues_detected","records_checked":len(records),"issues":issues,
            "limitations":["Near-duplicate detection uses 8x8 average hash and can miss transformed or cropped duplicates.","Tile-overlap checks require source-coordinate tile_bbox values."],"metrics_status":"NOT_COMPUTED"}
