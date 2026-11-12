# Initial model card

Task: six-class detection on bare-PCB images. Architecture: Ultralytics YOLO26 nano, transfer learning from the official pretrained checkpoint. Inference uses the one-to-many head with NMS. Application overlays are renderer-generated approximate ellipses.

Training data: DeepPCB research dataset. Prepared split: 802 train, 198 validation, 500 published test. Validation is separated by source-board group from training. Published test is not fully board-disjoint; details are in dataset_report.md.

Current installed model: `deeppcb-development-v1`, explicitly `training_status: development`. It ran 5 epochs on 80 of 802 training images (the sorted subset is entirely source board 00041). This is an integration check with **poor accuracy**, not a reliable defect detector. Training took 432.71 seconds on the installed CPU runtime; standalone evaluation took 47.33 seconds.

Validation on 198 images / 1345 defects at confidence 0.25, NMS IoU 0.5 and match IoU 0.5: **TP 0, FP 88, FN 1345, F1 0**. Sweep mAP50: 0.01295; mAP50-95: 0.00545. No representative good set exists, so its false-alarm rate is unmeasured. No test data was evaluated. The application forces `review_needed` for this development model.

Full-data training, threshold selection and nano/small comparisons remain pending. See `runs/pcb/development-nano-5ep-subset/`, its run metadata, validation JSON and exact training_subset.json. These local artifacts stay outside Git.

Input: canonical RGB JPG/PNG, orientation normalized before inference. Operating profile: 640px, confidence 0.25, NMS IoU 0.5, CPU by default. These initial thresholds are not calibrated.

Unsupported claims: assembled-board component inspection, solder-joint inspection, physical defect area, electrical functionality, robust phone-camera deployment, and learned segmentation boundaries. Representative factory-good photographs are not available; false-alarm rate on that population is unmeasured.

Deployment: a single local worker; SHA-256 checked immutable bundles with six-class mapping. Feedback is append-only and does not trigger training.
