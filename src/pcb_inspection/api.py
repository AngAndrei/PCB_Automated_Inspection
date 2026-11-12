import asyncio
from contextlib import asynccontextmanager, suppress
import os
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .artifacts import render_overlay
from .contracts import InspectionRequest, ReviewRequest, CLASS_NAMES, CLASS_COLORS
from .images import ImageInputError
from .models import ModelRegistry, ModelError, public_model
from .storage import Store, Conflict, CapacityError

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def public_image(row):
    return {key: value for key, value in row.items() if key != "canonical_path"} | {
        "url": f"/api/artifacts/{row['image_id']}"
    }


def public_job(store, row):
    allowed = (
        "inspection_id",
        "image_id",
        "status",
        "created_at",
        "updated_at",
        "attempt",
        "profile",
        "result",
        "error",
    )
    return {key: row[key] for key in allowed} | {
        "model": public_model(row["model"]),
        "image": public_image(store.get_image(row["image_id"])),
        "reviews": store.reviews(row["inspection_id"]),
    }


def create_app(data_root=None, model_root=None):
    store = Store(Path(data_root or os.getenv("PCB_DATA_DIR", str(PROJECT_ROOT / "data/app"))))
    registry = ModelRegistry(model_root or os.getenv("PCB_MODEL_DIR", str(PROJECT_ROOT / "models")))

    @asynccontextmanager
    async def lifespan(app):
        async def reconcile():
            while True:
                store.expire()
                await asyncio.sleep(5)

        task = asyncio.create_task(reconcile())
        yield
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    app = FastAPI(title="Circuit Inspect", version="0.1.0", lifespan=lifespan)
    app.state.store = store
    app.state.registry = registry
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def local_origin(request, call_next):
        origin = request.headers.get("origin")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and origin:
            if urlparse(origin).hostname not in {"localhost", "127.0.0.1", "::1"}:
                return JSONResponse(
                    {"detail": "This local application accepts local origins only."}, status_code=403
                )
        return await call_next(request)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": "Record not found."}, status_code=404)

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(CapacityError)
    async def capacity(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=429)

    @app.exception_handler(ImageInputError)
    async def invalid_image(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.get("/api/health")
    def health():
        models, errors = registry.list()
        return {
            "status": "ok",
            "worker_ready": store.worker_ready(),
            "model_ready": bool(models),
            "model_count": len(models),
            "model_errors": errors,
            "version": "0.1.0",
        }

    @app.get("/api/models")
    def models():
        found, errors = registry.list()
        return {
            "items": [public_model(model) for model in found],
            "errors": errors,
            "classes": [
                {"class_id": i, "name": name, "color": CLASS_COLORS[i]}
                for i, name in enumerate(CLASS_NAMES)
            ],
        }

    @app.post("/api/images", status_code=201)
    async def upload(file: UploadFile):
        content = await file.read(25 * 1024 * 1024 + 1)
        await file.close()
        return public_image(await asyncio.to_thread(store.add_image, content, file.filename))

    @app.post("/api/inspections", status_code=202)
    def inspect(request: InspectionRequest):
        store.get_image(request.image_id)
        try:
            model = registry.get(request.model_id)
        except ModelError as exc:
            raise HTTPException(503, str(exc)) from exc
        profiles = [p for p in model["profiles"] if p["profile_id"] == request.profile_id]
        if not profiles:
            raise HTTPException(422, "Choose an installed inference profile.")
        if not store.worker_ready():
            raise HTTPException(503, "Inference worker is offline. Start the worker and retry.")
        return public_job(store, store.enqueue(request.image_id, model, profiles[0]))

    @app.get("/api/inspections")
    def history(limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0)):
        result = store.history(limit, offset)
        result["items"] = [public_job(store, row) for row in result["items"]]
        return result

    @app.get("/api/inspections/{inspection_id}")
    def get_inspection(inspection_id: str):
        return public_job(store, store.get_job(inspection_id))

    @app.post("/api/inspections/{inspection_id}/cancel")
    def cancel(inspection_id: str):
        store.get_job(inspection_id)
        store.cancel(inspection_id)
        return public_job(store, store.get_job(inspection_id))

    @app.post("/api/inspections/{inspection_id}/retry", status_code=202)
    def retry(inspection_id: str):
        old = store.get_job(inspection_id)
        try:
            current = registry.get(old["model"]["model_id"])
            if current["manifest_sha256"] != old["model"].get("manifest_sha256"):
                raise ModelError(
                    "The original model bundle has changed; install the original bundle to retry."
                )
        except ModelError as exc:
            raise HTTPException(503, str(exc)) from exc
        if not store.worker_ready():
            raise HTTPException(503, "Inference worker is offline.")
        store.retry(inspection_id)
        return public_job(store, store.get_job(inspection_id))

    @app.post("/api/inspections/{inspection_id}/reviews", status_code=201)
    def review(inspection_id: str, request: ReviewRequest):
        try:
            return store.review(inspection_id, request.defect_id, request.verdict, request.note)
        except Conflict:
            raise
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/inspections/{inspection_id}/export")
    def export(
        inspection_id: str,
        format: str = Query("json", pattern="^(json|png)$"),
        opacity: float = Query(0.4, ge=0, le=0.8),
    ):
        job = store.get_job(inspection_id)
        if job["status"] != "completed":
            raise HTTPException(409, "Only completed inspections can be exported.")
        headers = {
            "Content-Disposition": f'attachment; filename="inspection-{inspection_id[:8]}.{format}"'
        }
        if format == "json":
            return JSONResponse(
                {
                    "schema_version": 1,
                    "result": job["result"],
                    "image": public_image(store.get_image(job["image_id"])),
                    "model": public_model(job["model"]),
                    "profile": job["profile"],
                    "reviews": store.reviews(inspection_id),
                },
                headers=headers,
            )
        image = store.get_image(job["image_id"])
        png = render_overlay(image["canonical_path"], job["result"]["defects"], opacity)
        return Response(png, media_type="image/png", headers=headers)

    @app.get("/api/artifacts/{artifact_id}")
    def artifact(artifact_id: str):
        image = store.get_image(artifact_id)
        return FileResponse(image["canonical_path"], media_type="image/png")

    frontend = PROJECT_ROOT / "frontend/dist"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app


app = create_app()
