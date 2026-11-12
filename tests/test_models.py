from hashlib import sha256
import json

import pytest

from pcb_inspection.models import ModelRegistry, ModelError


NAMES = ["open_circuit", "short_circuit", "mouse_bite", "spur", "spurious_copper", "pin_hole"]


def bundle(root, **changes):
    directory = root / "test-v1"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "weights.pt").write_bytes(b"fixture weights")
    manifest = {
        "model_id": "test-v1",
        "label": "Test detector",
        "task": "detect",
        "class_names": NAMES,
        "weights_sha256": sha256(b"fixture weights").hexdigest(),
        "dataset_version": "fixture",
        "profiles": [{"profile_id": "quality-v1"}],
    }
    manifest.update(changes)
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return directory


def test_rejects_corrupt_or_incompatible_bundle(tmp_path):
    directory = bundle(tmp_path)
    registry = ModelRegistry(tmp_path)
    assert registry.get("test-v1")["class_names"] == NAMES
    (directory / "weights.pt").write_bytes(b"corrupt")
    with pytest.raises(ModelError):
        registry.get("test-v1")
    bundle(tmp_path, class_names=list(reversed(NAMES)))
    with pytest.raises(ModelError):
        registry.get("test-v1")


def test_registry_rejects_traversal_and_reports_bad_bundle(tmp_path):
    bundle(tmp_path, weights_sha256="bad")
    registry = ModelRegistry(tmp_path)
    with pytest.raises(ModelError):
        registry.get("../outside")
    models, errors = registry.list()
    assert models == []
    assert len(errors) == 1


def test_training_promotion_creates_a_bundle_the_app_can_load(tmp_path):
    from pcb_inspection.ml.bundle import promote

    weights = tmp_path / "trained.pt"
    weights.write_bytes(b"fixture trained checkpoint")
    models = tmp_path / "models"
    from test_promotion_integrity import measured

    promote(weights, models, "detector-v1", "Detector", "fixture", measured(weights), NAMES)
    assert ModelRegistry(models).get("detector-v1")["class_names"] == NAMES
