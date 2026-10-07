"""Shared test doubles."""

import os

import numpy as np
from PIL import Image

from backend.app.ingestion.access import RasterAccess
from backend.app.ingestion.info import Bounds, Modality, RasterInfo


def make_info(modality=Modality.OPTICAL, bands=3, width=100, height=100, when=None):
    return RasterInfo(
        width=width,
        height=height,
        bands=bands,
        dtype="float32",
        crs="EPSG:4326",
        bounds=Bounds(left=77.0, bottom=27.0, right=78.0, top=28.0),
        pixel_size=(0.01, 0.01),
        modality=modality,
        modality_confidence="high",
        modality_reason="test",
        acquisition_date=when,
    )


class FakeAccess(RasterAccess):
    """In-memory rasters; PNGs are written to a temp directory."""

    def __init__(self, arrays, out_dir, pixel_area=None, scale=(1.0, 1.0), infos=None):
        self.arrays = arrays
        self.out_dir = str(out_dir)
        self.pixel_area = pixel_area
        self.scale = scale
        self.infos = infos or {}

    def resolve(self, image_id):
        return image_id if image_id in self.arrays else None

    def load_array(self, path, max_side=4096):
        return self.arrays[path], self.scale

    def load_rgb(self, path, max_side=None):
        band = np.nan_to_num(self.arrays[path][0])
        low, high = float(band.min()), float(band.max())
        if not 0 <= low <= high <= 255:
            band = (band - low) / (high - low + 1e-12) * 255
        band = np.clip(band, 0, 255).astype("uint8")
        return Image.fromarray(np.stack([band, band, band], axis=-1))

    def read_info(self, path):
        return self.infos.get(path)

    def pixel_area_m2(self, path):
        return self.pixel_area

    def save_png(self, image, filename):
        image.save(os.path.join(self.out_dir, filename))
        return filename
