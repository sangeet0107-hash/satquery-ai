from datetime import date

import pytest
from pydantic import ValidationError

from backend.app.controller.controller import analyze_query
from backend.app.controller.preflight import run_preflight
from backend.app.controller.registry import (
    NoParams,
    ToolSpec,
    get_tool,
    list_tools,
    register_tool,
)
from backend.app.ingestion.info import Bounds, Modality, RasterInfo, check_pair
from backend.app.models.query import AnalyzeRequest, TaskType

BOUNDS = Bounds(left=77.0, bottom=27.0, right=78.0, top=28.0)


def make_info(modality=Modality.OPTICAL, when=None, bounds=BOUNDS):
    return RasterInfo(
        width=100,
        height=100,
        bands=3,
        dtype="uint16",
        crs="EPSG:4326",
        bounds=bounds,
        pixel_size=(0.01, 0.01),
        modality=modality,
        modality_confidence="high",
        modality_reason="test",
        acquisition_date=when,
    )


def loader_for(mapping):
    return lambda image_id: mapping.get(image_id)


# ---- registry -------------------------------------------------------------

def test_every_task_has_a_registered_tool():
    assert {t.task for t in list_tools()} == set(TaskType)


def test_vqa_params_are_validated():
    tool = get_tool(TaskType.VQA)
    assert tool.build_params({"max_new_tokens": 50}).max_new_tokens == 50

    with pytest.raises(ValidationError):
        tool.build_params({"max_new_tokens": 5000})

    with pytest.raises(ValidationError):
        tool.build_params({"temperature": 2})  # not a permitted parameter


def test_duplicate_registration_rejected():
    spec = ToolSpec(
        name="dup",
        task=TaskType.VQA,
        description="",
        params_model=NoParams,
        runner=lambda q, a, b, p: ("", 0.0, []),
    )

    with pytest.raises(ValueError):
        register_tool(spec)


# ---- preflight -------------------------------------------------------------

def test_change_needs_two_images():
    result = run_preflight(TaskType.CHANGE, "a.tif", None, None, None, None)
    assert not result.ok


def test_vqa_without_image_is_blocked():
    assert not run_preflight(TaskType.VQA, None, None, None, None, None).ok


def test_sar_task_on_optical_image_is_blocked():
    result = run_preflight(
        TaskType.SAR, "a.tif", None, make_info(Modality.OPTICAL), None, None
    )
    assert not result.ok and "optical" in result.blockers[0]


def test_vqa_on_sar_image_warns_but_runs():
    result = run_preflight(
        TaskType.VQA, "a.tif", None, make_info(Modality.SAR), None, None
    )
    assert result.ok and result.warnings


def test_change_on_optical_sar_pair_is_blocked():
    a, b = make_info(Modality.OPTICAL), make_info(Modality.SAR)
    result = run_preflight(
        TaskType.CHANGE, "a", "b", a, b, check_pair(a, b)
    )
    assert not result.ok


def test_change_on_valid_bitemporal_pair_passes_cleanly():
    a = make_info(when=date(2023, 1, 1))
    b = make_info(when=date(2024, 1, 1))
    result = run_preflight(
        TaskType.CHANGE, "a", "b", a, b, check_pair(a, b)
    )
    assert result.ok and not result.warnings


# ---- controller wiring ------------------------------------------------------

def test_controller_blocks_and_explains_incompatible_request():
    loader = loader_for({"a.tif": make_info(Modality.OPTICAL)})
    response = analyze_query(
        AnalyzeRequest(query="Analyse this SAR image", image_id="a.tif"),
        info_loader=loader,
    )

    assert response.task == TaskType.SAR
    assert response.answer.startswith("I can't run SAR")
    assert response.confidence <= 0.1
    assert any(step.status == "blocked" for step in response.execution_trace)


def test_controller_records_tool_and_params_in_trace():
    response = analyze_query(AnalyzeRequest(query="zzz qqq"))
    selected = [s for s in response.execution_trace if s.step.startswith("Selected tool")]
    assert selected and selected[0].tool == "no-op"


def test_controller_routes_valid_change_request_to_specialist():
    a = make_info(when=date(2023, 1, 1))
    b = make_info(when=date(2024, 1, 1))
    response = analyze_query(
        AnalyzeRequest(
            query="What changed between the two dates?",
            image_id="a.tif",
            image_id_2="b.tif",
        ),
        info_loader=loader_for({"a.tif": a, "b.tif": b}),
    )

    assert response.task == TaskType.CHANGE
    steps = [s.step for s in response.execution_trace]
    assert any("BITEMPORAL" in s for s in steps)
    assert any("Change detection specialist" in s for s in steps)


def test_change_on_images_with_different_dimensions_is_blocked():
    a = make_info(when=date(2023, 1, 1))
    b = make_info(when=date(2024, 1, 1)).model_copy(update={"width": 50})

    result = run_preflight(TaskType.CHANGE, "a", "b", a, b, check_pair(a, b))

    assert not result.ok
    assert any("different pixel dimensions" in blocker for blocker in result.blockers)
