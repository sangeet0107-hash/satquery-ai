from datetime import datetime, timezone

import numpy as np
from PIL import Image

from backend.app.analysis.overlay import render_overlay
from backend.app.ingestion.info import geographic_pixel_area_m2
from backend.app.models.query import (
    AnalyzeRequest,
    AnalyzeResponse,
    Evidence,
    ExecutionStep,
    TaskType,
)
from backend.app.reporting.report import build_report_html
from backend.app.reporting.store import AnalysisRecord, load_analysis, save_analysis


def grey(width=600, height=400):
    return Image.fromarray(np.full((height, width, 3), 90, dtype="uint8"))


def test_overlay_tints_masked_pixels_only():
    mask = np.zeros((400, 600), dtype=bool)
    mask[100:200, 300:400] = True

    out = render_overlay(grey(), mask=mask)

    assert out.size == (600, 400)
    red, green, blue = out.getpixel((350, 150))
    assert red > green and red > blue
    assert out.getpixel((10, 10)) == (90, 90, 90)


def test_overlay_scales_large_images_and_box_coordinates():
    out = render_overlay(
        grey(6000, 3000),
        boxes=[((3000, 1000, 4000, 2000), None)],
        max_side=1200,
    )

    assert out.size == (1200, 600)
    # Box edge lands at source x=3000 -> overlay x=600.
    assert out.getpixel((600, 300)) != (90, 90, 90)
    assert out.getpixel((100, 100)) == (90, 90, 90)


def test_overlay_accepts_low_resolution_mask_and_separate_source_size():
    mask = np.zeros((40, 60), dtype=bool)
    mask[10:20, 30:40] = True

    out = render_overlay(
        grey(),
        boxes=[((3000, 1000, 4000, 2000), "region")],
        mask=mask,
        source_size=(6000, 4000),
    )

    assert out.getpixel((350, 150)) != (90, 90, 90)


def test_geographic_pixel_area_shrinks_with_latitude():
    equator = geographic_pixel_area_m2(0.0001, 0.0001, 0)
    assert 123 < equator < 125
    assert abs(geographic_pixel_area_m2(0.0001, 0.0001, 60) - equator / 2) < 0.5


def make_response(**overrides):
    values = dict(
        query="Where are the <b>ships</b>?",
        task=TaskType.GROUNDING,
        answer="Found 1 x 'ship'.",
        confidence=0.42,
        execution_trace=[
            ExecutionStep(step="Query received", status="complete"),
            ExecutionStep(
                step="Model run",
                status="complete",
                tool="some-model",
                params={"score_threshold": 0.1},
            ),
            ExecutionStep(step="Warning - <script>x</script>", status="warning"),
        ],
        evidence=[
            Evidence(kind="bbox", label="ship", bbox=[1, 2, 30, 40], score=0.42)
        ],
    )
    values.update(overrides)
    return AnalyzeResponse(**values)


def test_store_round_trip_and_id_validation(tmp_path):
    request = AnalyzeRequest(query="q", image_id="a.tif", image_id_2="b.tif")
    response = make_response()

    record = save_analysis(request, response, directory=str(tmp_path))

    assert response.analysis_id == record.analysis_id
    assert len(record.analysis_id) == 32

    loaded = load_analysis(record.analysis_id, directory=str(tmp_path))

    assert loaded.image_id == "a.tif" and loaded.image_id_2 == "b.tif"
    assert loaded.response.evidence[0].label == "ship"

    assert load_analysis("0" * 32, directory=str(tmp_path)) is None
    assert load_analysis("../../etc/passwd", directory=str(tmp_path)) is None
    assert load_analysis("", directory=str(tmp_path)) is None


def test_report_contains_answer_trace_evidence_and_escapes_user_text():
    record = AnalysisRecord(
        analysis_id="a" * 32,
        created_at=datetime(2026, 10, 7, 6, 0, tzinfo=timezone.utc),
        image_id="scene.tif",
        response=make_response(),
    )

    html = build_report_html(record, overlay_png=b"\x89PNG fake")

    assert "Found 1 x &#x27;ship&#x27;." in html
    assert "2026-10-07 06:00 UTC" in html
    assert "scene.tif" in html
    assert "some-model" in html and "score_threshold" in html
    assert "data:image/png;base64," in html
    assert "1, 2, 30, 40" in html and "42%" in html

    # Nothing the user typed may reach the page as live markup.
    assert "<b>ships</b>" not in html and "&lt;b&gt;ships&lt;/b&gt;" in html
    assert "<script>" not in html


def test_report_without_images_or_evidence_still_builds():
    record = AnalysisRecord(
        analysis_id="b" * 32,
        created_at=datetime(2026, 10, 7, tzinfo=timezone.utc),
        response=make_response(evidence=[]),
    )

    html = build_report_html(record)

    assert "Visual evidence" not in html and "Evidence items" not in html
    assert "Execution trace" in html
