"""Draws evidence (change masks, bounding boxes) on top of an image."""

import numpy as np
from PIL import Image, ImageDraw, ImageFont

MASK_COLOUR = (255, 64, 64)
BOX_COLOUR = (45, 212, 191)
MASK_ALPHA = 0.45


def render_overlay(
    image: Image.Image,
    boxes: list[tuple[tuple[float, float, float, float], str | None]] | None = None,
    mask: np.ndarray | None = None,
    source_size: tuple[int, int] | None = None,
    max_side: int = 1200,
) -> Image.Image:
    """
    image:       RGB picture to draw on (any resolution).
    boxes:       [(bbox, label)] with bbox in source-image pixels.
    mask:        boolean array (any resolution) covering the full image.
    source_size: (width, height) the box coordinates refer to; defaults to
                 the size of `image`.
    """

    canvas = image.convert("RGB")
    canvas.thumbnail((max_side, max_side))
    width, height = canvas.size
    source_width, source_height = source_size or image.size

    if mask is not None and mask.any():
        resized = Image.fromarray(mask.astype("uint8") * 255).resize(
            (width, height), Image.NEAREST
        )
        selected = np.asarray(resized) > 0
        pixels = np.asarray(canvas, dtype="float32")
        pixels[selected] = (
            (1 - MASK_ALPHA) * pixels[selected]
            + MASK_ALPHA * np.array(MASK_COLOUR, dtype="float32")
        )
        canvas = Image.fromarray(pixels.astype("uint8"))

    if boxes:
        draw = ImageDraw.Draw(canvas)
        try:
            # Pillow >= 10.1 ships a scalable default font.
            font = ImageFont.load_default(size=max(11, round(max(width, height) / 90)))
        except TypeError:
            font = ImageFont.load_default()
        scale_x = width / source_width
        scale_y = height / source_height
        line = max(2, round(max(width, height) / 400))

        for (x0, y0, x1, y1), label in boxes:
            left, top = x0 * scale_x, y0 * scale_y
            right = max(x1 * scale_x, left + 1)
            bottom = max(y1 * scale_y, top + 1)

            draw.rectangle([left, top, right, bottom], outline=BOX_COLOUR, width=line)

            if label:
                text_box = draw.textbbox((0, 0), label, font=font)
                text_width = text_box[2] - text_box[0] + 6
                text_height = text_box[3] - text_box[1] + 6
                text_top = top - text_height if top >= text_height else top
                text_left = min(left, max(0, width - text_width))

                draw.rectangle(
                    [text_left, text_top, text_left + text_width, text_top + text_height],
                    fill=BOX_COLOUR,
                )
                draw.text((text_left + 3, text_top + 2), label, fill=(0, 0, 0), font=font)

    return canvas
