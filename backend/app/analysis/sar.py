"""
Single-image SAR analysis and decision-level optical-SAR fusion.

Pure numpy/scipy; nothing here reads files.

What it does:
  - Works out whether the band is already in decibels or in linear units,
    and reduces speckle with a Lee filter.
  - Looks for a distinct low-backscatter class. Smooth surfaces reflect the
    radar pulse away from the sensor, so open water shows up dark. Tarmac,
    smooth bare ground and radar shadow look the same, which is why results
    are described as "water-like", not "water".
  - Finds bright point targets (ships, metal structures, buildings) with a
    two-parameter CFAR detector: a pixel is a target when it stands out
    from a ring of surrounding background by more than k standard
    deviations.
  - With a co-registered optical image, checks how much of the SAR
    low-backscatter area is also dark in the optical image.

Backscatter values are only absolute if the file was calibrated; the
analysis relies on contrasts inside the scene, so it works either way.
"""

import re
from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage

from backend.app.analysis.masks import SQUARE, clean_mask, otsu_threshold

_FLOOR = 1e-12


@dataclass
class Region:
    # [x_min, y_min, x_max, y_max] in pixels of the analysed array;
    # max edges are exclusive.
    bbox: tuple[int, int, int, int]
    area_px: int


@dataclass
class Target(Region):
    contrast_db: float = 0.0
    peak_z: float = 0.0


@dataclass
class SarScene:
    linear: np.ndarray       # unfiltered intensity, 0 where invalid
    db: np.ndarray           # speckle-filtered decibels, NaN where invalid
    valid: np.ndarray
    input_scale: str         # "decibel" or "linear"
    median_db: float
    p05_db: float
    p95_db: float
    valid_fraction: float


@dataclass
class LowBackscatter:
    distinct: bool
    mask: np.ndarray
    fraction: float
    contrast_db: float
    bimodality: float
    threshold_db: float | None = None
    region_count: int = 0
    regions: list[Region] = field(default_factory=list)


@dataclass
class Fusion:
    indicator: str
    optical_dark_distinct: bool
    both: np.ndarray
    sar_only: np.ndarray
    optical_only: np.ndarray
    # Share of the SAR low-backscatter area that is also dark optically.
    sar_confirmed_fraction: float
    # Intersection over union of the two masks.
    agreement: float


# --------------------------------------------------------------------------
# Query intent
# --------------------------------------------------------------------------

_WATER = re.compile(
    r"\b(water|flood\w*|inundat\w*|river\w*|lake\w*|reservoir\w*|pond\w*|"
    r"wet\w*|sea|ocean|coast\w*|shore\w*)\b"
)
_TARGETS = re.compile(
    r"\b(ship\w*|vessel\w*|boat\w*|target\w*|bright\w*|metal\w*|"
    r"structure\w*|building\w*|vehicle\w*|object\w*|reflector\w*)\b"
)
_FUSION = re.compile(r"\b(fus\w+|combin\w+|optical|together|both)\b")


def sar_intent(query: str) -> str:
    """'water', 'targets', 'fusion' or 'summary'."""

    text = query.lower()

    if _WATER.search(text):
        return "water"

    if _TARGETS.search(text):
        return "targets"

    if _FUSION.search(text):
        return "fusion"

    return "summary"


# --------------------------------------------------------------------------
# Preparation
# --------------------------------------------------------------------------

def lee_filter(linear: np.ndarray, valid: np.ndarray, window: int = 5) -> np.ndarray:
    """
    Lee speckle filter. Flat areas are replaced by their local mean; areas
    with real structure (edges, point targets) are left closer to the
    original, so smoothing does not blur them away.
    """

    weights = valid.astype("float64")
    values = np.where(valid, linear, 0.0).astype("float64")

    count = np.maximum(ndimage.uniform_filter(weights, window), 1e-6)
    mean = ndimage.uniform_filter(values, window) / count
    mean_square = ndimage.uniform_filter(values * values, window) / count
    variance = np.maximum(mean_square - mean * mean, 0.0)

    # Squared coefficient of variation: locally, and for pure speckle
    # (estimated as the scene's typical value).
    local = variance / np.maximum(mean * mean, _FLOOR)
    speckle = float(np.median(local[valid])) if valid.any() else 0.0

    weight = np.clip(1.0 - speckle / np.maximum(local, _FLOOR), 0.0, 1.0)

    return mean + weight * (values - mean)


def prepare(band: np.ndarray, speckle_window: int = 5) -> SarScene:
    band = np.asarray(band, dtype="float64")

    if band.ndim != 2:
        raise ValueError("expected a single SAR band shaped (height, width)")

    finite = np.isfinite(band)

    if not finite.any():
        raise ValueError("the SAR band has no valid pixels")

    # Linear intensity/amplitude is never negative; decibel products are
    # negative over most surfaces.
    if float((band[finite] < 0).mean()) > 0.05:
        input_scale = "decibel"
        valid = finite
        linear = np.where(valid, 10.0 ** (np.where(valid, band, 0.0) / 10.0), 0.0)
    else:
        input_scale = "linear"
        # Zero is the usual fill value outside the swath.
        valid = finite & (band > 0)
        linear = np.where(valid, band, 0.0)

    if not valid.any():
        raise ValueError("the SAR band has no valid pixels")

    filtered = lee_filter(linear, valid, speckle_window)
    db = np.full(band.shape, np.nan)
    db[valid] = 10.0 * np.log10(np.maximum(filtered[valid], _FLOOR))

    values = db[valid]

    return SarScene(
        linear=linear,
        db=db,
        valid=valid,
        input_scale=input_scale,
        median_db=float(np.median(values)),
        p05_db=float(np.percentile(values, 5)),
        p95_db=float(np.percentile(values, 95)),
        valid_fraction=float(valid.mean()),
    )


# --------------------------------------------------------------------------
# Low backscatter (water-like)
# --------------------------------------------------------------------------

def _two_class_split(values: np.ndarray) -> tuple[float, float, float]:
    """(threshold, gap between class means, Ashman's D)."""

    threshold = otsu_threshold(values)
    low = values[values < threshold]
    high = values[values >= threshold]

    if low.size < 10 or high.size < 10:
        return threshold, 0.0, 0.0

    gap = float(high.mean() - low.mean())
    spread = float(np.sqrt(high.var() + low.var()))
    bimodality = float(np.sqrt(2.0) * gap / spread) if spread > 0 else 0.0

    return threshold, gap, bimodality


def find_low_backscatter(
    scene: SarScene,
    min_contrast_db: float = 5.0,
    min_region_px: int = 50,
    max_regions: int = 20,
) -> LowBackscatter:
    """
    Reports a low-backscatter class only when it is at least
    min_contrast_db darker than the rest of the scene. Ordinary land-cover
    differences are a few decibels; open water against land is typically
    much more. Without this test the threshold would split any scene in two.
    """

    threshold, gap, bimodality = _two_class_split(scene.db[scene.valid])
    empty = np.zeros(scene.valid.shape, dtype=bool)

    if gap < min_contrast_db:
        return LowBackscatter(
            distinct=False,
            mask=empty,
            fraction=0.0,
            contrast_db=gap,
            bimodality=bimodality,
        )

    raw = scene.valid & (np.nan_to_num(scene.db, nan=np.inf) < threshold)
    mask, labels, count, areas = clean_mask(raw, scene.valid, min_region_px)

    regions = [
        Region(
            bbox=(cols.start, rows.start, cols.stop, rows.stop),
            area_px=int(areas[label_id]),
        )
        for label_id, (rows, cols) in enumerate(ndimage.find_objects(labels), start=1)
    ]
    regions.sort(key=lambda region: region.area_px, reverse=True)

    return LowBackscatter(
        distinct=bool(mask.any()),
        mask=mask,
        fraction=float(mask.sum() / scene.valid.sum()),
        contrast_db=gap,
        bimodality=bimodality,
        threshold_db=float(threshold),
        region_count=len(regions),
        regions=regions[:max_regions],
    )


# --------------------------------------------------------------------------
# Bright targets (CFAR)
# --------------------------------------------------------------------------

def _window_sum(array: np.ndarray, size: int) -> np.ndarray:
    return ndimage.uniform_filter(array, size, mode="constant") * (size * size)


def find_bright_targets(
    scene: SarScene,
    k: float = 5.0,
    guard_px: int = 4,
    background_px: int = 12,
    min_target_px: int = 3,
    max_targets: int = 50,
) -> tuple[list[Target], int]:
    """
    Two-parameter CFAR in decibels on a lightly averaged (3x3) image.

    For each pixel the background is a square ring: everything within
    background_px, except the inner guard_px that might belong to the
    target itself. Returns (targets sorted by contrast, total found).
    """

    valid = scene.valid
    weights = valid.astype("float64")

    count = np.maximum(ndimage.uniform_filter(weights, 3), 1e-6)
    averaged = ndimage.uniform_filter(scene.linear, 3) / count
    db = np.where(valid, 10.0 * np.log10(np.maximum(averaged, _FLOOR)), 0.0)

    outer, inner = 2 * background_px + 1, 2 * guard_px + 1

    ring_count = _window_sum(weights, outer) - _window_sum(weights, inner)
    ring_sum = _window_sum(db, outer) - _window_sum(db, inner)
    ring_square = _window_sum(db * db, outer) - _window_sum(db * db, inner)

    enough = ring_count >= 0.25 * (outer * outer - inner * inner)
    safe = np.maximum(ring_count, 1.0)
    mean = ring_sum / safe
    std = np.sqrt(np.maximum(ring_square / safe - mean * mean, 1e-6))

    z = np.where(valid & enough, (db - mean) / std, 0.0)

    labels, found = ndimage.label(z > k, structure=SQUARE)

    if not found:
        return [], 0

    areas = np.bincount(labels.ravel(), minlength=found + 1)
    index = np.arange(1, found + 1)
    peak_z = ndimage.maximum(z, labels=labels, index=index)
    contrast = ndimage.maximum(db - mean, labels=labels, index=index)

    targets = [
        Target(
            bbox=(cols.start, rows.start, cols.stop, rows.stop),
            area_px=int(areas[label_id]),
            contrast_db=float(contrast[label_id - 1]),
            peak_z=float(peak_z[label_id - 1]),
        )
        for label_id, (rows, cols) in enumerate(ndimage.find_objects(labels), start=1)
        if areas[label_id] >= min_target_px
    ]
    targets.sort(key=lambda target: target.contrast_db, reverse=True)

    return targets[:max_targets], len(targets)


# --------------------------------------------------------------------------
# Optical-SAR fusion
# --------------------------------------------------------------------------

def fuse_with_optical(
    low: LowBackscatter,
    valid: np.ndarray,
    optical: np.ndarray,
) -> Fusion:
    """
    Decision-level fusion: compare the SAR low-backscatter mask with the
    dark surfaces of a co-registered optical image.

    Water absorbs near-infrared light strongly, so when the optical image
    has four or more bands, band 4 is used and assumed to be near-infrared
    (true for the common R,G,B,NIR and B,G,R,NIR layouts). Otherwise the
    mean brightness of all bands is used, which is a weaker indicator.
    """

    optical = np.asarray(optical, dtype="float64")

    if optical.ndim == 2:
        optical = optical[np.newaxis, ...]

    if optical.shape[1:] != valid.shape:
        raise ValueError(
            f"image shapes differ: {optical.shape[1:]} vs {valid.shape}"
        )

    if optical.shape[0] >= 4:
        indicator = "band 4, assumed near-infrared"
        brightness = optical[3]
    else:
        indicator = "mean brightness of all bands"
        brightness = optical.mean(axis=0)

    usable = valid & np.isfinite(brightness)
    empty = np.zeros(valid.shape, dtype=bool)
    dark = empty
    distinct = False

    if usable.any():
        threshold, _, bimodality = _two_class_split(brightness[usable])

        # Splitting a single-peaked histogram in two gives about 2.2.
        if bimodality >= 3.0:
            distinct = True
            dark, _, _, _ = clean_mask(
                usable & (brightness < threshold), usable, min_region_px=1
            )

    sar = low.mask & usable
    both = sar & dark
    union = sar | dark

    return Fusion(
        indicator=indicator,
        optical_dark_distinct=distinct,
        both=both,
        sar_only=sar & ~dark,
        optical_only=dark & ~sar,
        sar_confirmed_fraction=float(both.sum() / sar.sum()) if sar.any() else 0.0,
        agreement=float(both.sum() / union.sum()) if union.any() else 0.0,
    )


# --------------------------------------------------------------------------
# Confidence (heuristic, not calibrated)
# --------------------------------------------------------------------------

def low_backscatter_confidence(low: LowBackscatter, min_contrast_db: float) -> float:
    """
    Found: grows with the contrast of the dark class (0.5 exactly at the
    minimum contrast). Not found: high when the scene is nearly uniform,
    low when it only just missed the minimum contrast.
    """

    if low.distinct:
        score = low.contrast_db / (low.contrast_db + min_contrast_db)
    else:
        score = 1.0 - low.contrast_db / min_contrast_db

    return round(float(np.clip(score, 0.3, 0.95)), 2)


def target_confidence(targets: list[Target], k: float) -> float | None:
    """Grows with how far targets exceed the detection threshold; None if none."""

    if not targets:
        return None

    peak = float(np.mean([target.peak_z for target in targets]))

    return round(float(np.clip(peak / (peak + k), 0.3, 0.95)), 2)
