"""
Model-independent logic for visual grounding:
  - working out which object(s) a question is asking to locate,
  - tiling large scenes so small objects survive the detector's resize,
  - merging duplicate boxes from overlapping tiles.

The detector itself is passed in as a function, so this module needs no
ML libraries and can be tested with a fake detector.
"""

import re
from dataclasses import dataclass
from typing import Callable

from PIL import Image

# detector(image, text_labels, score_threshold) ->
#   [{"label": str, "score": float, "box": [x_min, y_min, x_max, y_max]}]
Detector = Callable[[Image.Image, list[str], float], list[dict]]

PROMPT_TEMPLATE = "a photo of a {}"


@dataclass
class Detection:
    label: str
    score: float
    # [x_min, y_min, x_max, y_max] in pixels of the full image.
    bbox: tuple[float, float, float, float]


# --------------------------------------------------------------------------
# Query -> target phrases
# --------------------------------------------------------------------------

_LEAD_IN = re.compile(
    r"^(?:please\s+)?(?:can|could|would)?\s*(?:you\s+)?(?:please\s+)?"
    r"(?:where\s+(?:is|are|can\s+i\s+find)|locate|find|show(?:\s+me)?|"
    r"point\s+(?:to|out)|mark|highlight|detect|identify|outline|"
    r"draw|give(?:\s+me)?|get|what\s+(?:is|are))\s+",
)

_BOX_WORDS = re.compile(
    r"^(?:the\s+|a\s+)?(?:bounding\s+box(?:es)?|box(?:es)?|coordinates?|"
    r"locations?|positions?)\s+(?:of|for|around|on)\s+",
)

_TRAILING = re.compile(
    r"\s+(?:(?:is|are)\s+)?(?:located|situated|present|visible)$|"
    r"\s+(?:in|on|within|from)\s+(?:the|this|that)\s+"
    r"(?:image|scene|picture|photo|imagery|tile|area|map)$",
)

_ARTICLES = re.compile(r"^(?:all|any|every|each|the|a|an|some)\s+(?:of\s+the\s+)?")

_NOT_OBJECTS = {
    "", "it", "them", "this", "that", "these", "those", "there", "here",
    "image", "scene", "picture", "photo", "object", "thing", "something",
    "everything", "anything", "where", "find", "locate", "show", "mark",
    "highlight", "detect", "identify", "outline", "draw",
}


_IRREGULAR = {
    "buses": "bus",
    "gases": "gas",
    "people": "person",
    "men": "man",
    "women": "woman",
    "children": "child",
    "aircraft": "aircraft",
}

_PREPOSITIONS = {
    "near", "in", "on", "by", "at", "beside", "along", "around", "next",
    "inside", "outside", "between", "behind", "with", "of",
}


def _singular(word: str) -> str:
    if word in _IRREGULAR:
        return _IRREGULAR[word]

    if len(word) <= 3:
        return word

    if word.endswith("ies"):
        return word[:-3] + "y"

    if word.endswith(("sses", "xes", "zes", "ches", "shes")):
        return word[:-2]

    if word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]

    return word


def _singular_phrase(phrase: str) -> str:
    """Singularise the head noun: the word before any preposition, else the last."""

    words = phrase.split(" ")
    head = len(words) - 1

    for index, word in enumerate(words):
        if word in _PREPOSITIONS and index > 0:
            head = index - 1
            break

    words[head] = _singular(words[head])

    return " ".join(words)


def extract_target_phrases(query: str) -> list[str]:
    """
    'Where are the ships located?'            -> ['ship']
    'Locate all aircraft and vehicles'        -> ['aircraft', 'vehicle']
    'Show me the bounding boxes of the tanks' -> ['tank']
    Returns [] when no object could be identified.
    """

    text = re.sub(r"[?!.]+$", "", query.strip().lower())
    text = re.sub(r"\s+", " ", text)

    text = _LEAD_IN.sub("", text, count=1)
    text = _BOX_WORDS.sub("", text, count=1)

    # Trailing words can stack ("... in the image located").
    for _ in range(3):
        text = _TRAILING.sub("", text)

    phrases: list[str] = []

    for part in re.split(r"\s*,\s*|\s+and\s+|\s+or\s+|\s*&\s*", text):
        part = part.strip()

        for _ in range(2):
            part = _ARTICLES.sub("", part).strip()

        if part in _NOT_OBJECTS:
            continue

        phrase = _singular_phrase(part)

        if phrase and phrase not in _NOT_OBJECTS and phrase not in phrases:
            phrases.append(phrase)

    return phrases


# --------------------------------------------------------------------------
# Tiling
# --------------------------------------------------------------------------

def _starts(length: int, tile: int, overlap: int) -> list[int]:
    if length <= tile:
        return [0]

    step = max(1, tile - overlap)
    starts = list(range(0, length - tile, step))
    starts.append(length - tile)

    return starts


def tile_windows(
    width: int,
    height: int,
    tile_size: int = 768,
    overlap: int = 96,
    max_tiles: int = 16,
) -> list[tuple[int, int, int, int]]:
    """
    Windows (x0, y0, x1, y1) that together cover the whole image.

    Images not much larger than one tile are processed whole. If the image
    would need more than max_tiles, the tiles are enlarged until it fits,
    trading small-object recall for a bounded run time.
    """

    if max(width, height) <= int(tile_size * 1.25):
        return [(0, 0, width, height)]

    tile = tile_size

    while True:
        xs = _starts(width, tile, overlap)
        ys = _starts(height, tile, overlap)

        if len(xs) * len(ys) <= max_tiles:
            break

        tile = int(tile * 1.25) + 1

    return [
        (x, y, min(x + tile, width), min(y + tile, height))
        for y in ys
        for x in xs
    ]


# --------------------------------------------------------------------------
# Box merging
# --------------------------------------------------------------------------

def _iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter

    return inter / union if union > 0 else 0.0


def non_max_suppression(
    detections: list[Detection],
    iou_threshold: float = 0.5,
) -> list[Detection]:
    """Keep the highest-scoring box among same-label boxes that overlap."""

    kept: list[Detection] = []

    for candidate in sorted(detections, key=lambda d: d.score, reverse=True):
        if all(
            candidate.label != other.label
            or _iou(candidate.bbox, other.bbox) < iou_threshold
            for other in kept
        ):
            kept.append(candidate)

    return kept


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def ground(
    image: Image.Image,
    phrases: list[str],
    detector: Detector,
    score_threshold: float = 0.10,
    tile_size: int = 768,
    max_tiles: int = 16,
    max_detections: int = 50,
) -> tuple[list[Detection], int]:
    """Returns (detections sorted by score, number of tiles processed)."""

    prompts = {PROMPT_TEMPLATE.format(phrase): phrase for phrase in phrases}
    width, height = image.size
    windows = tile_windows(width, height, tile_size=tile_size, max_tiles=max_tiles)

    found: list[Detection] = []

    for x0, y0, x1, y1 in windows:
        tile = image if len(windows) == 1 else image.crop((x0, y0, x1, y1))

        for raw in detector(tile, list(prompts), score_threshold):
            score = float(raw["score"])

            if score < score_threshold:
                continue

            bx0, by0, bx1, by1 = (float(v) for v in raw["box"])

            box = (
                min(max(bx0 + x0, 0.0), width),
                min(max(by0 + y0, 0.0), height),
                min(max(bx1 + x0, 0.0), width),
                min(max(by1 + y0, 0.0), height),
            )

            if box[2] - box[0] < 1 or box[3] - box[1] < 1:
                continue

            found.append(
                Detection(
                    label=prompts.get(raw["label"], raw["label"]),
                    score=score,
                    bbox=box,
                )
            )

    kept = non_max_suppression(found)

    return kept[:max_detections], len(windows)
