"""Platt and isotonic calibration, kept separate from detector evaluation."""
from __future__ import annotations
import json
import math
from pathlib import Path


class ConfidenceCalibrator:
    def __init__(self, method: str = "platt"):
        if method not in {"platt", "isotonic"}: raise ValueError("method must be platt or isotonic")
        self.method=method; self.a=None; self.b=None; self.breakpoints=None

    @property
    def fitted(self): return self.a is not None if self.method == "platt" else self.breakpoints is not None

    def fit(self, scores: list[float], labels: list[int], *, split_name: str, evaluation_ids: set[str] | None = None, sample_ids: list[str] | None = None):
        if split_name.lower() not in {"calibration", "cal", "validation_calibration"}:
            raise ValueError("calibration must be fitted on a dedicated calibration split")
        if sample_ids is not None and evaluation_ids and evaluation_ids.intersection(sample_ids):
            raise ValueError("calibration samples overlap the declared evaluation IDs")
        if len(scores) != len(labels) or len(scores) < 4 or set(labels) != {0, 1}:
            raise ValueError("calibration requires >=4 matching samples and both correctness outcomes")
        if any(not math.isfinite(float(x)) or not 0 <= float(x) <= 1 for x in scores): raise ValueError("scores must be finite values in [0,1]")
        if self.method == "platt":
            xs=[math.log(max(1e-6,min(1-1e-6,float(x)))/(1-max(1e-6,min(1-1e-6,float(x))))) for x in scores]
            a,b=1.0,0.0
            for _ in range(1200):
                ga=gb=0.0
                for x,y in zip(xs,labels):
                    p=1/(1+math.exp(-max(-30,min(30,a*x+b)))); ga+=(p-y)*x; gb+=p-y
                a-=0.03*(ga/len(xs)+0.001*a); b-=0.03*gb/len(xs)
            self.a,self.b=a,b
        else:
            points=sorted(zip(map(float,scores),map(int,labels)))
            blocks=[]
            for score,label in points:
                blocks.append([score,score,float(label),1])
                while len(blocks)>1 and blocks[-2][2]/blocks[-2][3] > blocks[-1][2]/blocks[-1][3]:
                    right=blocks.pop(); left=blocks.pop(); blocks.append([left[0],right[1],left[2]+right[2],left[3]+right[3]])
            self.breakpoints=[[lo,hi,total/count] for lo,hi,total,count in blocks]
        return self

    def transform(self, score: float) -> float | None:
        if not self.fitted: return None
        score=max(0.0,min(1.0,float(score)))
        if self.method == "platt":
            x=math.log(max(1e-6,min(1-1e-6,score))/(1-max(1e-6,min(1-1e-6,score))))
            return 1/(1+math.exp(-max(-30,min(30,self.a*x+self.b))))
        for lo,hi,value in self.breakpoints:
            if score <= hi: return value
        return self.breakpoints[-1][2]

    def save(self,path):
        if not self.fitted: raise ValueError("cannot persist an unfitted calibrator")
        Path(path).write_text(json.dumps({"method":self.method,"a":self.a,"b":self.b,"breakpoints":self.breakpoints},indent=2))

    @classmethod
    def load(cls,path):
        data=json.loads(Path(path).read_text()); obj=cls(data["method"]); obj.a=data.get("a"); obj.b=data.get("b"); obj.breakpoints=data.get("breakpoints"); return obj
