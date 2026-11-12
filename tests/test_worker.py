from pcb_inspection.models import ModelRegistry
from pcb_inspection.storage import Store
from pcb_inspection.worker import Worker
from test_jobs import image_id
from test_models import bundle


def test_worker_runs_real_lifecycle_and_failures_have_no_decision(tmp_path):
    models = tmp_path / "models"
    bundle(models)
    registry = ModelRegistry(models)
    store = Store(tmp_path / "app")
    model = registry.get("test-v1")
    record = store.enqueue(image_id(store), model, model["profiles"][0])

    class BrokenPredictor:
        def __init__(self, path):
            pass

        def predict(self, image, profile):
            raise RuntimeError("Model could not run")

    worker = Worker(store, registry, factory=BrokenPredictor)
    assert worker.process_once()
    saved = store.get_job(record["inspection_id"])
    assert saved["status"] == "failed"
    assert saved["result"] is None
    assert saved["error"]["code"] == "INFERENCE_ERROR"


def test_worker_checks_model_identity_before_loading_and_switches_between_jobs(tmp_path):
    models = tmp_path / "models"
    bundle(models)
    registry = ModelRegistry(models)
    store = Store(tmp_path / "app")
    model = registry.get("test-v1")
    row = store.enqueue(image_id(store), model, model["profiles"][0])
    bundle(models, label="modified after queue")
    worker = Worker(
        store,
        registry,
        factory=lambda path: (_ for _ in ()).throw(AssertionError("Must not load changed bundle")),
    )
    worker.process_once()
    failed = store.get_job(row["inspection_id"])
    assert failed["status"] == "failed"
    assert failed["error"]["code"] == "MODEL_UNAVAILABLE"


def test_development_model_requires_manual_review_even_for_an_empty_prediction(tmp_path):
    models = tmp_path / "models"
    bundle(models, training_status="development")
    registry = ModelRegistry(models)
    store = Store(tmp_path / "app")
    model = registry.get("test-v1")
    row = store.enqueue(image_id(store), model, model["profiles"][0])

    class EmptyPredictor:
        def __init__(self, path):
            pass

        def predict(self, image, profile):
            return {"defects": [], "warnings": [], "timings_ms": {"inference": 1}}

    Worker(store, registry, factory=EmptyPredictor).process_once()
    result = store.get_job(row["inspection_id"])["result"]
    assert result["decision"] == "review_needed"
    assert "development" in result["warnings"][0].lower()
