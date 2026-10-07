import hashlib
import os

from PIL import Image

from backend.app.analysis.change import change_confidence, detect_change
from backend.app.analysis.overlay import render_overlay
from backend.app.ingestion.access import RasterAccess
from backend.app.models.params import ChangeParams
from backend.app.models.query import Evidence, ExecutionStep, SpecialistResult

TOOL_NAME = "change-detection"
METHOD = "change vector analysis, robust MAD/Otsu threshold"

# Larger scenes are compared at reduced resolution to bound memory and time;
# the scale actually used is recorded in the execution trace.
ANALYSIS_MAX_SIDE = 2048

# Shown on every positive result so nobody reads more into it than is there.
SCOPE_NOTE = (
    "This is a pixel-level comparison of the second image against the "
    "first: it shows where the imagery changed, not what kind of change it is."
)


def _format_area(area_m2: float) -> str:
    if area_m2 >= 1_000_000:
        return f"{area_m2 / 1_000_000:,.2f} sq. km"

    if area_m2 >= 10_000:
        return f"{area_m2 / 10_000:,.2f} hectares"

    return f"{area_m2:,.0f} sq. m"


def _failed(answer: str, trace: list[ExecutionStep], step: str) -> SpecialistResult:
    trace.append(ExecutionStep(step=step, status="failed", tool=TOOL_NAME))

    return SpecialistResult(answer=answer, confidence=0.10, trace=trace)


def run_change_detection(
    query: str,
    image_id: str | None = None,
    image_id_2: str | None = None,
    params: ChangeParams | None = None,
    access: RasterAccess | None = None,
) -> SpecialistResult:
    params = params or ChangeParams()
    access = access or RasterAccess()

    trace = [
        ExecutionStep(
            step="Change detection specialist initialized",
            status="complete",
            tool=TOOL_NAME,
        )
    ]

    path_1 = access.resolve(image_id)
    path_2 = access.resolve(image_id_2)

    if path_1 is None or path_2 is None:
        return _failed(
            "I could not locate both uploaded images. Change detection "
            "needs a before image and an after image.",
            trace,
            "Uploaded image lookup",
        )

    try:
        before, scale = access.load_array(path_1, max_side=ANALYSIS_MAX_SIDE)
        after, _ = access.load_array(path_2, max_side=ANALYSIS_MAX_SIDE)
    except Exception as exc:
        return _failed(
            f"The images could not be read: {exc}",
            trace,
            "Raster loading",
        )

    if before.shape[1:] != after.shape[1:]:
        return _failed(
            "The two images are on different pixel grids "
            f"({before.shape[2]}x{before.shape[1]} vs "
            f"{after.shape[2]}x{after.shape[1]} px). Change detection "
            "currently needs both images resampled to the same grid.",
            trace,
            "Grid compatibility check",
        )

    bands = min(before.shape[0], after.shape[0])

    if before.shape[0] != after.shape[0]:
        trace.append(
            ExecutionStep(
                step=(
                    f"Warning - band counts differ ({before.shape[0]} vs "
                    f"{after.shape[0]}); comparing the first {bands} band(s)"
                ),
                status="warning",
                tool=TOOL_NAME,
            )
        )

    trace.append(
        ExecutionStep(
            step=(
                f"Loaded both images ({before.shape[2]}x{before.shape[1]} px, "
                f"{bands} band(s) compared)"
            ),
            status="complete",
            tool=TOOL_NAME,
            params={"analysis_scale": [round(scale[0], 3), round(scale[1], 3)]},
        )
    )

    try:
        result = detect_change(
            before[:bands],
            after[:bands],
            sensitivity=params.sensitivity,
            min_region_px=params.min_region_px,
            max_regions=params.max_regions,
            registration_tolerance_px=params.registration_tolerance_px,
        )
    except ValueError as exc:
        return _failed(
            f"Change detection could not run: {exc}.",
            trace,
            "Multi-temporal image comparison",
        )

    confidence = change_confidence(result)

    trace.append(
        ExecutionStep(
            step="Multi-temporal image comparison",
            status="complete",
            tool=TOOL_NAME,
            params={
                "method": METHOD,
                **params.model_dump(),
                "threshold": round(result.threshold, 4),
                "separability": round(result.separability, 2),
                "confidence_kind": "uncalibrated heuristic",
            },
        )
    )

    if result.region_count == 0:
        return SpecialistResult(
            answer=(
                "No significant change was detected between the two images "
                "at the current sensitivity."
            ),
            confidence=confidence,
            trace=trace,
        )

    # Regions back in source-image pixel coordinates.
    scale_x, scale_y = scale
    source_size = (round(before.shape[2] * scale_x), round(before.shape[1] * scale_y))

    def to_source(bbox):
        return [
            round(bbox[0] * scale_x, 1),
            round(bbox[1] * scale_y, 1),
            round(bbox[2] * scale_x, 1),
            round(bbox[3] * scale_y, 1),
        ]

    pixel_factor = scale_x * scale_y
    changed_px = float(result.mask.sum()) * pixel_factor

    try:
        pixel_area = access.pixel_area_m2(path_2)
    except Exception:
        pixel_area = None

    area_text = (
        f" (about {_format_area(changed_px * pixel_area)})" if pixel_area else ""
    )

    digest = hashlib.sha1(
        f"{image_id}|{image_id_2}|{params.model_dump_json()}".encode()
    ).hexdigest()[:10]
    stem = os.path.splitext(os.path.basename(image_id_2 or "image"))[0]

    evidence: list[Evidence] = []
    overlay_name = None

    try:
        mask_name = access.save_png(
            Image.fromarray(result.mask.astype("uint8") * 255),
            f"{stem}_changemask_{digest}.png",
        )
        evidence.append(
            Evidence(kind="mask", label="changed pixels", mask_ref=mask_name)
        )

        overlay = render_overlay(
            access.load_rgb(path_2, max_side=1200),
            boxes=[(to_source(r.bbox), None) for r in result.regions],
            mask=result.mask,
            source_size=source_size,
        )
        overlay_name = access.save_png(overlay, f"{stem}_evidence_{digest}.png")

        trace.append(
            ExecutionStep(
                step="Evidence overlay rendered",
                status="complete",
                tool=TOOL_NAME,
                params={"overlay": overlay_name, "mask": mask_name},
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

    for region in result.regions:
        evidence.append(
            Evidence(
                kind="bbox",
                label=(
                    f"changed region, {region.area_px * pixel_factor:,.0f} px, "
                    f"{region.direction} in image 2"
                ),
                bbox=to_source(region.bbox),
            )
        )

    largest = result.regions[0]
    box = to_source(largest.bbox)
    plural = "region" if result.region_count == 1 else "regions"

    answer = (
        f"Detected {result.region_count} changed {plural} covering "
        f"{result.changed_fraction:.1%} of the scene{area_text}. The largest "
        f"is {largest.area_px * pixel_factor:,.0f} px at x {box[0]:.0f}-{box[2]:.0f}, "
        f"y {box[1]:.0f}-{box[3]:.0f} and is {largest.direction} in the second "
        f"image. {SCOPE_NOTE}"
    )

    return SpecialistResult(
        answer=answer,
        confidence=confidence,
        trace=trace,
        evidence=evidence,
        overlay=overlay_name,
    )
