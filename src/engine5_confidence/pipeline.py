from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from .calibration import ConfidenceCalibrator
from .evidence import extract_evidence
from .filtering import decide
from .fusion import LogisticFusion, row_from_evidence
from .schemas import Detection, ScoredDetection


class ConfidencePipeline:
    def __init__(self, config_path: str | Path | None = None, fusion: LogisticFusion | None = None, calibrator: ConfidenceCalibrator | None = None):
        path=Path(config_path) if config_path else Path(__file__).with_name("config.json")
        self.config=json.loads(path.read_text()); self.fusion=fusion or LogisticFusion(); self.calibrator=calibrator or ConfidenceCalibrator(self.config["calibration_method"])

    def score(self, image: Any, detection: Detection | dict) -> ScoredDetection:
        det=detection if isinstance(detection,Detection) else Detection.from_dict(detection)
        # Re-validate dataclass instances too; Engine 4 implementations may
        # construct these directly rather than going through from_dict.
        det=Detection.from_dict({**det.__dict__,"bbox":det.bbox.to_list()})
        evidence=extract_evidence(image,det)
        row=row_from_evidence(det.raw_confidence,evidence)
        fusion_score=self.fusion.predict_score(row)
        calibrated=self.calibrator.transform(fusion_score) if fusion_score is not None else None
        status,reasons=decide(det.raw_confidence,fusion_score,self.config)
        confidence_status="CALIBRATED" if calibrated is not None else "UNCALIBRATED"
        if not self.fusion.fitted: reasons.append("FUSION_MODEL_UNAVAILABLE")
        return ScoredDetection(
            detection_id=det.detection_id,image_id=det.image_id,class_id=det.class_id,class_name=det.class_name,bbox=det.bbox.to_list(),
            raw_confidence=det.raw_confidence,shadow_consistency=evidence["shadow_consistency"],shadow_diagnostics=evidence["shadow_diagnostics"],
            local_contrast=evidence["local_contrast"],contrast_diagnostics=evidence["contrast_diagnostics"],
            object_mean_intensity=evidence["object_mean_intensity"],background_mean_intensity=evidence["background_mean_intensity"],contrast_difference=evidence["contrast_difference"],
            bbox_width=evidence["bbox_width"],bbox_height=evidence["bbox_height"],bbox_area=evidence["bbox_area"],aspect_ratio=evidence["aspect_ratio"],
            normalized_area=evidence["normalized_area"],normalized_width=evidence["normalized_width"],normalized_height=evidence["normalized_height"],
            fusion_score=fusion_score,calibrated_confidence=calibrated,confidence_status=confidence_status,false_positive_status=status,
            reason_codes=reasons,evidence_scores={"shadow_consistency":evidence["shadow_consistency"],"local_contrast":evidence["local_contrast"]},
            source_dataset=det.source_dataset,provenance=det.provenance)
