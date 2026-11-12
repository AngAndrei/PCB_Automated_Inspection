"""Evaluate a fixed validation or test split; thresholds must be selected using validation only."""

import argparse
import json
from pathlib import Path

from .common import CLASS_NAMES, sha256, write_json
from .metrics import aggregate


def inference_arguments(imgsz=640, batch=4, device="auto"):
    if imgsz < 32 or batch < 1:
        raise ValueError("Invalid inference configuration")
    kwargs = {"imgsz": imgsz, "batch": batch, "workers": 0, "nms": True}
    if device != "auto":
        kwargs["device"] = device
    return kwargs


def evaluate_saved(manifest, predictions, split="val", iou_threshold=0.5):
    if split not in ("val", "test"):
        raise ValueError("Evaluation split must be val or test")
    selected = [s for s in manifest["samples"] if s["split"] == split]
    if not selected:
        raise ValueError(f"No samples in {split} split")
    records = []
    for sample in selected:
        if sample["id"] not in predictions:
            raise ValueError(
                f"Missing predictions for {sample['id']}; use an explicit empty list for no detections"
            )
        records.append(
            {
                "truth": sample["boxes"],
                "predictions": predictions[sample["id"]],
                "verified_negative": sample.get("verified_negative", False),
            }
        )
    return {
        "dataset_version": manifest["dataset_version"],
        "split": split,
        "metrics": aggregate(records, iou_threshold),
        "negative_metric_note": "Rates use explicitly verified negatives only; null means no good-set denominator.",
    }


def evaluate(
    weights,
    data,
    output,
    split="val",
    confidence=0.25,
    iou=0.5,
    imgsz=640,
    batch=4,
    device="auto",
    predictions_file=None,
):
    data, output = Path(data).resolve(), Path(output).resolve()
    manifest_path = data.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validation_metrics = None
    if predictions_file:
        predictions = json.loads(Path(predictions_file).read_text(encoding="utf-8"))
    else:
        if weights is None:
            raise ValueError("Provide weights or a saved predictions file")
        from ..runtime import configure_runtime

        configure_runtime()
        from ultralytics import YOLO

        model = YOLO(str(weights))
        names = model.names
        names = [names[i] for i in range(len(names))] if isinstance(names, dict) else list(names)
        if names != CLASS_NAMES:
            raise ValueError("Model class names do not match prepared data")
        kwargs = inference_arguments(imgsz, batch, device)
        output.parent.mkdir(parents=True, exist_ok=True)
        # mAP uses the validator's full confidence sweep, independently from deployment threshold counts.
        validation = model.val(
            data=str(data),
            split=split,
            conf=0.001,
            iou=iou,
            project=str(output.parent / "validation"),
            name=output.stem,
            plots=True,
            **kwargs,
        )
        validation_metrics = {str(k): float(v) for k, v in validation.results_dict.items()}
        selected = [s for s in manifest["samples"] if s["split"] == split]
        predictions = {}
        for offset in range(0, len(selected), batch):
            chunk = selected[offset : offset + batch]
            results = model.predict(
                source=[str(data.parent / s["image"]) for s in chunk],
                conf=confidence,
                iou=iou,
                verbose=False,
                **kwargs,
            )
            for sample, result in zip(chunk, results, strict=True):
                predictions[sample["id"]] = [
                    {"class_id": int(cls), "box": list(map(float, box)), "confidence": float(score)}
                    for cls, box, score in zip(
                        result.boxes.cls.cpu().tolist(),
                        result.boxes.xyxy.cpu().tolist(),
                        result.boxes.conf.cpu().tolist(),
                        strict=True,
                    )
                ]
        write_json(output.with_name(output.stem + "_predictions.json"), predictions)
    result = evaluate_saved(manifest, predictions, split, 0.5)
    result.update(
        {
            "source_manifest_sha256": sha256(manifest_path),
            "configuration": {
                "confidence": confidence,
                "nms_iou": iou,
                "matching_iou": 0.5,
                "imgsz": imgsz,
                "end2end": False,
                "nms": True,
            },
            "ultralytics_validation": validation_metrics,
            "weights_sha256": sha256(weights) if weights else None,
            "prediction_source": str(predictions_file)
            if predictions_file
            else "measured_model_inference",
        }
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, result)
    print(output)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=("val", "test"), default="val")
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--predictions-file", type=Path)
    evaluate(**vars(parser.parse_args()))


if __name__ == "__main__":
    main()
