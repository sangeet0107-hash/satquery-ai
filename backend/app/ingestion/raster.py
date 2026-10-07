import numpy as np
import rasterio
from PIL import Image


def inspect_raster(file_path: str):
    with rasterio.open(file_path) as dataset:
        return {
            "width": dataset.width,
            "height": dataset.height,
            "bands": dataset.count,
            "crs": str(dataset.crs),
            "dtype": dataset.dtypes[0],
            "bounds": {
                "left": dataset.bounds.left,
                "bottom": dataset.bounds.bottom,
                "right": dataset.bounds.right,
                "top": dataset.bounds.top,
            },
        }


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


def load_rgb_image(file_path: str) -> Image.Image:
    """
    Load a GeoTIFF as an 8-bit RGB PIL image.

    Rasters with 3+ bands use bands 1-3 as R, G, B. Single-band
    rasters (for example SAR backscatter) are shown as greyscale.
    This is the single place where rasters become model/preview
    input, so previews and specialist models always see the same image.
    """

    with rasterio.open(file_path) as dataset:
        if dataset.count >= 3:
            data = dataset.read([1, 2, 3])
            array = np.stack(
                [_stretch_to_uint8(band) for band in data],
                axis=-1,
            )
        else:
            band = _stretch_to_uint8(dataset.read(1))
            array = np.stack([band, band, band], axis=-1)

    return Image.fromarray(array, mode="RGB")


def create_preview(file_path: str, output_path: str):
    image = load_rgb_image(file_path)
    image.thumbnail((1200, 1200))
    image.save(output_path)
