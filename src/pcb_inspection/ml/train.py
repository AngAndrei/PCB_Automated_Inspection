"""Train a reproducible, conservative YOLO26 baseline without consulting the test split."""

import argparse
from datetime import datetime, timezone
import importlib.metadata
from pathlib import Path
import platform
import sys

from .common import sha256, write_json


def training_arguments(
    data,
    epochs=100,
    imgsz=640,
    batch=4,
    device="auto",
    workers=0,
    patience=20,
    seed=42,
    fraction=1.0,
    project="runs/pcb",
    name="baseline",
):
    if epochs < 1 or imgsz < 32 or batch < 1 or workers < 0 or patience < 0 or not 0 < fraction <= 1:
        raise ValueError("Invalid training configuration")
    args = {
        "data": str(data),
        "epochs": epochs,
        "imgsz": imgsz,
        "batch": batch,
        "workers": workers,
        "patience": patience,
        "seed": seed,
        "fraction": fraction,
        "project": str(Path(project).resolve()),
        "name": name,
        "exist_ok": False,
        "deterministic": True,
        "mosaic": 0.0,
        "mixup": 0.0,
        "copy_paste": 0.0,
        "degrees": 0.0,
        "translate": 0.05,
        "scale": 0.1,
        "shear": 0.0,
        "perspective": 0.0,
        "flipud": 0.0,
        "fliplr": 0.5,
        "hsv_h": 0.0,
        "hsv_s": 0.0,
        "hsv_v": 0.1,
        "nms": True,
        "plots": True,
        "val": True,
    }
    if device != "auto":
        args["device"] = device
    return args


def runtime_metadata():
    import torch

    dependencies = {}
    for name in ("ultralytics", "torch", "torchvision", "numpy", "pillow", "pyyaml"):
        try:
            dependencies[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            dependencies[name] = None
    return {
        "python": sys.version,
        "dependencies": dependencies,
        "hardware": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cuda_available": torch.cuda.is_available(),
            "cuda_version": torch.version.cuda,
            "gpu_names": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
        },
    }


def train(model="yolo26n.pt", **kwargs):
    from ..runtime import configure_runtime

    configure_runtime()
    from ultralytics import YOLO
    from ultralytics.cfg import DEFAULT_CFG_DICT

    if "nms" not in DEFAULT_CFG_DICT:
        raise RuntimeError("Installed Ultralytics does not support explicit NMS head selection")
    args = training_arguments(**kwargs)
    data = Path(args["data"]).resolve()
    manifest = data.parent / "manifest.json"
    if not manifest.is_file():
        raise ValueError("Prepared data requires adjacent manifest.json")
    metadata = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "source_manifest_sha256": sha256(manifest),
        "configuration": args,
        "inference_mode": {
            "end2end": False,
            "nms": True,
            "api_argument": "nms=True",
            "description": "one-to-many head with NMS",
        },
        **runtime_metadata(),
    }
    detector = YOLO(model)
    try:
        detector.train(**args)
    except BaseException as exc:
        trainer = getattr(detector, "trainer", None)
        if trainer is not None and getattr(trainer, "save_dir", None):
            metadata.update({"status": "failed", "error": str(exc)})
            write_json(Path(trainer.save_dir) / "run_metadata.json", metadata)
        raise
    run = Path(detector.trainer.save_dir)
    metadata.update(
        {
            "status": "completed",
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "resolved_device": str(detector.trainer.device),
            "resolved_save_dir": str(run.resolve()),
        }
    )
    write_json(run / "run_metadata.json", metadata)
    print(run)
    return run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="yolo26n.pt")
    parser.add_argument("--data", required=True)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--fraction",
        type=float,
        default=1.0,
        help="Train subset fraction; use with small epochs for smoke runs",
    )
    parser.add_argument("--project", default="runs/pcb")
    parser.add_argument("--name", default="baseline")
    train(**vars(parser.parse_args()))


if __name__ == "__main__":
    main()
