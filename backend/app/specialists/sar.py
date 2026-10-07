import hashlib
import os

from PIL import Image

from backend.app.analysis.overlay import render_overlay
from backend.app.analysis.sar import (
    Fusion,
    find_bright_targets,
    find_low_backscatter,
    fuse_with_optical,
    low_backscatter_confidence,
    prepare,
    sar_intent,
    target_confidence,
)
from backend.app.ingestion.access import RasterAccess
from backend.app.ingestion.info import Modality
from backend.app.models.params import SARParams
from backend.app.models.query import Evidence, ExecutionStep, SpecialistResult

TOOL_NAME = "sar-analysis"

# Larger scenes are analysed at reduced resolution to bound memory and time;
# the scale actually used is recorded in the execution trace.
ANALYSIS_MAX_SIDE = 2048

# Placeholder until confidences are calibrated (proposal section 5.7): the
# detector gives no score for "nothing is there".
NO_TARGET_CONFIDENCE = 0.50

LOW_COLOUR = (64, 140, 255)       # low backscatter / dark in both images
SAR_ONLY_COLOUR = (255, 170, 40)
OPTICAL_ONLY_COLOUR = (190, 90, 255)

CAVEAT = (
    "Low backscatter usually means smooth open water, but tarmac, smooth "
    "bare ground and radar shadow look the same."
)

_OPTICAL = (Modality.OPTICAL, Modality.MULTISPECTRAL)


def _format_area(area_m2: float) -> str:
    if area_m2 >= 1_000_000:
        return f"{area_m2 / 1_000_000:,.2f} sq. km"

    if area_m2 >= 10_000:
        return f"{area_m2 / 10_000:,.2f} hectares"

    return f"{area_m2:,.0f} sq. m"


def _failed(answer: str, trace: list[ExecutionStep], step: str) -> SpecialistResult:
    trace.append(ExecutionStep(step=step, status="failed", tool=TOOL_NAME))

    return SpecialistResult(answer=answer, confidence=0.10, trace=trace)


def _choose_images(candidates):
    """
    candidates: [(image_id, path, info)] for the images that exist.
    Returns (sar, optical_or_None, notes) or (None, None, [reason]).
    """

    if len(candidates) == 1:
        only = candidates[0]

        if only[2] is not None and only[2].modality in _OPTICAL:
            return None, None, [
                "The uploaded image is optical. SAR analysis needs a SAR "
                "image, or an optical and SAR pair."
            ]

        return only, None, []

    first, second = candidates

    def kind(candidate):
        return candidate[2].modality if candidate[2] is not None else None

    for wanted in (Modality.SAR, Modality.SINGLE_BAND, None):
        matches = [c for c in candidates if kind(c) == wanted]

        if len(matches) == 1:
            sar = matches[0]
            other = second if sar is first else first
            notes = []

            if wanted == Modality.SINGLE_BAND:
                notes.append(
                    f"{sar[0]} has a single band and no sensor metadata; "
                    "it was assumed to be the SAR image"
                )
            elif wanted is None:
                notes.append(
                    f"{sar[0]} could not be inspected; it was assumed to be "
                    "the SAR image"
                )

            return sar, other, notes

        if len(matches) == 2:
            reason = (
                "Both images are SAR"
                if wanted == Modality.SAR
                else "The two images could not be told apart as SAR and optical"
            )

            return first, None, [
                f"{reason}; only {first[0]} was analysed. To compare two "
                "SAR images, ask what changed between them."
            ]

    return None, None, [
        "Neither uploaded image looks like SAR. Upload a SAR image, or an "
        "optical and SAR pair."
    ]


def run_sar(
    query: str,
    image_id: str | None = None,
    image_id_2: str | None = None,
    params: SARParams | None = None,
    access: RasterAccess | None = None,
) -> SpecialistResult:
    params = params or SARParams()
    access = access or RasterAccess()
    intent = sar_intent(query)

    trace = [
        ExecutionStep(
            step="SAR specialist initialized",
            status="complete",
            tool=TOOL_NAME,
            params={"intent": intent},
        )
    ]

    candidates = []

    for candidate_id in (image_id, image_id_2):
        path = access.resolve(candidate_id)

        if path is not None:
            candidates.append((candidate_id, path, access.read_info(path)))

    if not candidates:
        return _failed(
            "I could not locate the selected satellite image. Please upload "
            "a SAR GeoTIFF first.",
            trace,
            "Uploaded image lookup",
        )

    sar, optical, notes = _choose_images(candidates)

    if sar is None:
        return _failed(notes[0], trace, "SAR image selection")

    for note in notes:
        trace.append(
            ExecutionStep(step=f"Warning - {note}", status="warning", tool=TOOL_NAME)
        )

    sar_id, sar_path, _ = sar

    try:
        array, scale = access.load_array(sar_path, max_side=ANALYSIS_MAX_SIDE)
        scene = prepare(array[0], speckle_window=params.speckle_window)
    except Exception as exc:
        return _failed(
            f"The SAR image could not be analysed: {exc}.",
            trace,
            "SAR preparation",
        )

    trace.append(
        ExecutionStep(
            step=(
                f"Speckle filtering and backscatter statistics on {sar_id} "
                f"(band 1 of {array.shape[0]}, {array.shape[2]}x{array.shape[1]} px)"
            ),
            status="complete",
            tool=TOOL_NAME,
            params={
                "filter": "Lee",
                "speckle_window": params.speckle_window,
                "input_scale": scene.input_scale,
                "median_db": round(scene.median_db, 2),
                "analysis_scale": [round(scale[0], 3), round(scale[1], 3)],
            },
        )
    )

    low = find_low_backscatter(
        scene,
        min_contrast_db=params.min_contrast_db,
        min_region_px=params.min_region_px,
        max_regions=params.max_regions,
    )

    trace.append(
        ExecutionStep(
            step=(
                "Low-backscatter analysis ("
                + ("distinct class found" if low.distinct else "no distinct class")
                + ")"
            ),
            status="complete",
            tool=TOOL_NAME,
            params={
                "method": "Otsu split with minimum-contrast test",
                "min_contrast_db": params.min_contrast_db,
                "contrast_db": round(low.contrast_db, 2),
                "threshold_db": (
                    round(low.threshold_db, 2) if low.threshold_db is not None else None
                ),
                "min_region_px": params.min_region_px,
                "confidence_kind": "uncalibrated heuristic",
            },
        )
    )

    targets, target_total = find_bright_targets(
        scene,
        k=params.cfar_k,
        min_target_px=params.min_target_px,
        max_targets=params.max_targets,
    )

    trace.append(
        ExecutionStep(
            step=f"Bright target detection ({target_total} found)",
            status="complete",
            tool=TOOL_NAME,
            params={
                "method": "two-parameter CFAR in decibels",
                "cfar_k": params.cfar_k,
                "min_target_px": params.min_target_px,
                "confidence_kind": "uncalibrated heuristic",
            },
        )
    )

    # ---- optical-SAR fusion --------------------------------------------------

    fusion: Fusion | None = None
    fusion_note = None

    if optical is None:
        if intent == "fusion":
            fusion_note = (
                "No optical image was supplied, so this is a SAR-only analysis."
            )
    elif not low.distinct:
        fusion_note = (
            "The optical image was not used: the SAR image has no "
            "low-backscatter class to cross-check."
        )
    else:
        try:
            optical_array, _ = access.load_array(
                optical[1], max_side=ANALYSIS_MAX_SIDE
            )
            fusion = fuse_with_optical(low, scene.valid, optical_array)

            trace.append(
                ExecutionStep(
                    step=f"Optical-SAR fusion with {optical[0]}",
                    status="complete",
                    tool=TOOL_NAME,
                    params={
                        "method": "decision-level mask agreement",
                        "optical_indicator": fusion.indicator,
                        "optical_dark_class_found": fusion.optical_dark_distinct,
                        "agreement_iou": round(fusion.agreement, 3),
                    },
                )
            )
        except Exception as exc:
            fusion_note = (
                "The optical image could not be combined with the SAR "
                f"image ({exc}); this is a SAR-only analysis."
            )
            trace.append(
                ExecutionStep(
                    step=f"Warning - optical-SAR fusion skipped: {exc}",
                    status="warning",
                    tool=TOOL_NAME,
                )
            )

    # ---- evidence ------------------------------------------------------------

    scale_x, scale_y = scale
    pixel_factor = scale_x * scale_y
    source_size = (round(array.shape[2] * scale_x), round(array.shape[1] * scale_y))

    def to_source(bbox):
        return [
            round(bbox[0] * scale_x, 1),
            round(bbox[1] * scale_y, 1),
            round(bbox[2] * scale_x, 1),
            round(bbox[3] * scale_y, 1),
        ]

    try:
        pixel_area = access.pixel_area_m2(sar_path)
    except Exception:
        pixel_area = None

    digest = hashlib.sha1(
        f"{image_id}|{image_id_2}|{query}|{params.model_dump_json()}".encode()
    ).hexdigest()[:10]
    stem = os.path.splitext(os.path.basename(sar_id))[0]

    low_evidence: list[Evidence] = []
    target_evidence = [
        Evidence(
            kind="bbox",
            label=(
                f"bright target, +{target.contrast_db:.1f} dB over its "
                f"surroundings, {target.area_px * pixel_factor:,.0f} px"
            ),
            bbox=to_source(target.bbox),
        )
        for target in targets
    ]
    overlay_name = None

    if low.distinct or targets:
        try:
            if low.distinct:
                mask_name = access.save_png(
                    Image.fromarray(low.mask.astype("uint8") * 255),
                    f"{stem}_lowbackscatter_{digest}.png",
                )
                low_evidence.append(
                    Evidence(
                        kind="mask",
                        label="low-backscatter (water-like) surface",
                        mask_ref=mask_name,
                    )
                )

            if fusion is not None:
                base = access.load_rgb(optical[1], max_side=1200)
                layers = [
                    (fusion.both, LOW_COLOUR),
                    (fusion.sar_only, SAR_ONLY_COLOUR),
                    (fusion.optical_only, OPTICAL_ONLY_COLOUR),
                ]
            else:
                base = access.load_rgb(sar_path, max_side=1200)
                layers = [(low.mask, LOW_COLOUR)]

            overlay = render_overlay(
                base,
                boxes=[
                    (to_source(target.bbox), f"+{target.contrast_db:.0f} dB")
                    for target in targets
                ],
                masks=layers,
                source_size=source_size,
            )
            overlay_name = access.save_png(overlay, f"{stem}_evidence_{digest}.png")

            trace.append(
                ExecutionStep(
                    step="Evidence overlay rendered",
                    status="complete",
                    tool=TOOL_NAME,
                    params={
                        "overlay": overlay_name,
                        "legend": (
                            "blue: dark in SAR and optical; orange: SAR only; "
                            "purple: optical only; boxes: bright targets"
                            if fusion is not None
                            else "blue: low backscatter; boxes: bright targets"
                        ),
                    },
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

    for region in low.regions[:5]:
        low_evidence.append(
            Evidence(
                kind="bbox",
                label=(
                    "low-backscatter region, "
                    f"{region.area_px * pixel_factor:,.0f} px"
                ),
                bbox=to_source(region.bbox),
            )
        )

    # ---- answer ----------------------------------------------------------------

    if low.distinct:
        area_text = ""

        if pixel_area:
            area = float(low.mask.sum()) * pixel_factor * pixel_area
            area_text = f" (about {_format_area(area)})"

        plural = "region" if low.region_count == 1 else "regions"

        water_text = (
            f"Low-backscatter (water-like) surfaces cover {low.fraction:.1%} "
            f"of the scene{area_text} in {low.region_count} {plural}, about "
            f"{low.contrast_db:.1f} dB darker than the rest. {CAVEAT}"
        )
    else:
        water_text = (
            "No distinct low-backscatter (water-like) surface was found: the "
            "darker and brighter parts of the scene differ by only "
            f"{low.contrast_db:.1f} dB."
        )

    if targets:
        best = targets[0]
        box = to_source(best.bbox)
        plural = "target" if target_total == 1 else "targets"

        target_text = (
            f"Found {target_total} bright {plural} (strong reflectors such as "
            f"ships, metal structures or buildings). The strongest is "
            f"{best.contrast_db:.1f} dB above its surroundings at "
            f"x {box[0]:.0f}-{box[2]:.0f}, y {box[1]:.0f}-{box[3]:.0f}."
        )
    else:
        target_text = "No bright point targets stood out from their surroundings."

    fusion_text = fusion_note

    if fusion is not None:
        if fusion.optical_dark_distinct:
            fusion_text = (
                f"Cross-check with the optical image ({fusion.indicator}): "
                f"{fusion.sar_confirmed_fraction:.0%} of the SAR "
                "low-backscatter area is also dark in the optical image, "
                "which supports open water; the rest is dark only in SAR. "
                "In the overlay, blue is dark in both, orange is SAR only "
                "and purple is optical only."
            )
        else:
            fusion_text = (
                f"Cross-check with the optical image ({fusion.indicator}): "
                "the optical image has no distinct dark surface class, so it "
                "neither confirms nor rules out water."
            )

    stats_text = (
        f"Backscatter in band 1 of {sar_id} has a median of "
        f"{scene.median_db:.1f} dB (5th to 95th percentile "
        f"{scene.p05_db:.1f} to {scene.p95_db:.1f} dB). Decibel values are "
        "relative unless the file was radiometrically calibrated."
    )

    water_confidence = low_backscatter_confidence(low, params.min_contrast_db)
    targets_confidence = target_confidence(targets, params.cfar_k)

    if targets_confidence is None:
        targets_confidence = NO_TARGET_CONFIDENCE

    if intent == "water":
        parts = [water_text, fusion_text]
        evidence = low_evidence + target_evidence
        confidence = water_confidence
    elif intent == "targets":
        parts = [target_text]
        evidence = target_evidence + low_evidence
        confidence = targets_confidence
    elif intent == "fusion":
        parts = [fusion_text, water_text, target_text]
        evidence = low_evidence + target_evidence
        confidence = water_confidence
    else:
        parts = [stats_text, water_text, target_text, fusion_text]
        evidence = low_evidence + target_evidence
        confidence = round((water_confidence + targets_confidence) / 2, 2)

    return SpecialistResult(
        answer=" ".join(part for part in parts if part),
        confidence=confidence,
        trace=trace,
        evidence=evidence,
        overlay=overlay_name,
    )
