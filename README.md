# SIH-PS2 Marine Debris & Anomaly Detection

## Current integration state

Engines 4–10 now have code paths for detector training/inference, confidence evidence, metadata-grounded geolocation, held-out evaluation, dashboard/API integration, edge export/benchmarking, and a separate synthetic Ghost Net experiment. **Real training, real performance metrics, SubPipe metadata verification, and edge measurements remain data/model-dependent and have not been generated here.** No dataset or trained checkpoint is bundled.

When `SIH_MODEL_WEIGHTS` is unset, the Engine 8 development `MockDetector` returns one synthetic, clearly labeled sample for each configured source dataset, mapped to the four core class names (Pipe, Shipwreck, Mine-like Contact, and Crab Pot). These are pipeline/UI fixtures, not detector predictions. Set `SIH_MODEL_WEIGHTS` to a trained four-class checkpoint to route uploads through the real Engine 4 YOLO adapter. Ghost Net remains a separate synthetic-only experiment, not a validated core class.

## Install backend dependencies

From the repository root, install Python dependencies once:

```powershell
python -m pip install -r requirements.txt
```

The frontend development command starts the local Engine 8 API at `http://127.0.0.1:8000` automatically. If that API is already running, the frontend reuses it.

## Start the frontend

```powershell
cd Frontend
npm ci
npm run dev
```

`npm run dev` starts both the API and Vite frontend. In mock mode, the browser can show one clearly synthetic example per configured source. With a real model, the browser sends the selected source dataset once; choosing “All mock examples / unknown real source” runs the real model once and labels provenance as `UNKNOWN`. Dataset names describe intended provenance; no source dataset is bundled or queried by the mock adapter. Set `VITE_API_BASE_URL` at frontend build/dev time to use a different API origin.

## Engine 4: train and connect the unified YOLO detector

The optional `src/engine4_detector/` package supplies a YOLO adapter with the stable detection schema, overlap-aware tile inference, and same-class duplicate merging. It requires a verified four-class YOLO `data.yaml` and trained weights; source datasets and labels are not bundled. Install the optional model stack and train a baseline:

```powershell
python -m pip install -r requirements-engine4.txt
$env:PYTHONPATH = "src"
python -m engine4_detector.train --data data/yolo_tiles/data.yaml --model yolov8n.pt --epochs 100
```

To connect the resulting checkpoint to the local API, set its path before starting the frontend:

```powershell
$env:SIH_MODEL_WEIGHTS = "runs/engine4/four-class-baseline/weights/best.pt"
cd Frontend
npm run dev
```

The adapter returns raw detector scores. Engine 5 still reports `UNCALIBRATED` until a fusion model and calibrator are fitted on the correct held-out splits.

## Engine 5: confidence and evidence

`src/engine5_confidence/` extracts bbox shape, local contrast, and a documented heuristic shadow-consistency feature. It returns diagnostic information and does not claim physical shadow reconstruction. Logistic regression fusion can be trained and persisted from caller-supplied labeled examples; no training labels are bundled. Platt or isotonic calibration is separate and accepts only a dedicated calibration split. Until a fitted fusion and calibrator are supplied, `fusion_score` and `calibrated_confidence` are null and confidence status is `UNCALIBRATED`. Configurable false-positive thresholds live in `config.json` and are provisional pending held-out validation.

## Engine 6: geolocation

`src/engine6_geolocation/` validates coordinates and associates explicit image timestamps with navigation records inside a configured time tolerance. AI4Shipwrecks and MILCO/NOMBO uploads receive `Unavailable` location unless verified per-image navigation metadata is supplied. The SubPipe adapter looks for caller-supplied `EstimatedState.csv` but does not create or require it. An optional simulation adapter accepts explicit coordinates and labels them `Simulated`; it is not enabled by upload analysis. No location is emitted as `0,0` by default.

## Engine 7: generalization and evaluation

`src/engine7_evaluation/` provides manifest records, deterministic group-aware splitting using only populated metadata, duplicate/tile leakage checks, mAP@0.5 and class-aware precision/recall/F1/support/confusion-matrix calculation, and artifact writers. No metrics are generated unless the caller supplies predictions and labeled ground truth. With no grouping metadata, reports explicitly state that independent acquisition grouping is unavailable. Near-duplicate image checks use a small average hash and are a heuristic.

To adapt an existing Engine 3 tile manifest and write only the observed manifest/split/leakage/report artifacts (no model metrics):

```powershell
$env:PYTHONPATH = "src"
python -m engine7_evaluation.cli --manifest data/yolo_tiles/manifest.csv --image-root data/yolo_tiles/images --label-root data/yolo_tiles/labels --out artifacts/evaluation
```

The optional `--assign-splits` flag creates deterministic splits from metadata actually present in the CSV; the current builder manifest does not contain survey/acquisition fields, so it will document that limitation rather than inventing those values.

### Calculate real project metrics

The model evaluation CLI runs a supplied checkpoint on caller-marked test images and compares predictions with labeled ground truth. It refuses images not marked `split: "test"`; it does not make labels, predictions, or metrics up. The JSON manifest must list the four class names in order, image records with unique IDs and `split: "test"`, and pixel `xyxy` ground-truth boxes:

```json
{
  "class_names": ["Pipe", "Shipwreck", "Mine-like Contact", "Crab Pot"],
  "images": [{"image_id": "frame-001", "image_path": "images/frame-001.png", "source_dataset": "SubPipe", "split": "test", "acquisition_group": "verified-survey-id"}],
  "ground_truth": [{"image_id": "frame-001", "class_id": 0, "bbox": [10, 20, 90, 120]}],
  "source_roles": {"SubPipe": "held-out-source"}
}
```

Run it with `PYTHONPATH=src python -m engine7_evaluation.model_eval --manifest data/evaluation/test.json --model runs/engine4/four-class-baseline/weights/best.pt --out artifacts/evaluation`. It writes mAP@0.5, per-class precision/recall/F1/support/AP50, confusion matrix, and per-source summaries. Use only a genuinely held-out labeled test set; the generated report is the first place project metrics will appear.

## Engine 8: API and dashboard

The standard-library local API exposes `GET /api/health`, `POST /api/analyze` (raw image request body; filename and optional dataset in headers), `POST /api/review` (JSON), `GET /api/reviews`, and `GET /api/export?format=json|csv`. Omitting `X-Source-Dataset` or sending `ALL` analyzes against every dataset listed in `src/engine8_api/config.json`; each result includes its `source_dataset`. Human decisions persist to `data/engine8/reviews.json` or the path in `SIH_REVIEW_STORE`. The API listens on localhost by default; it has no authentication and is for local development only. The existing React frontend uploads once to this API, labels `MOCK`/`REAL`/`UNAVAILABLE` status, groups results by source dataset, shows evidence/location fields when a detector supplies detections, and exports the current analysis as JSON/CSV. Its old sample dashboard data remain visibly illustrative.

Inspection Priority is a configurable weighted score over available normalized evidence in `src/engine8_api/config.json`; it is not a cleanup priority and does not use proximity or sensitive-zone GIS data.

## Engine 9: ONNX export and measured host latency

`src/engine9_edge/` exports a trained checkpoint to ONNX, optionally requests INT8 static quantization using representative calibration data, and measures latency against a real image on the current host. These are optional model dependencies and no edge/AUV result is implied. INT8 export requires a representative YOLO calibration `data.yaml` that is kept separate from the final held-out test set:

```powershell
$env:PYTHONPATH = "src"
python -m engine9_edge.cli export --model runs/engine4/four-class-baseline/weights/best.pt --output artifacts/edge/model-int8.onnx --quantize int8 --data data/calibration/quantization.yaml
python -m engine9_edge.cli benchmark --model artifacts/edge/model-int8.onnx --image data/verified-test/sample.png --output artifacts/edge/host-benchmark.json --device cpu --warmup 5 --repetitions 50
```

The benchmark records host/device details and latency distribution for the supplied model and image. Report it only for that measured environment; it is not a real-time or AUV claim.

## Engine 10: separate synthetic Ghost Net experiment

`src/engine10_ghostnet/` composites simple net-like returns and shadow cues over caller-supplied, verified object-free sonar backgrounds. It writes a separate one-class YOLO dataset, keeps source background groups together across train/validation/synthetic-test, and never merges synthetic records into the four-class manifest. Check source licenses and object-free status before generation:

```powershell
$env:PYTHONPATH = "src"
python -m engine10_ghostnet.generate --background-dir data/verified-object-free-backgrounds --out data/experimental/ghost-net --count 500 --seed 0
python -m engine10_ghostnet.train --data data/experimental/ghost-net/data.yaml --epochs 50 --evaluate-synthetic-test
```

The optional report is explicitly synthetic-only. It cannot establish field accuracy; if there are too few independent background images to form a held-out group, synthetic-test evaluation is disabled.

## SubPipe integration after download

Do not change the engines to wait on SubPipe. After it finishes downloading, inspect the actual release and license, identify image IDs/timestamps and annotation paths, locate the real `EstimatedState.csv` schema, and verify timestamp/coordinate associations on matching records. Add only observed metadata to manifests; run group/leakage checks before splitting. Never infer GPS from filenames or fabricate navigation/annotations. No SubPipe data or metadata are currently bundled here.

## Tests

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

Test images and labels are synthetic fixtures used only by tests; test outputs are not project performance claims.
