from io import BytesIO
from PIL import Image, ImageDraw

from .contracts import CLASS_COLORS


def render_overlay(image_path, defects, opacity=0.4):
    """Render approximate elliptical areas using original image coordinates."""
    if not 0 <= opacity <= 0.8:
        raise ValueError("Opacity must be between 0 and 0.8")
    with Image.open(image_path) as source:
        canvas = source.convert("RGBA")
    # Composite each region individually, matching Canvas source-over behavior.
    for defect in defects:
        layer = Image.new("RGBA", canvas.size)
        color = CLASS_COLORS[defect["class_id"]]
        rgb = tuple(int(color[index : index + 2], 16) for index in (1, 3, 5))
        ImageDraw.Draw(layer).ellipse(tuple(defect["bbox_xyxy"]), fill=(*rgb, round(opacity * 255)))
        canvas = Image.alpha_composite(canvas, layer)
    output = BytesIO()
    canvas.convert("RGB").save(output, "PNG")
    return output.getvalue()
