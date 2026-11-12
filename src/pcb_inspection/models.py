from hashlib import file_digest
import json
from pathlib import Path
import re

from .contracts import CLASS_NAMES, InferenceProfile


class ModelError(ValueError):
    pass


class ModelRegistry:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def get(self, model_id):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}", model_id):
            raise ModelError("Invalid model identifier")
        directory = (self.root / model_id).resolve()
        if directory.parent != self.root:
            raise ModelError("Invalid bundle path")
        try:
            path = directory / "manifest.json"
            manifest_bytes = path.read_bytes()
            manifest = json.loads(manifest_bytes)
            if manifest["model_id"] != model_id or manifest["task"] != "detect":
                raise ModelError("Bundle identity or task mismatch")
            if manifest["class_names"] != CLASS_NAMES:
                raise ModelError("Bundle classes do not match the six supported PCB categories")
            status = manifest.get("training_status", "unvalidated")
            if status not in {"development", "unvalidated", "validated"}:
                raise ModelError("Unknown training status")
            manifest["training_status"] = status
            weights = directory / "weights.pt"
            if not weights.is_file() or weights.resolve().parent != directory:
                raise ModelError("Bundle weights are missing")
            with weights.open("rb") as stream:
                digest = file_digest(stream, "sha256").hexdigest()
            declared = manifest.get(
                "weights_sha256", manifest.get("sha256", manifest.get("weights_hash"))
            )
            if digest != declared:
                raise ModelError("Bundle weights failed SHA-256 verification")
            profiles = [
                InferenceProfile.model_validate(profile).model_dump() for profile in manifest["profiles"]
            ]
            if not profiles or len({p["profile_id"] for p in profiles}) != len(profiles):
                raise ModelError("Bundle must provide uniquely named inference profiles")
            manifest.update(profiles=profiles, weights_sha256=digest, weights_path=str(weights))
            from hashlib import sha256

            manifest["manifest_sha256"] = sha256(manifest_bytes).hexdigest()
            return manifest
        except (OSError, KeyError, ValueError, TypeError) as exc:
            raise ModelError(f"{model_id}: {exc}") from exc

    def list(self):
        models, errors = [], []
        for path in sorted(self.root.glob("*/manifest.json")):
            try:
                models.append(self.get(path.parent.name))
            except ModelError as exc:
                errors.append(str(exc))
        return models, errors


def public_model(model):
    return {key: value for key, value in model.items() if key != "weights_path"}
