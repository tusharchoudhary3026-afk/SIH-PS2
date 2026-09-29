"""Trainable logistic-regression score fusion; no bundled/fabricated labels."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

FEATURE_NAMES = ("raw_confidence", "shadow_consistency", "local_contrast", "log_aspect_ratio", "normalized_area")


def row_from_evidence(raw_confidence: float, evidence: dict[str, Any]) -> list[float]:
    ratio = max(float(evidence.get("aspect_ratio") or 0.0), 1e-6)
    return [float(raw_confidence), float(evidence.get("shadow_consistency") or 0.0),
            float(evidence.get("local_contrast") or 0.0), math.log(ratio),
            float(evidence.get("normalized_area") or 0.0)]


class LogisticFusion:
    """Small deterministic LR trainer, avoiding hidden training/test fixtures.

    ``fit`` accepts only caller-provided labeled rows. Persisted weights carry
    their feature names/version so a mismatched pipeline fails closed.
    """
    def __init__(self):
        self.means: list[float] | None = None
        self.scales: list[float] | None = None
        self.weights: list[float] | None = None
        self.bias: float | None = None

    @property
    def fitted(self) -> bool:
        return self.weights is not None

    def fit(self, rows: list[list[float]], labels: list[int], *, iterations: int = 1200, learning_rate: float = 0.08, l2: float = 0.01):
        if len(rows) != len(labels) or len(rows) < 4:
            raise ValueError("at least four feature rows and matching labels are required")
        if set(labels) != {0, 1}:
            raise ValueError("fusion training requires both positive and negative labels")
        if any(len(r) != len(FEATURE_NAMES) or not all(math.isfinite(float(x)) for x in r) for r in rows):
            raise ValueError("feature rows must contain finite values in the documented feature order")
        self.means = [sum(float(r[j]) for r in rows) / len(rows) for j in range(len(FEATURE_NAMES))]
        self.scales = [max((sum((float(r[j])-self.means[j])**2 for r in rows) / len(rows))**0.5, 1e-8) for j in range(len(FEATURE_NAMES))]
        x = [[(float(r[j])-self.means[j])/self.scales[j] for j in range(len(FEATURE_NAMES))] for r in rows]
        w, b = [0.0] * len(FEATURE_NAMES), 0.0
        for step in range(iterations):
            grad = [0.0] * len(w); gb = 0.0
            for vector, label in zip(x, labels):
                z = max(-30.0, min(30.0, b + sum(a*c for a, c in zip(w, vector))))
                p = 1.0 / (1.0 + math.exp(-z)); err = p - label
                gb += err
                for j, v in enumerate(vector): grad[j] += err*v
            rate = learning_rate / (1.0 + step * 0.001)
            n = len(x)
            w = [a - rate * (grad[j]/n + l2*a) for j, a in enumerate(w)]
            b -= rate * gb/n
        self.weights, self.bias = w, b
        return self

    def predict_score(self, row: list[float]) -> float:
        if not self.fitted:
            return None
        if len(row) != len(FEATURE_NAMES) or not all(math.isfinite(float(x)) for x in row):
            raise ValueError("invalid fusion feature row")
        z = self.bias + sum(w*((float(x)-m)/s) for w, x, m, s in zip(self.weights, row, self.means, self.scales))
        return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))

    def save(self, path: str | Path) -> None:
        if not self.fitted:
            raise ValueError("cannot persist an unfitted fusion model")
        Path(path).write_text(json.dumps({"model": "logistic_regression", "feature_names": FEATURE_NAMES, "means": self.means, "scales": self.scales, "weights": self.weights, "bias": self.bias}, indent=2))

    @classmethod
    def load(cls, path: str | Path) -> "LogisticFusion":
        data = json.loads(Path(path).read_text())
        if tuple(data.get("feature_names", ())) != FEATURE_NAMES or data.get("model") != "logistic_regression":
            raise ValueError("fusion model schema or feature order does not match")
        obj = cls(); obj.means=data["means"]; obj.scales=data["scales"]; obj.weights=data["weights"]; obj.bias=float(data["bias"])
        return obj
