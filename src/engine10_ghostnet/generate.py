"""Composite clearly synthetic net signatures on supplied object-free sonar backgrounds.

This output is a standalone one-class experiment. It is never appended to the
verified four-class data manifest or benchmark.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def _rotate(x: float, y: float, angle: float, cx: float, cy: float) -> tuple[float, float]:
    return (cx + x * math.cos(angle) - y * math.sin(angle),
            cy + x * math.sin(angle) + y * math.cos(angle))


def _group_splits(backgrounds: list[Path], seed: int) -> dict[Path, str]:
    ordered = sorted(backgrounds, key=lambda p: hashlib.sha256(f"{seed}:{p.name}".encode()).hexdigest())
    if len(ordered) < 3:
        return {path: "train" for path in ordered}
    test_count = max(1, round(len(ordered) * 0.15))
    val_count = max(1, round(len(ordered) * 0.15))
    if test_count + val_count >= len(ordered):
        test_count, val_count = 1, 1
    result = {}
    for index, path in enumerate(ordered):
        if index < test_count:
            result[path] = "synthetic_test"
        elif index < test_count + val_count:
            result[path] = "val"
        else:
            result[path] = "train"
    return result


def _composite(background: Image.Image, rng: random.Random) -> tuple[Image.Image, list[float]]:
    base = background.convert("RGB")
    width, height = base.size
    if width < 32 or height < 32:
        raise ValueError("background images must be at least 32 x 32 pixels")
    net_width = rng.uniform(0.18, 0.48) * width
    net_height = rng.uniform(0.06, 0.16) * height
    cx = rng.uniform(net_width / 2 + 2, width - net_width / 2 - 2)
    cy = rng.uniform(net_height / 2 + 2, height - net_height / 2 - 2)
    angle = rng.uniform(-math.pi / 3, math.pi / 3)
    corners = [_rotate(x, y, angle, cx, cy) for x, y in
               [(-net_width / 2, -net_height / 2), (net_width / 2, -net_height / 2),
                (net_width / 2, net_height / 2), (-net_width / 2, net_height / 2)]]
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    # Heuristic acoustic shadow behind the synthetic net; not a physical sonar renderer.
    shadow_depth = rng.uniform(0.06, 0.14) * height
    shadow_offset = (math.sin(angle) * shadow_depth, math.cos(angle) * shadow_depth)
    shadow = [(x + shadow_offset[0], y + shadow_offset[1]) for x, y in corners]
    draw.polygon(shadow, fill=(0, 0, 0, rng.randint(125, 185)))
    draw.line(corners + [corners[0]], fill=(225, 225, 225, 220), width=max(1, round(min(width, height) / 350)))
    # Cross-lines suggest loose netting without claiming photorealistic structure.
    for fraction in (0.2, 0.4, 0.6, 0.8):
        left = (corners[0][0] * (1 - fraction) + corners[3][0] * fraction,
                corners[0][1] * (1 - fraction) + corners[3][1] * fraction)
        right = (corners[1][0] * (1 - fraction) + corners[2][0] * fraction,
                 corners[1][1] * (1 - fraction) + corners[2][1] * fraction)
        draw.line([left, right], fill=(238, 238, 238, 205), width=max(1, round(min(width, height) / 450)))
        top = (corners[0][0] * (1 - fraction) + corners[1][0] * fraction,
               corners[0][1] * (1 - fraction) + corners[1][1] * fraction)
        bottom = (corners[3][0] * (1 - fraction) + corners[2][0] * fraction,
                  corners[3][1] * (1 - fraction) + corners[2][1] * fraction)
        draw.line([top, bottom], fill=(205, 205, 205, 185), width=max(1, round(min(width, height) / 500)))
    result = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    x1, y1 = min(p[0] for p in corners), min(p[1] for p in corners)
    x2, y2 = max(p[0] for p in corners), max(p[1] for p in corners)
    box = [max(0.0, x1), max(0.0, y1), min(float(width), x2), min(float(height), y2)]
    return result, box


def generate(background_dir: str | Path, out_dir: str | Path, *, count: int = 500,
             seed: int = 0) -> dict:
    source = Path(background_dir).expanduser().resolve()
    destination = Path(out_dir).expanduser().resolve()
    backgrounds = sorted(path for path in source.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
    if not backgrounds:
        raise ValueError("no background images found")
    if count < len(backgrounds) or count < 1:
        raise ValueError("count must be positive and at least the number of backgrounds")
    split_for = _group_splits(backgrounds, seed)
    rng = random.Random(seed)
    rows = []
    destination.mkdir(parents=True, exist_ok=True)
    for split in ("train", "val", "synthetic_test"):
        (destination / "images" / split).mkdir(parents=True, exist_ok=True)
        (destination / "labels" / split).mkdir(parents=True, exist_ok=True)
    for index in range(count):
        background = backgrounds[index % len(backgrounds)]
        try:
            with Image.open(background) as opened:
                generated, box = _composite(opened, rng)
        except (OSError, ValueError) as exc:
            raise ValueError(f"could not use background {background}: {exc}") from exc
        image_name = f"ghostnet-synthetic-{index:06d}.png"
        split = split_for[background]
        image_path = destination / "images" / split / image_name
        label_path = destination / "labels" / split / f"{Path(image_name).stem}.txt"
        width, height = generated.size
        x1, y1, x2, y2 = box
        label_path.write_text(
            f"0 {(x1+x2)/2/width:.6f} {(y1+y2)/2/height:.6f} {(x2-x1)/width:.6f} {(y2-y1)/height:.6f}\n",
            encoding="utf-8",
        )
        generated.save(image_path)
        rows.append({"image": str(image_path.relative_to(destination)), "split": split,
                     "background_image": str(background), "source_group": background.name,
                     "synthetic": True, "class_name": "experimental_ghost_net",
                     "bbox_xyxy": json.dumps(box)})
    with (destination / "manifest.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    has_test = any(value == "synthetic_test" for value in split_for.values())
    yaml = [f"path: {destination.as_posix()}", "train: images/train",
            "val: images/val" if any(value == "val" for value in split_for.values()) else "val: images/train",
            "test: images/synthetic_test" if has_test else "test: images/train",
            "names:", "  0: experimental_ghost_net", ""]
    (destination / "data.yaml").write_text("\n".join(yaml), encoding="utf-8")
    report = {"status": "SYNTHETIC_EXPERIMENT_ONLY", "generated_images": count,
              "background_count": len(backgrounds), "background_group_splits":
              {split: sum(value == split for value in split_for.values()) for split in ("train", "val", "synthetic_test")},
              "synthetic_test_available": has_test,
              "limitation": "Synthetic signatures do not establish real-world ghost-net detection accuracy. Confirm every supplied background is object-free and retain its source/license record."}
    (destination / "generation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--background-dir", required=True, help="caller-supplied verified object-free sonar backgrounds")
    parser.add_argument("--out", required=True, help="separate experimental output directory")
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    print(json.dumps(generate(args.background_dir, args.out, count=args.count, seed=args.seed), indent=2))


if __name__ == "__main__":
    main()
