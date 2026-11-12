from io import BytesIO

import pytest
from PIL import Image

from pcb_inspection.images import normalize_image, ImageInputError


def encoded(image, fmt="PNG", **kwargs):
    stream = BytesIO()
    image.save(stream, fmt, **kwargs)
    return stream.getvalue()


def test_grayscale_becomes_rgb_and_png():
    result = normalize_image(encoded(Image.new("L", (80, 40), 128)))
    assert result.image.mode == "RGB"
    assert result.image.size == (80, 40)
    assert result.png.startswith(b"\x89PNG")


def test_orientation_is_applied_once():
    image = Image.new("RGB", (80, 40))
    exif = image.getexif()
    exif[274] = 6
    result = normalize_image(encoded(image, "JPEG", exif=exif))
    assert result.image.size == (40, 80)
    assert normalize_image(result.png).image.size == (40, 80)


def test_invalid_and_oversized_input():
    with pytest.raises(ImageInputError):
        normalize_image(b"not an image")
    with pytest.raises(ImageInputError):
        normalize_image(encoded(Image.new("RGB", (100, 80))), max_pixels=100)


def test_transparent_pixels_use_white_background():
    image = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    assert normalize_image(encoded(image)).image.getpixel((0, 0)) == (255, 255, 255)
