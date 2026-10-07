"""
Pure-data description of an ingested raster plus the logic that reasons
about it (modality detection, pair compatibility).

Nothing in this module imports rasterio, so it is cheap to import and easy
to unit-test. raster.py is responsible for filling a RasterInfo from a file.
"""

import math
import re
from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class Modality(str, Enum):
    SAR = "SAR"
    OPTICAL = "OPTICAL"            # 3-4 bands (RGB / RGB+NIR)
    MULTISPECTRAL = "MULTISPECTRAL"  # 5+ bands
    SINGLE_BAND = "SINGLE_BAND"    # panchromatic or unlabeled SAR; ambiguous


class Bounds(BaseModel):
    left: float
    bottom: float
    right: float
    top: float


class RasterInfo(BaseModel):
    image_id: str | None = None
    width: int
    height: int
    bands: int
    dtype: str
    crs: str | None = None
    bounds: Bounds
    pixel_size: tuple[float, float] | None = None
    modality: Modality
    modality_confidence: str = Field(description="'high', 'medium' or 'low'.")
    modality_reason: str
    acquisition_date: date | None = None
    acquisition_source: str | None = None


# --------------------------------------------------------------------------
# Modality detection
# --------------------------------------------------------------------------

_SAR_HINT = re.compile(
    r"(?<![a-z])(sar|radar|sentinel-?1|risat|vv|vh|hh|hv|backscatter|"
    r"sigma0|gamma0)(?![a-z])"
)


def detect_modality(
    band_count: int,
    dtype: str,
    hint_text: str = "",
) -> tuple[Modality, str, str]:
    """
    Decide the sensor modality of a raster.

    hint_text is the lower-cased concatenation of the file name, dataset
    tags and band descriptions. Returns (modality, confidence, reason).
    Explicit metadata hints beat band-count heuristics.
    """

    match = _SAR_HINT.search(hint_text.lower())

    if match:
        return (
            Modality.SAR,
            "high",
            f"metadata/file name contains SAR hint '{match.group(1)}'",
        )

    if band_count >= 5:
        return (
            Modality.MULTISPECTRAL,
            "medium",
            f"{band_count} bands, consistent with multispectral imagery",
        )

    if band_count in (3, 4):
        return (
            Modality.OPTICAL,
            "medium",
            f"{band_count} bands, consistent with RGB(+NIR) optical imagery",
        )

    if band_count == 2 and dtype.startswith("float"):
        return (
            Modality.SAR,
            "low",
            "two floating-point bands resemble dual-polarisation SAR "
            "(e.g. VV/VH); no explicit SAR metadata found",
        )

    return (
        Modality.SINGLE_BAND,
        "low",
        "single band with no sensor metadata; could be panchromatic "
        "optical or single-polarisation SAR",
    )


# --------------------------------------------------------------------------
# Acquisition date
# --------------------------------------------------------------------------

_DATE_TAG_KEYS = (
    "acquisition_date",
    "date_acquired",
    "sensing_time",
    "product_start_time",
)

_WEAK_DATE_TAG_KEYS = ("tifftag_datetime", "datetime")

_DATE_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})[-:/_]?(0[1-9]|1[0-2])[-:/_]?(0[1-9]|[12]\d|3[01])(?!\d)")


def _parse_date(text: str) -> date | None:
    match = _DATE_RE.search(text)

    if not match:
        return None

    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def parse_acquisition_date(
    tags: dict[str, str],
    filename: str = "",
) -> tuple[date | None, str | None]:
    """
    Best-effort acquisition date. Order of trust: explicit acquisition
    tags, then a date embedded in the file name, then the generic TIFF
    DateTime tag (which is usually file-creation time, so it is weak).
    """

    lowered = {k.lower(): v for k, v in tags.items()}

    for key in _DATE_TAG_KEYS:
        value = lowered.get(key)
        if value:
            parsed = _parse_date(str(value))
            if parsed:
                return parsed, f"tag:{key}"

    parsed = _parse_date(filename)
    if parsed:
        return parsed, "filename"

    for key in _WEAK_DATE_TAG_KEYS:
        value = lowered.get(key)
        if value:
            parsed = _parse_date(str(value))
            if parsed:
                return parsed, f"tag:{key} (file time, weak)"

    return None, None


# --------------------------------------------------------------------------
# Ground area
# --------------------------------------------------------------------------

_METRES_PER_DEGREE = 111_320.0


def geographic_pixel_area_m2(
    res_x_deg: float,
    res_y_deg: float,
    latitude_deg: float,
) -> float:
    """
    Approximate ground area of a pixel given in degrees. A degree of
    longitude shrinks with the cosine of latitude; good to about 1% away
    from the poles, which is enough for reporting changed area.
    """

    metres_y = res_y_deg * _METRES_PER_DEGREE
    metres_x = res_x_deg * _METRES_PER_DEGREE * math.cos(math.radians(latitude_deg))

    return abs(metres_x * metres_y)


# --------------------------------------------------------------------------
# Pair compatibility
# --------------------------------------------------------------------------

class PairType(str, Enum):
    OPTICAL_SAR = "OPTICAL_SAR"
    BITEMPORAL = "BITEMPORAL"
    SAME_SCENE_UNDATED = "SAME_SCENE_UNDATED"
    UNRELATED = "UNRELATED"


class PairReport(BaseModel):
    same_crs: bool
    same_grid: bool
    co_registered: bool
    bounds_overlap: float = Field(
        description="Intersection-over-union of the two extents (0-1); "
        "0 when the CRS differs and it cannot be computed."
    )
    bitemporal: bool | None = Field(
        description="True/False when both dates are known, else None."
    )
    pair_type: PairType
    issues: list[str]


def _iou(a: Bounds, b: Bounds) -> float:
    ix = max(0.0, min(a.right, b.right) - max(a.left, b.left))
    iy = max(0.0, min(a.top, b.top) - max(a.bottom, b.bottom))
    inter = ix * iy
    area_a = (a.right - a.left) * (a.top - a.bottom)
    area_b = (b.right - b.left) * (b.top - b.bottom)
    union = area_a + area_b - inter

    return inter / union if union > 0 else 0.0


def _close(x: float, y: float, rel: float = 1e-3) -> bool:
    return abs(x - y) <= rel * max(abs(x), abs(y), 1e-12)


def check_pair(a: RasterInfo, b: RasterInfo) -> PairReport:
    issues: list[str] = []

    same_crs = a.crs is not None and a.crs == b.crs

    if not same_crs:
        issues.append(
            f"CRS differs or is missing ({a.crs} vs {b.crs}); "
            "reprojection would be needed before pixel-level comparison"
        )

    same_grid = (
        a.width == b.width
        and a.height == b.height
        and a.pixel_size is not None
        and b.pixel_size is not None
        and _close(a.pixel_size[0], b.pixel_size[0])
        and _close(a.pixel_size[1], b.pixel_size[1])
    )

    if not same_grid:
        issues.append(
            f"raster grids differ ({a.width}x{a.height} vs "
            f"{b.width}x{b.height} px or different pixel size)"
        )

    overlap = _iou(a.bounds, b.bounds) if same_crs else 0.0

    if same_crs and overlap < 0.98:
        issues.append(f"extents overlap only {overlap:.0%}")

    co_registered = same_crs and same_grid and overlap >= 0.98

    if a.acquisition_date and b.acquisition_date:
        bitemporal = a.acquisition_date != b.acquisition_date
    else:
        bitemporal = None
        issues.append("acquisition date unknown for at least one image")

    modalities = {a.modality, b.modality}
    one_sar = (Modality.SAR in modalities) and (modalities != {Modality.SAR})

    if overlap < 0.5 and same_crs:
        pair_type = PairType.UNRELATED
    elif one_sar:
        pair_type = PairType.OPTICAL_SAR
    elif bitemporal:
        pair_type = PairType.BITEMPORAL
    else:
        pair_type = PairType.SAME_SCENE_UNDATED

    return PairReport(
        same_crs=same_crs,
        same_grid=same_grid,
        co_registered=co_registered,
        bounds_overlap=round(overlap, 4),
        bitemporal=bitemporal,
        pair_type=pair_type,
        issues=issues,
    )
