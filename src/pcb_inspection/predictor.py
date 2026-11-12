from math import isfinite
from time import perf_counter

from .contracts import CLASS_NAMES
from .geometry import tile_windows, class_aware_nms, valid_box


class YoloAdapter:
    def __init__(self, weights_path):
        from .runtime import configure_runtime

        configure_runtime()
        from ultralytics import YOLO

        self.model = YOLO(weights_path, task="detect")
        names = [self.model.names[index] for index in range(len(self.model.names))]
        if names != CLASS_NAMES:
            raise ValueError("Checkpoint classes do not match the PCB bundle.")

    def __call__(self, image, profile):
        results = self.model.predict(
            image,
            imgsz=profile.get("imgsz", 640),
            conf=profile.get("confidence", 0.25),
            iou=profile.get("iou", 0.5),
            device=profile.get("device", "cpu"),
            nms=profile.get("nms", not profile.get("end2end", False)),
            verbose=False,
        )
        return [
            {"box": box, "score": score, "class_id": int(class_id)}
            for box, score, class_id in zip(
                results[0].boxes.xyxy.cpu().tolist(),
                results[0].boxes.conf.cpu().tolist(),
                results[0].boxes.cls.cpu().tolist(),
            )
        ]


class Predictor:
    def __init__(self, weights_path=None, *, adapter=None):
        self.adapter = adapter if adapter is not None else YoloAdapter(weights_path)

    def predict(self, image, profile):
        start = perf_counter()
        width, height = image.image.size
        windows = (
            tile_windows(width, height, profile.get("imgsz", 640))
            if profile.get("tiled")
            else [(0, 0, width, height)]
        )
        boxes, scores, classes = [], [], []
        warnings = []
        if len(windows) > 1:
            warnings.append("Tiled inspection: review tile seams for clipped or repeated defects.")
        elif max(width, height) > 1600:
            warnings.append(
                "Large image resized for inference. Tiny defects may be missed; use a crop or tiled profile."
            )
        for x1, y1, x2, y2 in windows:
            crop = image.image if len(windows) == 1 else image.image.crop((x1, y1, x2, y2))
            for raw in self.adapter(crop, profile):
                box = raw["box"]
                score, class_id = float(raw["score"]), int(raw["class_id"])
                if (
                    not valid_box(box, x2 - x1, y2 - y1)
                    or not isfinite(score)
                    or not 0 <= score <= 1
                    or not 0 <= class_id < len(CLASS_NAMES)
                ):
                    raise ValueError("Model returned invalid coordinates, confidence, or class.")
                if score < profile.get("confidence", 0.25):
                    continue
                boxes.append([box[0] + x1, box[1] + y1, box[2] + x1, box[3] + y1])
                scores.append(score)
                classes.append(class_id)
        keep = class_aware_nms(boxes, scores, classes, profile.get("iou", 0.5))
        defects = [
            {
                "defect_id": f"d{number + 1}",
                "class_id": classes[index],
                "class_name": CLASS_NAMES[classes[index]],
                "confidence": scores[index],
                "bbox_xyxy": boxes[index],
                "localization_kind": "bbox_region",
                "mask_ref": None,
                "warnings": [],
            }
            for number, index in enumerate(keep)
        ]
        return {
            "defects": defects,
            "warnings": warnings,
            "timings_ms": {"inference": round((perf_counter() - start) * 1000, 2)},
            "tile_count": len(windows),
        }
