from backend.app.controller.controller import analyze_query
from backend.app.models.query import AnalyzeRequest, TaskType


def test_unknown_query_returns_trace_and_empty_evidence():
    r = analyze_query(AnalyzeRequest(query="zzz qqq"))
    assert r.task == TaskType.UNKNOWN
    assert r.evidence == []
    assert r.execution_trace[0].step.startswith("Query received")


def test_change_without_second_image_is_low_confidence():
    r = analyze_query(AnalyzeRequest(query="what changed?", image_id="a.tif"))
    assert r.task == TaskType.CHANGE
    assert r.confidence < 0.5
