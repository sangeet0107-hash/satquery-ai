import re

from backend.app.models.query import TaskType


VQA_KEYWORDS = [
    "what",
    "which",
    "describe",
    "identify",
    "visible",
    "see",
    "image",
    "scene",
    "objects",
    "building",
    "road",
    "vehicle",
    "car",
    "truck",
    "ship",
    "aircraft",
    "land",
    "water",
]


GROUNDING_KEYWORDS = [
    "where",
    "locate",
    "location",
    "point",
    "mark",
    "highlight",
    "bounding box",
    "bounding boxes",
    "coordinates",
    "find the",
]


CHANGE_KEYWORDS = [
    "change",
    "changed",
    "difference",
    "differences",
    "before and after",
    "compare",
    "comparison",
    "construction",
    "new building",
    "new road",
    "demolished",
    "growth",
    "loss",
]


SAR_KEYWORDS = [
    "sar",
    "synthetic aperture radar",
    "radar",
    "optical and sar",
    "sar and optical",
    "radar image",
    "sar image",
    "fusion",
    "fuse",
]


def _contains_keyword(query: str, keywords: list[str]) -> bool:
    query = query.lower()

    for keyword in keywords:
        if " " in keyword:
            if keyword in query:
                return True
        else:
            pattern = rf"\b{re.escape(keyword)}\b"

            if re.search(pattern, query):
                return True

    return False


def classify_query(query: str) -> TaskType:
    """
    Classify a natural-language satellite query.

    This is intentionally a lightweight rule-based classifier
    for the first controller milestone.

    Later this can be replaced with an ML/LLM classifier
    without changing the rest of the architecture.
    """

    normalized_query = query.strip().lower()

    if not normalized_query:
        return TaskType.UNKNOWN

    # SAR gets priority because queries may also contain
    # generic words such as "compare" or "image".
    if _contains_keyword(normalized_query, SAR_KEYWORDS):
        return TaskType.SAR

    if _contains_keyword(normalized_query, CHANGE_KEYWORDS):
        return TaskType.CHANGE

    if _contains_keyword(normalized_query, GROUNDING_KEYWORDS):
        return TaskType.GROUNDING

    if _contains_keyword(normalized_query, VQA_KEYWORDS):
        return TaskType.VQA

    return TaskType.UNKNOWN