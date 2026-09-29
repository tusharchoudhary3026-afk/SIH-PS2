"""Evaluate a real Engine 4 checkpoint against caller-supplied held-out labels."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from engine4_detector import CORE_CLASS_NAMES, YOLODetector
from .artifacts import write_artifacts
from .metrics import evaluate_detections


def run_evaluation(manifest_path: str | Path, model_path: str | Path,
                   out_dir: str | Path, *, device: str | None = None,
                   tile_size: int = 640, overlap: int = 160) -> dict:
    source = Path(manifest_path).expanduser().resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    images = payload.get("images")
    truth = payload.get("ground_truth")
    if not isinstance(images, list) or not images:
        raise ValueError("evaluation manifest must contain a non-empty images list")
    if not isinstance(truth, list) or not truth:
        raise ValueError("evaluation manifest must contain labeled test ground_truth records")
    if payload.get("class_names") != list(CORE_CLASS_NAMES):
        raise ValueError(f"class_names must match the four Engine 4 classes: {list(CORE_CLASS_NAMES)}")
    if any(row.get("split") != "test" for row in images):
        raise ValueError("real performance evaluation accepts only images explicitly marked split='test'")
    image_ids = [str(row.get("image_id", "")) for row in images]
    if any(not image_id for image_id in image_ids) or len(image_ids) != len(set(image_ids)):
        raise ValueError("each test image needs a unique, non-empty image_id")
    allowed_ids = set(image_ids)
    for row in truth:
        if str(row.get("image_id", "")) not in allowed_ids:
            raise ValueError("every ground-truth row must reference an image in the test manifest")
        if not 0 <= int(row["class_id"]) < len(CORE_CLASS_NAMES):
            raise ValueError("ground-truth class_id must be one of the four core classes")

    detector = YOLODetector(model_path, tile_size=tile_size, overlap=overlap, device=device)
    predictions = []
    records = []
    for row in images:
        image_path = Path(row["image_path"])
        if not image_path.is_absolute():
            image_path = source.parent / image_path
        with Image.open(image_path) as opened:
            pixels = np.asarray(opened.convert("RGB"))
        dataset = str(row.get("source_dataset", "UNKNOWN"))
        for detection in detector.analyze(pixels, image_id=str(row["image_id"]), source_dataset=dataset):
            predictions.append({"image_id": detection.image_id, "class_id": detection.class_id,
                                "bbox": detection.bbox.to_list(), "confidence": detection.raw_confidence,
                                "source_dataset": dataset})
        records.append({**row, "image_path": str(image_path), "split": "test"})
    ground_truth = [{**row, "source_dataset": str(row.get("source_dataset") or next(
        (image.get("source_dataset", "UNKNOWN") for image in images if str(image["image_id"]) == str(row["image_id"])), "UNKNOWN"))}
                    for row in truth]
    metrics = evaluate_detections(ground_truth, predictions, list(CORE_CLASS_NAMES))
    result = write_artifacts(records, records, out_dir, metrics=metrics,
                             limitations=["Metrics describe only the explicitly supplied held-out test records.",
                                           "Dataset release, acquisition grouping, and test-set independence must be verified by the caller."],
                             source_roles=payload.get("source_roles"))
    output = Path(out_dir)
    (output / "predictions.json").write_text(json.dumps(predictions, indent=2), encoding="utf-8")
    summary = {"status": "REAL_CHECKPOINT_AND_CALLER_SUPPLIED_TEST_LABELS",
               "model_path": str(Path(model_path).expanduser().resolve()),
               "test_images": len(images), "ground_truth_detections": len(ground_truth),
               "predictions": len(predictions), "metrics": metrics,
               "evaluation_artifacts": result["output_dir"]}
    (output / "evaluation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="JSON manifest containing test images and labeled ground truth")
    parser.add_argument("--model", required=True, help="trained four-class YOLO checkpoint")
    parser.add_argument("--out", required=True)
    parser.add_argument("--device", default=None)
    parser.add_argument("--tile-size", type=int, default=640)
    parser.add_argument("--overlap", type=int, default=160)
    args = parser.parse_args()
    if args.tile_size < 1 or args.overlap < 0 or args.overlap >= args.tile_size:
        parser.error("overlap must be non-negative and smaller than tile-size")
    print(json.dumps(run_evaluation(args.manifest, args.model, args.out, device=args.device,
                                    tile_size=args.tile_size, overlap=args.overlap), indent=2))


if __name__ == "__main__":
    main()
