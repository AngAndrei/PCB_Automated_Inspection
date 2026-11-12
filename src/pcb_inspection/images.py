"""Decode once; all downstream coordinates refer to this canonical RGB image."""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError


class ImageInputError(ValueError):
    pass


@dataclass
class CanonicalImage:
    image: Image.Image
    png: bytes
    content_hash: str


def normalize_image(
    data: bytes, *, max_pixels=40_000_000, max_bytes=25 * 1024 * 1024, max_side=12_000
) -> CanonicalImage:
    if not data or len(data) > max_bytes:
        raise ImageInputError("Upload a JPG or PNG smaller than 25 MiB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.format not in {"JPEG", "PNG"}:
                    raise ImageInputError("Only JPG and PNG images are supported.")
                w, h = source.size
                if w * h > max_pixels or max(w, h) > max_side:
                    raise ImageInputError("Image exceeds the 40 MP / 12000 px limit. Upload a crop.")
                source.load()
                oriented = ImageOps.exif_transpose(source)
                if "A" in oriented.getbands() or "transparency" in oriented.info:
                    rgba = oriented.convert("RGBA")
                    rgb = Image.new("RGB", rgba.size, "white")
                    rgb.paste(rgba, mask=rgba.getchannel("A"))
                else:
                    rgb = oriented.convert("RGB")
                rgb.info.clear()
        stream = BytesIO()
        rgb.save(stream, "PNG")
        png = stream.getvalue()
        return CanonicalImage(rgb, png, sha256(png).hexdigest())
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        SyntaxError,
    ) as exc:
        raise ImageInputError("The file could not be decoded as a valid JPG or PNG.") from exc
