import numpy as np
import rasterio
from rasterio.transform import from_origin

from backend.app.ingestion.raster import (
    create_preview,
    inspect_raster,
    load_rgb_image,
)


def _write_tif(path, count):
    data = np.random.randint(0, 3000, (count, 32, 32)).astype("uint16")
    with rasterio.open(
        path, "w", driver="GTiff", height=32, width=32, count=count,
        dtype="uint16", crs="EPSG:4326",
        transform=from_origin(77.0, 28.0, 0.01, 0.01),
    ) as dst:
        dst.write(data)


def test_inspect_reports_bands(tmp_path):
    p = str(tmp_path / "a.tif")
    _write_tif(p, 4)
    meta = inspect_raster(p)
    assert meta["bands"] == 4 and meta["width"] == 32


def test_single_band_becomes_rgb(tmp_path):
    p = str(tmp_path / "sar.tif")
    _write_tif(p, 1)
    img = load_rgb_image(p)
    assert img.mode == "RGB" and img.size == (32, 32)


def test_preview_written(tmp_path):
    p = str(tmp_path / "o.tif")
    _write_tif(p, 3)
    out = str(tmp_path / "o.png")
    create_preview(p, out)
    assert (tmp_path / "o.png").exists()
