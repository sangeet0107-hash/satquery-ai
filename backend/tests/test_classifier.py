import pytest

from backend.app.controller.classifier import classify_query
from backend.app.models.query import TaskType


@pytest.mark.parametrize(
    "query,expected",
    [
        ("What is visible in this image?", TaskType.VQA),
        ("Where are the ships located?", TaskType.GROUNDING),
        ("What changed between the two dates?", TaskType.CHANGE),
        ("Analyse this SAR image", TaskType.SAR),
        ("Fuse the optical and SAR data", TaskType.SAR),
        ("", TaskType.UNKNOWN),
        ("zzz qqq", TaskType.UNKNOWN),
    ],
)
def test_classify_query(query, expected):
    assert classify_query(query) == expected


def test_sar_takes_priority_over_change():
    assert classify_query("compare the SAR images") == TaskType.SAR
