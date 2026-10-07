import hashlib
import os

from backend.app.analysis.grounding import (
    Detector,
    extract_target_phrases,
    ground,
)
from backend.app.analysis.overlay import render_overlay
from backend.app.ingestion.access import RasterAccess
from backend.app.models.params import GroundingParams
from backend.app.models.query import Evidence, ExecutionStep, SpecialistResult

TOOL_NAME = "grounding"
MODEL_NAME = "google/owlvit-base-patch32"

# Placeholder until confidences are calibrated (proposal section 5.7): the
# detector gives no score for "nothing is there".
NO_DETECTION_CONFIDENCE = 0.30

_pipeline = None


def owlvit_detector(image, labels: list[str], threshold: float) -> list[dict]:
    """Open-vocabulary detection with OWL-ViT on CPU (loaded on first use)."""

    global _pipeline

    if _pipeline is None:
        from transformers import pipeline

        _pipeline = pipeline(
            "zero-shot-object-detection",
            model=MODEL_NAME,
            device=-1,
        )

    raw = _pipeline(image, candidate_labels=labels, threshold=threshold)

    return [
        {
            "label": item["label"],
            "score": float(item["score"]),
            "box": [
                item["box"]["xmin"],
                item["box"]["ymin"],
                item["box"]["xmax"],
                item["box"]["ymax"],
            ],
        }
        for item in raw
    ]


def _failed(answer: str, trace: list[ExecutionStep], step: str) -> SpecialistResult:
    trace.append(ExecutionStep(step=step, status="failed", tool=TOOL_NAME))

    return SpecialistResult(answer=answer, confidence=0.10, trace=trace)


def run_grounding(
    query: str,
    image_id: str | None = None,
    params: GroundingParams | None = None,
    access: RasterAccess | None = None,
    detector: Detector | None = None,
) -> SpecialistResult:
    params = params or GroundingParams()
    access = access or RasterAccess()
    detector = detector or owlvit_detector

    trace = [
        ExecutionStep(
            step="Grounding specialist initialized",
            status="complete",
            tool=TOOL_NAME,
        )
    ]

    path = access.resolve(image_id)

    if path is None:
        return _failed(
            "I could not locate the selected satellite image. Please upload "
            "a GeoTIFF image before asking where something is.",
            trace,
            "Uploaded image lookup",
        )

    phrases = extract_target_phrases(query)

    if not phrases:
        return _failed(
            "I could not tell which object to look for. Try naming it, for "
            "example: 'Where are the ships?'",
            trace,
            "Target object extraction",
        )

    trace.append(
        ExecutionStep(
            step=f"Target object(s): {', '.join(phrases)}",
            status="complete",
            tool="query-parser",
        )
    )

    try:
        image = access.load_rgb(path)
        detections, tiles = ground(
            image,
            phrases,
            detector,
            score_threshold=params.score_threshold,
            tile_size=params.tile_size,
            max_tiles=params.max_tiles,
            max_detections=params.max_detections,
        )
    except Exception as exc:
        return _failed(
            f"Object localization failed: {exc}",
            trace,
            "Object localization model execution",
        )

    trace.append(
        ExecutionStep(
            step=(
                f"Object localization model execution "
                f"({tiles} tile(s), {len(detections)} detection(s))"
            ),
            status="complete",
            tool=MODEL_NAME,
            params={
                **params.model_dump(),
                "device": "cpu",
                "confidence_kind": "raw detector score, uncalibrated",
            },
        )
    )

    quoted = ", ".join(f"'{phrase}'" for phrase in phrases)

    if not detections:
        return SpecialistResult(
            answer=(
                f"No {quoted} was detected above the score threshold of "
                f"{params.score_threshold:.2f}. The detector is a "
                "general-purpose model, so small or unusual objects in "
                "satellite imagery can be missed."
            ),
            confidence=NO_DETECTION_CONFIDENCE,
            trace=trace,
        )

    evidence = [
        Evidence(
            kind="bbox",
            label=detection.label,
            bbox=[round(value, 1) for value in detection.bbox],
            score=round(detection.score, 3),
        )
        for detection in detections
    ]

    overlay_name = None

    try:
        digest = hashlib.sha1(
            f"{image_id}|{query}|{params.model_dump_json()}".encode()
        ).hexdigest()[:10]
        stem = os.path.splitext(os.path.basename(image_id or "image"))[0]

        overlay = render_overlay(
            image,
            boxes=[
                (detection.bbox, f"{detection.label} {detection.score:.2f}")
                for detection in detections
            ],
        )
        overlay_name = access.save_png(overlay, f"{stem}_evidence_{digest}.png")

        trace.append(
            ExecutionStep(
                step="Evidence overlay rendered",
                status="complete",
                tool=TOOL_NAME,
                params={"overlay": overlay_name},
            )
        )
    except Exception as exc:
        trace.append(
            ExecutionStep(
                step=f"Evidence overlay could not be rendered: {exc}",
                status="warning",
                tool=TOOL_NAME,
            )
        )

    counts = []

    for phrase in phrases:
        scores = [d.score for d in detections if d.label == phrase]

        if scores:
            counts.append(
                f"{len(scores)} x '{phrase}' "
                f"(scores {min(scores):.2f}-{max(scores):.2f})"
            )
        else:
            counts.append(f"no '{phrase}'")

    best = detections[0]

    answer = (
        f"Found {'; '.join(counts)}. The strongest match is a '{best.label}' "
        f"at x {best.bbox[0]:.0f}-{best.bbox[2]:.0f}, "
        f"y {best.bbox[1]:.0f}-{best.bbox[3]:.0f} (pixel coordinates). "
        "All boxes are listed under Evidence."
    )

    confidence = round(sum(d.score for d in detections) / len(detections), 2)

    return SpecialistResult(
        answer=answer,
        confidence=confidence,
        trace=trace,
        evidence=evidence,
        overlay=overlay_name,
    )
