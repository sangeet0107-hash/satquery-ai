import os

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling

from backend.app.ingestion.info import (
    Bounds,
    RasterInfo,
    detect_modality,
    geographic_pixel_area_m2,
    parse_acquisition_date,
)


def read_raster_info(file_path: str, image_id: str | None = None) -> RasterInfo:
    """Parse a GeoTIFF into a RasterInfo (deterministic; no model involved)."""

    filename = os.path.basename(file_path)

    with rasterio.open(file_path) as dataset:
        tags = {str(k): str(v) for k, v in dataset.tags().items()}
        descriptions = [d for d in (dataset.descriptions or ()) if d]

        hint_text = " ".join(
            [filename, *tags.keys(), *tags.values(), *descriptions]
        )

        modality, confidence, reason = detect_modality(
            band_count=dataset.count,
            dtype=dataset.dtypes[0],
            hint_text=hint_text,
        )

        acquired, source = parse_acquisition_date(tags, filename)

        return RasterInfo(
            image_id=image_id or filename,
            width=dataset.width,
            height=dataset.height,
            bands=dataset.count,
            dtype=dataset.dtypes[0],
            crs=str(dataset.crs) if dataset.crs else None,
            bounds=Bounds(
                left=dataset.bounds.left,
                bottom=dataset.bounds.bottom,
                right=dataset.bounds.right,
                top=dataset.bounds.top,
            ),
            pixel_size=(abs(dataset.res[0]), abs(dataset.res[1])),
            modality=modality,
            modality_confidence=confidence,
            modality_reason=reason,
            acquisition_date=acquired,
            acquisition_source=source,
        )


def inspect_raster(file_path: str):
    """
    API-facing metadata. Original keys are unchanged (the frontend reads
    them); ingestion results are added alongside as plain values.
    """

    info = read_raster_info(file_path)

    return {
        "width": info.width,
        "height": info.height,
        "bands": info.bands,
        "crs": str(info.crs),
        "dtype": info.dtype,
        "bounds": {
            "left": info.bounds.left,
            "bottom": info.bounds.bottom,
            "right": info.bounds.right,
            "top": info.bounds.top,
        },
        "modality": info.modality.value,
        "modality_confidence": info.modality_confidence,
        "modality_reason": info.modality_reason,
        "pixel_size": list(info.pixel_size) if info.pixel_size else None,
        "acquisition_date": (
            info.acquisition_date.isoformat() if info.acquisition_date else None
        ),
        "acquisition_source": info.acquisition_source,
    }


def _decimated_shape(dataset, max_side: int | None) -> tuple[int, int] | None:
    """(height, width) to read at so the longest side is <= max_side."""

    longest = max(dataset.width, dataset.height)

    if not max_side or longest <= max_side:
        return None

    ratio = max_side / longest

    return (
        max(1, round(dataset.height * ratio)),
        max(1, round(dataset.width * ratio)),
    )


def load_array(
    file_path: str,
    max_side: int | None = 4096,
) -> tuple[np.ndarray, tuple[float, float]]:
    """
    Read all bands as float32 shaped (bands, height, width); nodata -> NaN.

    Very large rasters are read at reduced resolution. The second return
    value is (scale_x, scale_y): multiply array pixel coordinates by it to
    get source-image pixel coordinates.
    """

    with rasterio.open(file_path) as dataset:
        shape = _decimated_shape(dataset, max_side)

        if shape is None:
            data = dataset.read(masked=True)
            scale = (1.0, 1.0)
        else:
            data = dataset.read(
                out_shape=(dataset.count, shape[0], shape[1]),
                resampling=Resampling.average,
                masked=True,
            )
            scale = (dataset.width / shape[1], dataset.height / shape[0])

    return data.astype("float32").filled(np.nan), scale


def pixel_area_m2(file_path: str) -> float | None:
    """Ground area of one pixel in square metres; None if not georeferenced."""

    with rasterio.open(file_path) as dataset:
        if dataset.crs is None:
            return None

        res_x, res_y = abs(dataset.res[0]), abs(dataset.res[1])

        if dataset.crs.is_geographic:
            latitude = (dataset.bounds.top + dataset.bounds.bottom) / 2
            return geographic_pixel_area_m2(res_x, res_y, latitude)

        try:
            factor = float(dataset.crs.linear_units_factor[1])
        except Exception:
            factor = 1.0

        return res_x * res_y * factor * factor


def _stretch_to_uint8(band: np.ndarray) -> np.ndarray:
    """Percentile (2-98) contrast stretch of one band to uint8."""

    band = band.astype("float32")
    valid = np.isfinite(band)

    if not np.any(valid):
        return np.zeros(band.shape, dtype="uint8")

    low, high = np.percentile(band[valid], (2, 98))

    if high <= low:
        return np.zeros(band.shape, dtype="uint8")

    scaled = np.clip((band - low) / (high - low), 0, 1)
    scaled = np.nan_to_num(scaled, nan=0.0)

    return (scaled * 255).astype("uint8")


def load_rgb_image(file_path: str, max_side: int | None = None) -> Image.Image:
    """
    Load a GeoTIFF as an 8-bit RGB PIL image.

    Rasters with 3+ bands use bands 1-3 as R, G, B. Single-band
    rasters (for example SAR backscatter) are shown as greyscale.
    This is the single place where rasters become model/preview
    input, so previews and specialist models always see the same image.

    max_side reads a reduced-resolution copy (longest side <= max_side),
    which keeps overlays of very large scenes cheap.
    """

    with rasterio.open(file_path) as dataset:
        indexes = [1, 2, 3] if dataset.count >= 3 else [1]
        shape = _decimated_shape(dataset, max_side)

        if shape is None:
            data = dataset.read(indexes)
        else:
            data = dataset.read(
                indexes,
                out_shape=(len(indexes), shape[0], shape[1]),
                resampling=Resampling.average,
            )

    bands = [_stretch_to_uint8(band) for band in data]

    if len(bands) == 1:
        bands = bands * 3

    return Image.fromarray(np.stack(bands, axis=-1))


def create_preview(file_path: str, output_path: str):
    image = load_rgb_image(file_path)
    image.thumbnail((1200, 1200))
    image.save(output_path)
