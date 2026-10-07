"""Helpers shared by the analyses that turn a per-pixel score into regions."""

import numpy as np
from scipy import ndimage

SQUARE = np.ones((3, 3), dtype=bool)


def otsu_threshold(values: np.ndarray, bins: int = 256) -> float:
    """Threshold that best separates the values into two classes."""

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


def clean_mask(
    raw: np.ndarray,
    valid: np.ndarray,
    min_region_px: int,
) -> tuple[np.ndarray, np.ndarray, int, np.ndarray]:
    """
    Remove speckle (opening), fill pinholes (closing) and drop connected
    regions smaller than min_region_px.

    Erosions treat the area outside the image as set, so regions touching
    the image edge are not shaved.

    Returns (mask, labels, region_count, areas) where areas[i] is the pixel
    count of the region labelled i (areas[0] is the background).
    """

    cleaned = ndimage.binary_dilation(
        ndimage.binary_erosion(raw, structure=SQUARE, border_value=1),
        structure=SQUARE,
    )
    cleaned = ndimage.binary_erosion(
        ndimage.binary_dilation(cleaned, structure=SQUARE),
        structure=SQUARE,
        border_value=1,
    ) & valid

    labels, count = ndimage.label(cleaned, structure=SQUARE)
    areas = np.bincount(labels.ravel(), minlength=count + 1)

    if count:
        too_small = np.flatnonzero(areas < min_region_px)
        too_small = too_small[too_small != 0]

        if too_small.size:
            cleaned[np.isin(labels, too_small)] = False
            labels, count = ndimage.label(cleaned, structure=SQUARE)
            areas = np.bincount(labels.ravel(), minlength=count + 1)

    return cleaned, labels, count, areas
