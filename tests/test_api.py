from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from pcb_inspection.api import create_app
from test_models import bundle


def upload(client):
    stream = BytesIO()
    Image.new("RGB", (100, 50), "white").save(stream, "PNG")
    response = client.post("/api/images", files={"file": ("board.png", stream.getvalue(), "image/png")})
    assert response.status_code == 201
    return response.json()["image_id"]


def test_missing_model_is_explicit_and_never_clean(tmp_path):
    with TestClient(create_app(tmp_path / "data", tmp_path / "models")) as client:
        assert client.get("/api/health").json()["model_ready"] is False
        image_id = upload(client)
        response = client.post(
            "/api/inspections",
            json={"image_id": image_id, "model_id": "absent", "profile_id": "quality-v1"},
        )
        assert response.status_code == 503
        assert client.get("/api/inspections").json()["total"] == 0
        assert (
            client.post("/api/images", files={"file": ("bad.png", b"bad", "image/png")}).status_code
            == 422
        )


def test_completed_review_export_and_restart(tmp_path):
    models = tmp_path / "models"
    bundle(models)
    app = create_app(tmp_path / "data", models)
    with TestClient(app) as client:
        store = app.state.store
        store.worker_heartbeat("fixture")
        image_id = upload(client)
        response = client.post(
            "/api/inspections",
            json={"image_id": image_id, "model_id": "test-v1", "profile_id": "quality-v1"},
        )
        assert response.status_code == 202
        inspection_id = response.json()["inspection_id"]
        lease = store.claim("fixture")
        result = {
            "inspection_id": inspection_id,
            "image_id": image_id,
            "model_id": "test-v1",
            "profile_id": "quality-v1",
            "decision": "defects_detected",
            "defects": [
                {
                    "defect_id": "d1",
                    "class_id": 0,
                    "class_name": "open_circuit",
                    "confidence": 0.9,
                    "bbox_xyxy": [10, 10, 30, 30],
                    "localization_kind": "bbox_region",
                    "mask_ref": None,
                    "warnings": [],
                }
            ],
            "timings_ms": {"total": 2},
            "warnings": [],
        }
        store.finish(lease, result)
        response = client.post(
            f"/api/inspections/{inspection_id}/reviews",
            json={"defect_id": "d1", "verdict": "confirmed", "note": "visible break"},
        )
        assert response.status_code == 201
        exported = client.get(f"/api/inspections/{inspection_id}/export?format=json").json()
        assert exported["result"]["defects"][0]["confidence"] == 0.9
        assert len(exported["reviews"]) == 1
        png = client.get(f"/api/inspections/{inspection_id}/export?format=png&opacity=0.4")
        assert png.headers["content-type"] == "image/png"
        pixels = Image.open(BytesIO(png.content)).convert("RGB")
        assert pixels.getpixel((20, 20)) != (255, 255, 255)
        assert pixels.getpixel((10, 10)) == (255, 255, 255)
        assert (
            client.get(f"/api/inspections/{inspection_id}/export?format=png&opacity=2").status_code
            == 422
        )
        assert client.get("/api/artifacts/not-found").status_code == 404
    with TestClient(create_app(tmp_path / "data", models)) as restarted:
        loaded = restarted.get(f"/api/inspections/{inspection_id}").json()
        assert loaded["result"] == result
        assert len(loaded["reviews"]) == 1
