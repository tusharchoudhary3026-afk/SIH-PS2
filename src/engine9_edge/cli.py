"""Export an Engine 4 checkpoint to ONNX and measure inference on real hardware."""
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import time
from pathlib import Path

from PIL import Image


def _load_yolo(weights: str):
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("Install requirements-engine4.txt to use Engine 9") from exc
    return YOLO(weights)


def export_onnx(model_path: str, output: str | None, imgsz: int,
                quantize: str, data: str | None) -> str:
    if imgsz < 1:
        raise ValueError("imgsz must be positive")
    if quantize == "int8" and not data:
        raise ValueError("INT8 ONNX export requires representative calibration data via --data")
    model_file = Path(model_path).expanduser().resolve()
    if not model_file.is_file():
        raise FileNotFoundError(f"model checkpoint not found: {model_file}")
    kwargs = {"format": "onnx", "imgsz": imgsz}
    if quantize == "int8":
        kwargs.update({"quantize": 8, "data": data})
    exported = _load_yolo(str(model_file)).export(**kwargs)
    result = Path(str(exported)).resolve()
    if output:
        destination = Path(output).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        if result != destination:
            destination.write_bytes(result.read_bytes())
        result = destination
    if not result.is_file():
        raise RuntimeError("Ultralytics export did not produce an ONNX file")
    return str(result)


def _hardware(device: str) -> dict:
    data = {"platform": platform.platform(), "machine": platform.machine(),
            "processor": platform.processor() or "Unavailable", "logical_cpu_count": os.cpu_count(),
            "device_requested": device}
    try:
        import torch
        data["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available() and device not in {"cpu", "-1"}:
            index = int(device) if device.isdigit() else torch.cuda.current_device()
            data["gpu_name"] = torch.cuda.get_device_name(index)
    except (ImportError, RuntimeError, ValueError):
        data["cuda_available"] = False
    return data


def benchmark(model_path: str, image_path: str, *, imgsz: int = 640,
              warmup: int = 5, repetitions: int = 50, device: str = "cpu") -> dict:
    if warmup < 0 or repetitions < 1 or imgsz < 1:
        raise ValueError("imgsz and repetitions must be positive; warmup cannot be negative")
    weights = Path(model_path).expanduser().resolve()
    sample = Path(image_path).expanduser().resolve()
    if not weights.is_file():
        raise FileNotFoundError(f"model not found: {weights}")
    if not sample.is_file():
        raise FileNotFoundError(f"benchmark image not found: {sample}")
    with Image.open(sample) as source:
        image = source.convert("RGB")
        width, height = image.size
    model = _load_yolo(str(weights))
    options = {"source": image, "imgsz": imgsz, "device": device, "verbose": False}
    for _ in range(warmup):
        model.predict(**options)
    samples_ms = []
    for _ in range(repetitions):
        start = time.perf_counter()
        model.predict(**options)
        samples_ms.append((time.perf_counter() - start) * 1000)
    ordered = sorted(samples_ms)
    p95 = ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]
    mean = statistics.fmean(samples_ms)
    return {
        "status": "MEASURED_ON_THIS_HOST",
        "model_path": str(weights),
        "model_bytes": weights.stat().st_size,
        "input_image": str(sample),
        "input_dimensions": {"width": width, "height": height},
        "imgsz": imgsz,
        "warmup_runs": warmup,
        "measured_runs": repetitions,
        "latency_ms": {"mean": mean, "median": statistics.median(samples_ms), "p95": p95,
                       "min": min(samples_ms), "max": max(samples_ms)},
        "images_per_second": 1000 / mean if mean else None,
        "hardware": _hardware(device),
        "claim_boundary": "Measurement covers Ultralytics prediction for this model, image, device, and host; it is not an AUV or real-time claim.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="export a trained checkpoint as ONNX")
    export.add_argument("--model", required=True)
    export.add_argument("--output")
    export.add_argument("--imgsz", type=int, default=640)
    export.add_argument("--quantize", choices=("none", "int8"), default="none")
    export.add_argument("--data", help="verified representative YOLO data.yaml for INT8 calibration")
    run = commands.add_parser("benchmark", help="measure model latency on a real sample image")
    run.add_argument("--model", required=True)
    run.add_argument("--image", required=True)
    run.add_argument("--output", required=True)
    run.add_argument("--imgsz", type=int, default=640)
    run.add_argument("--warmup", type=int, default=5)
    run.add_argument("--repetitions", type=int, default=50)
    run.add_argument("--device", default="cpu")
    args = parser.parse_args()
    if args.command == "export":
        print(export_onnx(args.model, args.output, args.imgsz, args.quantize, args.data))
        return
    report = benchmark(args.model, args.image, imgsz=args.imgsz, warmup=args.warmup,
                       repetitions=args.repetitions, device=args.device)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
