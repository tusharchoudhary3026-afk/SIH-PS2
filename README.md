# SIH-PS2 Marine Debris & Anomaly Detection

## Current integration state

Engine 5 (confidence/evidence infrastructure), Engine 6 (metadata-grounded geolocation), Engine 7 (evaluation infrastructure), and Engine 8 (local API and dashboard integration) are implemented as modular infrastructure. **Engine 4 and SubPipe integration are pending.** No trained detector is bundled and no project performance metrics are available.

The Engine 8 development `MockDetector` returns one synthetic, clearly labeled sample for each configured source dataset, mapped to the scope's four core class names (Pipe, Shipwreck, Mine-like Contact, and Crab Pot). These are pipeline/UI fixtures, not detector predictions. No trained detector or downloaded project datasets are bundled, and no project performance metrics are available. Ghost Net remains an experimental extension, not a validated core class.

## Start the backend

From the repository root, install Python dependencies once, then run:

```powershell
python -m pip install -r requirements.txt
$env:PYTHONPATH = "src"
python -m engine8_api.server
```

The local development API listens at `http://127.0.0.1:8000`.

## Start the frontend

```powershell
cd Frontend
npm ci
npm run dev
```

Set `VITE_API_BASE_URL` at frontend build/dev time to use a different local API origin. The browser sends one uploaded image to all configured datasets (AI4Shipwrecks, MILCO/NOMBO, SubPipe, and PINGEcosystem) when **Start scanning** is selected. Dataset names describe intended provenance; no source dataset is bundled or queried by the mock adapter.

## Engine 4 detector contract

Implement `DetectorInterface.analyze(image, *, image_id, source_dataset) -> list[Detection]`. `Detection` requires detection/image IDs, class ID/name, `bbox` as pixel `xyxy` coordinates, raw confidence in `[0,1]`, source image width/height, source dataset, and provenance. Raw confidence is not a calibrated probability. A future Engine 4 adapter should replace `MockDetector` through dependency injection; Engines 5–8 consume the stable schema.

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

## Engine 8: API and dashboard

The standard-library local API exposes `GET /api/health`, `POST /api/analyze` (raw image request body; filename and optional dataset in headers), `POST /api/review` (JSON), `GET /api/reviews`, and `GET /api/export?format=json|csv`. Omitting `X-Source-Dataset` or sending `ALL` analyzes against every dataset listed in `src/engine8_api/config.json`; each result includes its `source_dataset`. Human decisions persist to `data/engine8/reviews.json` or the path in `SIH_REVIEW_STORE`. The API listens on localhost by default; it has no authentication and is for local development only. The existing React frontend uploads once to this API, labels `MOCK`/`REAL`/`UNAVAILABLE` status, groups results by source dataset, shows evidence/location fields when a detector supplies detections, and exports the current analysis as JSON/CSV. Its old sample dashboard data remain visibly illustrative.

Inspection Priority is a configurable weighted score over available normalized evidence in `src/engine8_api/config.json`; it is not a cleanup priority and does not use proximity or sensitive-zone GIS data.

## SubPipe integration after download

Do not change the engines to wait on SubPipe. After it finishes downloading, inspect the actual release and license, identify image IDs/timestamps and annotation paths, locate the real `EstimatedState.csv` schema, and verify timestamp/coordinate associations on matching records. Add only observed metadata to manifests; run group/leakage checks before splitting. Never infer GPS from filenames or fabricate navigation/annotations. No SubPipe data or metadata are currently bundled here.

## Tests

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

Test images and labels are synthetic fixtures used only by tests; test outputs are not project performance claims.
