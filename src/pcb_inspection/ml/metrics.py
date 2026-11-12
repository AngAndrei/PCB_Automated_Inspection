"""Confidence-ordered, same-class, one-to-one detection metrics in pixel xyxy coordinates."""

import math


def iou(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    return intersection / union if union > 0 else 0.0


def _validate_detection(item, prediction):
    box = item["box"]
    cls = item["class_id"]
    if not isinstance(cls, int) or isinstance(cls, bool) or not 0 <= cls < 6:
        raise ValueError("Invalid detection class ID")
    if len(box) != 4 or not all(math.isfinite(x) for x in box) or box[0] >= box[2] or box[1] >= box[3]:
        raise ValueError("Invalid detection box")
    if prediction and not (math.isfinite(item["confidence"]) and 0 <= item["confidence"] <= 1):
        raise ValueError("Invalid prediction confidence")


def aggregate(images, iou_threshold=0.5):
    if not 0 < iou_threshold <= 1:
        raise ValueError("IoU threshold must be in (0, 1]")
    tp = fp = fn = good_count = good_fp = alarm_images = count = 0
    for image in images:
        count += 1
        truth, predictions = image["truth"], image["predictions"]
        negative = image.get("verified_negative", False) is True
        if negative and truth:
            raise ValueError("Verified negative image has ground truth defects")
        for item in truth:
            _validate_detection(item, False)
        for item in predictions:
            _validate_detection(item, True)
        matched = set()
        image_fp = 0
        for _, prediction in sorted(enumerate(predictions), key=lambda p: (-p[1]["confidence"], p[0])):
            candidates = [
                (iou(prediction["box"], target["box"]), index)
                for index, target in enumerate(truth)
                if index not in matched and target["class_id"] == prediction["class_id"]
            ]
            overlap, index = max(candidates, key=lambda p: (p[0], -p[1]), default=(0, -1))
            if index >= 0 and overlap >= iou_threshold:
                matched.add(index)
                tp += 1
            else:
                fp += 1
                image_fp += 1
        fn += len(truth) - len(matched)
        if negative:
            good_count += 1
            good_fp += image_fp
            alarm_images += bool(image_fp)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "images": count,
        "iou_threshold": iou_threshold,
        "verified_negative_images": good_count,
        "false_positive_per_good_image": good_fp / good_count if good_count else None,
        "false_alarm_image_rate": alarm_images / good_count if good_count else None,
    }
