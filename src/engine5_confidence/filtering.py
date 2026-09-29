"""Configurable triage decisions. Defaults are provisional, not validated."""
from __future__ import annotations


def decide(raw_confidence: float, fusion_score: float | None, config: dict) -> tuple[str, list[str]]:
    rules=config["false_positive_filter"]
    reasons=[]
    if fusion_score is not None:
        if fusion_score < rules["fusion_reject_below"]: return "reject", ["LOW_FUSION_SCORE"]
        if fusion_score >= rules["fusion_keep_at_or_above"]: return "keep", ["FUSION_SCORE_ABOVE_CONFIGURED_KEEP_THRESHOLD"]
        return "review", ["FUSION_SCORE_IN_REVIEW_BAND"]
    if raw_confidence < rules["raw_reject_below"]:
        return "reject", ["RAW_SCORE_BELOW_CONFIGURED_REVIEW_FLOOR", "UNCALIBRATED_RAW_SCORE_RULE"]
    if raw_confidence >= rules["raw_keep_at_or_above"]:
        return "keep", ["RAW_SCORE_ABOVE_CONFIGURED_TRIAGE_THRESHOLD", "UNCALIBRATED_RAW_SCORE_RULE"]
    return "review", ["FUSION_MODEL_UNAVAILABLE", "UNCALIBRATED_RAW_SCORE_RULE"]
