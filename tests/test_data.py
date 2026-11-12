import json
import pytest
from PIL import Image


def fixture_source(root):
    """Real files in DeepPCB's split + image-dir + sibling annotation-dir layout."""
    train = []
    for group, color in [("00001", 20), ("00002", 50), ("00003", 80)]:
        path = root / f"group{group}" / group
        path.mkdir(parents=True)
        ann = path.parent / f"{group}_not"
        ann.mkdir()
        for index in range(2):
            name = f"{group}{index:03}"
            Image.new("RGB", (100, 80), (color + index, 0, 0)).save(path / f"{name}_test.jpg")
            Image.new("RGB", (100, 80), (0, color + index, 0)).save(path / f"{name}_temp.jpg")
            (ann / f"{name}.txt").write_text("10 20 30 60 1\n", encoding="utf-8")
            train.append(f"group{group}/{group}/{name}.jpg group{group}/{group}_not/{name}.txt")
    (root / "trainval.txt").write_text("\n".join(train[:4]), encoding="utf-8")
    (root / "test.txt").write_text("\n".join(train[4:]), encoding="utf-8")
    return root


def test_prepare_converts_boxes_preserves_protocol_and_group_split(tmp_path):
    from pcb_inspection.ml.prepare import prepare

    source = fixture_source(tmp_path / "source")
    out = tmp_path / "out"
    manifest = prepare(source, out, val_fraction=0.5, seed=42)
    samples = manifest["samples"]
    assert len(samples) == 6
    assert {s["source_split"] for s in samples if s["split"] == "test"} == {"test"}
    assert {s["group"] for s in samples if s["split"] == "train"}.isdisjoint(
        {s["group"] for s in samples if s["split"] == "val"}
    )
    for sample in samples:
        assert len(sample["sha256"]) == 64
        assert sample["verified_negative"] is False
        label = out / sample["label"]
        assert label.read_text().strip() == "0 0.20000000 0.50000000 0.20000000 0.50000000"
    assert (out / "data.yaml").exists()
    assert json.loads((out / "audit.json").read_text())["counts"] == {"train": 2, "val": 2, "test": 2}
    again = prepare(source, tmp_path / "again", val_fraction=0.5, seed=42)
    assert manifest == again


@pytest.mark.parametrize(
    "line", ["10 20 30 60 7", "10 20 10 60 1", "-1 20 30 60 1", "10 20 101 60 1", "10 20 nan 60 1"]
)
def test_invalid_annotations_rejected(tmp_path, line):
    from pcb_inspection.ml.prepare import prepare

    source = fixture_source(tmp_path / "source")
    next(source.glob("group*/*_not/*.txt")).write_text(line)
    with pytest.raises(ValueError):
        prepare(source, tmp_path / "out", val_fraction=0.5)


def test_unknown_unannotated_sample_rejected(tmp_path):
    from pcb_inspection.ml.prepare import prepare

    source = fixture_source(tmp_path / "source")
    next(source.glob("group*/*_not/*.txt")).unlink()
    with pytest.raises(ValueError, match="annotation"):
        prepare(source, tmp_path / "out", val_fraction=0.5)


def test_cross_split_duplicate_rejected(tmp_path):
    from pcb_inspection.ml.prepare import prepare

    source = fixture_source(tmp_path / "source")
    images = sorted(source.glob("group*/*/*_test.jpg"))
    images[-1].write_bytes(images[0].read_bytes())
    with pytest.raises(ValueError, match="duplicate"):
        prepare(source, tmp_path / "out", val_fraction=0.5)


def test_published_shared_test_groups_are_reported(tmp_path):
    from pcb_inspection.ml.prepare import prepare

    source = fixture_source(tmp_path / "source")
    train = (source / "trainval.txt").read_text().splitlines()
    test = (source / "test.txt").read_text().splitlines()
    (source / "trainval.txt").write_text("\n".join(train[:-1]))
    (source / "test.txt").write_text("\n".join(test + train[-1:]))
    prepare(source, tmp_path / "out", val_fraction=0.5)
    audit = json.loads((tmp_path / "out/audit.json").read_text())
    assert audit["published_test_group_overlap"] == ["group00002/00002"]


def test_bundle_rejects_wrong_classes_and_overwrite(tmp_path):
    from pcb_inspection.ml.bundle import promote
    from pcb_inspection.ml.common import CLASS_NAMES

    weights = tmp_path / "trained.pt"
    weights.write_bytes(b"fixture-weights")
    with pytest.raises(ValueError, match="class"):
        promote(weights, tmp_path / "models", "test-model", "Test", "fixture-v1", {}, ["wrong"])
    from test_promotion_integrity import measured

    evaluation = measured(weights, dataset_version="fixture-v1")
    bundle = promote(
        weights, tmp_path / "models", "test-model", "Test", "fixture-v1", evaluation, CLASS_NAMES
    )
    metadata = json.loads((bundle / "manifest.json").read_text())
    assert metadata["task"] == "detect"
    assert len(metadata["sha256"]) == 64
    assert metadata["profiles"][0]["end2end"] is False
    with pytest.raises(FileExistsError):
        promote(
            weights, tmp_path / "models", "test-model", "Test", "fixture-v1", evaluation, CLASS_NAMES
        )


def test_baseline_training_arguments_and_smoke_fraction():
    from pcb_inspection.ml.train import training_arguments

    args = training_arguments("fixture/data.yaml", epochs=1, fraction=0.05, device="cpu")
    assert args["epochs"] == 1
    assert args["fraction"] == 0.05
    assert args["mosaic"] == args["mixup"] == args["copy_paste"] == 0
    assert args["nms"] is True
    assert args["workers"] == 0
    assert args["device"] == "cpu"
    with pytest.raises(ValueError):
        training_arguments("fixture/data.yaml", fraction=0)


@pytest.mark.parametrize("source_id,app_id", [(1, 0), (2, 1), (3, 2), (4, 3), (5, 4), (6, 5)])
def test_authoritative_class_mapping(tmp_path, source_id, app_id):
    from pcb_inspection.ml.prepare import prepare

    source = fixture_source(tmp_path / "source")
    for annotation in source.glob("group*/*_not/*.txt"):
        annotation.write_text(f"10 20 30 60 {source_id}\n")
    manifest = prepare(source, tmp_path / "out", val_fraction=0.5)
    assert {box["class_id"] for sample in manifest["samples"] for box in sample["boxes"]} == {app_id}


def test_empty_annotation_is_unknown_not_good(tmp_path):
    from pcb_inspection.ml.prepare import prepare

    source = fixture_source(tmp_path / "source")
    next(source.glob("group*/*_not/*.txt")).write_text("")
    with pytest.raises(ValueError, match="verified negative"):
        prepare(source, tmp_path / "out", val_fraction=0.5)


def test_training_kwargs_accepted_by_installed_ultralytics():
    from pcb_inspection.ml.train import training_arguments

    cfg = pytest.importorskip("ultralytics.cfg")
    config = cfg.get_cfg(overrides=training_arguments("fixture/data.yaml", epochs=1, device="cpu"))
    assert config.nms is True


def test_validation_kwargs_accepted_by_installed_ultralytics():
    from pcb_inspection.ml.evaluate import inference_arguments

    cfg = pytest.importorskip("ultralytics.cfg")
    config = cfg.get_cfg(overrides=inference_arguments(imgsz=640, batch=4, device="cpu"))
    assert config.nms is True


def test_training_project_is_resolved_relative_to_invocation_directory(tmp_path, monkeypatch):
    from pcb_inspection.ml.train import training_arguments

    cfg = pytest.importorskip("ultralytics.cfg")
    monkeypatch.chdir(tmp_path)
    config = cfg.get_cfg(
        overrides=training_arguments("fixture/data.yaml", project="outputs", name="demo")
    )
    assert cfg.get_save_dir(config) == tmp_path / "outputs" / "demo"
