"""Configure the ML dependency before importing model code or event callbacks."""

import os
from pathlib import Path


def configure_runtime():
    # These are supported Ultralytics environment controls, read during its first import.
    os.environ["YOLO_OFFLINE"] = "true"
    os.environ["YOLO_AUTOINSTALL"] = "false"
    config = Path(
        os.environ.setdefault(
            "YOLO_CONFIG_DIR", str(Path(__file__).resolve().parents[2] / "data/ultralytics")
        )
    )
    config.mkdir(parents=True, exist_ok=True)
    from ultralytics import settings

    settings.update(
        {
            key: False
            for key in ("sync", "hub", "clearml", "comet", "mlflow", "neptune", "raytune", "wandb")
            if key in settings
        }
    )
