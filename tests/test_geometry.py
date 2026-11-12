import pytest

from pcb_inspection.geometry import ellipse_geometry, tile_windows, class_aware_nms


def test_ellipse_uses_original_image_coordinates():
    assert ellipse_geometry([420, 180, 455, 205]) == (437.5, 192.5, 17.5, 12.5)


def test_tiles_cover_edges_and_do_not_tile_standard_crops():
    assert tile_windows(640, 640) == [(0, 0, 640, 640)]
    windows = tile_windows(1300, 700)
    assert windows[-1] == (660, 60, 1300, 700)
    assert len(windows) == 6
    with pytest.raises(ValueError):
        tile_windows(12000, 12000)


def test_nms_removes_duplicates_but_preserves_different_classes_and_nearby_defects():
    boxes = [[0, 0, 20, 20], [1, 1, 20, 20], [15, 0, 30, 20], [0, 0, 20, 20]]
    assert class_aware_nms(boxes, [0.9, 0.8, 0.7, 0.6], [0, 0, 0, 1], 0.5) == [0, 2, 3]
