import os

import numpy as np
from PIL import Image

from backend.app.controller import controller as controller_module
from backend.app.controller.controller import analyze_query
from backend.app.controller.registry import NoParams, ToolSpec, get_tool
from backend.app.ingestion.access import RasterAccess
from backend.app.models.params import ChangeParams, GroundingParams
from backend.app.models.query import (
    AnalyzeRequest,
    Evidence,
    SpecialistResult,
    TaskType,
    as_specialist_result,
)
from backend.app.specialists.change import run_change_detection
from backend.app.specialists.grounding import run_grounding


class FakeAccess(RasterAccess):
    """In-memory rasters; PNGs are written to a temp directory."""

    def __init__(self, arrays, out_dir, pixel_area=None, scale=(1.0, 1.0)):
        self.arrays = arrays
        self.out_dir = str(out_dir)
        self.pixel_area = pixel_area
        self.scale = scale

    def resolve(self, image_id):
        return image_id if image_id in self.arrays else None

    def load_array(self, path, max_side=4096):
        return self.arrays[path], self.scale

    def load_rgb(self, path, max_side=None):
        band = np.nan_to_num(self.arrays[path][0])
        band = np.clip(band, 0, 255).astype("uint8")
        return Image.fromarray(np.stack([band, band, band], axis=-1))

    def pixel_area_m2(self, path):
        return self.pixel_area

    def save_png(self, image, filename):
        image.save(os.path.join(self.out_dir, filename))
        return filename


def pair(size=200):
    rng = np.random.default_rng(0)
    before = rng.normal(100, 20, (3, size, size)).astype("float32")
    after = before.copy()
    after[:, 50:90, 120:170] += 120
    return before, after


# ---- change detection -------------------------------------------------------

def test_change_specialist_returns_mask_boxes_overlay_and_area(tmp_path):
    before, after = pair()
    access = FakeAccess({"t1.tif": before, "t2.tif": after}, tmp_path, pixel_area=100.0)

    result = run_change_detection("what changed?", "t1.tif", "t2.tif", access=access)

    assert "Detected 1 changed region covering 5.0% of the scene" in result.answer
    assert "20.00 hectares" in result.answer  # 2000 px x 100 sq. m
    assert "not what kind of change" in result.answer

    kinds = [item.kind for item in result.evidence]
    assert kinds == ["mask", "bbox"]
    assert result.evidence[1].bbox == [120, 50, 170, 90]

    assert result.overlay and (tmp_path / result.overlay).exists()
    assert (tmp_path / result.evidence[0].mask_ref).exists()

    mask = np.asarray(Image.open(tmp_path / result.evidence[0].mask_ref))
    assert mask.shape == (200, 200) and mask[60, 130] == 255 and mask[0, 0] == 0

    step = [s for s in result.trace if s.step == "Multi-temporal image comparison"][0]
    assert step.status == "complete"
    assert step.params["sensitivity"] == 3.0
    assert step.params["confidence_kind"] == "uncalibrated heuristic"


def test_change_specialist_reports_no_change(tmp_path):
    before, _ = pair()
    access = FakeAccess({"t1.tif": before, "t2.tif": before.copy()}, tmp_path)

    result = run_change_detection("what changed?", "t1.tif", "t2.tif", access=access)

    assert result.answer.startswith("No significant change")
    assert result.evidence == [] and result.overlay is None


def test_change_specialist_maps_boxes_back_to_source_pixels(tmp_path):
    before, after = pair()
    access = FakeAccess(
        {"t1.tif": before, "t2.tif": after}, tmp_path, pixel_area=1.0, scale=(4.0, 4.0)
    )

    result = run_change_detection("what changed?", "t1.tif", "t2.tif", access=access)

    assert result.evidence[1].bbox == [480, 200, 680, 360]
    assert "32,000 px" in result.answer  # 2000 analysed px x 16


def test_change_specialist_explains_missing_image_and_grid_mismatch(tmp_path):
    before, after = pair()
    access = FakeAccess({"t1.tif": before, "small.tif": after[:, :100, :100]}, tmp_path)

    missing = run_change_detection("q", "t1.tif", "nope.tif", access=access)
    assert "could not locate both" in missing.answer
    assert missing.trace[-1].status == "failed"

    mismatch = run_change_detection("q", "t1.tif", "small.tif", access=access)
    assert "different pixel grids" in mismatch.answer
    assert mismatch.confidence <= 0.1


def test_change_specialist_compares_common_bands_with_a_warning(tmp_path):
    before, after = pair()
    access = FakeAccess({"t1.tif": before, "t2.tif": after[:1]}, tmp_path)

    result = run_change_detection("q", "t1.tif", "t2.tif", access=access)

    assert any(s.status == "warning" and "band counts differ" in s.step for s in result.trace)
    assert "Detected 1 changed region" in result.answer


def test_change_params_are_validated_by_the_registry():
    tool = get_tool(TaskType.CHANGE)
    assert isinstance(tool.build_params(), ChangeParams)
    assert tool.build_params({"sensitivity": 5}).sensitivity == 5


# ---- grounding ---------------------------------------------------------------

def fake_detector(tile, labels, threshold):
    return [
        {"label": labels[0], "score": 0.62, "box": [20, 30, 60, 80]},
        {"label": labels[0], "score": 0.31, "box": [100, 100, 140, 130]},
    ]


def test_grounding_specialist_returns_boxes_overlay_and_scores(tmp_path):
    access = FakeAccess({"port.tif": np.full((3, 200, 300), 90.0)}, tmp_path)

    result = run_grounding(
        "Where are the ships located?", "port.tif", access=access, detector=fake_detector
    )

    assert "2 x 'ship' (scores 0.31-0.62)" in result.answer
    assert [e.bbox for e in result.evidence] == [[20, 30, 60, 80], [100, 100, 140, 130]]
    assert [e.score for e in result.evidence] == [0.62, 0.31]
    assert all(e.label == "ship" for e in result.evidence)
    assert abs(result.confidence - 0.465) < 0.006  # mean raw detector score
    assert (tmp_path / result.overlay).exists()

    overlay = Image.open(tmp_path / result.overlay)
    assert overlay.size == (300, 200)
    assert overlay.getpixel((20, 50)) != (90, 90, 90)


def test_grounding_specialist_handles_no_detection_and_unclear_query(tmp_path):
    access = FakeAccess({"port.tif": np.full((3, 200, 300), 90.0)}, tmp_path)

    nothing = run_grounding(
        "Where are the ships?", "port.tif", access=access, detector=lambda *a: []
    )
    assert nothing.answer.startswith("No 'ship' was detected")
    assert nothing.evidence == [] and nothing.overlay is None

    unclear = run_grounding("where is it", "port.tif", access=access, detector=fake_detector)
    assert "could not tell which object" in unclear.answer

    missing = run_grounding("Where are the ships?", "nope.tif", access=access, detector=fake_detector)
    assert "could not locate" in missing.answer


def test_grounding_specialist_reports_detector_failure(tmp_path):
    access = FakeAccess({"port.tif": np.full((3, 200, 300), 90.0)}, tmp_path)

    def broken(tile, labels, threshold):
        raise RuntimeError("model unavailable")

    result = run_grounding("Where are the ships?", "port.tif", access=access, detector=broken)

    assert "model unavailable" in result.answer
    assert result.trace[-1].status == "failed"


def test_grounding_passes_validated_params_to_the_detector(tmp_path):
    access = FakeAccess({"port.tif": np.full((3, 200, 300), 90.0)}, tmp_path)
    seen = {}

    def detector(tile, labels, threshold):
        seen["threshold"] = threshold
        return []

    run_grounding(
        "Find the bridge",
        "port.tif",
        params=GroundingParams(score_threshold=0.25),
        access=access,
        detector=detector,
    )

    assert seen["threshold"] == 0.25


# ---- controller --------------------------------------------------------------

def test_tuple_results_are_still_accepted():
    result = as_specialist_result(("answer", 0.5, []))
    assert isinstance(result, SpecialistResult) and result.evidence == []


def test_controller_passes_evidence_and_overlay_to_the_response(monkeypatch):
    spec = ToolSpec(
        name="fake",
        task=TaskType.VQA,
        description="",
        params_model=NoParams,
        runner=lambda q, a, b, p: SpecialistResult(
            answer="done",
            confidence=0.8,
            evidence=[Evidence(kind="bbox", label="x", bbox=[0, 0, 1, 1])],
            overlay="scene_evidence_abc.png",
        ),
    )
    monkeypatch.setattr(controller_module, "get_tool", lambda task: spec)

    response = analyze_query(
        AnalyzeRequest(query="What is visible in this image?", image_id="scene.tif")
    )

    assert response.answer == "done"
    assert response.overlay == "scene_evidence_abc.png"
    assert response.evidence[0].label == "x"
