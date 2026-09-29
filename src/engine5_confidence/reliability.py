"""Reliability bins and PNG plot; caller must provide real held-out outcomes."""
from __future__ import annotations
import math
from pathlib import Path

from PIL import Image, ImageDraw


def reliability_bins(scores: list[float], outcomes: list[int], n_bins: int = 10) -> list[dict]:
    if n_bins < 1 or len(scores)!=len(outcomes): raise ValueError("invalid reliability inputs")
    if not scores: return [{"lower":i/n_bins,"upper":(i+1)/n_bins,"predicted_confidence":None,"observed_correctness":None,"count":0} for i in range(n_bins)]
    bins=[[] for _ in range(n_bins)]
    for score,outcome in zip(scores,outcomes):
        if not math.isfinite(float(score)) or not 0<=score<=1 or outcome not in (0,1): raise ValueError("scores must be [0,1] and outcomes binary")
        bins[min(n_bins-1,int(score*n_bins))].append((float(score),int(outcome)))
    return [{"lower":i/n_bins,"upper":(i+1)/n_bins,"predicted_confidence":sum(x for x,_ in rows)/len(rows) if rows else None,
             "observed_correctness":sum(y for _,y in rows)/len(rows) if rows else None,"count":len(rows)} for i,rows in enumerate(bins)]


def write_reliability_png(bins: list[dict], path: str | Path) -> None:
    size=640; left,top,right,bottom=72,32,24,64
    im=Image.new("RGB",(size,size),"white"); d=ImageDraw.Draw(im); w=size-left-right; h=size-top-bottom
    d.line((left,top,left,top+h),fill="#222",width=2); d.line((left,top+h,left+w,top+h),fill="#222",width=2)
    for tick in range(6):
        x=left+w*tick/5; y=top+h*(1-tick/5)
        d.line((x,top+h,x,top+h+5),fill="#222"); d.line((left-5,y,left,y),fill="#222")
    d.line((left,top+h,left+w,top),fill="#888",width=2)
    for row in bins:
        if row["count"]==0: continue
        x=left+w*row["predicted_confidence"]; y=top+h*(1-row["observed_correctness"])
        d.ellipse((x-5,y-5,x+5,y+5),fill="#087e8b")
    d.text((left+80,size-32),"Predicted confidence",fill="#222")
    d.text((12,top+8),"Observed correctness",fill="#222")
    Path(path).parent.mkdir(parents=True,exist_ok=True); im.save(path)
