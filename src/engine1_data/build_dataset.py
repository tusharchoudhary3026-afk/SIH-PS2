# # """Split + tile the unified sources into one YOLO-ready dataset.

# #     python src\\engine1_data\\build_dataset.py --unified data\\unified --out data\\yolo_tiles

# # Split rules (chosen so that train and test never contain near-identical images):
# #   pipe      (subpipe_hf)        sorted by timestamp -> contiguous blocks 70/15/15,
# #                                 with a buffer of frames dropped at each boundary
# #                                 (SubPipe frames overlap ~96% with their neighbours).
# #   shipwreck (ai4shipwrecks_*)   official test folder = test; the train folder is split
# #                                 BY SITE (name without the _NN suffix) into train/val;
# #                                 terrain images (no wrecks) go to train as background.
# #   mine      (milco_nombo)       split BY SURVEY YEAR (see --mine-train/val/test).

# # Every image is cut into overlapping tiles. All tiles that contain objects are
# # kept; empty tiles are randomly sampled (--bg-ratio x number of object tiles).
# # The folder given to --out is owned by this script: its images/ and labels/
# # sub-folders are deleted and rebuilt on every run.
# # """
# # import argparse
# # import csv
# # import math
# # import random
# # import re
# # import shutil
# # from collections import Counter, defaultdict
# # from pathlib import Path

# # import cv2
# # import numpy as np

# # from taxonomy import CLASSES, IMG_EXT

# # SOURCES = {  # folder name -> group
# #     "subpipe_hf": "pipe",
# #     "ai4shipwrecks_train": "shipwreck",
# #     "ai4shipwrecks_test": "shipwreck",
# #     "ai4shipwrecks_terrain": "shipwreck",
# #     "milco_nombo": "mine",
# # }


# # def list_images(folder):
# #     return sorted(p for p in (folder / "images").iterdir() if p.suffix.lower() in IMG_EXT)


# # def image_size(path):
# #     try:
# #         from PIL import Image
# #         with Image.open(path) as im:
# #             return im.size  # (W, H), header only
# #     except Exception:
# #         h, w = cv2.imread(str(path), cv2.IMREAD_UNCHANGED).shape[:2]
# #         return w, h


# # # ----------------------------------------------------------------- splitting
# # def split_pipe(imgs, buffer):
# #     def key(p):
# #         try:
# #             return float(p.stem)
# #         except ValueError:
# #             return p.stem
# #     imgs = sorted(imgs, key=lambda p: (isinstance(key(p), str), key(p)))
# #     n = len(imgs)
# #     a, b = int(0.70 * n), int(0.85 * n)
# #     return {"train": imgs[: max(0, a - buffer)],
# #             "val": imgs[a: max(a, b - buffer)],
# #             "test": imgs[b:]}


# # def split_shipwreck_train(imgs, val_frac, seed):
# #     sites = defaultdict(list)
# #     for p in imgs:
# #         sites[re.sub(r"_\d+$", "", p.stem)].append(p)
# #     names = sorted(sites)
# #     random.Random(seed).shuffle(names)
# #     val, tot = [], len(imgs)
# #     for s in names:
# #         if len(val) >= val_frac * tot or len(names) < 2:
# #             break
# #         val += sites[s]
# #     val_set = set(val)
# #     return [p for p in imgs if p not in val_set], val


# # def split_mine(imgs, years_by_split):
# #     out = defaultdict(list)
# #     for p in imgs:
# #         year = p.stem.rsplit("_", 1)[-1]
# #         for split, years in years_by_split.items():
# #             if year in years:
# #                 out[split].append(p)
# #     return out


# # # -------------------------------------------------------------------- tiling
# # def grid(length, tile, stride):
# #     if length <= tile:
# #         return [0]
# #     xs = list(range(0, length - tile + 1, stride))
# #     if xs[-1] + tile < length:
# #         xs.append(length - tile)
# #     return xs


# # def read_boxes(lbl, w, h):
# #     boxes = []
# #     if lbl.exists():
# #         for line in lbl.read_text().splitlines():
# #             p = line.split()
# #             if len(p) != 5:
# #                 continue
# #             c, cx, cy, bw, bh = int(p[0]), *map(float, p[1:])
# #             boxes.append((c, (cx - bw / 2) * w, (cy - bh / 2) * h,
# #                           (cx + bw / 2) * w, (cy + bh / 2) * h))
# #     return boxes


# # def candidate_tiles(img_path, args):
# #     """Yield (x, y, kept_boxes) for every usable tile of one image."""
# #     w, h = image_size(img_path)
# #     boxes = read_boxes(img_path.parent.parent / "labels" / (img_path.stem + ".txt"), w, h)
# #     t = args.tile
# #     for y in grid(h, t, args.stride):
# #         for x in grid(w, t, args.stride):
# #             kept, ambiguous = [], False
# #             for c, x1, y1, x2, y2 in boxes:
# #                 ix1, iy1, ix2, iy2 = max(x1, x), max(y1, y), min(x2, x + t), min(y2, y + t)
# #                 area = (x2 - x1) * (y2 - y1)
# #                 if ix2 <= ix1 or iy2 <= iy1 or area <= 0:
# #                     continue
# #                 inter = (ix2 - ix1) * (iy2 - iy1)
# #                 if inter / area >= args.min_vis or inter >= args.big_area:
# #                     kept.append((c, ix1 - x, iy1 - y, ix2 - x, iy2 - y))
# #                 else:  # just a sliver of an object: confusing either way, skip tile
# #                     ambiguous = True
# #             if not ambiguous:
# #                 yield x, y, kept


# # def render_tile(img, x, y, t, clahe):
# #     crop = img[y: y + t, x: x + t]
# #     if crop.ndim == 3 and crop.shape[2] == 4:
# #         crop = crop[:, :, :3]
# #     if clahe is not None:
# #         if crop.ndim == 3:
# #             crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
# #         crop = clahe.apply(crop)
# #     canvas = np.zeros((t, t) + crop.shape[2:], dtype=crop.dtype)
# #     canvas[: crop.shape[0], : crop.shape[1]] = crop
# #     return canvas


# # def main():
# #     ap = argparse.ArgumentParser()
# #     ap.add_argument("--unified", required=True)
# #     ap.add_argument("--out", required=True)
# #     ap.add_argument("--tile", type=int, default=640)
# #     ap.add_argument("--stride", type=int, default=480)
# #     ap.add_argument("--bg-ratio", type=float, default=1.0,
# #                     help="empty tiles kept per object tile (per group and split)")
# #     ap.add_argument("--min-vis", type=float, default=0.4,
# #                     help="keep a cut object if this fraction of it is inside the tile")
# #     ap.add_argument("--big-area", type=float, default=20000,
# #                     help="...or if at least this many pixels of it are inside the tile")
# #     ap.add_argument("--pipe-buffer", type=int, default=30,
# #                     help="frames dropped at each pipe split boundary")
# #     ap.add_argument("--mine-train", default="2010,2015,2017")
# #     ap.add_argument("--mine-val", default="2021")
# #     ap.add_argument("--mine-test", default="2018")
# #     ap.add_argument("--clahe", action="store_true", help="apply CLAHE to every tile")
# #     ap.add_argument("--seed", type=int, default=0)
# #     args = ap.parse_args()

# #     root, out = Path(args.unified), Path(args.out)
# #     rng = random.Random(args.seed)

# #     # 1) assign images to splits ------------------------------------------------
# #     plan = defaultdict(list)  # (source, split) -> images
# #     for src in SOURCES:
# #         if not (root / src / "images").exists():
# #             print(f"[skip] {src}: not found in {root}")
# #     if (root / "subpipe_hf" / "images").exists():
# #         for sp, im in split_pipe(list_images(root / "subpipe_hf"), args.pipe_buffer).items():
# #             plan[("subpipe_hf", sp)] += im
# #     if (root / "ai4shipwrecks_train" / "images").exists():
# #         tr, va = split_shipwreck_train(list_images(root / "ai4shipwrecks_train"), 0.15, args.seed)
# #         plan[("ai4shipwrecks_train", "train")] += tr
# #         plan[("ai4shipwrecks_train", "val")] += va
# #     if (root / "ai4shipwrecks_test" / "images").exists():
# #         plan[("ai4shipwrecks_test", "test")] += list_images(root / "ai4shipwrecks_test")
# #     if (root / "ai4shipwrecks_terrain" / "images").exists():
# #         plan[("ai4shipwrecks_terrain", "train")] += list_images(root / "ai4shipwrecks_terrain")
# #     if (root / "milco_nombo" / "images").exists():
# #         years = {"train": args.mine_train.split(","), "val": args.mine_val.split(","),
# #                  "test": args.mine_test.split(",")}
# #         for sp, im in split_mine(list_images(root / "milco_nombo"), years).items():
# #             plan[("milco_nombo", sp)] += im

# #     # 2) collect candidate tiles and sample the empty ones ----------------------
# #     pools = defaultdict(lambda: {"pos": [], "bg": []})  # (group, split)
# #     for (src, split), imgs in sorted(plan.items()):
# #         for img in imgs:
# #             for x, y, kept in candidate_tiles(img, args):
# #                 pools[(SOURCES[src], split)]["pos" if kept else "bg"].append((src, img, x, y, kept))
# #     selected = defaultdict(list)  # image path -> tiles
# #     meta = {}
# #     for (group, split), pool in sorted(pools.items()):
# #         npos = len(pool["pos"])
# #         nbg = math.ceil(args.bg_ratio * npos) if npos else min(len(pool["bg"]), 50)
# #         keep = pool["pos"] + rng.sample(pool["bg"], min(nbg, len(pool["bg"])))
# #         for src, img, x, y, kept in keep:
# #             selected[img].append((split, src, x, y, kept))
# #         print(f"[{group:9} {split:5}] {len(plan_imgs(plan, group, split)):4} images -> "
# #               f"{npos:5} object tiles + {min(nbg, len(pool['bg'])):5} empty tiles")

# #     # 3) write tiles --------------------------------------------------------------
# #     for d in ("images", "labels"):
# #         shutil.rmtree(out / d, ignore_errors=True)
# #     for split in ("train", "val", "test"):
# #         (out / "images" / split).mkdir(parents=True, exist_ok=True)
# #         (out / "labels" / split).mkdir(parents=True, exist_ok=True)
# #     clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)) if args.clahe else None

# #     stats = defaultdict(Counter)
# #     rows = []
# #     t = args.tile
# #     for i, (img_path, tiles) in enumerate(sorted(selected.items()), 1):
# #         img = cv2.imread(str(img_path), cv2.IMREAD_UNCHANGED)
# #         for split, src, x, y, kept in tiles:
# #             name = f"{src}__{img_path.stem.replace('.', '-')}__x{x}_y{y}"
# #             cv2.imwrite(str(out / "images" / split / f"{name}.png"),
# #                         render_tile(img, x, y, t, clahe))
# #             lines = []
# #             for c, x1, y1, x2, y2 in kept:
# #                 lines.append(f"{c} {(x1 + x2) / 2 / t:.6f} {(y1 + y2) / 2 / t:.6f} "
# #                              f"{(x2 - x1) / t:.6f} {(y2 - y1) / t:.6f}")
# #                 stats[split][CLASSES[c]] += 1
# #             (out / "labels" / split / f"{name}.txt").write_text("\n".join(lines))
# #             stats[split]["_tiles"] += 1
# #             rows.append([name, split, src, img_path.name, x, y, len(kept)])
# #         if i % 50 == 0:
# #             print(f"  ... {i}/{len(selected)} source images done")

# #     with open(out / "manifest.csv", "w", newline="") as f:
# #         wr = csv.writer(f)
# #         wr.writerow(["tile", "split", "source", "orig_image", "x", "y", "n_boxes"])
# #         wr.writerows(rows)
# #     names = "\n".join(f"  {i}: {n}" for i, n in enumerate(CLASSES))
# #     (out / "data.yaml").write_text(
# #         "# auto-generated; keep this file at the dataset root\n"
# #         f"train: images/train\nval: images/val\ntest: images/test\nnames:\n{names}\n")

# #     print("\nFINAL (tiles and boxes per split)")
# #     for split in ("train", "val", "test"):
# #         s = stats[split]
# #         print(f"  {split:5}: {s['_tiles']:5} tiles | " +
# #               " | ".join(f"{c}: {s[c]}" for c in CLASSES))
# #     print(f"\nwritten to {out}  (manifest.csv + data.yaml included)")


# # def plan_imgs(plan, group, split):
# #     return [p for (src, sp), ims in plan.items() if sp == split and SOURCES[src] == group for p in ims]


# # if __name__ == "__main__":
# #     main()



# """Split + tile the unified sources into one YOLO-ready dataset.

#     python src\\engine1_data\\build_dataset.py --unified data\\unified --out data\\yolo_tiles

# Split rules (chosen so that train and test never contain near-identical images):
#   pipe      (subpipe_hf)        sorted by timestamp, cut into contiguous chunks; whole
#                                 chunks (that contain pipe) go to val/test, with a buffer
#                                 of frames dropped at the borders (SubPipe frames
#                                 overlap ~96% with their neighbours).
#   shipwreck (ai4shipwrecks_*)   official test folder = test; the train folder is split
#                                 BY SITE (name without the _NN suffix) into train/val;
#                                 terrain images (no wrecks) go to train as background.
#   mine      (milco_nombo)       split BY SURVEY YEAR (see --mine-train/val/test).

# Every image is cut into overlapping tiles. All tiles that contain objects are
# kept; empty tiles are randomly sampled (--bg-ratio x number of object tiles).
# The folder given to --out is owned by this script: its images/ and labels/
# sub-folders are deleted and rebuilt on every run.
# """
# import argparse
# import csv
# import math
# import random
# import re
# import shutil
# from collections import Counter, defaultdict
# from pathlib import Path

# import cv2
# import numpy as np

# from taxonomy import CLASSES, IMG_EXT

# SOURCES = {  # folder name -> group
#     "subpipe_hf": "pipe",
#     "ai4shipwrecks_train": "shipwreck",
#     "ai4shipwrecks_test": "shipwreck",
#     "ai4shipwrecks_terrain": "shipwreck",
#     "milco_nombo": "mine",
# }


# def list_images(folder):
#     return sorted(p for p in (folder / "images").iterdir() if p.suffix.lower() in IMG_EXT)


# def image_size(path):
#     try:
#         from PIL import Image
#         with Image.open(path) as im:
#             return im.size  # (W, H), header only
#     except Exception:
#         h, w = cv2.imread(str(path), cv2.IMREAD_UNCHANGED).shape[:2]
#         return w, h


# # ----------------------------------------------------------------- splitting
# def has_boxes(img):
#     lbl = img.parent.parent / "labels" / (img.stem + ".txt")
#     return lbl.exists() and lbl.stat().st_size > 0


# def split_pipe(imgs, args):
#     """Cut the survey (sorted by time) into contiguous chunks and give whole chunks
#     to val/test. Only chunks where the pipe is actually visible are eligible, so
#     val/test are never empty. Frames next to a chunk of a different split are
#     dropped (--pipe-buffer) because neighbouring frames overlap."""
#     def key(p):
#         try:
#             return (0, float(p.stem))
#         except ValueError:
#             return (1, p.stem)
#     imgs = sorted(imgs, key=key)
#     n, k = len(imgs), args.pipe_chunks
#     cut = [round(i * n / k) for i in range(k + 1)]
#     chunks = [imgs[cut[i]: cut[i + 1]] for i in range(k)]
#     frac = [sum(map(has_boxes, c)) / max(1, len(c)) for c in chunks]
#     need = args.pipe_val_chunks + args.pipe_test_chunks
#     eligible = [i for i in range(k) if frac[i] >= 0.4]
#     random.Random(args.seed).shuffle(eligible)
#     rest = sorted((i for i in range(k) if i not in eligible), key=lambda i: -frac[i])
#     chosen = (eligible + rest)[:need]
#     role = {i: "train" for i in range(k)}
#     for j, i in enumerate(chosen):
#         role[i] = "val" if j < args.pipe_val_chunks else "test"
#     out = {"train": [], "val": [], "test": []}
#     for i, c in enumerate(chunks):
#         lo = args.pipe_buffer if i > 0 and role[i - 1] != role[i] and role[i] != "train" else 0
#         hi = args.pipe_buffer if i < k - 1 and role[i + 1] != role[i] and role[i] != "train" else 0
#         out[role[i]] += c[lo: len(c) - hi]
#         if role[i] != "train" and len(c) - lo - hi < 20:
#             print(f"  WARNING: pipe chunk {i} has only {max(0, len(c) - lo - hi)} frames "
#                   f"left after the buffer; use fewer --pipe-chunks or a smaller --pipe-buffer")
#         print(f"  pipe chunk {i}: {role[i]:5} | {len(c):3} frames | pipe visible in {frac[i]:.0%}")
#     return out


# def split_shipwreck_train(imgs, val_frac, seed):
#     sites = defaultdict(list)
#     for p in imgs:
#         sites[re.sub(r"_\d+$", "", p.stem)].append(p)
#     names = sorted(sites)
#     random.Random(seed).shuffle(names)
#     val, tot = [], len(imgs)
#     for s in names:
#         if len(val) >= val_frac * tot or len(names) < 2:
#             break
#         val += sites[s]
#     val_set = set(val)
#     return [p for p in imgs if p not in val_set], val


# def split_mine(imgs, years_by_split):
#     out = defaultdict(list)
#     for p in imgs:
#         year = p.stem.rsplit("_", 1)[-1]
#         for split, years in years_by_split.items():
#             if year in years:
#                 out[split].append(p)
#     return out


# # -------------------------------------------------------------------- tiling
# def grid(length, tile, stride):
#     if length <= tile:
#         return [0]
#     xs = list(range(0, length - tile + 1, stride))
#     if xs[-1] + tile < length:
#         xs.append(length - tile)
#     return xs


# def read_boxes(lbl, w, h):
#     boxes = []
#     if lbl.exists():
#         for line in lbl.read_text().splitlines():
#             p = line.split()
#             if len(p) != 5:
#                 continue
#             c, cx, cy, bw, bh = int(p[0]), *map(float, p[1:])
#             boxes.append((c, (cx - bw / 2) * w, (cy - bh / 2) * h,
#                           (cx + bw / 2) * w, (cy + bh / 2) * h))
#     return boxes


# def candidate_tiles(img_path, args):
#     """Yield (x, y, kept_boxes) for every usable tile of one image."""
#     w, h = image_size(img_path)
#     boxes = read_boxes(img_path.parent.parent / "labels" / (img_path.stem + ".txt"), w, h)
#     t = args.tile
#     for y in grid(h, t, args.stride):
#         for x in grid(w, t, args.stride):
#             kept, ambiguous = [], False
#             for c, x1, y1, x2, y2 in boxes:
#                 ix1, iy1, ix2, iy2 = max(x1, x), max(y1, y), min(x2, x + t), min(y2, y + t)
#                 area = (x2 - x1) * (y2 - y1)
#                 if ix2 <= ix1 or iy2 <= iy1 or area <= 0:
#                     continue
#                 inter = (ix2 - ix1) * (iy2 - iy1)
#                 if inter / area >= args.min_vis or inter >= args.big_area:
#                     kept.append((c, ix1 - x, iy1 - y, ix2 - x, iy2 - y))
#                 else:  # just a sliver of an object: confusing either way, skip tile
#                     ambiguous = True
#             if not ambiguous:
#                 yield x, y, kept


# def render_tile(img, x, y, t, clahe):
#     crop = img[y: y + t, x: x + t]
#     if crop.ndim == 3 and crop.shape[2] == 4:
#         crop = crop[:, :, :3]
#     if clahe is not None:
#         if crop.ndim == 3:
#             crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
#         crop = clahe.apply(crop)
#     canvas = np.zeros((t, t) + crop.shape[2:], dtype=crop.dtype)
#     canvas[: crop.shape[0], : crop.shape[1]] = crop
#     return canvas


# def main():
#     ap = argparse.ArgumentParser()
#     ap.add_argument("--unified", required=True)
#     ap.add_argument("--out", required=True)
#     ap.add_argument("--tile", type=int, default=640)
#     ap.add_argument("--stride", type=int, default=480)
#     ap.add_argument("--bg-ratio", type=float, default=1.0,
#                     help="empty tiles kept per object tile (per group and split)")
#     ap.add_argument("--min-vis", type=float, default=0.4,
#                     help="keep a cut object if this fraction of it is inside the tile")
#     ap.add_argument("--big-area", type=float, default=20000,
#                     help="...or if at least this many pixels of it are inside the tile")
#     ap.add_argument("--pipe-buffer", type=int, default=30,
#                     help="frames dropped where a val/test chunk touches another split")
#     ap.add_argument("--pipe-chunks", type=int, default=6)
#     ap.add_argument("--pipe-val-chunks", type=int, default=1)
#     ap.add_argument("--pipe-test-chunks", type=int, default=1)
#     ap.add_argument("--mine-train", default="2010,2015,2017")
#     ap.add_argument("--mine-val", default="2021")
#     ap.add_argument("--mine-test", default="2018")
#     ap.add_argument("--clahe", action="store_true", help="apply CLAHE to every tile")
#     ap.add_argument("--seed", type=int, default=0)
#     args = ap.parse_args()

#     root, out = Path(args.unified), Path(args.out)
#     rng = random.Random(args.seed)

#     # 1) assign images to splits ------------------------------------------------
#     plan = defaultdict(list)  # (source, split) -> images
#     for src in SOURCES:
#         if not (root / src / "images").exists():
#             print(f"[skip] {src}: not found in {root}")
#     if (root / "subpipe_hf" / "images").exists():
#         for sp, im in split_pipe(list_images(root / "subpipe_hf"), args).items():
#             plan[("subpipe_hf", sp)] += im
#     if (root / "ai4shipwrecks_train" / "images").exists():
#         tr, va = split_shipwreck_train(list_images(root / "ai4shipwrecks_train"), 0.15, args.seed)
#         plan[("ai4shipwrecks_train", "train")] += tr
#         plan[("ai4shipwrecks_train", "val")] += va
#     if (root / "ai4shipwrecks_test" / "images").exists():
#         plan[("ai4shipwrecks_test", "test")] += list_images(root / "ai4shipwrecks_test")
#     if (root / "ai4shipwrecks_terrain" / "images").exists():
#         plan[("ai4shipwrecks_terrain", "train")] += list_images(root / "ai4shipwrecks_terrain")
#     if (root / "milco_nombo" / "images").exists():
#         years = {"train": args.mine_train.split(","), "val": args.mine_val.split(","),
#                  "test": args.mine_test.split(",")}
#         for sp, im in split_mine(list_images(root / "milco_nombo"), years).items():
#             plan[("milco_nombo", sp)] += im

#     # 2) collect candidate tiles and sample the empty ones ----------------------
#     pools = defaultdict(lambda: {"pos": [], "bg": []})  # (group, split)
#     for (src, split), imgs in sorted(plan.items()):
#         for img in imgs:
#             for x, y, kept in candidate_tiles(img, args):
#                 pools[(SOURCES[src], split)]["pos" if kept else "bg"].append((src, img, x, y, kept))
#     selected = defaultdict(list)  # image path -> tiles
#     meta = {}
#     for (group, split), pool in sorted(pools.items()):
#         npos = len(pool["pos"])
#         nbg = math.ceil(args.bg_ratio * npos) if npos else min(len(pool["bg"]), 50)
#         keep = pool["pos"] + rng.sample(pool["bg"], min(nbg, len(pool["bg"])))
#         for src, img, x, y, kept in keep:
#             selected[img].append((split, src, x, y, kept))
#         print(f"[{group:9} {split:5}] {len(plan_imgs(plan, group, split)):4} images -> "
#               f"{npos:5} object tiles + {min(nbg, len(pool['bg'])):5} empty tiles")

#     # 3) write tiles --------------------------------------------------------------
#     for d in ("images", "labels"):
#         shutil.rmtree(out / d, ignore_errors=True)
#     for split in ("train", "val", "test"):
#         (out / "images" / split).mkdir(parents=True, exist_ok=True)
#         (out / "labels" / split).mkdir(parents=True, exist_ok=True)
#     clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)) if args.clahe else None

#     stats = defaultdict(Counter)
#     rows = []
#     t = args.tile
#     for i, (img_path, tiles) in enumerate(sorted(selected.items()), 1):
#         img = cv2.imread(str(img_path), cv2.IMREAD_UNCHANGED)
#         for split, src, x, y, kept in tiles:
#             name = f"{src}__{img_path.stem.replace('.', '-')}__x{x}_y{y}"
#             cv2.imwrite(str(out / "images" / split / f"{name}.png"),
#                         render_tile(img, x, y, t, clahe))
#             lines = []
#             for c, x1, y1, x2, y2 in kept:
#                 lines.append(f"{c} {(x1 + x2) / 2 / t:.6f} {(y1 + y2) / 2 / t:.6f} "
#                              f"{(x2 - x1) / t:.6f} {(y2 - y1) / t:.6f}")
#                 stats[split][CLASSES[c]] += 1
#             (out / "labels" / split / f"{name}.txt").write_text("\n".join(lines))
#             stats[split]["_tiles"] += 1
#             rows.append([name, split, src, img_path.name, x, y, len(kept)])
#         if i % 50 == 0:
#             print(f"  ... {i}/{len(selected)} source images done")

#     with open(out / "manifest.csv", "w", newline="") as f:
#         wr = csv.writer(f)
#         wr.writerow(["tile", "split", "source", "orig_image", "x", "y", "n_boxes"])
#         wr.writerows(rows)
#     names = "\n".join(f"  {i}: {n}" for i, n in enumerate(CLASSES))
#     (out / "data.yaml").write_text(
#         "# auto-generated; keep this file at the dataset root\n"
#         f"train: images/train\nval: images/val\ntest: images/test\nnames:\n{names}\n")

#     print("\nFINAL (tiles and boxes per split)")
#     for split in ("train", "val", "test"):
#         s = stats[split]
#         print(f"  {split:5}: {s['_tiles']:5} tiles | " +
#               " | ".join(f"{c}: {s[c]}" for c in CLASSES))
#     print(f"\nwritten to {out}  (manifest.csv + data.yaml included)")


# def plan_imgs(plan, group, split):
#     return [p for (src, sp), ims in plan.items() if sp == split and SOURCES[src] == group for p in ims]


# if __name__ == "__main__":
#     main()



# """Split + tile the unified sources into one YOLO-ready dataset.

#     python src\\engine1_data\\build_dataset.py --unified data\\unified --out data\\yolo_tiles

# Split rules (chosen so that train and test never contain near-identical images):
#   pipe      (subpipe_hf)        sorted by timestamp, cut into contiguous chunks; whole
#                                 chunks (that contain pipe) go to val/test, with a buffer
#                                 of frames dropped at the borders (SubPipe frames
#                                 overlap ~96% with their neighbours).
#   shipwreck (ai4shipwrecks_*)   official test folder = test; the train folder is split
#                                 BY SITE (name without the _NN suffix) into train/val;
#                                 terrain images (no wrecks) go to train as background.
#   mine      (milco_nombo)       split BY SURVEY YEAR (see --mine-train/val/test).

# Every image is cut into overlapping tiles. All tiles that contain objects are
# kept; empty tiles are randomly sampled (--bg-ratio x number of object tiles).
# The folder given to --out is owned by this script: its images/ and labels/
# sub-folders are deleted and rebuilt on every run.
# """
# import argparse
# import csv
# import math
# import random
# import re
# import shutil
# from collections import Counter, defaultdict
# from pathlib import Path

# import cv2
# import numpy as np

# from taxonomy import CLASSES, IMG_EXT

# SOURCES = {  # folder name -> group
#     "subpipe_hf": "pipe",
#     "ai4shipwrecks_train": "shipwreck",
#     "ai4shipwrecks_test": "shipwreck",
#     "ai4shipwrecks_terrain": "shipwreck",
#     "milco_nombo": "mine",
# }


# def list_images(folder):
#     return sorted(p for p in (folder / "images").iterdir() if p.suffix.lower() in IMG_EXT)


# def image_size(path):
#     try:
#         from PIL import Image
#         with Image.open(path) as im:
#             return im.size  # (W, H), header only
#     except Exception:
#         h, w = cv2.imread(str(path), cv2.IMREAD_UNCHANGED).shape[:2]
#         return w, h


# # ----------------------------------------------------------------- splitting
# def has_boxes(img):
#     lbl = img.parent.parent / "labels" / (img.stem + ".txt")
#     return lbl.exists() and lbl.stat().st_size > 0


# def split_pipe(imgs, args):
#     """Cut the survey (sorted by time) into contiguous chunks and give whole chunks
#     to val/test. Only chunks where the pipe is actually visible are eligible, so
#     val/test are never empty. Frames next to a chunk of a different split are
#     dropped (--pipe-buffer) because neighbouring frames overlap."""
#     def key(p):
#         try:
#             return (0, float(p.stem))
#         except ValueError:
#             return (1, p.stem)
#     imgs = sorted(imgs, key=key)
#     n, k = len(imgs), args.pipe_chunks
#     cut = [round(i * n / k) for i in range(k + 1)]
#     chunks = [imgs[cut[i]: cut[i + 1]] for i in range(k)]
#     frac = [sum(map(has_boxes, c)) / max(1, len(c)) for c in chunks]
#     need = args.pipe_val_chunks + args.pipe_test_chunks
#     eligible = [i for i in range(k) if frac[i] >= 0.4]
#     random.Random(args.seed).shuffle(eligible)
#     rest = sorted((i for i in range(k) if i not in eligible), key=lambda i: -frac[i])
#     chosen = (eligible + rest)[:need]
#     role = {i: "train" for i in range(k)}
#     for j, i in enumerate(chosen):
#         role[i] = "val" if j < args.pipe_val_chunks else "test"
#     out = {"train": [], "val": [], "test": []}
#     for i, c in enumerate(chunks):
#         lo = args.pipe_buffer if i > 0 and role[i - 1] != role[i] and role[i] != "train" else 0
#         hi = args.pipe_buffer if i < k - 1 and role[i + 1] != role[i] and role[i] != "train" else 0
#         out[role[i]] += c[lo: len(c) - hi]
#         if role[i] != "train" and len(c) - lo - hi < 20:
#             print(f"  WARNING: pipe chunk {i} has only {max(0, len(c) - lo - hi)} frames "
#                   f"left after the buffer; use fewer --pipe-chunks or a smaller --pipe-buffer")
#         print(f"  pipe chunk {i}: {role[i]:5} | {len(c):3} frames | pipe visible in {frac[i]:.0%}")
#     return out


# def split_shipwreck_train(imgs, val_frac, seed):
#     sites = defaultdict(list)
#     for p in imgs:
#         sites[re.sub(r"_\d+$", "", p.stem)].append(p)
#     names = sorted(sites)
#     random.Random(seed).shuffle(names)
#     val, tot = [], len(imgs)
#     for s in names:
#         if len(val) >= val_frac * tot or len(names) < 2:
#             break
#         val += sites[s]
#     val_set = set(val)
#     return [p for p in imgs if p not in val_set], val


# def split_mine(imgs, years_by_split):
#     out = defaultdict(list)
#     for p in imgs:
#         year = p.stem.rsplit("_", 1)[-1]
#         for split, years in years_by_split.items():
#             if year in years:
#                 out[split].append(p)
#     return out


# # -------------------------------------------------------------------- tiling
# def grid(length, tile, stride):
#     if length <= tile:
#         return [0]
#     xs = list(range(0, length - tile + 1, stride))
#     if xs[-1] + tile < length:
#         xs.append(length - tile)
#     return xs


# def read_boxes(lbl, w, h):
#     boxes = []
#     if lbl.exists():
#         for line in lbl.read_text().splitlines():
#             p = line.split()
#             if len(p) != 5:
#                 continue
#             c, cx, cy, bw, bh = int(p[0]), *map(float, p[1:])
#             boxes.append((c, (cx - bw / 2) * w, (cy - bh / 2) * h,
#                           (cx + bw / 2) * w, (cy + bh / 2) * h))
#     return boxes


# def candidate_tiles(img_path, args):
#     """Yield (x, y, kept_boxes) for every usable tile of one image."""
#     w, h = image_size(img_path)
#     boxes = read_boxes(img_path.parent.parent / "labels" / (img_path.stem + ".txt"), w, h)
#     t = args.tile
#     for y in grid(h, t, args.stride):
#         for x in grid(w, t, args.stride):
#             kept, ambiguous = [], False
#             for c, x1, y1, x2, y2 in boxes:
#                 ix1, iy1, ix2, iy2 = max(x1, x), max(y1, y), min(x2, x + t), min(y2, y + t)
#                 area = (x2 - x1) * (y2 - y1)
#                 if ix2 <= ix1 or iy2 <= iy1 or area <= 0:
#                     continue
#                 inter = (ix2 - ix1) * (iy2 - iy1)
#                 if inter / area >= args.min_vis or inter >= args.big_area:
#                     kept.append((c, ix1 - x, iy1 - y, ix2 - x, iy2 - y))
#                 else:  # just a sliver of an object: confusing either way, skip tile
#                     ambiguous = True
#             if not ambiguous:
#                 yield x, y, kept


# def render_tile(img, x, y, t, clahe):
#     crop = img[y: y + t, x: x + t]
#     if crop.ndim == 3 and crop.shape[2] == 4:
#         crop = crop[:, :, :3]
#     if clahe is not None:
#         if crop.ndim == 3:
#             crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
#         crop = clahe.apply(crop)
#     canvas = np.zeros((t, t) + crop.shape[2:], dtype=crop.dtype)
#     canvas[: crop.shape[0], : crop.shape[1]] = crop
#     return canvas


# def main():
#     ap = argparse.ArgumentParser()
#     ap.add_argument("--unified", required=True)
#     ap.add_argument("--out", required=True)
#     ap.add_argument("--tile", type=int, default=640)
#     ap.add_argument("--stride", type=int, default=480)
#     ap.add_argument("--bg-ratio", type=float, default=1.0,
#                     help="empty tiles kept per object tile (per group and split)")
#     ap.add_argument("--min-vis", type=float, default=0.4,
#                     help="keep a cut object if this fraction of it is inside the tile")
#     ap.add_argument("--big-area", type=float, default=20000,
#                     help="...or if at least this many pixels of it are inside the tile")
#     ap.add_argument("--pipe-buffer", type=int, default=30,
#                     help="frames dropped where a val/test chunk touches another split")
#     ap.add_argument("--pipe-chunks", type=int, default=6)
#     ap.add_argument("--pipe-val-chunks", type=int, default=1)
#     ap.add_argument("--pipe-test-chunks", type=int, default=1)
#     ap.add_argument("--mine-train", default="2010,2015,2017")
#     ap.add_argument("--mine-val", default="2021")
#     ap.add_argument("--mine-test", default="2018")
#     ap.add_argument("--clahe", action="store_true", help="apply CLAHE to every tile")
#     ap.add_argument("--jpg", action="store_true",
#                     help="save tiles as JPEG (much smaller than PNG; easier to upload)")
#     ap.add_argument("--jpg-quality", type=int, default=95)
#     ap.add_argument("--seed", type=int, default=0)
#     args = ap.parse_args()

#     root, out = Path(args.unified), Path(args.out)
#     rng = random.Random(args.seed)

#     # 1) assign images to splits ------------------------------------------------
#     plan = defaultdict(list)  # (source, split) -> images
#     for src in SOURCES:
#         if not (root / src / "images").exists():
#             print(f"[skip] {src}: not found in {root}")
#     if (root / "subpipe_hf" / "images").exists():
#         for sp, im in split_pipe(list_images(root / "subpipe_hf"), args).items():
#             plan[("subpipe_hf", sp)] += im
#     if (root / "ai4shipwrecks_train" / "images").exists():
#         tr, va = split_shipwreck_train(list_images(root / "ai4shipwrecks_train"), 0.15, args.seed)
#         plan[("ai4shipwrecks_train", "train")] += tr
#         plan[("ai4shipwrecks_train", "val")] += va
#     if (root / "ai4shipwrecks_test" / "images").exists():
#         plan[("ai4shipwrecks_test", "test")] += list_images(root / "ai4shipwrecks_test")
#     if (root / "ai4shipwrecks_terrain" / "images").exists():
#         plan[("ai4shipwrecks_terrain", "train")] += list_images(root / "ai4shipwrecks_terrain")
#     if (root / "milco_nombo" / "images").exists():
#         years = {"train": args.mine_train.split(","), "val": args.mine_val.split(","),
#                  "test": args.mine_test.split(",")}
#         for sp, im in split_mine(list_images(root / "milco_nombo"), years).items():
#             plan[("milco_nombo", sp)] += im

#     # 2) collect candidate tiles and sample the empty ones ----------------------
#     pools = defaultdict(lambda: {"pos": [], "bg": []})  # (group, split)
#     for (src, split), imgs in sorted(plan.items()):
#         for img in imgs:
#             for x, y, kept in candidate_tiles(img, args):
#                 pools[(SOURCES[src], split)]["pos" if kept else "bg"].append((src, img, x, y, kept))
#     selected = defaultdict(list)  # image path -> tiles
#     meta = {}
#     for (group, split), pool in sorted(pools.items()):
#         npos = len(pool["pos"])
#         nbg = math.ceil(args.bg_ratio * npos) if npos else min(len(pool["bg"]), 50)
#         keep = pool["pos"] + rng.sample(pool["bg"], min(nbg, len(pool["bg"])))
#         for src, img, x, y, kept in keep:
#             selected[img].append((split, src, x, y, kept))
#         print(f"[{group:9} {split:5}] {len(plan_imgs(plan, group, split)):4} images -> "
#               f"{npos:5} object tiles + {min(nbg, len(pool['bg'])):5} empty tiles")

#     # 3) write tiles --------------------------------------------------------------
#     for d in ("images", "labels"):
#         shutil.rmtree(out / d, ignore_errors=True)
#     for split in ("train", "val", "test"):
#         (out / "images" / split).mkdir(parents=True, exist_ok=True)
#         (out / "labels" / split).mkdir(parents=True, exist_ok=True)
#     clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)) if args.clahe else None

#     stats = defaultdict(Counter)
#     rows = []
#     t = args.tile
#     for i, (img_path, tiles) in enumerate(sorted(selected.items()), 1):
#         img = cv2.imread(str(img_path), cv2.IMREAD_UNCHANGED)
#         for split, src, x, y, kept in tiles:
#             name = f"{src}__{img_path.stem.replace('.', '-')}__x{x}_y{y}"
#             tile_img = render_tile(img, x, y, t, clahe)
#             if args.jpg:
#                 cv2.imwrite(str(out / "images" / split / f"{name}.jpg"), tile_img,
#                             [cv2.IMWRITE_JPEG_QUALITY, args.jpg_quality])
#             else:
#                 cv2.imwrite(str(out / "images" / split / f"{name}.png"), tile_img)
#             lines = []
#             for c, x1, y1, x2, y2 in kept:
#                 lines.append(f"{c} {(x1 + x2) / 2 / t:.6f} {(y1 + y2) / 2 / t:.6f} "
#                              f"{(x2 - x1) / t:.6f} {(y2 - y1) / t:.6f}")
#                 stats[split][CLASSES[c]] += 1
#             (out / "labels" / split / f"{name}.txt").write_text("\n".join(lines))
#             stats[split]["_tiles"] += 1
#             rows.append([name, split, src, img_path.name, x, y, len(kept)])
#         if i % 50 == 0:
#             print(f"  ... {i}/{len(selected)} source images done")

#     with open(out / "manifest.csv", "w", newline="") as f:
#         wr = csv.writer(f)
#         wr.writerow(["tile", "split", "source", "orig_image", "x", "y", "n_boxes"])
#         wr.writerows(rows)
#     names = "\n".join(f"  {i}: {n}" for i, n in enumerate(CLASSES))
#     (out / "data.yaml").write_text(
#         "# auto-generated; keep this file at the dataset root\n"
#         f"train: images/train\nval: images/val\ntest: images/test\nnames:\n{names}\n")

#     print("\nFINAL (tiles and boxes per split)")
#     for split in ("train", "val", "test"):
#         s = stats[split]
#         print(f"  {split:5}: {s['_tiles']:5} tiles | " +
#               " | ".join(f"{c}: {s[c]}" for c in CLASSES))
#     print(f"\nwritten to {out}  (manifest.csv + data.yaml included)")


# def plan_imgs(plan, group, split):
#     return [p for (src, sp), ims in plan.items() if sp == split and SOURCES[src] == group for p in ims]


# if __name__ == "__main__":
#     main()



"""Split + tile the unified sources into one YOLO-ready dataset.

    python src\\engine1_data\\build_dataset.py --unified data\\unified --out data\\yolo_tiles

Split rules (chosen so that train and test never contain near-identical images):
  pipe      (subpipe_hf)        sorted by timestamp, cut into contiguous chunks; whole
                                chunks (that contain pipe) go to val/test, with a buffer
                                of frames dropped at the borders (SubPipe frames
                                overlap ~96% with their neighbours).
  shipwreck (ai4shipwrecks_*)   official test folder = test; the train folder is split
                                BY SITE (name without the _NN suffix) into train/val;
                                terrain images (no wrecks) go to train as background.
  mine      (milco_nombo)       split BY SURVEY YEAR (see --mine-train/val/test).

Every image is cut into overlapping tiles. All tiles that contain objects are
kept; empty tiles are randomly sampled (--bg-ratio x number of object tiles).
Optional preprocessing (see preprocess.py): --lee, --normalize, --clahe. The chosen
settings are saved to <out>/preprocessing.json so every dataset version is reproducible.

The folder given to --out is owned by this script: its images/ and labels/
sub-folders are deleted and rebuilt on every run.
"""
import argparse
import csv
import json
import math
import random
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

from preprocess import Preprocessor
from taxonomy import CLASSES, IMG_EXT

SOURCES = {  # folder name -> group
    "subpipe_hf": "pipe",
    "ai4shipwrecks_train": "shipwreck",
    "ai4shipwrecks_test": "shipwreck",
    "ai4shipwrecks_terrain": "shipwreck",
    "milco_nombo": "mine",
    "crab_pot": "crab_pot",
}


def list_images(folder):
    return sorted(p for p in (folder / "images").iterdir() if p.suffix.lower() in IMG_EXT)


def image_size(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size  # (W, H), header only
    except Exception:
        h, w = cv2.imread(str(path), cv2.IMREAD_UNCHANGED).shape[:2]
        return w, h


# ----------------------------------------------------------------- splitting
def has_boxes(img):
    lbl = img.parent.parent / "labels" / (img.stem + ".txt")
    return lbl.exists() and lbl.stat().st_size > 0


def split_pipe(imgs, args):
    """Cut the survey (sorted by time) into contiguous chunks and give whole chunks
    to val/test. Only chunks where the pipe is actually visible are eligible, so
    val/test are never empty. Frames next to a chunk of a different split are
    dropped (--pipe-buffer) because neighbouring frames overlap."""
    def key(p):
        try:
            return (0, float(p.stem))
        except ValueError:
            return (1, p.stem)
    imgs = sorted(imgs, key=key)
    n, k = len(imgs), args.pipe_chunks
    cut = [round(i * n / k) for i in range(k + 1)]
    chunks = [imgs[cut[i]: cut[i + 1]] for i in range(k)]
    frac = [sum(map(has_boxes, c)) / max(1, len(c)) for c in chunks]
    need = args.pipe_val_chunks + args.pipe_test_chunks
    eligible = [i for i in range(k) if frac[i] >= 0.4]
    random.Random(args.seed).shuffle(eligible)
    rest = sorted((i for i in range(k) if i not in eligible), key=lambda i: -frac[i])
    chosen = (eligible + rest)[:need]
    role = {i: "train" for i in range(k)}
    for j, i in enumerate(chosen):
        role[i] = "val" if j < args.pipe_val_chunks else "test"
    out = {"train": [], "val": [], "test": []}
    for i, c in enumerate(chunks):
        # Remove frames on both sides of every split boundary. SubPipe frames
        # are highly overlapping, so retaining the train-side neighbors leaks
        # near-identical sonar into validation/test.
        lo = args.pipe_buffer if i > 0 and role[i - 1] != role[i] else 0
        hi = args.pipe_buffer if i < k - 1 and role[i + 1] != role[i] else 0
        out[role[i]] += c[lo: len(c) - hi]
        if role[i] != "train" and len(c) - lo - hi < 20:
            print(f"  WARNING: pipe chunk {i} has only {max(0, len(c) - lo - hi)} frames "
                  f"left after the buffer; use fewer --pipe-chunks or a smaller --pipe-buffer")
        print(f"  pipe chunk {i}: {role[i]:5} | {len(c):3} frames | pipe visible in {frac[i]:.0%}")
    return out


def split_shipwreck_train(imgs, val_frac, seed):
    sites = defaultdict(list)
    for p in imgs:
        sites[re.sub(r"_\d+$", "", p.stem)].append(p)
    names = sorted(sites)
    random.Random(seed).shuffle(names)
    val, tot = [], len(imgs)
    for s in names:
        if len(val) >= val_frac * tot or len(names) < 2:
            break
        val += sites[s]
    val_set = set(val)
    return [p for p in imgs if p not in val_set], val


def split_mine(imgs, years_by_split):
    out = defaultdict(list)
    for p in imgs:
        year = p.stem.rsplit("_", 1)[-1]
        for split, years in years_by_split.items():
            if year in years:
                out[split].append(p)
    return out


def split_crab_pot(imgs, seed):
    """Make a repeatable image-level split when no acquisition groups exist."""
    ordered = sorted(imgs, key=lambda path: (path.stem.lower(), path.suffix.lower()))
    random.Random(seed).shuffle(ordered)
    n = len(ordered)
    if n < 3:
        return {"train": ordered, "val": [], "test": []}
    val_count = max(1, round(n * 0.15))
    test_count = max(1, round(n * 0.15))
    if val_count + test_count >= n:
        val_count, test_count = 1, 1
    return {"train": ordered[:n - val_count - test_count],
            "val": ordered[n - val_count - test_count:n - test_count],
            "test": ordered[n - test_count:]}


# -------------------------------------------------------------------- tiling
def grid(length, tile, stride):
    if length <= tile:
        return [0]
    xs = list(range(0, length - tile + 1, stride))
    if xs[-1] + tile < length:
        xs.append(length - tile)
    return xs


def read_boxes(lbl, w, h):
    boxes = []
    if lbl.exists():
        for line in lbl.read_text().splitlines():
            p = line.split()
            if len(p) != 5:
                continue
            c, cx, cy, bw, bh = int(p[0]), *map(float, p[1:])
            boxes.append((c, (cx - bw / 2) * w, (cy - bh / 2) * h,
                          (cx + bw / 2) * w, (cy + bh / 2) * h))
    return boxes


def candidate_tiles(img_path, args):
    """Yield (x, y, kept_boxes) for every usable tile of one image."""
    w, h = image_size(img_path)
    boxes = read_boxes(img_path.parent.parent / "labels" / (img_path.stem + ".txt"), w, h)
    t = args.tile
    for y in grid(h, t, args.stride):
        for x in grid(w, t, args.stride):
            kept, ambiguous = [], False
            for c, x1, y1, x2, y2 in boxes:
                ix1, iy1, ix2, iy2 = max(x1, x), max(y1, y), min(x2, x + t), min(y2, y + t)
                area = (x2 - x1) * (y2 - y1)
                if ix2 <= ix1 or iy2 <= iy1 or area <= 0:
                    continue
                inter = (ix2 - ix1) * (iy2 - iy1)
                if inter / area >= args.min_vis or inter >= args.big_area:
                    kept.append((c, ix1 - x, iy1 - y, ix2 - x, iy2 - y))
                else:  # just a sliver of an object: confusing either way, skip tile
                    ambiguous = True
            if not ambiguous:
                yield x, y, kept


def render_tile(img, x, y, t, pre):
    crop = img[y: y + t, x: x + t]
    if crop.ndim == 3 and crop.shape[2] == 4:
        crop = crop[:, :, :3]
    if pre is not None and pre.enabled:
        crop = pre(crop)
    canvas = np.zeros((t, t) + crop.shape[2:], dtype=crop.dtype)
    canvas[: crop.shape[0], : crop.shape[1]] = crop
    return canvas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unified", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tile", type=int, default=640)
    ap.add_argument("--stride", type=int, default=480)
    ap.add_argument("--bg-ratio", type=float, default=1.0,
                    help="empty tiles kept per object tile (per group and split)")
    ap.add_argument("--min-vis", type=float, default=0.4,
                    help="keep a cut object if this fraction of it is inside the tile")
    ap.add_argument("--big-area", type=float, default=20000,
                    help="...or if at least this many pixels of it are inside the tile")
    ap.add_argument("--pipe-buffer", type=int, default=30,
                    help="frames dropped where a val/test chunk touches another split")
    ap.add_argument("--pipe-chunks", type=int, default=6)
    ap.add_argument("--pipe-val-chunks", type=int, default=1)
    ap.add_argument("--pipe-test-chunks", type=int, default=1)
    ap.add_argument("--mine-train", default="2010,2015,2017")
    ap.add_argument("--mine-val", default="2021")
    ap.add_argument("--mine-test", default="2018")
    ap.add_argument("--lee", action="store_true", help="Lee speckle filter on every tile")
    ap.add_argument("--lee-win", type=int, default=5, help="Lee filter window (odd number)")
    ap.add_argument("--normalize", action="store_true",
                    help="per-tile percentile contrast stretch (evens out different sonars)")
    ap.add_argument("--clahe", action="store_true", help="apply CLAHE to every tile")
    ap.add_argument("--jpg", action="store_true",
                    help="save tiles as JPEG (much smaller than PNG; easier to upload)")
    ap.add_argument("--jpg-quality", type=int, default=95)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    root, out = Path(args.unified), Path(args.out)
    rng = random.Random(args.seed)

    # 1) assign images to splits ------------------------------------------------
    plan = defaultdict(list)  # (source, split) -> images
    for src in SOURCES:
        if not (root / src / "images").exists():
            print(f"[skip] {src}: not found in {root}")
    if (root / "subpipe_hf" / "images").exists():
        for sp, im in split_pipe(list_images(root / "subpipe_hf"), args).items():
            plan[("subpipe_hf", sp)] += im
    if (root / "ai4shipwrecks_train" / "images").exists():
        tr, va = split_shipwreck_train(list_images(root / "ai4shipwrecks_train"), 0.15, args.seed)
        plan[("ai4shipwrecks_train", "train")] += tr
        plan[("ai4shipwrecks_train", "val")] += va
    if (root / "ai4shipwrecks_test" / "images").exists():
        plan[("ai4shipwrecks_test", "test")] += list_images(root / "ai4shipwrecks_test")
    if (root / "ai4shipwrecks_terrain" / "images").exists():
        plan[("ai4shipwrecks_terrain", "train")] += list_images(root / "ai4shipwrecks_terrain")
    if (root / "milco_nombo" / "images").exists():
        years = {"train": args.mine_train.split(","), "val": args.mine_val.split(","),
                 "test": args.mine_test.split(",")}
        for sp, im in split_mine(list_images(root / "milco_nombo"), years).items():
            plan[("milco_nombo", sp)] += im
    if (root / "crab_pot" / "images").exists():
        for sp, im in split_crab_pot(list_images(root / "crab_pot"), args.seed).items():
            plan[("crab_pot", sp)] += im

    # 2) collect candidate tiles and sample the empty ones ----------------------
    pools = defaultdict(lambda: {"pos": [], "bg": []})  # (group, split)
    for (src, split), imgs in sorted(plan.items()):
        for img in imgs:
            for x, y, kept in candidate_tiles(img, args):
                pools[(SOURCES[src], split)]["pos" if kept else "bg"].append((src, img, x, y, kept))
    selected = defaultdict(list)  # image path -> tiles
    meta = {}
    for (group, split), pool in sorted(pools.items()):
        npos = len(pool["pos"])
        nbg = math.ceil(args.bg_ratio * npos) if npos else min(len(pool["bg"]), 50)
        keep = pool["pos"] + rng.sample(pool["bg"], min(nbg, len(pool["bg"])))
        for src, img, x, y, kept in keep:
            selected[img].append((split, src, x, y, kept))
        print(f"[{group:9} {split:5}] {len(plan_imgs(plan, group, split)):4} images -> "
              f"{npos:5} object tiles + {min(nbg, len(pool['bg'])):5} empty tiles")

    # 3) write tiles --------------------------------------------------------------
    for d in ("images", "labels"):
        shutil.rmtree(out / d, ignore_errors=True)
    for split in ("train", "val", "test"):
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)
    pre = Preprocessor(lee=args.lee, norm=args.normalize, clahe=args.clahe, lee_win=args.lee_win)
    print("preprocessing:", pre.describe() if pre.enabled else "none (raw tiles)")

    stats = defaultdict(Counter)
    rows = []
    t = args.tile
    for i, (img_path, tiles) in enumerate(sorted(selected.items()), 1):
        img = cv2.imread(str(img_path), cv2.IMREAD_UNCHANGED)
        for split, src, x, y, kept in tiles:
            name = f"{src}__{img_path.stem.replace('.', '-')}__x{x}_y{y}"
            tile_img = render_tile(img, x, y, t, pre)
            if args.jpg:
                cv2.imwrite(str(out / "images" / split / f"{name}.jpg"), tile_img,
                            [cv2.IMWRITE_JPEG_QUALITY, args.jpg_quality])
            else:
                cv2.imwrite(str(out / "images" / split / f"{name}.png"), tile_img)
            lines = []
            for c, x1, y1, x2, y2 in kept:
                lines.append(f"{c} {(x1 + x2) / 2 / t:.6f} {(y1 + y2) / 2 / t:.6f} "
                             f"{(x2 - x1) / t:.6f} {(y2 - y1) / t:.6f}")
                stats[split][CLASSES[c]] += 1
            (out / "labels" / split / f"{name}.txt").write_text("\n".join(lines))
            stats[split]["_tiles"] += 1
            rows.append([name, split, src, img_path.name, x, y, len(kept)])
        if i % 50 == 0:
            print(f"  ... {i}/{len(selected)} source images done")

    with open(out / "manifest.csv", "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["tile", "split", "source", "orig_image", "x", "y", "n_boxes"])
        wr.writerows(rows)
    (out / "preprocessing.json").write_text(json.dumps(pre.describe(), indent=2))
    names = "\n".join(f"  {i}: {n}" for i, n in enumerate(CLASSES))
    (out / "data.yaml").write_text(
        "# auto-generated; keep this file at the dataset root\n"
        f"train: images/train\nval: images/val\ntest: images/test\nnames:\n{names}\n")

    print("\nFINAL (tiles and boxes per split)")
    for split in ("train", "val", "test"):
        s = stats[split]
        print(f"  {split:5}: {s['_tiles']:5} tiles | " +
              " | ".join(f"{c}: {s[c]}" for c in CLASSES))
    print(f"\nwritten to {out}  (manifest.csv + data.yaml included)")


def plan_imgs(plan, group, split):
    return [p for (src, sp), ims in plan.items() if sp == split and SOURCES[src] == group for p in ims]


if __name__ == "__main__":
    main()
