import pytest
from PIL import Image

from backend.app.analysis.grounding import (
    PROMPT_TEMPLATE,
    Detection,
    extract_target_phrases,
    ground,
    non_max_suppression,
    tile_windows,
)


@pytest.mark.parametrize(
    "query,expected",
    [
        ("Where are the ships located?", ["ship"]),
        ("Locate all aircraft and vehicles in the image", ["aircraft", "vehicle"]),
        ("Show me the bounding boxes of the storage tanks", ["storage tank"]),
        ("Find the bridge", ["bridge"]),
        ("Can you point out the buses?", ["bus"]),
        ("Locate the glass houses", ["glass house"]),
        ("Mark buildings near the river", ["building near the river"]),
        ("detect ships, planes and trucks", ["ship", "plane", "truck"]),
        ("Give me the coordinates of the helipad in this scene", ["helipad"]),
        ("where is it", []),
        ("find", []),
        ("", []),
    ],
)
def test_extract_target_phrases(query, expected):
    assert extract_target_phrases(query) == expected


def test_small_image_is_a_single_window():
    assert tile_windows(800, 600) == [(0, 0, 800, 600)]


@pytest.mark.parametrize("size", [(3000, 2000), (2000, 700), (20000, 20000), (769, 5000)])
def test_tiles_cover_the_whole_image_within_the_limit(size):
    width, height = size
    windows = tile_windows(width, height, max_tiles=16)

    assert len(windows) <= 16
    assert all(0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height for x0, y0, x1, y1 in windows)

    # Every corner and the centre are inside some window, and the windows
    # reach all four edges.
    assert min(w[0] for w in windows) == 0 and min(w[1] for w in windows) == 0
    assert max(w[2] for w in windows) == width and max(w[3] for w in windows) == height

    xs = sorted({(w[0], w[2]) for w in windows})
    ys = sorted({(w[1], w[3]) for w in windows})

    for spans in (xs, ys):
        for (_, end), (start, _) in zip(spans, spans[1:]):
            assert start <= end  # no gaps between neighbouring tiles


def test_nms_keeps_best_of_overlapping_same_label_boxes():
    boxes = [
        Detection("ship", 0.9, (10, 10, 50, 50)),
        Detection("ship", 0.6, (12, 12, 52, 52)),
        Detection("ship", 0.5, (200, 200, 240, 240)),
        Detection("plane", 0.4, (11, 11, 51, 51)),
    ]

    kept = non_max_suppression(boxes)

    assert [(d.label, d.score) for d in kept] == [
        ("ship", 0.9),
        ("ship", 0.5),
        ("plane", 0.4),
    ]


def test_ground_maps_tile_boxes_to_full_image_and_merges_duplicates():
    image = Image.new("RGB", (2000, 700))
    target = (700.0, 100.0, 740.0, 140.0)  # lies in the overlap of tiles 1 and 2
    calls = []

    def fake_detector(tile, labels, threshold):
        calls.append(tile.size)
        assert labels == [PROMPT_TEMPLATE.format("ship")]
        origin_x = [0, 672, 1232][len(calls) - 1]
        x0, y0, x1, y1 = target

        if origin_x <= x0 and x1 <= origin_x + tile.size[0]:
            return [
                {
                    "label": labels[0],
                    "score": 0.5 + 0.1 * len(calls),
                    "box": [x0 - origin_x, y0, x1 - origin_x, y1],
                }
            ]

        return []

    detections, tiles = ground(image, ["ship"], fake_detector)

    assert tiles == 3 and len(calls) == 3
    assert len(detections) == 1
    assert detections[0].label == "ship"
    assert detections[0].bbox == target
    assert detections[0].score == pytest.approx(0.7)


def test_ground_drops_low_scores_degenerate_boxes_and_clips_to_image():
    image = Image.new("RGB", (400, 300))

    def fake_detector(tile, labels, threshold):
        return [
            {"label": labels[0], "score": 0.05, "box": [10, 10, 60, 60]},
            {"label": labels[0], "score": 0.8, "box": [100, 100, 100.2, 150]},
            {"label": labels[0], "score": 0.7, "box": [350, 250, 500, 400]},
        ]

    detections, _ = ground(image, ["tank"], fake_detector, score_threshold=0.1)

    assert [d.bbox for d in detections] == [(350.0, 250.0, 400.0, 300.0)]


def test_ground_respects_max_detections_and_orders_by_score():
    image = Image.new("RGB", (400, 300))

    def fake_detector(tile, labels, threshold):
        return [
            {"label": labels[0], "score": 0.2 + i * 0.1, "box": [i * 60, 0, i * 60 + 40, 40]}
            for i in range(5)
        ]

    detections, _ = ground(image, ["car"], fake_detector, max_detections=3)

    assert [round(d.score, 1) for d in detections] == [0.6, 0.5, 0.4]
