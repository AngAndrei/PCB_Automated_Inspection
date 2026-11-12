from PIL import Image
from io import BytesIO
import pytest

from pcb_inspection.images import normalize_image
from pcb_inspection.predictor import Predictor


def canonical(size):
    stream = BytesIO()
    Image.new("RGB", size, "white").save(stream, "PNG")
    return normalize_image(stream.getvalue())


def test_predictor_keeps_original_coordinates_and_does_not_invent_masks():
    def adapter(image, profile):
        assert image.size == (1200, 600)
        return [{"box": [420, 180, 455, 205], "score": 0.94, "class_id": 0}]

    result = Predictor(adapter=adapter).predict(canonical((1200, 600)), {"tiled": False})
    assert result["defects"][0]["bbox_xyxy"] == [420, 180, 455, 205]
    assert result["defects"][0]["localization_kind"] == "bbox_region"
    assert result["defects"][0]["mask_ref"] is None


def test_tiled_offsets_and_duplicate_suppression():
    calls = []

    def adapter(image, profile):
        calls.append(image.size)
        x = 550 if len(calls) == 1 else 38
        return [{"box": [x, 10, x + 20, 30], "score": 0.9, "class_id": 1}]

    batch = Predictor(adapter=adapter).predict(canonical((1152, 640)), {"tiled": True, "iou": 0.5})
    assert calls == [(640, 640), (640, 640)]
    assert len(batch["defects"]) == 1
    assert batch["defects"][0]["bbox_xyxy"] == [550, 10, 570, 30]


def test_invalid_outputs_fail_instead_of_returning_clean_board():
    def adapter(image, profile):
        return [{"box": [0, 0, float("nan"), 4], "score": 0.9, "class_id": 1}]

    with pytest.raises(ValueError):
        Predictor(adapter=adapter).predict(canonical((640, 640)), {})
