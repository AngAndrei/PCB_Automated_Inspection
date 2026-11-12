# PCB Defect Inspection Architecture and Implementation Plan

**Prepared for:** Andrei Anghelea  
**Research date:** 12 November 2026  
**Status:** Proposed architecture; no model has been trained or benchmarked for this project.

> For implementation agents: execute Section 14 task by task. Sections 1–13 are the architecture specification. The user accepts approximate defect-location overlays; accurate pixel boundaries are an optional upgrade.

**Goal:** Build a YOLO-based PCB inspection app that identifies visible defects, highlights their approximate locations with colored semi-transparent overlays, and supplies reproducible evaluation suitable for an ML/CV engineering portfolio.

**Architecture:** Train a YOLO detector first and display each prediction as a translucent area marker. A local browser interface communicates with a Python API and a single inference worker. The prediction contract also supports optional YOLO segmentation masks, so better contours can be added without rebuilding the app.

**Tech stack:** Python, Ultralytics YOLO/PyTorch, OpenCV/Pillow, FastAPI/Pydantic, SQLite, React/TypeScript/Vite, Canvas 2D, pytest, Vitest/Playwright; optional ONNX Runtime for deployment.

**Spec:** Sections 1–13 of this document. Section 14 is the corresponding implementation plan.

## 1. Scope and decisions

### Confirmed user requirements

- Use YOLO.
- Display colored, semi-transparent masks or region highlights instead of requiring visible rectangular outlines.
- Approximate relative location is sufficient; precise pixel-by-pixel segmentation is not required.
- Build a usable app and a credible CV project.
- Provide a detailed architecture informed by internet research.

The updated interpretation simplifies the first release: **the model can predict a bounding box internally while the interface displays a translucent approximate area**. This is an estimated-region overlay, not a learned segmentation boundary. The interface and CV description must preserve that distinction.

The project is independently inspired by UPT's AOI work. Project 3 in the cited UPT announcement includes AI inspection of electronic boards [S1]; the announcement does not establish that this portfolio app is an official UPT deliverable.

### Proposed defaults

The board-scope and interface questions received no selection, so these remain proposals:

| Decision | Default | Reason |
|---|---|---|
| First domain | Bare PCB tracks | A coherent first dataset and defect vocabulary. |
| First model | YOLO26n detector; compare YOLO26s | Low starting cost with a controlled capacity comparison. |
| First dataset | DeepPCB | Existing boxes are sufficient for the clarified requirement. |
| Normal display | Colored translucent ellipse centered on each detection | Shows approximate location without a rectangular outline. |
| Optional upgrade | YOLO26n-seg / YOLO26s-seg | Produces learned contours when suitable masks are available. |
| Input | Uploaded JPG/PNG images | Avoids coupling early development to camera hardware. |
| Interface | Polished local browser dashboard | Supports inspection, demonstration, and saved results. |
| Runtime | Windows, localhost, one user | Matches the current workspace. |
| Training | Available local/university/notebook NVIDIA GPU | Exact hardware and VRAM are unverified. |
| Cost | No paid inference API required | Downloaded model weights run locally. |

The project directory was empty and not a Git repository when inspected. The file layout below is proposed new work.

### First release

The first release includes data audit, a trained detector, evaluation, image upload, translucent region overlays, defect details, inspection history, review notes, and PNG/JSON exports.

Exact segmentation, live camera capture, assembled-board models, automatic retraining, and public hosting are later additions. A working first release does not depend on segmentation labels or perfect contours.

## 2. Recommended approach and alternatives

| Approach | Labels needed | Display | Decision |
|---|---|---|---|
| **YOLO detection + approximate overlay** | Bounding boxes and defect categories | App draws a translucent estimated region at each predicted location | **First release.** |
| **YOLO instance segmentation** | Polygons or pixel masks representing defect instances | Model-predicted, possibly coarse defect contours | Optional upgrade if the improvement justifies the data work. |
| YOLO detection + separate prompted segmenter | Boxes plus prompts/refinement | A second model proposes contours | Keep as an annotation experiment; unnecessary for the first release. |

Ultralytics detection outputs boxes, labels, and confidence scores [S27]. Its segmentation variants add masks and use the -seg suffix [S2]. The first option satisfies approximate localization with the simplest labelled-data path.

YOLO can produce masks directly; the main additional work is suitable training labels and validating their quality. It is not necessary to abandon YOLO to obtain irregular overlays later.

For native raster masks, current YOLO26 semantic segmentation is another available option [S3]. It is reserved for an experiment where dense pixel classes matter more than separate defect instances.

The final choice of model size and settings comes from project measurements. Published COCO results do not establish the best PCB model.

## 3. Dataset plan

### Primary: DeepPCB

DeepPCB supplies 1,500 aligned reference/test image pairs and bounding annotations for six classes. Its original images are cropped to 640×640, and the authors manually added some artificial defects [S6].

Use the inspected image as the YOLO input. A reference image is not required at runtime. The paired template is useful for dataset review and an optional classical comparison.

| App class ID | Name | Meaning |
|---:|---|---|
| 0 | open_circuit | A gap interrupting a conductive track. |
| 1 | short_circuit | An unwanted connection between conductors. |
| 2 | mouse_bite | A notch or missing copper along an edge. |
| 3 | spur | Unwanted copper protruding from a conductor. |
| 4 | spurious_copper | An isolated unwanted copper region. |
| 5 | pin_hole | A hole within a copper region. |

DeepPCB's original numbered labels differ from this zero-based app mapping. Map by verified source names; do not assume arbitrary annotation IDs match the app.

### What DeepPCB establishes

It supports a reproducible benchmark and working demo on its acquisition domain. Its processed imagery and artificially added defects do not establish performance on arbitrary phone photographs or populated boards.

The first demo should include held-out examples resembling the training domain. Camera adaptation is a separate milestone with new development and test images.

### Other researched datasets

| Dataset | Verified facts | Role |
|---|---|---|
| VISION PCB_1 | Instance polygons for six named bare-board defect categories; normal provider access is gated [S4, S5]. | First candidate for a future multiclass segmentation model. |
| MeiweiPCB | Official repository lists defect/normal image archives, pixel masks, and COCO split archives; 220×220 patches [S7]. | Binary-defect segmentation experiment. |
| VisA PCB1–PCB4 | Assembled-board images with pixel annotations; original class maps are available [S8, S9]. | Later assembled-board inspection, using a separate model. |

VISION PCB_1 derives from a synthetic PCB source [S10]. Its polygons do not remove that limitation. Its categories include missing_hole, while DeepPCB includes pin_hole. Those are not interchangeable.

The VISION paper and current dataset card describe different release stages; the inference folder may have no usable test labels. Verify actual archives before designing its experiment. Do not interpret missing labels as proof that an image is good.

Meiwei's public archive listing was verified during research, but its binary masks were not downloaded and audited. Its exact available count and topology remain checks for the optional experiment.

PCB-Vision is a different resource: its documented labels include ICs, capacitors, and connectors [S11]. Component segmentation is not automatically defect segmentation.

### Data acquisition and provenance

Write a download/import command that records source URL, downloaded version, checksum, annotation format, class mapping, and license. Keep original files immutable and exclude datasets from ordinary Git commits.

Do not require a paid data platform. The first milestone uses DeepPCB's published annotations.

## 4. Data preparation and leakage prevention

### Canonical manifest

One record per source image:

- sample_id, dataset/version, original filename, SHA-256;
- width/height, source annotation path and class inventory;
- parent image, board/layout ID, acquisition session when recoverable;
- paired-template ID and duplicate-group ID;
- split, annotation quality, and verified-good status.

Preserve source boxes and original images. YOLO text labels are derived artifacts.

### Dataset splits

DeepPCB publishes 1,000 training and 500 test images [S6]. Start with that as the benchmark protocol:

1. Audit exact duplicates and related images across the original split.
2. Reserve approximately 20% of the original training pool for validation by source group, not independent random crops.
3. Keep the published test pool untouched for final evaluation.
4. Keep paired normal/defective samples and all variants of a parent image in the same group.
5. If leakage requires repairs, create a separately named split and report the repairs. Do not describe its scores as an unchanged official benchmark.

For a later unseen-layout experiment, hold out entire layout IDs where those identifiers can be recovered. If the dataset cannot support that split, explicitly limit the generalization claim.

Assign groups before creating tiles or augmentations. No crop, rotated copy, or synthetic variant of a source image crosses the split boundary.

### Good images

A detector also needs evaluation on good images:

- Use defect-free templates only after inspection and keep each template with its corresponding test image's split.
- Keep a separate report for these cleaned template negatives: they are not equivalent to independent factory good-board samples.
- Add real same-domain good images when available.
- A file with no annotation is unknown unless verified good.
- Do not fabricate a production false-alarm rate from unverified negatives.

### Conversion and audits

For every annotation, check class ID, finite coordinates, positive area, bounds, and source-image identity. Visually inspect a class-stratified sample, every suspicious box, and the smallest defects.

Convert to YOLO detection labels: class_id, normalized center_x, center_y, width, height. Round-trip boxes back to source pixels and check that conversion error is below one pixel.

Maintain a report of class counts, box sizes, defect density, aspect ratios, negative counts, and group distribution. Do not silently discard small boxes because they are inconvenient.

The first release does **not** require polygons, pixel-perfect ground truth, Dice, or boundary-IoU checks.

## 5. Model and experiment plan

### Starting configuration

These are proposed starting values, not a claimed optimum.

| Setting | Initial choice |
|---|---|
| Checkpoint | COCO-pretrained yolo26n.pt |
| Task | Detection |
| Image size | 640 for DeepPCB's existing crops |
| Training limit | 100 epochs |
| Early stopping | Patience 20, using validation only |
| Batch | 4 for smoke test; tune to measured VRAM |
| Optimizer | Framework auto; save resolved parameters |
| Seed | 42; repeat finalist with 43 and 44 if practical |
| Windows data workers | 0 initially; increase after stability checks |
| Mosaic / mixup / copy-paste | Disabled for the baseline |
| Augmentation | Mild geometry and brightness/contrast; synchronized with boxes |
| Model selection | Validation AP and recall/false-alarm trade-off |
| First inference head | One-to-many with NMS, explicitly configured |

Current YOLO26 documentation describes small-target training changes [S14]. We will test its nano and small variants on the actual PCB data.

The current official head-selection guide maps nms=True/None to one-to-many and nms=False to one-to-one [S26]. Use an explicit choice in training-time validation, inference, and export. The quality-oriented baseline uses one-to-many; compare the one-to-one path on validation if deployment latency matters.

Freeze package versions and checkpoint hashes after the initial train/predict/export smoke test. A YOLO11 checkpoint is a compatibility fallback if the selected current toolchain cannot be reproduced, not another mandatory research branch.

### Experiment sequence

| Run | Experiment | Decision it informs |
|---|---|---|
| E0 | Overfit a tiny training subset | Confirms labels, class mapping, and training pipeline. |
| E1 | YOLO26n, 640, standard crops | Establishes the main baseline. |
| E2 | YOLO26s with the same split/settings | Tests whether more capacity helps. |
| E3 | One controlled augmentation change | Tests robustness without changing several variables at once. |
| E4 | Tiled inference on genuinely larger held-out images | Tests scale preservation where high-resolution source images exist. |
| E5 | Head/backend comparison | Measures deployment accuracy and latency trade-offs. |

E4 is conditional: do not tile the existing 640×640 DeepPCB crops just to add complexity. Upscaling a low-resolution crop does not create new optical information.

Keep experiments small. Improve data issues and input resolution before inventing a custom network. Training notebooks may explain experiments, but reusable code belongs in Python modules/CLI commands.

### Recorded artifacts

For each run save configuration, data/split hashes, seed, code commit, resolved dependencies, hardware/VRAM, training time, metrics, prediction examples, best weights, and validation thresholds.

Ultralytics run outputs plus a JSON experiment summary are sufficient initially. A hosted experiment tracker is optional.

## 6. Approximate overlay specification

### First-release display

For a prediction with box [x1, y1, x2, y2], render a translucent ellipse:

- center: ((x1+x2)/2, (y1+y2)/2);
- initial radii: half the predicted width and height;
- one stable color per defect category;
- default opacity 0.40, user-adjustable between 0 and 0.80;
- a distinct outline/marker for the selected instance;
- no rectangular outline in the normal view.

For tiny detections, add a constant-screen-size locator ring so users can find them when zoomed out. This marker is presentation-only and does not change the prediction coordinates.

An ellipse identifies the approximate center and extent; it does not guarantee coverage of every defect pixel or represent the real boundary. Include the concise legend **"Approximate defect areas"**. Boxes remain available as an optional diagnostic view.

If softer edges are added, they are a visual style. Do not describe the fade as pixel confidence or an attention heatmap. A uniform-opacity ellipse is the simplest default.

### Mock example

A model returns:

~~~json
{
  "class_name": "open_circuit",
  "confidence": 0.94,
  "bbox_xyxy": [420, 180, 455, 205]
}
~~~

The app places a colored translucent ellipse centered at (437.5, 192.5), with radii 17.5 and 12.5 pixels, plus a selectable "Open circuit" entry. These are illustrative values, not measured results.

### Separate concepts

| Concept | Controlled by | Meaning |
|---|---|---|
| Detection confidence | Model and operating threshold | How strongly the model supports a defect prediction. |
| Overlay opacity | User | How much of the original image remains visible. |
| Overlay shape | Renderer, or future segmentation model | Estimated area now; model-predicted contour in the upgrade. |

Changing opacity cannot change the inspection decision. Do not measure physical defect area from an ellipse. Even future pixel masks require camera calibration before reporting square millimeters.

### Coordinate contract

All predictions and overlays refer to the orientation-normalized original image. Origin is top-left; x increases right and y down. Use exclusive right/bottom edges for stored boxes.

Normalize EXIF orientation once; save the exact image used for inference. Image and overlays share one canvas transform for zoom/pan. Browser resize, device pixel ratio, and display scaling must not move a marker relative to the defect.

If library output is already mapped to the original image, do not apply the transform again.

## 7. Large images and optional tiling

A 12-pixel feature in a 6000-pixel-wide photo becomes about 1.28 pixels if resized to width 640. This illustrative calculation explains why whole-board photos may need native-resolution crops.

Current Ultralytics tiling supports training/validation/prediction with overlapping windows [S16]. Initial large-image experiment:

- window size 640;
- 20% overlap;
- sequential/bounded tile batches;
- original-coordinate predictions after merging;
- identical policies during evaluation and application inference.

Check one interior defect, one in overlap, one crossing a seam, two close same-class defects, and one at the image edge. The same defect must not be counted twice. Two nearby defects must not be merged just because their boxes overlap.

Start with supported built-in merging. Add custom tile-aware logic only for a demonstrated failure. A clipped/ambiguous region can be re-inspected in a larger contextual crop; unresolved clipping gets a review warning.

The application must not silently resize an oversized image to bypass limits. Ask for a crop or use a declared profile. Tiling remains preprocessing/application logic when exporting the model [S16].

## 8. Evaluation and acceptance criteria

### Required first-release metrics

| Metric | Purpose |
|---|---|
| Box mAP50 and mAP50–95 | Defect localization and classification across IoU/confidence settings. |
| Per-class precision, recall, F1 | Exposes classes that are missed or confused. |
| Recall by defect-box size | Measures performance on small defects. |
| False positives per image | Quantifies spurious detections. |
| False-alarm image rate on verified-good inputs | Fraction of good inputs with at least one defect report. |
| Latency p50/p95 and peak memory | Documents actual deployment cost on named hardware. |

The approximate UI overlay has no segmentation ground truth and receives no mask-IoU score. Evaluate the detector's actual boxes. Ultralytics documents AP/precision/recall metrics [S18].

Use one-to-one, same-class matching at box IoU 0.5 for operating-threshold recall. Report mAP50–95 separately. DeepPCB's original published evaluation uses a different IoU threshold; do not directly compare scores computed under different protocols [S6].

### Thresholds and release decision

Choose thresholds on validation, never on test:

- Begin with a global confidence threshold; use per-class thresholds only if there is enough validation support.
- A provisional demo objective is at least 90% defect recall with no more than 5% false-alarm images on the declared verified-good set.
- These are aspirations, not expected or already achieved results.
- If the target is unmet, report the observed trade-off and keep assisted review.
- When good images are cleaned templates, label that evaluation accordingly.
- If adequate good data is absent, report false-alarm performance as unmeasured.
- Freeze model, head, preprocessing, and thresholds before test evaluation.

Choose the smallest model that meets the selected objective. If none does, choose the best measured trade-off and disclose limitations. Do not invent CV accuracy figures.

### Results and error states

Processing state and inspection decision are separate:

- A valid completed run with detections: defects_detected.
- A valid completed run with none above threshold: no_defects_detected.
- A completed run with a material input/coverage warning: review_needed, while still showing any predictions.
- Invalid input, missing model, crash, or incomplete output: Failed processing state with no inspection decision.

"No defects detected" is not a guarantee that the PCB is electrically good. Optical inspection covers visible appearance in the supported domain.

Benchmark total decode → inference → saved result time separately from model-only time. Record cold/warm behavior, image size, tile count, backend, hardware, and batch size. Published GPU timings are not laptop estimates.

## 9. Application architecture

This is the proposed application structure, not existing code.

~~~mermaid
flowchart TD
    UI["React inspection interface"] -->|Upload and review| API["FastAPI service"]
    API -->|Jobs and metadata| DB[("SQLite")]
    API -->|Images and exports| FS[("Artifact directory")]
    WORKER["Single inference worker"] -->|Claim jobs and commit results| DB
    WORKER -->|Read images and write predictions| FS
    WORKER -->|Load requested version| MODEL["Versioned YOLO bundle"]
    TRAIN["Offline training and evaluation"] -->|Promote evaluated artifact| MODEL
    API -->|Predictions and image URLs| UI
~~~

### Components

| Component | Responsibility |
|---|---|
| React/TypeScript frontend | Upload, progress, zoomable image/overlays, defect selection, history, export. |
| FastAPI | Input validation, enqueueing, results, review API, registered artifact serving. |
| Inference worker | One active job and one resident model; bounded memory and model loading. |
| ML core | Preprocessing, YOLO adapter, coordinate restoration, metrics, optional tiling. |
| SQLite | Image metadata, durable jobs, model/profile snapshots, predictions, reviews. |
| File storage | Canonical images, result JSON, overlays, optional masks, model bundles. |
| Training workflow | Separate commands/notebooks for data preparation, experiments, and evaluation. |

FastAPI's documentation distinguishes lightweight background tasks from heavy computation [S19]. A separate local worker keeps the API responsive. One process owns the loaded YOLO instance, avoiding concurrent access to mutable predictor state [S20].

This remains a small single-machine application. Redis, Celery, Kubernetes, and a distributed database are unnecessary for the initial scale.

### Durable jobs

~~~mermaid
stateDiagram-v2
    [*] --> queued
    queued --> running: worker claims
    queued --> cancelled: user cancels
    running --> completed: result committed
    running --> failed: error or expired lease
    failed --> queued: explicit retry
    completed --> [*]
    cancelled --> [*]
~~~

Use SQLite WAL mode, short transactions, and atomic claims. Each attempt has a worker ID, unique lease token, and attempt number. Heartbeat every 5 seconds, including during long inference through a dedicated heartbeat thread. A lease expires after 60 seconds.

The API sweeps stale leases every 5 seconds; the worker also sweeps before claiming work. This handles worker death even when the API stays alive, and restart before lease expiry. A stale attempt cannot finalize after another attempt replaces it.

Queued jobs survive restarts. Failed jobs have an explicit retry action. Initial cancellation applies only to queued jobs; an active GPU call is not promised to stop immediately.

Write artifacts to an attempt-specific temporary directory, rename them atomically, then commit Completed. The API never exposes partial output as a valid inspection.

### Model selection

Each job snapshots an immutable model ID and inference profile. The worker retains one model in memory and switches bundles only between jobs when necessary. Historical retries use the original bundle, not the current UI default.

Keep installed historical bundles. A missing requested bundle produces a clear error rather than substitution. New requests return 503 when the worker is unavailable; accepted queued jobs remain durable across outages.

## 10. Interface behavior

Proposed functional layout: a large image viewer, compact top toolbar, and right-side defect list. Branding, light/dark theme, and detailed styling remain customizable.

| Area | Behavior |
|---|---|
| Inspect | Upload image, choose installed model/profile, start inspection. |
| Toolbar | Fit image, zoom, pan, original/overlay toggle, opacity, export. |
| Viewer | Translucent approximate regions; optional boxes; selected defect marker. |
| Defect list | Class, confidence, ID, review state; click to focus. |
| Summary | Decision, model/profile, image size, latency, warnings. |
| History | Thumbnail, date, decision, model; reopen saved inspection. |
| Models | Declared task, classes, supported domain, measured evaluation. |

Use stable colors per class and text labels/IDs. A selected marker has a distinct outline. Color alone must not be the only way to identify a defect.

Canvas 2D supports alpha blending [S21]. Keep application controls in ordinary HTML for keyboard access. A single image-coordinate transform drives image, ellipse, locator ring, and optional future mask rendering.

A display-confidence filter only hides already-stored predictions. Label it as a display filter; it must not mutate the saved decision or recover predictions discarded during inference. A new operating threshold creates a new versioned profile and inspection.

User review can confirm, reject, or mark a detection uncertain; an image-level note can record a missed defect. Feedback is separate from raw predictions and never triggers automatic retraining.

Mobile layout prioritizes the image with a collapsible defect list. Keyboard controls support navigation, selection, zoom/fit, and Escape to clear selection.

## 11. API, persistence, and contracts

### Endpoints

| Method and path | Contract |
|---|---|
| GET /api/health | API/worker/model readiness. |
| GET /api/models | Installed model bundles and profiles. |
| POST /api/images | Multipart JPG/PNG; returns image_id and normalized dimensions. |
| POST /api/inspections | image_id, model_id, profile_id; returns 202 and inspection_id. |
| GET /api/inspections/{id} | State, progress, error or completed result. |
| GET /api/inspections | Paginated history. |
| POST /api/inspections/{id}/cancel | Cancel Queued; otherwise 409. |
| POST /api/inspections/{id}/retry | Retry Failed with original snapshot; otherwise 409. |
| POST /api/inspections/{id}/reviews | Append validated review event. |
| GET /api/inspections/{id}/export?format=json\|png | Export saved result or rendered overlay. |
| GET /api/artifacts/{artifact_id} | Serve registered artifact, never an arbitrary path. |

Serve the production-local frontend and API from one origin. Development allows only the explicit Vite localhost origin.

### Core contracts

Define shared types in contracts.py and generate TypeScript API types from OpenAPI:

- ImageRecord: image_id, content_hash, width, height, canonical_path, original_name, created_at.
- ModelManifest: model_id, task, weights_hash, class_map, dataset_version, runtime_versions, profiles, metrics_path.
- InspectionRequest: image_id, model_id, profile_id.
- DefectPrediction: defect_id, class_id, class_name, confidence, bbox_xyxy, localization_kind, optional mask_ref, warnings.
- InspectionResult: inspection_id, image_id, model_id, profile_id, decision, defects, timings_ms, warnings, created_at.
- ReviewEvent: review_id, inspection_id, optional defect_id, verdict, note, created_at.
- InferenceProfile: input size, tile policy, resolved head mode, NMS settings, thresholds, backend.

localization_kind is bbox_region for the first detector and predicted_mask only when a segmentation model supplies a real mask. A bbox_region prediction has no mask_ref. Do not serialize an ellipse as if the model predicted its boundary.

~~~python
class Predictor:
    def predict(self, image: CanonicalImage, profile: InferenceProfile) -> PredictionBatch:
        ...
~~~

CanonicalImage contains normalized RGB pixels and dimensions. PredictionBatch contains original-coordinate predictions and timings. API routes never depend on Ultralytics' internal Results object.

### Example completed prediction

~~~json
{
  "inspection_id": "example-inspection-001",
  "image_id": "example-board-017",
  "model_id": "deeppcb-yolo26n-v1",
  "profile_id": "quality-v1",
  "decision": "defects_detected",
  "defects": [
    {
      "defect_id": "d1",
      "class_id": 0,
      "class_name": "open_circuit",
      "confidence": 0.94,
      "bbox_xyxy": [420, 180, 455, 205],
      "localization_kind": "bbox_region",
      "mask_ref": null,
      "warnings": []
    }
  ],
  "warnings": []
}
~~~

This is mock data. A defect score is not a calibrated probability that the entire board is faulty.

### Tables

| Table | Data |
|---|---|
| images | Content identity, dimensions, canonical file reference. |
| models | Immutable bundle and manifest identity. |
| inspections | Image/model links, profile snapshot, status, timestamps. |
| inspection_attempts | Worker lease, heartbeat, errors, artifact directory. |
| defects | Class, confidence, box, localization kind, optional mask reference. |
| artifacts | Registered paths, MIME types, checksums. |
| reviews | Append-only human feedback. |

### Default limits and error behavior

Proposed bounds, adjustable after profiling:

- JPG/PNG; reject animated/multipage inputs.
- Maximum 25 MiB upload, 40 megapixels decoded, 12,000 pixels per side.
- Maximum 128 tiles; otherwise require a deliberate crop/profile change.
- One active job; at most 20 queued jobs.
- Generated IDs for paths; validate decoded bytes, not merely file extensions.
- No arbitrary checkpoint upload through the UI.
- Normalize EXIF once and grayscale to RGB; reject transparency until a fixed compositing rule is added.
- Do not silently shrink an image to pass a limit.
- Do not classify corrupt input or missing-model output as clean.

Keep files local. Log job/model IDs, timings, and structured errors. Initial retention is manual; do not silently delete inspection history.

## 12. Deployment and optional segmentation upgrade

### Model bundle and deployment

Bundle weights.pt, optional model.onnx, manifest.json, inference profiles, metrics.json, model_card.md, and small licensed smoke-test examples.

The manifest records dataset/split hashes, class map, actual task/head, weights checksum, package versions, preprocessing, thresholds, and supported input domain. A generic COCO checkpoint is initialization only: the UI must not present it as a PCB model.

Start with native PyTorch. Then test ONNX using the same Predictor contract. Ultralytics supports export [S22] and ONNX Runtime provides CPU/GPU execution providers [S23].

For the one-to-many baseline, preserve confidence filtering and NMS through the adapter. If using raw ONNX outputs, explicitly reproduce those operations; do not assume raw outputs are final predictions. Record whether NMS is external or embedded. Export-time low-score filtering must not discard candidates needed by the configured per-class thresholds.

The current documented nms setting can also select the YOLO26 inference head [S26]. Save the resolved head as well as the options, and check the pinned release. A backend that silently falls back to another head is a different profile requiring evaluation.

### Detection export parity

On a fixed reviewed fixture set:

- identical decisions/classes/per-class counts for clear cases;
- one-to-one same-class box matching at IoU 0.5;
- zero unmatched detections in either backend for those clear cases;
- mean matched-box IoU at least 0.98;
- validation mAP50–95 reduction no greater than 0.005 on the 0–1 scale.

These are proposed tolerances, not achieved results. Mark threshold-borderline fixtures in advance using native scores within 0.02 of the threshold and report differences separately. Do not hide lost detections by computing overlap only on surviving matches. Failed parity keeps PyTorch as the deployed backend.

Target Python 3.11 initially for conservative package compatibility; select a supported Node LTS that satisfies the chosen Vite release [S24]. Pin dependencies after smoke tests. Provide PowerShell commands to start the API/worker and serve the built frontend. Docker can follow a verified native setup.

### Optional segmentation upgrade

This upgrade is independent of first-release completion:

1. Obtain/audit VISION PCB_1 or reviewed project-specific polygons.
2. Train YOLO26n-seg and compare s-seg if warranted.
3. Preserve that dataset's class map; no silent pin_hole ↔ missing_hole conversion.
4. Return localization_kind=predicted_mask with a cropped binary PNG and original-image offsets.
5. Render its approximate learned contour with the same opacity and selection controls.
6. Clearly distinguish this model from the detector-based approximate-area model in model metadata.

**Coarse, useful boundaries are acceptable.** Use source annotation granularity consistently. Do not make perfect pixel agreement an application acceptance requirement. The primary acceptance question is whether the region usefully identifies the defect and preserves recall; report mask AP/IoU where truth supports it.

Ultralytics' instance format uses polygons [S12]. Preserve original masks/contours and visually audit conversion for major losses. Flag empty/disappearing instances, severe misalignment, and erased thin defects after actual training-time resizing/downsampling. Small boundary differences are not blockers.

mask_ratio affects training targets, not predicted mask resolution [S15]; retina_masks restores output to image dimensions but cannot invent lost detail [S17]. Neither setting guarantees exact defect boundaries.

For holes/disconnected structures, preserve source masks and use manual correction or a native-raster semantic experiment if necessary. CVAT supports YOLO segmentation export [S13]. A separate prompted segmenter is optional annotation assistance, never assumed to identify tiny defects correctly without review.

### Release attribution

Ultralytics provides AGPL-3.0 and enterprise options [S25]. Plan a compatible public portfolio release with notices. Keep dataset terms/provenance separate; VISION's polygon annotations are marked CC BY-NC 4.0 and original-image terms also apply [S4, S5]. Link datasets rather than bundling assets whose redistribution terms have not been verified.

## 13. Repository structure and constraints

| Planned path | Responsibility |
|---|---|
| pyproject.toml and dependency lock | Python package and exact dependencies. |
| src/pcb_inspection/contracts.py | Shared types and model/profile schemas. |
| src/pcb_inspection/data/ | Import, audit, split, convert detection labels; optional mask adapter later. |
| src/pcb_inspection/ml/train.py | Reproducible training CLI. |
| src/pcb_inspection/ml/evaluate.py | Metrics, thresholds, error gallery, experiment summaries. |
| src/pcb_inspection/ml/images.py | Decode, normalize, validate images. |
| src/pcb_inspection/ml/predictor.py | YOLO adapter and backend/head configuration. |
| src/pcb_inspection/ml/geometry.py | Coordinates, optional tiles, detection merging. |
| src/pcb_inspection/ml/export.py | ONNX parity and bundle packaging. |
| src/pcb_inspection/api/ | FastAPI app/routes. |
| src/pcb_inspection/storage.py | SQLite access, transactions, leases. |
| src/pcb_inspection/worker.py | Serial inference process. |
| src/pcb_inspection/artifacts.py | Atomic writes and server-side PNG/JSON export. |
| frontend/src/features/inspection/ | Viewer, overlays, controls, defect list. |
| frontend/src/features/history/ | Reopening saved inspections. |
| frontend/src/features/models/ | Model capabilities and measured performance. |
| frontend/src/api/ | Generated API types/client. |
| configs/ | Data maps, experiments, inference profiles. |
| tests/ and frontend/tests/ | Data, geometry, jobs, API, export, browser-flow tests. |
| scripts/ | Windows launch/development commands. |
| docs/ | Architecture, setup, model card, evaluation, attribution. |
| data/, runs/, models/, storage/ | Local artifacts excluded from normal Git commits. |

Create files when their task needs them; do not scaffold unnecessary abstractions.

### Global constraints

- Approximate region localization satisfies v1; learned segmentation is optional.
- The display must not claim a renderer-generated region is a predicted pixel mask.
- Original-image coordinates are canonical.
- Related source images/variants remain together across splits.
- Thresholds and hyperparameters are chosen on validation.
- Saved predictions, display preferences, and human feedback are separate.
- One worker owns one resident model at a time.
- Model/profile changes create new immutable identities.
- Scores and timing claims must be backed by measured runs.

### Review focus

| Failure mode | Required behavior | Task |
|---|---|---|
| Same-board variants leak into evaluation | Split audit flags/group-locks them. | 1 |
| EXIF or resize shifts overlay | Common canonical coordinates and transform tests. | 3/5 |
| Tile overlap duplicates a defect | Validated merge or explicit warning. | 3 |
| Worker stops or stale attempt completes | Periodic expiry recovery and lease-guarded finalize. | 4 |
| Display/review mutates saved decision | Immutable prediction with separate presentation/review. | 5/6 |
| ONNX loses one defect but retains another | Unmatched-instance/count parity checks. | 7 |

## 14. Implementation tasks

Each task should deliver a reviewable working result. Use focused tests for meaningful failures and small commits. These are planned checks, not tests already executed.

### Task 1 — Data and baseline-ready environment

**Files:** contracts.py; data/import.py, audit.py, splits.py, convert.py; configs/deeppcb.yaml; tests/test_data.py; docs/dataset_report.md.

**Consumes:** Original DeepPCB archive and source annotations.  
**Produces:** DatasetManifest, SplitManifest, converted labels, audit report.

Interfaces: import_dataset(root: Path) -> DatasetManifest; audit_dataset(manifest: DatasetManifest) -> AuditReport; make_splits(manifest: DatasetManifest, seed: int) -> SplitManifest; convert_labels(manifest: DatasetManifest, splits: SplitManifest) -> ConversionReport.

- [ ] Create isolated dependencies and source layout needed by this task.
- [ ] Download/import data with checksums and the explicit six-class mapping.
- [ ] Write failing fixtures for duplicate-parent leakage, unknown negatives, invalid boxes, and conversion error.
- [ ] Implement the audit, split, and label conversion.
- [ ] Run pytest tests/test_data.py -q and inspect representative images from every class.
- [ ] Freeze manifests; document negative-image provenance and generalization limits.
- [ ] Commit code/config/report, excluding data.

**Gate:** Valid annotations and a reproducible split exist.

### Task 2 — Train a real detector and evaluate it

**Files:** ml/train.py, evaluate.py; configs/train_nano.yaml; tests/test_metrics.py; docs/experiments.md.

**Consumes:** Task 1 manifests.  
**Produces:** TrainingRun, EvaluationReport, ThresholdProfile, trained weights.

Interfaces: train_model(config: TrainConfig) -> TrainingRun; evaluate_model(run: TrainingRun, split: str) -> EvaluationReport; choose_thresholds(report: EvaluationReport) -> ThresholdProfile.

- [ ] Define the configuration/report types.
- [ ] Write metric fixtures for exact match, duplicate prediction, missed defect, wrong class, and false alarm.
- [ ] Run tests to confirm expected failures, then implement metric aggregation.
- [ ] Run E0 and E1; inspect predicted locations and class mapping.
- [ ] Save validation metrics, error gallery, hardware/timing records, and thresholds.
- [ ] Commit reproducible training/evaluation code and baseline findings.

**Gate:** The checkpoint detects actual PCB defects; no target score is presumed achieved.

### Task 3 — Build inference and geometry

**Files:** ml/images.py, predictor.py, geometry.py; tests/test_geometry.py, test_predictor.py.

**Consumes:** Checkpoint and threshold profile.  
**Produces:** Predictor.predict(CanonicalImage, InferenceProfile) -> PredictionBatch.

- [ ] Add fixtures for EXIF rotation, grayscale, non-square images, empty detections, and tile seam cases.
- [ ] Assert restored coordinates and exact instance counts for fixture predictions.
- [ ] Implement validation, normalization, model adapter, and bounded optional tiling.
- [ ] Keep tiling disabled for standard 640×640 DeepPCB inputs.
- [ ] Run pytest tests/test_geometry.py tests/test_predictor.py -q.
- [ ] Inspect real predictions and commit.

**Gate:** Predictions are correctly mapped and independent of framework-internal result types.

### Task 4 — Deliver the API and durable worker

**Files:** storage.py, worker.py, artifacts.py, api/; tests/test_jobs.py, test_api.py.

**Consumes:** Task 3 predictor.  
**Produces:** Inspection endpoints, lease-safe execution, persisted results.

Interfaces: enqueue_inspection(request: InspectionRequest) -> InspectionRecord; claim_job(worker_id: str) -> JobLease | None; finish_job(lease: JobLease, result: InspectionResult) -> None; fail_job(lease: JobLease, error: JobError) -> None.

- [ ] Define state transitions, migrations, and structured errors.
- [ ] Write failing tests for bad/oversized input, missing worker/model, queue capacity, stale completion, and restart before lease expiry.
- [ ] Implement atomic claims, heartbeats, periodic reconciliation, and atomic artifact finalization.
- [ ] Verify API/history remain responsive during inference.
- [ ] Kill/restart the worker and verify failure/retry behavior.
- [ ] Queue jobs for different installed bundles and verify historical retries preserve model identity.
- [ ] Run the job/API tests and commit.

**Gate:** Every accepted job has a recoverable lifecycle; technical failures never appear as clean results.

### Task 5 — Build the approximate-area viewer

**Files:** frontend/src/features/inspection/; frontend/src/api/; viewer unit tests and browser inspection test.

**Consumes:** Canonical image and DefectPrediction records.  
**Produces:** Upload → inspect → translucent regions → selected defect.

- [ ] Define overlay state separately from prediction state.
- [ ] Test ellipse center/radii, non-square scaling, zoom/pan, resizing, overlapping detections, and opacity bounds.
- [ ] Implement Canvas image/overlay layers, locator rings, legend, toolbar, defect list, and processing states.
- [ ] Ensure the legend says approximate areas and no exact contour/area claim appears.
- [ ] Run frontend tests and a browser inspection flow.
- [ ] Commit the viewer.

**Gate:** Regions remain aligned and users can identify each predicted defect without visible rectangles.

### Task 6 — Add history, reviews, and export

**Files:** history/review frontend, review/export routes, artifacts.py; tests/test_reviews.py, test_exports.py.

**Consumes:** Completed results.  
**Produces:** Persistent reviews, reopened inspections, JSON/PNG export.

Interfaces: append_review(event: ReviewEvent) -> ReviewEvent; export_result(inspection_id: str, format: str, display: DisplayOptions) -> ArtifactRef.

- [ ] Test that feedback, filters, and opacity do not change stored predictions.
- [ ] Test shared ellipse-rendering fixtures between browser and PNG export.
- [ ] Implement append-only reviews, history, and exports with model/profile metadata.
- [ ] Reopen a result after restart and verify matching content.
- [ ] Run review/export and browser history tests; commit.

**Gate:** Results are reproducible and distinguish AI output from presentation and user feedback.

### Task 7 — Improve, select, and package the model

**Files:** experiment configs, ml/export.py, manifest schema, scripts/start.ps1, docs/model_card.md; tests/test_bundle.py.

**Consumes:** Baseline and fixed data/evaluation pipeline.  
**Produces:** Selected model/profile and validated local deployment.

- [ ] Run E2–E5 where data/compute support them.
- [ ] Choose model/settings on validation using accuracy/latency trade-offs.
- [ ] Repeat finalist seeds if feasible; disclose otherwise.
- [ ] Test missing/corrupt bundle files, class mismatch, and loss of one of multiple detections during export.
- [ ] Run ONNX parity; retain PyTorch if it fails.
- [ ] Build frontend, verify PowerShell launch, run Python/frontend/browser checks.
- [ ] Commit packaging, dependency locks, and measured comparisons.

**Gate:** The app runs from documented commands with a known, measured model.

### Task 8 — Final evaluation and portfolio delivery

**Files:** README.md; docs/evaluation_report.md, limitations.md; licensed demo assets.

**Consumes:** Frozen model, thresholds, application, untouched test data.  
**Produces:** Final measurements, reproducible demo, honest CV evidence.

- [ ] Evaluate final test data only after freezing decisions.
- [ ] Publish per-class metrics, dataset limitations, negative-set provenance, latency, and failure examples.
- [ ] If further tuning uses test findings, version the experiment and disclose that test reuse.
- [ ] Record a short demo of upload, colored regions, defect selection, history, and export.
- [ ] Write a CV description using measured detection/localization results.
- [ ] Verify setup from a clean environment and commit release documentation.

**Gate:** The project demonstrates trained object detection and working deployment. Call it segmentation only if the optional learned-mask upgrade is actually completed.

### Optional Task 9 — Add learned coarse contours

**Files:** data/masks.py, ml/masks.py, segmentation configs; mask adapter/tests; viewer predicted-mask layer.

**Consumes:** Reviewed segmentation data and existing application contracts.  
**Produces:** A separately versioned YOLO segmentation bundle.

- [ ] Audit accessible VISION/project labels and define its actual class map.
- [ ] Convert labels and inspect real training targets for empty/disappearing instances.
- [ ] Train a segmentation baseline and evaluate useful localization plus available mask metrics.
- [ ] Add predicted_mask rendering and original-coordinate mask export.
- [ ] Verify zoom/alignment, seam behavior, and backend parity.
- [ ] Compare visual usefulness and runtime against the detector; retain the simpler model if contours add little value.

**Gate:** Coarse learned contours are acceptable. Perfect boundary agreement is not a release condition.

## 15. Effort, risks, and remaining preferences

Approximate planning budget for a student, excluding extensive new annotation:

| Work | Estimated focused hours |
|---|---:|
| Data audit, splits, setup | 5–10 |
| Baseline training/evaluation | 5–10 plus unattended training time |
| Inference, API, persistence | 8–14 |
| Viewer, history, export | 8–14 |
| Experiments, packaging, final report | 8–16 |
| Optional learned segmentation | Additional work, estimated after label audit |

A sensible initial budget is **35–65 hours**, roughly **4–7 weeks at 10 hours/week**. Unfamiliar tooling, data-access delays, or real-camera collection can extend this. These estimates are not guarantees.

| Risk | Response |
|---|---|
| Dataset performance fails on camera photos | Collect a separate real-camera development/test set and report domain limits. |
| Tiny defects missed | Audit labels/resolution; test larger original-image tiles before changing architecture. |
| Too few realistic good images | Report template-negative performance separately and acquire real negatives. |
| GPU memory constraints | Nano model, measured batch sizes, bounded tile batches. |
| User mistakes overlay for precise segmentation | Approximate-area legend; preserve localization_kind in results. |
| App work eclipses ML work | Deliver the trained baseline before polishing secondary screens. |

The plan can proceed with the stated defaults. The most useful customization details are the available GPU/VRAM, preferred dark/light styling, and whether the later target is a camera station or uploaded-image inspection. These do not block the current architecture.



## 16. Evidence register


All links were consulted on 12 November 2026. Dataset facts and library capabilities come from the sources below. Architectural boundaries, defaults, test thresholds, and effort estimates are this plan's proposals.

- **[S1] UPT, IPCEI announcement:** [Project 3 and AOI research context](https://www.upt.ro/articole/ipcei--cel-mai-important-proiect-din-istoria-universitatii-politehnica-timisoara-cercetare-de-varf-infrastructura-strategica-si-un-nou-ecosistem-al-inovarii).
- **[S2] Ultralytics:** [Instance segmentation task and pretrained model family](https://docs.ultralytics.com/tasks/segment).
- **[S3] Ultralytics:** [Semantic segmentation task](https://docs.ultralytics.com/tasks/semantic).
- **[S4] Bai et al.:** [VISION Datasets paper, annotation method, splits, and PCB_1 categories](https://arxiv.org/html/2306.07890v2).
- **[S5] VISION Workshop:** [Official dataset card, access conditions, formats, and license](https://huggingface.co/datasets/VISION-Workshop/VISION-Datasets).
- **[S6] DeepPCB authors:** [Original dataset repository](https://github.com/tangsanli5201/DeepPCB).
- **[S7] MeiweiPCB authors:** [Dataset repository and available annotations](https://github.com/youtang1993/MeiweiPCB).
- **[S8] Amazon Science:** [VisA dataset and split preparation](https://github.com/amazon-science/spot-diff).
- **[S9] Amazon Science:** [Original pixel-label category mappings](https://github.com/amazon-science/spot-diff/blob/main/utils/id2class.py).
- **[S10] Original PCB_1 source:** [Synthetic PCB dataset linked by the VISION paper](https://github.com/Ironbrotherstyle/PCB-DATASET).
- **[S11] HZDR:** [PCB-Vision dataset description and component classes](https://rodare.hzdr.de/record/2704).
- **[S12] Ultralytics:** [Instance segmentation dataset format](https://docs.ultralytics.com/datasets/segment).
- **[S13] CVAT:** [Ultralytics YOLO annotation import/export](https://docs.cvat.ai/docs/dataset_management/formats/format-yolo-ultralytics/).
- **[S14] Ultralytics:** [YOLO26 architecture and task support](https://docs.ultralytics.com/models/yolo26).
- **[S15] Ultralytics:** [Configuration, mask_ratio, and inference-head settings](https://docs.ultralytics.com/usage/cfg).
- **[S16] Ultralytics:** [High-resolution tiling and mask placement](https://docs.ultralytics.com/guides/high-resolution-tiling).
- **[S17] Ultralytics:** [Prediction results and retina_masks](https://docs.ultralytics.com/modes/predict).
- **[S18] Ultralytics:** [Performance metrics](https://docs.ultralytics.com/guides/yolo-performance-metrics).
- **[S19] FastAPI:** [Background tasks and heavy-computation caveat](https://fastapi.tiangolo.com/tutorial/background-tasks/).
- **[S20] Ultralytics:** [Model ownership and thread-safe inference](https://docs.ultralytics.com/guides/yolo-thread-safe-inference).
- **[S21] MDN:** [Canvas transparency](https://developer.mozilla.org/en-US/docs/Web/API/CanvasRenderingContext2D/globalAlpha).
- **[S22] Ultralytics:** [Model export options](https://docs.ultralytics.com/modes/export).
- **[S23] ONNX Runtime:** [Execution providers](https://onnxruntime.ai/docs/execution-providers/).
- **[S24] Vite:** [Setup and environment requirements](https://vite.dev/guide/).
- **[S25] Ultralytics:** [Licensing options](https://www.ultralytics.com/license).
- **[S26] Ultralytics:** [Explicit head selection across prediction, validation, and export](https://docs.ultralytics.com/guides/end2end-detection).


- **[S27] Ultralytics:** [Object detection outputs and current detector models](https://docs.ultralytics.com/tasks/detect).
