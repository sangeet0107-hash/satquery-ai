import os

from backend.app.ingestion.raster import load_rgb_image
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


def _load_model():
    """Load BLIP once and reuse it for subsequent requests."""

    global _processor
    global _model

    # Imported lazily so the API starts (and tests run) without loading
    # the heavy ML stack until a VQA request actually needs it.
    from transformers import BlipForQuestionAnswering, BlipProcessor

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
        image = load_rgb_image(image_path)

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
                tool=MODEL_NAME,
                params={"max_new_tokens": 30, "device": "cpu"},
            )
        )

        import torch

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
            tool=MODEL_NAME,
            params={"max_new_tokens": 30, "device": "cpu"},
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