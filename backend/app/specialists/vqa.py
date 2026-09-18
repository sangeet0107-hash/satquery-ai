import os

import numpy as np
import rasterio
import torch
from PIL import Image
from transformers import BlipForQuestionAnswering, BlipProcessor

from backend.app.models.query import ExecutionStep


UPLOAD_DIR = "uploads"
MODEL_NAME = "Salesforce/blip-vqa-base"

_processor = None
_model = None


def _resolve_image_path(image_id: str | None) -> str | None:
    """Resolve the uploaded image filename to a file in uploads/."""

    if not image_id:
        return None

    filename = os.path.basename(image_id)
    image_path = os.path.join(UPLOAD_DIR, filename)

    if os.path.exists(image_path):
        return image_path

    return None


def _load_raster_as_rgb(image_path: str) -> Image.Image:
    """
    Load the first raster band from a GeoTIFF and convert it
    into an RGB PIL image suitable for BLIP.
    """

    with rasterio.open(image_path) as src:
        band = src.read(1).astype(np.float32)

    # Remove invalid values.
    valid = np.isfinite(band)

    if not np.any(valid):
        raise ValueError("The raster contains no valid pixel values.")

    valid_pixels = band[valid]

    low = np.percentile(valid_pixels, 2)
    high = np.percentile(valid_pixels, 98)

    if high <= low:
        high = low + 1.0

    normalized = (band - low) / (high - low)
    normalized = np.clip(normalized, 0, 1)

    image_8bit = (normalized * 255).astype(np.uint8)

    # BLIP expects RGB.
    rgb_array = np.stack(
        [image_8bit, image_8bit, image_8bit],
        axis=-1,
    )

    return Image.fromarray(rgb_array, mode="RGB")


def _load_model():
    """Load BLIP once and reuse it for subsequent requests."""

    global _processor
    global _model

    if _processor is None or _model is None:
        _processor = BlipProcessor.from_pretrained(MODEL_NAME)

        _model = BlipForQuestionAnswering.from_pretrained(
            MODEL_NAME
        )

        _model.to("cpu")
        _model.eval()

    return _processor, _model


def run_vqa(
    query: str,
    image_id: str | None = None,
) -> tuple[str, float, list[ExecutionStep]]:

    trace = [
        ExecutionStep(
            step="VQA specialist initialized",
            status="complete",
        )
    ]

    image_path = _resolve_image_path(image_id)

    if image_path is None:
        trace.append(
            ExecutionStep(
                step="Uploaded image lookup",
                status="failed",
            )
        )

        return (
            "I could not locate the selected satellite image. "
            "Please upload a GeoTIFF image before running VQA.",
            0.10,
            trace,
        )

    trace.append(
        ExecutionStep(
            step="Uploaded image located",
            status="complete",
        )
    )

    try:
        image = _load_raster_as_rgb(image_path)

        trace.append(
            ExecutionStep(
                step="GeoTIFF converted to RGB image",
                status="complete",
            )
        )

        processor, model = _load_model()

        trace.append(
            ExecutionStep(
                step="BLIP VQA model loaded",
                status="complete",
            )
        )

        inputs = processor(
            images=image,
            text=query,
            return_tensors="pt",
        )

        inputs = {
            key: value.to("cpu")
            for key, value in inputs.items()
        }

        trace.append(
            ExecutionStep(
                step="VQA model execution",
                status="running",
            )
        )

        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=30,
            )

        answer = processor.decode(
            output[0],
            skip_special_tokens=True,
        ).strip()

        if not answer:
            answer = "The model could not produce a clear answer."

        trace[-1] = ExecutionStep(
            step="VQA model execution",
            status="complete",
        )

        trace.append(
            ExecutionStep(
                step="VQA answer generated",
                status="complete",
            )
        )

        # BLIP generation does not directly provide a calibrated
        # confidence score, so this is currently a system-level
        # placeholder confidence.
        confidence = 0.70

        return answer, confidence, trace

    except Exception as exc:
        trace.append(
            ExecutionStep(
                step="VQA model execution",
                status="failed",
            )
        )

        return (
            f"VQA processing failed: {str(exc)}",
            0.10,
            trace,
        )