# Scope and limitations

- DeepPCB consists of processed, aligned bare-board crops, with artificial defects added to some samples. Evaluate real-camera images separately.
- Published test membership is preserved, including source-board overlap with training. Adjacent crop dependence cannot be ruled out by byte-level duplicate checks.
- A short training run verifies the pipeline, not reliable inspection quality. Baseline selection, confidence thresholds and test metrics require the planned experiments.
- No representative real-good image set has been collected. False-alarm rate is not inferred from unlabeled images or synthesized negatives.
- Colored ellipses show approximate center/extent derived from detection boxes. Their shape and area are presentation choices.
- Large-image resizing can erase small defects. Optional tiling can introduce clipped/duplicate seam predictions; warnings require review.
- This initial local service has no multi-user authentication, remote deployment, live camera capture, learned segmentation, or ONNX optimization. Its launcher binds to localhost.
- UI acceptance tests use a labeled fixture predictor in an isolated test service. Production inference loads only installed PCB checkpoints.
- The installed PyTorch runtime initially uses CPU. CUDA support depends on the actual GPU, driver and compatible PyTorch distribution.
- Uploaded images and results are stored locally under data/app. Back up valuable inspections before clearing that directory.
