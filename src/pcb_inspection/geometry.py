"""Small, framework-independent image-coordinate operations."""

from math import isfinite


def ellipse_geometry(box):
    x1, y1, x2, y2 = box
    return ((x1 + x2) / 2, (y1 + y2) / 2, (x2 - x1) / 2, (y2 - y1) / 2)


def tile_windows(width, height, size=640, overlap=0.2, max_tiles=128):
    if width < 1 or height < 1 or size < 1 or not 0 <= overlap < 1:
        raise ValueError("Invalid tiling dimensions or overlap")

    def starts(length):
        end = max(0, length - size)
        return sorted(set([*range(0, end, max(1, int(size * (1 - overlap)))), end]))

    windows = [
        (x, y, min(x + size, width), min(y + size, height))
        for y in starts(height)
        for x in starts(width)
    ]
    if len(windows) > max_tiles:
        raise ValueError(f"Image requires {len(windows)} tiles; limit is {max_tiles}. Upload a crop.")
    return windows


def box_iou(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    return intersection / union if union > 0 else 0.0


def class_aware_nms(boxes, scores, classes, iou=0.5):
    order = sorted(range(len(boxes)), key=lambda index: (-scores[index], index))
    kept = []
    for index in order:
        if not any(
            classes[index] == classes[other] and box_iou(boxes[index], boxes[other]) > iou
            for other in kept
        ):
            kept.append(index)
    return kept


def valid_box(box, width, height):
    return (
        len(box) == 4
        and all(isfinite(v) for v in box)
        and 0 <= box[0] < box[2] <= width
        and 0 <= box[1] < box[3] <= height
    )
