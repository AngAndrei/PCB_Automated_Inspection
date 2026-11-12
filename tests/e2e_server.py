"""Isolated UI test service. Its fixture detector is never part of the application."""

from hashlib import sha256
import json
from pathlib import Path
import tempfile
from threading import Event, Thread

import uvicorn

from pcb_inspection.api import create_app
from pcb_inspection.contracts import CLASS_NAMES
from pcb_inspection.models import ModelRegistry
from pcb_inspection.predictor import Predictor
from pcb_inspection.storage import Store
from pcb_inspection.worker import Worker


def main():
    with tempfile.TemporaryDirectory(prefix="pcb-e2e-") as scratch:
        root = Path(scratch)
        bundle = root / "models/fixture-v1"
        bundle.mkdir(parents=True)
        (bundle / "weights.pt").write_bytes(b"test-only")
        (bundle / "manifest.json").write_text(
            json.dumps(
                {
                    "model_id": "fixture-v1",
                    "label": "Test fixture detector",
                    "task": "detect",
                    "weights_sha256": sha256(b"test-only").hexdigest(),
                    "class_names": CLASS_NAMES,
                    "dataset_version": "UI fixture",
                    "training_status": "validated",
                    "profiles": [{"profile_id": "quality-v1"}],
                }
            ),
            encoding="utf-8",
        )
        app = create_app(root / "app", root / "models")

        def adapter(image, profile):
            return [{"box": [20, 20, 50, 50], "score": 0.94, "class_id": 0}]

        worker = Worker(
            Store(root / "app"),
            ModelRegistry(root / "models"),
            factory=lambda weights: Predictor(adapter=adapter),
        )
        stop = Event()

        def process():
            while not stop.is_set():
                worker.process_once()
                stop.wait(0.1)

        thread = Thread(target=process, daemon=True)
        thread.start()
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8765, log_level="warning"))

        @app.post("/__test__/shutdown")
        def shutdown():
            server.should_exit = True
            return {"stopping": True}

        # create_app mounts the production frontend last; test-only control stays before that mount.
        app.router.routes.insert(0, app.router.routes.pop())

        try:
            server.run()
        finally:
            stop.set()
            thread.join(5)


if __name__ == "__main__":
    main()
