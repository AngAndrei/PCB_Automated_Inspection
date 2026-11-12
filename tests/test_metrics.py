import pytest


def detection(cls=0, box=(0, 0, 10, 10), confidence=0.9):
    return {"class_id": cls, "box": list(box), "confidence": confidence}


@pytest.mark.parametrize(
    "truth,predictions,expected",
    [
        ([detection()], [detection()], (1, 0, 0)),
        ([detection()], [detection(), detection(confidence=0.8)], (1, 1, 0)),
        ([detection()], [], (0, 0, 1)),
        ([detection()], [detection(cls=1)], (0, 1, 1)),
        ([detection()], [detection(box=(5, 5, 15, 15))], (0, 1, 1)),
    ],
)
def test_one_to_one_same_class_matching(truth, predictions, expected):
    from pcb_inspection.ml.metrics import aggregate

    result = aggregate([{"truth": truth, "predictions": predictions, "verified_negative": False}])
    assert (result["tp"], result["fp"], result["fn"]) == expected
    assert result["false_positive_per_good_image"] is None
    assert result["false_alarm_image_rate"] is None


def test_only_verified_negatives_define_false_alarm_rates():
    from pcb_inspection.ml.metrics import aggregate

    result = aggregate(
        [
            {"truth": [], "predictions": [detection(), detection(cls=1)], "verified_negative": True},
            {"truth": [], "predictions": [], "verified_negative": True},
            {"truth": [], "predictions": [detection()], "verified_negative": False},
        ]
    )
    assert result["false_positive_per_good_image"] == 1
    assert result["false_alarm_image_rate"] == 0.5
    assert result["verified_negative_images"] == 2


def test_confidence_order_decides_matching():
    from pcb_inspection.ml.metrics import aggregate

    result = aggregate(
        [
            {
                "truth": [detection(), detection(box=(6, 0, 16, 10))],
                "predictions": [
                    detection(box=(3, 0, 13, 10), confidence=0.9),
                    detection(confidence=0.8),
                ],
                "verified_negative": False,
            }
        ]
    )
    assert (result["tp"], result["fp"], result["fn"]) == (1, 1, 1)


def test_verified_negative_cannot_have_ground_truth():
    from pcb_inspection.ml.metrics import aggregate

    with pytest.raises(ValueError, match="negative"):
        aggregate([{"truth": [detection()], "predictions": [], "verified_negative": True}])


def test_saved_evaluation_preserves_split_and_requires_complete_predictions():
    from pcb_inspection.ml.evaluate import evaluate_saved

    manifest = {
        "dataset_version": "fixture",
        "samples": [
            {"id": "a", "split": "val", "boxes": [detection()], "verified_negative": False},
            {"id": "b", "split": "test", "boxes": [detection()], "verified_negative": False},
        ],
    }
    result = evaluate_saved(manifest, {"a": [detection()]}, "val")
    assert result["split"] == "val"
    assert result["metrics"]["tp"] == 1
    assert result["metrics"]["images"] == 1
    with pytest.raises(ValueError, match="Missing predictions"):
        evaluate_saved(manifest, {"a": []}, "test")
