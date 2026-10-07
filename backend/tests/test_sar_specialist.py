import numpy as np
import pytest
from PIL import Image
from pydantic import ValidationError

from backend.app.controller.preflight import run_preflight
from backend.app.controller.registry import get_tool
from backend.app.ingestion.info import Modality, check_pair
from backend.app.models.params import SARParams
from backend.app.models.query import TaskType
from backend.app.specialists.sar import run_sar
from backend.tests.helpers import FakeAccess, make_info
from backend.tests.test_sar_analysis import lake_scene, land, optical_with_dark_block, speckle

SAR = make_info(Modality.SAR, bands=1, width=400, height=400)
OPTICAL = make_info(Modality.OPTICAL, bands=4, width=400, height=400)


def sar_array(mean=None):
    return speckle(lake_scene() if mean is None else mean)[np.newaxis, ...]


def test_water_query_returns_mask_area_caveat_and_overlay(tmp_path):
    access = FakeAccess(
        {"s1_vv.tif": sar_array()}, tmp_path, pixel_area=100.0, infos={"s1_vv.tif": SAR}
    )

    result = run_sar("Where is the water in this SAR image?", "s1_vv.tif", access=access)

    assert result.answer.startswith("Low-backscatter (water-like) surfaces cover 25.0%")
    assert "sq. km" in result.answer          # 40,000 px x 100 sq. m = 4 sq. km
    assert "tarmac" in result.answer          # the caveat is always shown
    assert "bright" not in result.answer      # only what was asked

    assert result.evidence[0].kind == "mask"
    assert (tmp_path / result.evidence[0].mask_ref).exists()
    assert result.overlay and (tmp_path / result.overlay).exists()

    mask = np.asarray(Image.open(tmp_path / result.evidence[0].mask_ref))
    assert mask[200, 150] == 255 and mask[20, 20] == 0

    assert 0.5 < result.confidence <= 0.95
    assert result.trace[0].params == {"intent": "water"}
    assert any(step.params and step.params.get("filter") == "Lee" for step in result.trace)


def test_target_query_lists_targets_first(tmp_path):
    access = FakeAccess({"s1_vv.tif": sar_array()}, tmp_path, infos={"s1_vv.tif": SAR})

    result = run_sar("Detect ships in the radar image", "s1_vv.tif", access=access)

    assert result.answer.startswith("Found 3 bright targets")
    assert "dB above its surroundings" in result.answer
    assert [e.kind for e in result.evidence[:3]] == ["bbox", "bbox", "bbox"]
    assert all(e.label.startswith("bright target") for e in result.evidence[:3])


def test_summary_covers_statistics_water_and_targets(tmp_path):
    access = FakeAccess({"s1_vv.tif": sar_array()}, tmp_path, infos={"s1_vv.tif": SAR})

    result = run_sar("Analyse this SAR image", "s1_vv.tif", access=access)

    assert "median of" in result.answer and "relative unless" in result.answer
    assert "Low-backscatter" in result.answer and "Found 3 bright targets" in result.answer


def test_featureless_scene_reports_nothing_and_has_no_overlay(tmp_path):
    access = FakeAccess(
        {"s1_vv.tif": sar_array(land())}, tmp_path, infos={"s1_vv.tif": SAR}
    )

    result = run_sar("Analyse this SAR image", "s1_vv.tif", access=access)

    assert "No distinct low-backscatter" in result.answer
    assert "No bright point targets" in result.answer
    assert result.evidence == [] and result.overlay is None


def test_fusion_uses_the_optical_image_whichever_order_they_arrive_in(tmp_path):
    optical = optical_with_dark_block(4, slice(100, 300), slice(50, 200))
    access = FakeAccess(
        {"s1_vv.tif": sar_array(), "s2.tif": optical},
        tmp_path,
        infos={"s1_vv.tif": SAR, "s2.tif": OPTICAL},
    )

    for first, second in (("s1_vv.tif", "s2.tif"), ("s2.tif", "s1_vv.tif")):
        result = run_sar("Fuse the optical and SAR data", first, second, access=access)

        assert result.answer.startswith("Cross-check with the optical image (band 4")
        assert "75% of the SAR low-backscatter area is also dark" in result.answer
        assert "blue is dark in both" in result.answer

        fusion_step = [s for s in result.trace if s.step.startswith("Optical-SAR fusion")][0]
        assert fusion_step.step.endswith("s2.tif")
        assert fusion_step.params["agreement_iou"] == pytest.approx(0.75, abs=0.01)

    # The overlay is drawn on the optical image, with three mask colours.
    overlay = np.asarray(Image.open(tmp_path / result.overlay)).astype(int)
    both, sar_only, outside = overlay[200, 100], overlay[200, 230], overlay[20, 20]
    assert both[2] > both[0]            # blue tint
    assert sar_only[0] > sar_only[2]    # orange tint
    assert abs(int(outside[0]) - int(outside[2])) < 3   # untinted grey


def test_fusion_request_without_optical_image_says_so(tmp_path):
    access = FakeAccess({"s1_vv.tif": sar_array()}, tmp_path, infos={"s1_vv.tif": SAR})

    result = run_sar("Fuse the optical and SAR data", "s1_vv.tif", access=access)

    assert result.answer.startswith("No optical image was supplied")


def test_fusion_is_skipped_with_a_warning_when_grids_differ(tmp_path):
    access = FakeAccess(
        {"s1_vv.tif": sar_array(), "s2.tif": np.zeros((4, 100, 100))},
        tmp_path,
        infos={"s1_vv.tif": SAR, "s2.tif": OPTICAL},
    )

    result = run_sar("Fuse the optical and SAR data", "s1_vv.tif", "s2.tif", access=access)

    assert "could not be combined" in result.answer
    assert "Low-backscatter" in result.answer   # SAR-only analysis still delivered
    assert any(s.status == "warning" and "fusion skipped" in s.step for s in result.trace)


def test_image_selection_problems_are_explained(tmp_path):
    arrays = {"a.tif": sar_array(), "b.tif": sar_array()}

    two_optical = FakeAccess(arrays, tmp_path, infos={"a.tif": OPTICAL, "b.tif": OPTICAL})
    assert "Neither uploaded image looks like SAR" in run_sar(
        "Analyse this SAR image", "a.tif", "b.tif", access=two_optical
    ).answer

    one_optical = FakeAccess(arrays, tmp_path, infos={"a.tif": OPTICAL})
    assert "is optical" in run_sar("Analyse this SAR image", "a.tif", access=one_optical).answer

    two_sar = FakeAccess(arrays, tmp_path, infos={"a.tif": SAR, "b.tif": SAR})
    result = run_sar("Analyse this SAR image", "a.tif", "b.tif", access=two_sar)
    assert any("Both images are SAR" in s.step for s in result.trace)
    assert "Low-backscatter" in result.answer

    missing = FakeAccess(arrays, tmp_path)
    assert "could not locate" in run_sar("Analyse this SAR image", "nope.tif", access=missing).answer


def test_ambiguous_single_band_image_is_assumed_sar_with_a_warning(tmp_path):
    optical = optical_with_dark_block(4, slice(100, 300), slice(50, 200))
    access = FakeAccess(
        {"pan.tif": sar_array(), "s2.tif": optical},
        tmp_path,
        infos={
            "pan.tif": make_info(Modality.SINGLE_BAND, bands=1, width=400, height=400),
            "s2.tif": OPTICAL,
        },
    )

    result = run_sar("Fuse the optical and SAR data", "s2.tif", "pan.tif", access=access)

    assert any(
        s.status == "warning" and "assumed to be the SAR image" in s.step
        for s in result.trace
    )
    assert "Cross-check with the optical image" in result.answer


def test_boxes_are_mapped_back_to_source_pixels(tmp_path):
    access = FakeAccess(
        {"s1_vv.tif": sar_array()}, tmp_path, scale=(2.0, 2.0), infos={"s1_vv.tif": SAR}
    )

    result = run_sar("Where is the water in this SAR image?", "s1_vv.tif", access=access)
    region = [e for e in result.evidence if e.label.startswith("low-backscatter region")][0]

    assert abs(region.bbox[0] - 100) <= 4 and abs(region.bbox[2] - 500) <= 4
    assert abs(region.bbox[1] - 200) <= 4 and abs(region.bbox[3] - 600) <= 4


def test_sar_params_are_validated_by_the_registry():
    tool = get_tool(TaskType.SAR)

    assert isinstance(tool.build_params(), SARParams)
    assert tool.build_params({"speckle_window": 7}).speckle_window == 7

    with pytest.raises(ValidationError):
        tool.build_params({"speckle_window": 6})

    with pytest.raises(ValidationError):
        tool.build_params({"cfar_k": 1})


def test_preflight_blocks_sar_query_on_two_optical_images():
    result = run_preflight(
        TaskType.SAR, "a", "b", OPTICAL, OPTICAL, check_pair(OPTICAL, OPTICAL)
    )
    assert not result.ok and "both uploaded images are optical" in result.blockers[0]

    mixed = run_preflight(TaskType.SAR, "a", "b", SAR, OPTICAL, check_pair(SAR, OPTICAL))
    assert mixed.ok
