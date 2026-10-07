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


def test_read_raster_info_uses_tags_for_modality_and_date(tmp_path):
    from backend.app.ingestion.info import Modality
    from backend.app.ingestion.raster import read_raster_info

    p = str(tmp_path / "scene.tif")
    data = np.random.rand(1, 16, 16).astype("float32")

    with rasterio.open(
        p, "w", driver="GTiff", height=16, width=16, count=1,
        dtype="float32", crs="EPSG:4326",
        transform=from_origin(77.0, 28.0, 0.01, 0.01),
    ) as dst:
        dst.write(data)
        dst.update_tags(SENSOR="Sentinel-1 SAR", ACQUISITION_DATE="2024-03-05")

    info = read_raster_info(p)

    assert info.modality == Modality.SAR
    assert str(info.acquisition_date) == "2024-03-05"
    assert info.pixel_size == (0.01, 0.01)


def test_inspect_raster_keeps_frontend_keys(tmp_path):
    p = str(tmp_path / "a.tif")
    _write_tif(p, 3)
    meta = inspect_raster(p)

    for key in ("width", "height", "bands", "crs", "bounds"):
        assert key in meta

    assert meta["modality"] in {"OPTICAL", "SAR", "MULTISPECTRAL", "SINGLE_BAND"}
