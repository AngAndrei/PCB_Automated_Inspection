"""Promote trained six-class detector weights into an immutable application bundle."""

import argparse
import json
from pathlib import Path
import re
import shutil

from .common import CLASS_NAMES, sha256, write_json
from ..contracts import InferenceProfile


def promote(
    weights,
    models,
    model_id,
    label,
    dataset_version,
    metrics,
    class_names,
    training_status="unvalidated",
):
    if list(class_names) != CLASS_NAMES:
        raise ValueError("Trained class list does not match the six application class names")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}", model_id):
        raise ValueError("Invalid model_id")
    weights = Path(weights)
    if not weights.is_file() or not weights.stat().st_size:
        raise ValueError("Weights must be a nonempty file")
    # Validate JSON before creating a bundle, so malformed metrics leave no partial directory.
    json.dumps(metrics, allow_nan=False)
    digest = sha256(weights)
    if not isinstance(metrics, dict) or metrics.get("weights_sha256") != digest:
        raise ValueError("Evaluation must identify this exact checkpoint SHA-256")
    if metrics.get("dataset_version") != dataset_version:
        raise ValueError("Evaluation dataset version does not match promotion")
    if metrics.get("prediction_source") != "measured_model_inference":
        raise ValueError(
            "Promotion requires a measured checkpoint evaluation, not saved-prediction replay"
        )
    if (
        metrics.get("split") not in {"val", "test"}
        or not isinstance(metrics.get("metrics"), dict)
        or not re.fullmatch(r"[a-f0-9]{64}", str(metrics.get("source_manifest_sha256", "")))
    ):
        raise ValueError("Evaluation split, metrics or dataset provenance is missing")
    config = metrics.get("configuration", {})
    if (
        not isinstance(config, dict)
        or config.get("end2end") is not False
        or config.get("nms") is not True
        or config.get("tiled", False)
        or config.get("matching_iou") != 0.5
    ):
        raise ValueError("Evaluation must use the supported whole-image one-to-many/NMS profile")
    try:
        profile = InferenceProfile(
            profile_id="quality-v1",
            imgsz=config["imgsz"],
            confidence=config["confidence"],
            iou=config["nms_iou"],
        ).model_dump()
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError("Evaluation operating settings are missing or invalid") from exc
    if training_status not in {"unvalidated", "development", "validated"}:
        raise ValueError("Unknown training status")
    model_root = Path(models).resolve()
    bundle = model_root / model_id
    if bundle.resolve().parent != model_root:
        raise ValueError("Invalid model bundle path")
    bundle.mkdir(parents=True, exist_ok=False)
    try:
        shutil.copyfile(weights, bundle / "weights.pt")
        if sha256(bundle / "weights.pt") != digest:
            raise ValueError("Checkpoint changed during promotion")
        write_json(
            bundle / "manifest.json",
            {
                "model_id": model_id,
                "label": label,
                "task": "detect",
                "dataset_version": dataset_version,
                "class_names": CLASS_NAMES,
                "sha256": digest,
                "weights_sha256": digest,
                "training_status": training_status,
                "metrics": metrics,
                "profiles": [profile],
            },
        )
    except BaseException:
        shutil.rmtree(bundle)
        raise
    return bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", required=True, type=Path)
    parser.add_argument("--models", type=Path, default=Path("models"))
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--dataset-version", default="deeppcb-published-v1")
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument(
        "--training-status", choices=("unvalidated", "development", "validated"), default="unvalidated"
    )
    args = parser.parse_args()
    from ..runtime import configure_runtime

    configure_runtime()
    from ultralytics import YOLO

    detector = YOLO(str(args.weights))
    if detector.task != "detect":
        raise ValueError("Weights are not an object detector")
    names = detector.names
    names = [names[i] for i in range(len(names))] if isinstance(names, dict) else list(names)
    result = promote(
        args.weights,
        args.models,
        args.model_id,
        args.label,
        args.dataset_version,
        json.loads(args.metrics.read_text(encoding="utf-8")),
        names,
        training_status=args.training_status,
    )
    print(result)


if __name__ == "__main__":
    main()
