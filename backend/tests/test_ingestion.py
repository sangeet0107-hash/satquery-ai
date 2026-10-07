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


def _write_grid(path, width, height, count=3, crs="EPSG:4326", res=0.0001, fill=None):
    data = (
        np.full((count, height, width), fill, dtype="uint16")
        if fill is not None
        else np.random.randint(0, 3000, (count, height, width)).astype("uint16")
    )
    profile = dict(
        driver="GTiff", height=height, width=width, count=count, dtype="uint16",
        transform=from_origin(77.0, 0.003, res, res),
    )
    if crs:
        profile["crs"] = crs
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data)


def test_load_array_returns_float_bands_and_unit_scale(tmp_path):
    from backend.app.ingestion.raster import load_array

    p = str(tmp_path / "a.tif")
    _write_grid(p, 100, 60, fill=7)

    array, scale = load_array(p)

    assert array.shape == (3, 60, 100) and array.dtype == np.float32
    assert scale == (1.0, 1.0)
    assert float(array.mean()) == 7.0


def test_load_array_decimates_large_rasters_and_reports_scale(tmp_path):
    from backend.app.ingestion.raster import load_array

    p = str(tmp_path / "a.tif")
    _write_grid(p, 100, 60)

    array, scale = load_array(p, max_side=50)

    assert array.shape == (3, 30, 50)
    assert scale == (2.0, 2.0)


def test_load_rgb_image_max_side(tmp_path):
    p = str(tmp_path / "a.tif")
    _write_grid(p, 100, 60)

    assert load_rgb_image(p).size == (100, 60)
    assert load_rgb_image(p, max_side=50).size == (50, 30)


def test_pixel_area_for_projected_geographic_and_missing_crs(tmp_path):
    from backend.app.ingestion.raster import pixel_area_m2

    utm = str(tmp_path / "utm.tif")
    _write_grid(utm, 10, 10, crs="EPSG:32643", res=10)
    assert pixel_area_m2(utm) == 100.0

    geo = str(tmp_path / "geo.tif")
    _write_grid(geo, 10, 10, crs="EPSG:4326", res=0.0001)
    assert 123 < pixel_area_m2(geo) < 125  # ~11.1 m square at the equator

    bare = str(tmp_path / "bare.tif")
    _write_grid(bare, 10, 10, crs=None, res=1)
    assert pixel_area_m2(bare) is None
