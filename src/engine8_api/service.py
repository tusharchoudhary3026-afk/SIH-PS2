from __future__ import annotations
import hashlib,json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any
from PIL import Image
import numpy as np

from engine5_confidence import ConfidencePipeline
from engine6_geolocation.service import GeolocationService
from .detector import MockDetector
from .priority import inspection_priority


class AnalysisService:
    def __init__(self, detector=None, confidence=None, geolocation=None, config_path=None, review_store=None):
        self.detector=detector or MockDetector(); self.confidence=confidence or ConfidencePipeline(); self.geolocation=geolocation or GeolocationService()
        path=Path(config_path) if config_path else Path(__file__).with_name("config.json")
        self.config=json.loads(path.read_text()); self.review_store=Path(review_store) if review_store else Path("data/engine8/reviews.json")

    @property
    def mode(self): return getattr(self.detector,"mode","UNAVAILABLE")

    def analyze_bytes(self, content: bytes, *, filename="upload", source_dataset="ALL") -> dict:
        digest=hashlib.sha256(content).hexdigest(); image_id=digest[:24]
        try:
            with Image.open(__import__("io").BytesIO(content)) as opened:
                fmt=(opened.format or "").upper()
                if fmt not in self.config["allowed_image_formats"]: raise ValueError("unsupported image format")
                opened.load(); image=opened.convert("RGB"); width,height=image.size
                array=np.asarray(image)
        except (OSError,ValueError) as exc: raise ValueError(f"invalid or unsupported image: {exc}") from exc
        configured_datasets=self.config.get("datasets", [])
        requested_dataset=(source_dataset or "ALL").strip()
        selected_datasets=configured_datasets if requested_dataset.upper() in {"", "ALL", "UNKNOWN"} else [requested_dataset]
        if not selected_datasets:
            raise ValueError("no source datasets are configured")
        detections=[]
        for dataset in selected_datasets:
            dataset_detections=self.detector.analyze(array,image_id=image_id,source_dataset=dataset)
            for det in dataset_detections:
                # The dataset loop is authoritative, even if an adapter omits or
                # mislabels the source field in its Detection object.
                tagged=replace(det,source_dataset=dataset)
                if any(existing.detection_id==tagged.detection_id for existing in detections):
                    dataset_key=re.sub(r"[^a-z0-9]+","-",dataset.lower()).strip("-") or "dataset"
                    tagged=replace(tagged,detection_id=f"{tagged.detection_id}-{dataset_key}")
                detections.append(tagged)
        rows=[]
        for det in detections:
            scored=self.confidence.score(array,det).to_dict()
            location=self.geolocation.locate(image_id=det.image_id,object_class=det.class_name,bbox=det.bbox.to_list(),confidence=scored["calibrated_confidence"],source_dataset=det.source_dataset,
                                              image_timestamp=det.provenance.get("image_timestamp"))
            evidence={"raw_confidence":scored["raw_confidence"],"shadow_consistency":scored["shadow_consistency"],"local_contrast":scored["local_contrast"],"normalized_area":scored["normalized_area"]}
            rows.append({**scored,**location.to_dict(),"inspection_priority":inspection_priority(evidence,self.config)})
        reviews=self._read_reviews()
        for row in rows: row["human_review"]=reviews.get(row["detection_id"],{"status":"pending"})
        response_dataset=selected_datasets[0] if len(selected_datasets)==1 else "ALL"
        return {"mode":self.mode,"image_id":image_id,"filename":Path(filename).name,"image_width":width,"image_height":height,"source_dataset":response_dataset,"datasets":selected_datasets,
                "detector_status":"NO_DETECTOR_CONNECTED" if self.mode=="MOCK" else self.mode,"message":"DEMO / MOCK MODE — NOT REAL DETECTOR OUTPUT" if self.mode=="MOCK" else None,
                "detections":rows,"location_policy":"Coordinates are unavailable unless verified image-to-navigation metadata is supplied."}

    def _read_reviews(self):
        try: return json.loads(self.review_store.read_text())
        except (FileNotFoundError,json.JSONDecodeError): return {}

    def save_review(self,detection_id: str, action: str, note: str="") -> dict:
        if action not in {"confirm","reject","flag"}: raise ValueError("action must be confirm, reject, or flag")
        if not detection_id or len(detection_id)>200: raise ValueError("invalid detection_id")
        reviews=self._read_reviews(); value={"status":action,"note":note[:2000],"updated_at":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}
        reviews[detection_id]=value; self.review_store.parent.mkdir(parents=True,exist_ok=True)
        temp=self.review_store.with_suffix(".tmp"); temp.write_text(json.dumps(reviews,indent=2)); temp.replace(self.review_store)
        return {"detection_id":detection_id,"human_review":value}
