"""One process owns the model. A separate thread renews leases during inference."""

import argparse
from contextlib import suppress
import logging
import os
from pathlib import Path
from threading import Event, Thread
from time import perf_counter
from uuid import uuid4

from .images import normalize_image
from .models import ModelRegistry, ModelError
from .predictor import Predictor
from .storage import Store, Conflict, timestamp

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]


class Worker:
    def __init__(self, store, registry, factory=Predictor):
        self.store, self.registry, self.factory = store, registry, factory
        self.worker_id = uuid4().hex
        self.loaded_identity = None
        self.predictor = None

    def process_once(self):
        self.store.expire()
        self.store.worker_heartbeat(self.worker_id)
        lease = self.store.claim(self.worker_id)
        if lease is None:
            return False
        stop = Event()

        def pulse():
            while not stop.wait(5):
                self.store.worker_heartbeat(self.worker_id)
                if not self.store.heartbeat(lease):
                    return

        thread = Thread(target=pulse, daemon=True)
        thread.start()
        start = perf_counter()
        try:
            installed = self.registry.get(lease["model"]["model_id"])
            if installed["manifest_sha256"] != lease["model"].get("manifest_sha256"):
                raise ModelError("Original model bundle changed after this job was queued.")
            identity = (installed["model_id"], installed["weights_sha256"], installed["manifest_sha256"])
            if self.loaded_identity != identity:
                self.predictor = None
                self.predictor = self.factory(installed["weights_path"])
                self.loaded_identity = identity
            record = self.store.get_image(lease["image_id"])
            canonical = normalize_image(
                Path(record["canonical_path"]).read_bytes(), max_bytes=160 * 1024 * 1024
            )
            batch = self.predictor.predict(canonical, lease["profile"])
            if installed.get("training_status") in {"development", "unvalidated"}:
                batch["warnings"].append(
                    "Development model: detection quality is not established. Manually review this image."
                )
            decision = "defects_detected" if batch["defects"] else "no_defects_detected"
            if batch["warnings"]:
                decision = "review_needed"
            result = {
                "inspection_id": lease["inspection_id"],
                "image_id": lease["image_id"],
                "model_id": installed["model_id"],
                "profile_id": lease["profile"]["profile_id"],
                "decision": decision,
                **batch,
                "created_at": timestamp(),
            }
            result["timings_ms"]["total"] = round((perf_counter() - start) * 1000, 2)
            self.store.finish(lease, result)
            log.info(
                "Completed %s: %s, %s detections",
                lease["inspection_id"],
                decision,
                len(batch["defects"]),
            )
        except Exception as exc:
            log.exception("Inspection failed: %s", lease["inspection_id"])
            with suppress(Conflict):
                self.store.fail(
                    lease,
                    "MODEL_UNAVAILABLE" if isinstance(exc, ModelError) else "INFERENCE_ERROR",
                    str(exc),
                )
        finally:
            stop.set()
            thread.join(timeout=6)
        return True

    def run(self):
        stop = Event()
        log.info("Worker %s ready", self.worker_id)
        try:
            while True:
                if not self.process_once():
                    stop.wait(1)
        except KeyboardInterrupt:
            log.info("Worker stopped")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir", type=Path, default=Path(os.getenv("PCB_DATA_DIR", ROOT / "data/app"))
    )
    parser.add_argument(
        "--model-dir", type=Path, default=Path(os.getenv("PCB_MODEL_DIR", ROOT / "models"))
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    Worker(Store(args.data_dir), ModelRegistry(args.model_dir)).run()


if __name__ == "__main__":
    main()
