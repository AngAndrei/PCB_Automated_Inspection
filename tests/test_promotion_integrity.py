from hashlib import sha256
import json

import pytest

from pcb_inspection.contracts import CLASS_NAMES
from pcb_inspection.ml.bundle import promote
from pcb_inspection.models import ModelRegistry, ModelError
from pcb_inspection.storage import Store
from pcb_inspection.worker import Worker
from test_jobs import image_id
from test_models import bundle


def measured(weights, **changes):
    result = {
        "weights_sha256": sha256(weights.read_bytes()).hexdigest(),
        "dataset_version": "fixture",
        "source_manifest_sha256": "a" * 64,
        "prediction_source": "measured_model_inference",
        "split": "val",
        "configuration": {
            "imgsz": 1280,
            "confidence": 0.7,
            "nms_iou": 0.4,
            "matching_iou": 0.5,
            "end2end": False,
            "nms": True,
        },
        "metrics": {"f1": 0.0},
    }
    result.update(changes)
    return result


@pytest.mark.parametrize(
    "changes",
    [
        {"weights_sha256": "0" * 64},
        {"dataset_version": "other"},
        {"prediction_source": "saved_predictions.json"},
    ],
)
def test_promotion_rejects_unrelated_or_unverifiable_evaluation(tmp_path, changes):
    weights = tmp_path / "weights.pt"
    weights.write_bytes(b"fixture")
    with pytest.raises(ValueError):
        promote(
            weights,
            tmp_path / "models",
            "test-v1",
            "Fixture",
            "fixture",
            measured(weights, **changes),
            CLASS_NAMES,
        )
    assert not (tmp_path / "models/test-v1").exists()


def test_promoted_profile_preserves_evaluated_operating_settings(tmp_path):
    weights = tmp_path / "weights.pt"
    weights.write_bytes(b"fixture")
    path = promote(
        weights, tmp_path / "models", "test-v1", "Fixture", "fixture", measured(weights), CLASS_NAMES
    )
    profile = json.loads((path / "manifest.json").read_text())["profiles"][0]
    assert (profile["imgsz"], profile["confidence"], profile["iou"]) == (1280, 0.7, 0.4)


def test_default_promoted_bundle_requires_manual_review(tmp_path):
    weights = tmp_path / "weights.pt"
    weights.write_bytes(b"fixture")
    models = tmp_path / "models"
    promote(weights, models, "test-v1", "Fixture", "fixture", measured(weights), CLASS_NAMES)
    registry = ModelRegistry(models)
    model = registry.get("test-v1")
    store = Store(tmp_path / "app")
    row = store.enqueue(image_id(store), model, model["profiles"][0])

    class Empty:
        def __init__(self, path):
            pass

        def predict(self, image, profile):
            return {"defects": [], "warnings": [], "timings_ms": {"inference": 1}}

    Worker(store, registry, Empty).process_once()
    assert store.get_job(row["inspection_id"])["result"]["decision"] == "review_needed"


def test_registry_defaults_legacy_status_and_rejects_unknown_status(tmp_path):
    bundle(tmp_path)
    assert ModelRegistry(tmp_path).get("test-v1")["training_status"] == "unvalidated"
    bundle(tmp_path, training_status="typo")
    with pytest.raises(ModelError):
        ModelRegistry(tmp_path).get("test-v1")
