import pytest
from PIL import Image
from io import BytesIO

from pcb_inspection.storage import Store, Conflict, CapacityError


def image_id(store):
    stream = BytesIO()
    Image.new("RGB", (100, 50), "white").save(stream, "PNG")
    return store.add_image(stream.getvalue(), "board.png")["image_id"]


def job(store):
    return store.enqueue(
        image_id(store), {"model_id": "original-v1"}, {"profile_id": "q", "confidence": 0.25}
    )


def test_atomic_claim_and_stale_completion_are_guarded(tmp_path):
    store = Store(tmp_path)
    row = job(store)
    lease = store.claim("worker-a", now=100)
    assert lease["inspection_id"] == row["inspection_id"]
    assert store.claim("worker-b", now=101) is None
    assert store.expire(now=161) == 1
    with pytest.raises(Conflict):
        store.finish(lease, {"decision": "no_defects_detected"}, now=162)
    assert store.get_job(row["inspection_id"])["status"] == "failed"


def test_retry_preserves_original_snapshot_and_requires_failed_state(tmp_path):
    store = Store(tmp_path)
    row = job(store)
    with pytest.raises(Conflict):
        store.retry(row["inspection_id"])
    lease = store.claim("a")
    store.fail(lease, "INFERENCE_ERROR", "test failure")
    store.retry(row["inspection_id"])
    retried = store.claim("b")
    assert retried["model"]["model_id"] == "original-v1"
    assert retried["profile"]["confidence"] == 0.25
    assert retried["attempt"] == 2
    with pytest.raises(Conflict):
        store.finish(lease, {})


def test_heartbeat_renews_and_expiry_is_periodic(tmp_path):
    store = Store(tmp_path)
    job(store)
    lease = store.claim("a", now=100)
    assert store.heartbeat(lease, now=150)
    assert store.expire(now=170) == 0
    restarted_store = Store(tmp_path)
    assert restarted_store.expire(now=211) == 1


def test_cancel_and_capacity(tmp_path):
    store = Store(tmp_path, queue_limit=1)
    row = job(store)
    with pytest.raises(CapacityError):
        job(store)
    store.cancel(row["inspection_id"])
    assert store.get_job(row["inspection_id"])["status"] == "cancelled"
    row = job(store)
    store.claim("a")
    with pytest.raises(Conflict):
        store.cancel(row["inspection_id"])


def test_only_one_inference_job_is_active_even_if_two_workers_start(tmp_path):
    store = Store(tmp_path)
    job(store)
    job(store)
    first = store.claim("first")
    assert store.claim("second") is None
    store.finish(first, {"defects": []})
    assert store.claim("second") is not None


def test_completed_predictions_are_immutable_when_reviewing(tmp_path):
    store = Store(tmp_path)
    row = job(store)
    lease = store.claim("a")
    result = {"decision": "defects_detected", "defects": [{"defect_id": "d1", "confidence": 0.9}]}
    store.finish(lease, result)
    store.review(row["inspection_id"], "d1", "rejected", "reflection")
    store.review(row["inspection_id"], "d1", "confirmed", "checked again")
    assert Store(tmp_path).get_job(row["inspection_id"])["result"] == result
    assert len(store.reviews(row["inspection_id"])) == 2
    with pytest.raises(ValueError):
        store.review(row["inspection_id"], "unknown", "confirmed", "")
