"""Train the baseline unified four-class YOLO model on a verified YOLO dataset."""
from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, help="YOLO data.yaml made from the verified four-class dataset")
    parser.add_argument("--model", default="yolov8n.pt", help="Baseline checkpoint; use yolov8n.pt or yolov8s.pt")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default=None, help="Ultralytics device, e.g. cpu or 0")
    parser.add_argument("--project", default="runs/engine4")
    parser.add_argument("--name", default="four-class-baseline")
    args = parser.parse_args()
    if args.epochs < 1 or args.imgsz < 1 or args.batch < 1:
        parser.error("epochs, imgsz, and batch must be positive")
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("Install requirements-engine4.txt before training") from exc
    model = YOLO(args.model)
    kwargs = {"data": args.data, "epochs": args.epochs, "imgsz": args.imgsz,
              "batch": args.batch, "project": args.project, "name": args.name}
    if args.device is not None:
        kwargs["device"] = args.device
    model.train(**kwargs)


if __name__ == "__main__":
    main()
