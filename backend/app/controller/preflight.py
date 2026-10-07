"""
Preflight checks: decide from the ingestion results whether the selected
task can sensibly run on the supplied imagery, before any model is called.
Blockers stop the run with an explanation; warnings are recorded in the
execution trace and the run continues.
"""

from pydantic import BaseModel

from backend.app.ingestion.info import (
    Modality,
    PairReport,
    PairType,
    RasterInfo,
)
from backend.app.models.query import TaskType


class Preflight(BaseModel):
    blockers: list[str] = []
    warnings: list[str] = []

    @property
    def ok(self) -> bool:
        return not self.blockers


def run_preflight(
    task: TaskType,
    image_id: str | None,
    image_id_2: str | None,
    info: RasterInfo | None,
    info_2: RasterInfo | None,
    pair: PairReport | None,
) -> Preflight:
    result = Preflight()

    if task == TaskType.UNKNOWN:
        return result

    # Image presence is decided from ids so it still works when an image
    # could not be parsed (specialists report their own lookup failures).
    if task in (TaskType.VQA, TaskType.GROUNDING, TaskType.SAR) and not image_id:
        result.blockers.append("no image was supplied")

    if task == TaskType.CHANGE:
        if not image_id or not image_id_2:
            result.blockers.append(
                "change detection needs two images (before and after)"
            )

    if result.blockers:
        return result

    if task in (TaskType.VQA, TaskType.GROUNDING) and info is not None:
        if info.modality == Modality.SAR:
            result.warnings.append(
                "the image looks like SAR; the selected model is trained "
                "mainly on optical imagery, so answers may be unreliable"
            )

    if task == TaskType.SAR:
        if image_id_2 is None and info is not None:
            if info.modality in (Modality.OPTICAL, Modality.MULTISPECTRAL):
                result.blockers.append(
                    "the uploaded image is optical, but the query needs SAR "
                    "data; upload a SAR image or an optical+SAR pair"
                )
            elif info.modality == Modality.SINGLE_BAND:
                result.warnings.append(
                    "could not confirm the single-band image is SAR"
                )

        if (
            info is not None
            and info_2 is not None
            and info.modality in (Modality.OPTICAL, Modality.MULTISPECTRAL)
            and info_2.modality in (Modality.OPTICAL, Modality.MULTISPECTRAL)
        ):
            result.blockers.append(
                "both uploaded images are optical, but the query needs SAR "
                "data; upload a SAR image or an optical+SAR pair"
            )

    if pair is not None:
        if pair.pair_type == PairType.UNRELATED:
            result.blockers.append(
                "the two images cover largely different areas "
                f"(extent overlap {pair.bounds_overlap:.0%})"
            )

        if task == TaskType.CHANGE:
            if pair.pair_type == PairType.OPTICAL_SAR:
                result.blockers.append(
                    "change detection needs two images from the same "
                    "sensor type, but this is an optical+SAR pair"
                )
            if (
                info is not None
                and info_2 is not None
                and (info.width, info.height) != (info_2.width, info_2.height)
            ):
                result.blockers.append(
                    "the two images have different pixel dimensions "
                    f"({info.width}x{info.height} vs "
                    f"{info_2.width}x{info_2.height}); change detection "
                    "currently needs both on the same grid"
                )
            if pair.bitemporal is False:
                result.warnings.append(
                    "both images have the same acquisition date"
                )
            if pair.bitemporal is None:
                result.warnings.append(
                    "acquisition dates are unknown, so the time order of "
                    "the images could not be verified"
                )

        if task in (TaskType.CHANGE, TaskType.SAR) and not pair.co_registered:
            if pair.pair_type != PairType.UNRELATED:
                result.warnings.append(
                    "the images are not co-registered (same CRS, grid and "
                    "extent); results may be misaligned"
                )

    return result
