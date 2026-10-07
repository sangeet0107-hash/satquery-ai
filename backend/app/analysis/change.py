"""
Pixel-level change detection between two co-registered images.

Pure numpy/scipy: nothing here reads files, so it is fully unit-testable.

Method (change vector analysis with a robust threshold):
  1. Each band of each image is standardised by its own median and MAD.
     A global brightness/contrast difference between the two dates
     (different sun angle, sensor gain) therefore cancels out.
  2. The per-pixel change magnitude is the Euclidean length of the
     band-wise difference.
  3. To tolerate small misregistration, the magnitude used is the
     smallest one found when the second image is shifted by up to
     `registration_tolerance_px` pixels in any direction.
  4. A pixel counts as changed when its magnitude exceeds all of: the
     scene's typical difference plus `sensitivity` robust sigmas, the Otsu
     threshold, and a small absolute floor.
  5. Speckle is removed by morphological opening and a minimum region size.

This says WHERE the imagery changed and by how much. It does not say what
kind of change it is; that needs a semantic model.
"""

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage

# MAD -> standard deviation for normally distributed data.
_MAD_TO_SIGMA = 1.4826

# Magnitudes are in units of each image's own robust spread. Differences
# below this are treated as noise even if the scene is otherwise static.
_ABSOLUTE_FLOOR = 0.3


@dataclass
class ChangeRegion:
    # [x_min, y_min, x_max, y_max] in pixels of the analysed array;
    # max edges are exclusive.
    bbox: tuple[int, int, int, int]
    area_px: int
    direction: str  # "brighter" or "darker" in the second image
    mean_magnitude: float


@dataclass
class ChangeResult:
    mask: np.ndarray
    changed_fraction: float
    valid_fraction: float
    region_count: int
    regions: list[ChangeRegion] = field(default_factory=list)
    threshold: float = 0.0
    separability: float = 0.0
    raw_fraction: float = 0.0


def _as_bands(array: np.ndarray) -> np.ndarray:
    array = np.asarray(array, dtype="float32")

    if array.ndim == 2:
        array = array[np.newaxis, ...]

    if array.ndim != 3:
        raise ValueError("expected an array shaped (bands, height, width)")

    return array


def _robust_standardise(band: np.ndarray, valid: np.ndarray) -> np.ndarray:
    values = band[valid]
    centre = np.median(values)
    spread = _MAD_TO_SIGMA * np.median(np.abs(values - centre))

    if spread <= 0:
        spread = values.std()

    if spread <= 0:
        spread = 1.0

    return (band - centre) / spread


def _otsu_threshold(values: np.ndarray, bins: int = 256) -> float:
    low, high = float(values.min()), float(values.max())

    if high <= low:
        return low

    hist, edges = np.histogram(values, bins=bins, range=(low, high))
    hist = hist.astype("float64")
    centres = (edges[:-1] + edges[1:]) / 2

    weight_low = np.cumsum(hist)
    weight_high = weight_low[-1] - weight_low
    sum_low = np.cumsum(hist * centres)
    total = sum_low[-1]

    with np.errstate(divide="ignore", invalid="ignore"):
        mean_low = sum_low / weight_low
        mean_high = (total - sum_low) / weight_high
        between = weight_low * weight_high * (mean_low - mean_high) ** 2

    between = np.nan_to_num(between, nan=0.0)

    return float(centres[int(np.argmax(between))])


def _min_shift_magnitude(
    reference: np.ndarray,
    moving: np.ndarray,
    radius: int,
) -> np.ndarray:
    """
    Smallest band-wise distance between each reference pixel and the
    moving image shifted by every offset within `radius` pixels.
    """

    _, height, width = reference.shape
    padded = np.pad(
        moving, ((0, 0), (radius, radius), (radius, radius)), mode="edge"
    )
    best = None

    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            shifted = padded[
                :,
                radius + dy : radius + dy + height,
                radius + dx : radius + dx + width,
            ]
            distance = np.sqrt(((shifted - reference) ** 2).sum(axis=0))
            best = distance if best is None else np.minimum(best, distance)

    return best


def detect_change(
    before: np.ndarray,
    after: np.ndarray,
    sensitivity: float = 3.0,
    min_region_px: int = 25,
    max_regions: int = 20,
    registration_tolerance_px: int = 1,
) -> ChangeResult:
    before = _as_bands(before)
    after = _as_bands(after)

    if before.shape != after.shape:
        raise ValueError(
            f"image shapes differ: {before.shape} vs {after.shape}"
        )

    valid = np.isfinite(before).all(axis=0) & np.isfinite(after).all(axis=0)

    if not valid.any():
        raise ValueError("the images have no valid pixels in common")

    standard_before = np.zeros_like(before)
    standard_after = np.zeros_like(after)

    for index in range(before.shape[0]):
        standard_before[index] = _robust_standardise(before[index], valid)
        standard_after[index] = _robust_standardise(after[index], valid)

    standard_before[:, ~valid] = 0.0
    standard_after[:, ~valid] = 0.0

    difference = standard_after - standard_before
    direct = np.sqrt((difference ** 2).sum(axis=0))
    signed = difference.mean(axis=0)

    # Tolerate small misregistration: a pixel only counts as changed if it
    # still differs after the second image is nudged by up to
    # `registration_tolerance_px` in every direction. Without this, every
    # sharp edge in a slightly misaligned pair shows up as change.
    radius = registration_tolerance_px
    magnitude = _min_shift_magnitude(standard_before, standard_after, radius)

    values = magnitude[valid]
    centre = np.median(values)
    sigma = _MAD_TO_SIGMA * np.median(np.abs(values - centre))

    threshold = max(
        centre + sensitivity * sigma,
        _otsu_threshold(values),
        _ABSOLUTE_FLOOR,
    )

    square = np.ones((3, 3), dtype=bool)
    raw = (magnitude > threshold) & valid

    if radius > 0:
        # Pixels on the image border have no neighbour to be matched against
        # once the content has shifted, so they cannot start a detection
        # (they can still be included when a detection grows into them).
        raw[:radius, :] = raw[-radius:, :] = False
        raw[:, :radius] = raw[:, -radius:] = False

    if radius > 0 and raw.any():
        # The nudging also shaves up to `radius` pixels off the border of
        # real changes; grow back (one pixel further, to recover corners)
        # into pixels the direct comparison flags.
        grown = ndimage.binary_dilation(
            raw, structure=square, iterations=radius + 1
        )
        raw = grown & (direct > threshold) & valid

    raw_fraction = float(raw.sum() / valid.sum())

    # Opening removes speckle, closing fills pinholes. Erosions treat the
    # area outside the image as set, so regions touching the image edge
    # are not shaved.
    cleaned = ndimage.binary_dilation(
        ndimage.binary_erosion(raw, structure=square, border_value=1),
        structure=square,
    )
    cleaned = ndimage.binary_erosion(
        ndimage.binary_dilation(cleaned, structure=square),
        structure=square,
        border_value=1,
    ) & valid

    labels, count = ndimage.label(cleaned, structure=square)

    regions: list[ChangeRegion] = []

    if count:
        areas = np.bincount(labels.ravel(), minlength=count + 1)
        too_small = np.flatnonzero(areas < min_region_px)
        too_small = too_small[too_small != 0]

        if too_small.size:
            cleaned[np.isin(labels, too_small)] = False
            labels, count = ndimage.label(cleaned, structure=square)
            areas = np.bincount(labels.ravel(), minlength=count + 1)

    if count:
        index = np.arange(1, count + 1)
        mean_magnitude = ndimage.mean(magnitude, labels=labels, index=index)
        mean_signed = ndimage.mean(signed, labels=labels, index=index)

        for label_id, slices in enumerate(ndimage.find_objects(labels), start=1):
            rows, cols = slices
            regions.append(
                ChangeRegion(
                    bbox=(cols.start, rows.start, cols.stop, rows.stop),
                    area_px=int(areas[label_id]),
                    direction=(
                        "brighter" if mean_signed[label_id - 1] >= 0 else "darker"
                    ),
                    mean_magnitude=float(mean_magnitude[label_id - 1]),
                )
            )

        regions.sort(key=lambda region: region.area_px, reverse=True)

    changed = cleaned & valid
    unchanged = valid & ~changed
    separability = 0.0

    if changed.any() and unchanged.any():
        spread = magnitude[unchanged].std()
        gap = magnitude[changed].mean() - magnitude[unchanged].mean()
        separability = float(gap / (spread + 1e-6))

    return ChangeResult(
        mask=changed,
        changed_fraction=float(changed.sum() / valid.sum()),
        valid_fraction=float(valid.mean()),
        region_count=len(regions),
        regions=regions[:max_regions],
        threshold=float(threshold),
        separability=separability,
        raw_fraction=raw_fraction,
    )


def change_confidence(result: ChangeResult) -> float:
    """
    Heuristic confidence in the reported outcome. NOT a calibrated
    probability (calibration is a later milestone, proposal section 5.7).

    Change found: grows with how far the changed pixels stand out from the
    unchanged background, measured in standard deviations of that
    background (separability s gives s / (s + 10), so 0.5 at ten sigmas).
    No change found: high when almost nothing was above the noise
    threshold, lower when many scattered pixels were.
    """

    if result.region_count:
        score = result.separability / (result.separability + 10.0)
    else:
        score = 0.9 - 10.0 * result.raw_fraction

    return round(float(np.clip(score, 0.05, 0.95)), 2)
