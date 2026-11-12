"""Prepare published DeepPCB membership as YOLO images and labels, with audited group holdout."""

import argparse
from collections import Counter, defaultdict
import math
from pathlib import Path, PurePosixPath
import random
import shutil

from PIL import Image
import yaml

from .common import CLASS_NAMES, sha256, write_json


def _safe_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Source path escapes dataset: {relative}")
    return path


def _annotations(path, width, height):
    if not path.is_file():
        raise ValueError(f"Missing annotation; sample is unknown: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    if not any(line.strip() for line in lines):
        raise ValueError(f"Empty annotation is not a verified negative: {path}")
    boxes = []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5:
            raise ValueError(f"Invalid annotation fields: {path}:{number}")
        try:
            x1, y1, x2, y2 = map(float, fields[:4])
            class_id = int(fields[4])
        except ValueError as exc:
            raise ValueError(f"Invalid annotation value: {path}:{number}") from exc
        if class_id not in range(1, 7):
            raise ValueError(f"Invalid source class ID: {path}:{number}")
        if not all(math.isfinite(v) for v in (x1, y1, x2, y2)) or not (
            0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height
        ):
            raise ValueError(f"Invalid annotation box: {path}:{number}")
        boxes.append({"class_id": class_id - 1, "box": [x1, y1, x2, y2]})
    return boxes


def prepare(source, output, val_fraction=0.2, seed=42):
    source, output = Path(source), Path(output)
    if (source / "PCBData").is_dir():
        source = source / "PCBData"
    if not 0 < val_fraction < 1:
        raise ValueError("Validation fraction must be in (0, 1)")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Output directory must be empty: {output}")
    samples, seen = [], set()
    for source_split in ("trainval", "test"):
        split_file = source / f"{source_split}.txt"
        for number, line in enumerate(split_file.read_text(encoding="utf-8").splitlines(), 1):
            parts = line.split()
            if len(parts) != 2:
                raise ValueError(f"Expected image and annotation paths: {split_file}:{number}")
            nominal, annotation = parts
            key = PurePosixPath(nominal)
            if nominal in seen:
                raise ValueError(f"Duplicate source membership: {nominal}")
            seen.add(nominal)
            image_rel = str(key.with_name(key.stem + "_test.jpg"))
            template_rel = str(key.with_name(key.stem + "_temp.jpg"))
            image = _safe_path(source, image_rel)
            annotation_path = _safe_path(source, annotation)
            template = _safe_path(source, template_rel)
            if not image.is_file() or not template.is_file():
                raise ValueError(f"Missing image pair: {nominal}")
            with Image.open(image) as opened:
                width, height = opened.size
                opened.verify()
            boxes = _annotations(annotation_path, width, height)
            with Image.open(template) as opened:
                if opened.size != (width, height):
                    raise ValueError(f"Template dimensions differ: {template}")
                opened.verify()
            samples.append(
                {
                    "id": "__".join(key.with_suffix("").parts),
                    "source_image": image_rel,
                    "source_annotation": annotation,
                    "source_split": source_split,
                    "group": str(key.parent),
                    "sha256": sha256(image),
                    "annotation_sha256": sha256(annotation_path),
                    "width": width,
                    "height": height,
                    "verified_negative": False,
                    "boxes": boxes,
                    "template": {
                        "source_image": template_rel,
                        "sha256": sha256(template),
                        "verified_negative": True,
                        "provenance": "DeepPCB README: manually checked and cleaned defect-free templates; not an independent production-good set",
                    },
                }
            )
    groups = sorted({s["group"] for s in samples if s["source_split"] == "trainval"})
    if len(groups) < 2:
        raise ValueError("At least two trainval source board groups are required")
    random.Random(seed).shuffle(groups)
    val_groups = set(groups[: max(1, min(len(groups) - 1, round(len(groups) * val_fraction)))])
    for sample in samples:
        sample["split"] = (
            "test"
            if sample["source_split"] == "test"
            else ("val" if sample["group"] in val_groups else "train")
        )
        sample["image"] = f"images/{sample['split']}/{sample['id']}.jpg"
        sample["label"] = f"labels/{sample['split']}/{sample['id']}.txt"
    hashes = defaultdict(list)
    for sample in samples:
        hashes[sample["sha256"]].append(sample)
    for digest, members in hashes.items():
        if len({s["split"] for s in members}) > 1:
            raise ValueError(f"Cross-split image duplicate {digest}: {[s['id'] for s in members]}")
    test_groups = {s["group"] for s in samples if s["source_split"] == "test"}
    overlap = sorted(test_groups & set(groups))
    manifest = {
        "dataset_version": "deeppcb-published-v1",
        "class_names": CLASS_NAMES,
        "seed": seed,
        "validation_group_fraction": val_fraction,
        "license": "research-only dataset",
        "box_convention": "source pixel corner coordinates interpreted continuously; width=x2-x1, height=y2-y1; no +1 expansion",
        "source_splits": {name: sha256(source / f"{name}.txt") for name in ("trainval", "test")},
        "samples": sorted(samples, key=lambda s: s["id"]),
    }
    counts = {split: sum(s["split"] == split for s in samples) for split in ("train", "val", "test")}
    audit = {
        "counts": counts,
        "class_boxes": dict(Counter(CLASS_NAMES[b["class_id"]] for s in samples for b in s["boxes"])),
        "published_test_group_overlap": overlap,
        "train_val_group_overlap": [],
        "cross_split_image_duplicates": [],
        "within_split_duplicate_images": sum(len(x) - 1 for x in hashes.values()),
        "verified_negative_training_images": 0,
        "template_policy": "Templates retained as source provenance only; excluded from YOLO images and headline metrics.",
        "warnings": [
            "Published test shares source board groups with trainval; retained published protocol."
        ]
        if overlap
        else [],
    }
    output.mkdir(parents=True, exist_ok=True)
    for split in counts:
        (output / "images" / split).mkdir(parents=True)
        (output / "labels" / split).mkdir(parents=True)
    for sample in samples:
        shutil.copyfile(source / sample["source_image"], output / sample["image"])
        labels = []
        for box in sample["boxes"]:
            x1, y1, x2, y2 = box["box"]
            coords = (
                (x1 + x2) / (2 * sample["width"]),
                (y1 + y2) / (2 * sample["height"]),
                (x2 - x1) / sample["width"],
                (y2 - y1) / sample["height"],
            )
            labels.append(str(box["class_id"]) + " " + " ".join(f"{v:.8f}" for v in coords))
        (output / sample["label"]).write_text("\n".join(labels) + "\n", encoding="utf-8")
    (output / "data.yaml").write_text(
        yaml.safe_dump(
            {
                "path": output.resolve().as_posix(),
                "train": "images/train",
                "val": "images/val",
                "test": "images/test",
                "names": dict(enumerate(CLASS_NAMES)),
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    write_json(output / "manifest.json", manifest)
    write_json(output / "audit.json", audit)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--val-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    result = prepare(args.source, args.output, args.val_fraction, args.seed)
    print(f"Prepared {len(result['samples'])} samples in {args.output}")


if __name__ == "__main__":
    main()
