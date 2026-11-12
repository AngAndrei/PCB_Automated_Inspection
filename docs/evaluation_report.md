# Development evaluation, 12 November 2026

This is a pipeline integration result, not the planned full-data detector baseline.

| Item | Measured value |
|---|---|
| Detector | YOLO26n, Ultralytics8.4.211 / PyTorch2.15.0+cpu |
| Training | 5 epochs, 80/802 training crops, CPU |
| Subset | Sorted first80 images, all from source board00041 |
| Validation | 198 crops from a separate source group, 1345 defects |
| Training wall time | 432.705 seconds |
| Separate evaluation wall time | 47.334 seconds |
| Operating profile | 640px, confidence0.25, NMS IoU0.5, match IoU0.5 |
| TP / FP / FN | 0 /88 /1345 |
| Precision / recall / F1 | 0 /0 /0 |
| Box mAP50 | 0.01295 |
| Box mAP50-95 | 0.00545 |
| Representative good-board false-alarm rate | Unmeasured: no verified representative good set |
| Final test evaluation | Not run |

The selected checkpoint has poor recognition performance. It remains explicitly a development model; the application requires manual review for all its outputs. This result must not be used as a successful PCB-defect-recognition CV metric.

Next ML work: train on the full802-image training split, inspect validation errors, compare nano/small if compute permits, select operating thresholds on validation, then evaluate the held-out published test once decisions are fixed. Obtain real camera images and representative good boards separately. Published test source-board overlap is documented in dataset_report.md.

Artifacts remain locally under `runs/pcb/development-nano-5ep-subset/`: checkpoint, run metadata, exact subset IDs/hash, training curves, validation predictions and metrics. Installed bundle: `models/deeppcb-development-v1`, weights SHA-256 `a2c826570e27c8d9c7b5473953801a021a25b8addc089d3dfebbb7aa01311f75`.

The application itself was verified independently: Python tests, frontend tests/build, desktop/mobile browser workflow, and a live real-YOLO API inspection with PNG/JSON export. Fixture detections in browser tests establish UI behavior only. Telemetry is disabled before ML imports, and a fresh-process test verifies analytics and online mode are off.
