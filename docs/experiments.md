# Training and evaluation protocol

The baseline is `yolo26n.pt`, 100 epochs, image size 640, batch 4, automatic device selection, workers 0, patience 20, and seed 42. It disables mosaic, mixup, and copy-paste. Mild augmentation uses translation 0.05, scale 0.1, horizontal flip 0.5, and value jitter 0.1. The readable configuration is `configs/baseline.yaml`; CLI options select run-specific settings.

Use validation only for choosing models, confidence thresholds, and profiles. Evaluate the published test split only after those choices are fixed. Its board overlap is documented in `dataset_report.md`; its results are not estimates of performance on unseen board designs.

```powershell
$env:PYTHONPATH='src'
# Quick execution check; these weights do not establish useful accuracy.
.venv/Scripts/python.exe -m pcb_inspection.ml.train --data data/processed/deeppcb/data.yaml --epochs 1 --fraction 0.05 --device cpu --project runs/pcb --name smoke

# Full baseline, with model acquisition performed by Ultralytics if needed.
.venv/Scripts/python.exe -m pcb_inspection.ml.train --model yolo26n.pt --data data/processed/deeppcb/data.yaml --epochs 100 --project runs/pcb --name baseline

# Choose thresholds on validation; preserve split identity in the output JSON.
.venv/Scripts/python.exe -m pcb_inspection.ml.evaluate --weights runs/pcb/baseline/weights/best.pt --data data/processed/deeppcb/data.yaml --split val --confidence 0.25 --iou 0.5 --output runs/pcb/baseline/val_metrics.json

# Run only after the deployment profile has been fixed.
.venv/Scripts/python.exe -m pcb_inspection.ml.evaluate --weights runs/pcb/baseline/weights/best.pt --data data/processed/deeppcb/data.yaml --split test --confidence 0.25 --iou 0.5 --output runs/pcb/baseline/test_metrics.json

# Promotion verifies the checkpoint's exact six-class names and refuses overwrites.
.venv/Scripts/python.exe -m pcb_inspection.ml.bundle --weights runs/pcb/baseline/weights/best.pt --models models --model-id deeppcb-yolo26n-v1 --label 'DeepPCB YOLO26 nano' --metrics runs/pcb/baseline/test_metrics.json
```

The installed Ultralytics 8.4.211 API selects YOLO26's one-to-many detection head using `nms=True`. Its predictor/validator resolve the model's internal `end2end` flag as `args.nms is False`, so this selects `end2end=False` followed by NMS. The old `end2end` configuration argument is deprecated; a regression checks generated train/validation kwargs against the real installed `get_cfg` without loading a network. The run metadata records the inference mode (`end2end:false`, `nms:true`, API argument `nms=True`), source-manifest SHA256, complete training configuration, dependency versions, Python, hardware, actual device, and run directory. Evaluation uses the same head mode. Bundle profiles retain the application contract's `end2end:false`; the application translates that to `nms=True`. Workers default to zero for predictable Windows execution. Set `$env:YOLO_CONFIG_DIR=(Join-Path (Get-Location) 'data/ultralytics')` before CLI runs to keep Ultralytics settings local. Project paths are resolved relative to the invocation directory before calling Ultralytics, avoiding its additional relative-project prefix.

Ultralytics validation computes mAP using its confidence sweep. Separately, deployment-threshold metrics use confidence-ordered, same-class, one-to-one matching at IoU >= 0.5; equal-confidence predictions retain their input order and equal-overlap ground truths use manifest order. The JSON reports TP, FP, FN, precision, recall, F1, and explicit negative-set availability. False positives per good image and false-alarm image rate are computed only on verified negatives and are null when that set is absent. DeepPCB's older published IoU 0.33 scores are not directly comparable to these IoU 0.5 metrics.

For deterministic replay without loading Ultralytics, pass `--predictions-file` instead of `--weights`. The file maps each selected manifest sample ID to an explicit prediction list, whose items contain `class_id`, pixel `box: [x1,y1,x2,y2]`, and `confidence`. Lists must already reflect the intended deployment confidence/NMS profile; an empty list is required for a measured no-detection image. Missing sample entries raise an error. Replay does not invent mAP; `ultralytics_validation` is null.

No accuracy claim is made by preparation or fixture tests. Actual measured training/evaluation runs and their metadata are the evidence for a promoted model. A smoke-trained bundle should be clearly labeled as a smoke result and must not be presented as a validated detector.

## Measured development runs

| Run | Training subset | Epochs | Validation | Wall time | Result |
|---|---|---|---|---|---|
| smoke | 40 of 802 train images (5%) | 1 | Whole held-out board, 198 images | Train 170.67s; explicit evaluation 50.98s | mAP50 .014394; mAP50-95 .004609; threshold F1 0 |
| development-nano-5ep-subset | 80 of 802 train images (10%) | 5 | Whole held-out board, 198 images | Train 432.71s; explicit evaluation 47.33s | mAP50 .012954; mAP50-95 .005448; threshold F1 0 |

The smoke standalone metrics use confidence 0.25, NMS IoU 0.5 and matching IoU 0.5. The full-data 100-epoch baseline and model-size comparison remain pending. An initial full-data 5-epoch run was interrupted before completing epoch 1 when the controller bounded the development run to a 10% training subset; it produced no completed-epoch model and is not an experiment result. Test images remain untouched.

The installed Ultralytics `fraction` option takes the sorted training-image prefix. The development subset therefore contains 80 images from `group00041/00041`, rather than a stratified selection across all six training boards. `training_subset.json` records the exact sample IDs and manifest hash. This is a further limitation of this bounded development model; validation still uses all 198 images from the separate board.

The promoted integration bundle is `models/deeppcb-development-v1`, label `YOLO26n · development (5 epochs, 10% train)`, explicitly marked `training_status: development`. Its manifest contains exact subset provenance and measured validation metrics. At the deployment profile's confidence 0.25, NMS IoU 0.5 and matching IoU 0.5, it produced **TP 0, FP 88, FN 1,345**. Its poor accuracy prevents a target-quality claim or a reliable clean-board decision. No test evaluation or threshold tuning was performed. Bundle README and `docs/development/ml-report.md` retain the full evidence and pending work.
