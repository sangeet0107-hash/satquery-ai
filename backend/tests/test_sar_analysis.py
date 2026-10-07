import numpy as np
import pytest

from backend.app.analysis.sar import (
    find_bright_targets,
    find_low_backscatter,
    fuse_with_optical,
    lee_filter,
    low_backscatter_confidence,
    prepare,
    sar_intent,
    target_confidence,
)


def speckle(mean, looks=4, seed=0):
    """Multiplicative gamma speckle, the standard SAR intensity model."""

    rng = np.random.default_rng(seed)
    return mean * rng.gamma(looks, 1.0 / looks, mean.shape)


def land(size=400, level=0.1):
    return np.full((size, size), level)


def lake_scene(size=400):
    """Land with a 200x200 lake 12 dB darker and three bright targets."""

    mean = land(size)
    mean[100:300, 50:250] *= 10 ** (-12 / 10)

    for row, col in [(30, 300), (350, 350), (200, 330)]:
        mean[row : row + 4, col : col + 4] *= 10 ** (15 / 10)

    return mean


@pytest.mark.parametrize(
    "query,expected",
    [
        ("Analyse this SAR image", "summary"),
        ("Where is the water in this SAR image?", "water"),
        ("Is there flooding in the SAR scene?", "water"),
        ("Detect ships in the radar image", "targets"),
        ("Fuse the optical and SAR data", "fusion"),
    ],
)
def test_sar_intent(query, expected):
    assert sar_intent(query) == expected


def test_lee_filter_reduces_speckle_but_keeps_the_mean_level():
    image = speckle(land(200))
    valid = np.ones(image.shape, dtype=bool)

    filtered = lee_filter(image, valid, window=5)

    assert filtered.std() < 0.5 * image.std()
    assert filtered.mean() == pytest.approx(image.mean(), rel=0.02)


def test_prepare_detects_linear_and_decibel_input_and_agrees():
    image = speckle(lake_scene())

    linear = prepare(image)
    decibel = prepare(10 * np.log10(image))

    assert linear.input_scale == "linear" and decibel.input_scale == "decibel"
    assert decibel.median_db == pytest.approx(linear.median_db, abs=0.01)
    assert linear.p05_db < linear.median_db < linear.p95_db


def test_lake_is_found_with_the_right_extent_and_contrast():
    scene = prepare(speckle(lake_scene()))
    low = find_low_backscatter(scene)

    assert low.distinct
    assert low.fraction == pytest.approx(0.25, abs=0.005)
    assert low.contrast_db == pytest.approx(12, abs=1.0)
    assert low.region_count == 1

    x0, y0, x1, y1 = low.regions[0].bbox
    assert abs(x0 - 50) <= 2 and abs(y0 - 100) <= 2
    assert abs(x1 - 250) <= 2 and abs(y1 - 300) <= 2
    assert low.mask[200, 150] and not low.mask[20, 20]


@pytest.mark.parametrize("looks", [1, 4])
def test_uniform_land_has_no_water_like_class_and_no_targets(looks):
    scene = prepare(speckle(land(), looks=looks))
    low = find_low_backscatter(scene)
    targets, total = find_bright_targets(scene)

    assert not low.distinct and not low.mask.any()
    assert low.contrast_db < 5
    assert total == 0 and targets == []


def test_ordinary_land_cover_difference_is_not_reported_as_water():
    mean = land()
    mean[:, :200] *= 10 ** (-3 / 10)  # two land covers 3 dB apart

    assert not find_low_backscatter(prepare(speckle(mean))).distinct


def test_min_contrast_parameter_controls_the_decision():
    mean = land()
    mean[:, :200] *= 10 ** (-6 / 10)
    scene = prepare(speckle(mean))

    assert find_low_backscatter(scene, min_contrast_db=5).distinct
    assert not find_low_backscatter(scene, min_contrast_db=8).distinct


@pytest.mark.parametrize("looks", [1, 4])
def test_bright_targets_are_found_at_the_right_places(looks):
    scene = prepare(speckle(lake_scene(), looks=looks))
    targets, total = find_bright_targets(scene)

    assert total == 3

    centres = sorted(
        ((t.bbox[1] + t.bbox[3]) // 2, (t.bbox[0] + t.bbox[2]) // 2) for t in targets
    )
    expected = sorted([(32, 302), (352, 352), (202, 332)])

    for (row, col), (want_row, want_col) in zip(centres, expected):
        assert abs(row - want_row) <= 2 and abs(col - want_col) <= 2

    assert all(t.contrast_db > 8 for t in targets)
    assert targets == sorted(targets, key=lambda t: t.contrast_db, reverse=True)


def test_target_inside_dark_water_is_found():
    mean = lake_scene()
    mean[150:153, 120:123] *= 10 ** (22 / 10)  # a ship on the lake

    targets, total = find_bright_targets(prepare(speckle(mean)))

    assert total == 4
    assert targets[0].bbox[0] <= 121 <= targets[0].bbox[2]
    assert targets[0].bbox[1] <= 151 <= targets[0].bbox[3]


def test_max_targets_caps_the_list_but_not_the_count():
    targets, total = find_bright_targets(prepare(speckle(lake_scene())), max_targets=2)

    assert total == 3 and len(targets) == 2


def test_zero_fill_is_treated_as_nodata():
    image = speckle(lake_scene())
    image[:, :40] = 0

    scene = prepare(image)
    low = find_low_backscatter(scene)

    assert scene.valid_fraction == pytest.approx(0.9)
    assert low.distinct and not low.mask[:, :40].any()
    assert find_bright_targets(scene)[1] == 3


def test_prepare_rejects_bad_input():
    with pytest.raises(ValueError):
        prepare(np.zeros((3, 10, 10)))

    with pytest.raises(ValueError):
        prepare(np.full((10, 10), np.nan))

    with pytest.raises(ValueError):
        prepare(np.zeros((10, 10)))


def optical_with_dark_block(bands, rows, cols, size=400, seed=1):
    rng = np.random.default_rng(seed)
    optical = rng.normal(120, 10, (bands, size, size))
    optical[-1, rows, cols] = rng.normal(20, 4, optical[-1, rows, cols].shape)
    return optical


def test_fusion_reports_how_much_of_the_sar_water_is_dark_optically():
    scene = prepare(speckle(lake_scene()))
    low = find_low_backscatter(scene)
    # Near-infrared (band 4) is dark over three quarters of the lake.
    optical = optical_with_dark_block(4, slice(100, 300), slice(50, 200))

    fusion = fuse_with_optical(low, scene.valid, optical)

    assert fusion.indicator.startswith("band 4")
    assert fusion.optical_dark_distinct
    assert fusion.sar_confirmed_fraction == pytest.approx(0.75, abs=0.01)
    assert fusion.agreement == pytest.approx(0.75, abs=0.01)
    assert fusion.both[200, 100] and fusion.sar_only[200, 230]
    assert not fusion.optical_only[200, 100]


def test_fusion_with_featureless_optical_image_confirms_nothing():
    scene = prepare(speckle(lake_scene()))
    low = find_low_backscatter(scene)
    optical = np.random.default_rng(1).normal(120, 10, (3, 400, 400))

    fusion = fuse_with_optical(low, scene.valid, optical)

    assert fusion.indicator.startswith("mean brightness")
    assert not fusion.optical_dark_distinct
    assert fusion.sar_confirmed_fraction == 0.0
    assert fusion.sar_only.sum() == low.mask.sum()


def test_fusion_rejects_mismatched_grids():
    scene = prepare(speckle(lake_scene()))
    low = find_low_backscatter(scene)

    with pytest.raises(ValueError):
        fuse_with_optical(low, scene.valid, np.zeros((3, 100, 100)))


def test_confidences_are_bounded_and_ordered():
    strong = find_low_backscatter(prepare(speckle(lake_scene())))
    none = find_low_backscatter(prepare(speckle(land())))

    assert 0.5 < low_backscatter_confidence(strong, 5.0) <= 0.95
    assert 0.3 <= low_backscatter_confidence(none, 5.0) <= 0.95

    targets, _ = find_bright_targets(prepare(speckle(lake_scene())))
    assert 0.3 <= target_confidence(targets, 5.0) <= 0.95
    assert target_confidence([], 5.0) is None
