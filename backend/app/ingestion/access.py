"""
File access used by specialist tools.

Specialists never touch rasterio or the uploads folder directly; they go
through a RasterAccess. Tests substitute an in-memory implementation, so
specialist logic can be exercised without real GeoTIFFs.
"""

import os

import numpy as np
from PIL import Image

from backend.app.ingestion.store import UPLOAD_DIR, resolve_upload_path


class RasterAccess:
    def resolve(self, image_id: str | None) -> str | None:
        return resolve_upload_path(image_id)

    def load_array(
        self,
        path: str,
        max_side: int | None = 4096,
    ) -> tuple[np.ndarray, tuple[float, float]]:
        from backend.app.ingestion.raster import load_array

        return load_array(path, max_side=max_side)

    def load_rgb(self, path: str, max_side: int | None = None) -> Image.Image:
        from backend.app.ingestion.raster import load_rgb_image

        return load_rgb_image(path, max_side=max_side)

    def pixel_area_m2(self, path: str) -> float | None:
        from backend.app.ingestion.raster import pixel_area_m2

        return pixel_area_m2(path)

    def save_png(self, image: Image.Image, filename: str) -> str:
        """Save into uploads/ and return the name GET /preview serves it under."""

        os.makedirs(UPLOAD_DIR, exist_ok=True)
        filename = os.path.basename(filename)
        image.save(os.path.join(UPLOAD_DIR, filename))

        return filename
