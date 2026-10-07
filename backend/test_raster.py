import rasterio
import numpy as np
from rasterio.transform import from_origin

from backend.app.ingestion.raster import inspect_raster, create_preview


# Create a tiny 10x10 GeoTIFF
with rasterio.open(
    "test.tif",
    "w",
    driver="GTiff",
    height=10,
    width=10,
    count=1,
    dtype="uint16",
    crs="EPSG:4326",
    transform=from_origin(77.0, 28.0, 0.01, 0.01),
) as dataset:
    dataset.write(np.full((10, 10), 100, dtype="uint16"), 1)


# Inspect the GeoTIFF
metadata = inspect_raster("test.tif")

print(metadata)
create_preview("test.tif", "test_preview.png")

print("Preview created successfully")