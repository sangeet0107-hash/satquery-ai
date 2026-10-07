import numpy as np
import pytest

from backend.app.analysis.change import change_confidence, detect_change


def scene(seed=0, bands=3, size=200):
    rng = np.random.default_rng(seed)
    return rng.normal(100, 20, (bands, size, size)).astype("float32")


def test_identical_images_have_no_change():
    base = scene()
    result = detect_change(base, base)

    assert result.region_count == 0
    assert result.changed_fraction == 0.0
    assert not result.mask.any()


def test_global_brightness_and_contrast_shift_is_not_change():
    base = scene()
    result = detect_change(base, base * 2 + 10)

    assert result.region_count == 0


def test_sensor_noise_alone_is_not_change():
    base = scene()
    noisy = base + np.random.default_rng(1).normal(0, 2, base.shape)

    assert detect_change(base, noisy).region_count == 0


def test_changed_block_is_found_with_correct_box_and_direction():
    base = scene()
    after = base + np.random.default_rng(1).normal(0, 2, base.shape)
    after[:, 50:90, 120:170] += 120

    result = detect_change(base, after)

    assert result.region_count == 1
    region = result.regions[0]
    assert region.bbox == (120, 50, 170, 90)
    assert region.area_px == 2000
    assert region.direction == "brighter"
    assert result.changed_fraction == pytest.approx(2000 / 40000)
    assert result.mask[60, 130] and not result.mask[10, 10]


def test_regions_are_sorted_largest_first_and_darker_is_reported():
    base = scene()
    after = base.copy()
    after[:, 50:90, 120:170] -= 120
    after[:, 150:160, 10:20] += 90

    result = detect_change(base, after)

    assert [r.area_px for r in result.regions] == [2000, 100]
    assert [r.direction for r in result.regions] == ["darker", "brighter"]


def test_small_regions_are_dropped_and_max_regions_caps_the_list():
    base = scene()
    after = base.copy()
    after[:, 10:14, 10:14] += 150      # 16 px
    after[:, 100:120, 100:120] += 150  # 400 px

    assert detect_change(base, after, min_region_px=25).region_count == 1
    both = detect_change(base, after, min_region_px=5)
    assert both.region_count == 2

    capped = detect_change(base, after, min_region_px=5, max_regions=1)
    assert capped.region_count == 2 and len(capped.regions) == 1


def test_nodata_pixels_are_ignored():
    base = scene()
    after = base.copy()
    after[:, 50:90, 120:170] += 120
    base[:, :20, :] = np.nan

    result = detect_change(base, after)

    assert result.region_count == 1
    assert not result.mask[:20].any()
    assert result.valid_fraction == pytest.approx(0.9)


def test_single_band_2d_input_is_accepted():
    base = scene(bands=1)[0]
    after = base.copy()
    after[30:70, 30:70] += 150

    assert detect_change(base, after).region_count == 1


def test_shape_mismatch_and_no_valid_pixels_raise():
    with pytest.raises(ValueError):
        detect_change(scene(size=100), scene(size=120))

    empty = np.full((1, 10, 10), np.nan, dtype="float32")

    with pytest.raises(ValueError):
        detect_change(empty, empty)


def test_confidence_is_bounded_and_higher_for_clearer_change():
    base = scene()
    noise = np.random.default_rng(1).normal(0, 4, base.shape)
    strong = base + noise
    strong[:, 50:90, 120:170] += 200
    weak = base + noise
    weak[:, 50:90, 120:170] += 45

    strong_score = change_confidence(detect_change(base, strong))
    weak_result = detect_change(base, weak)

    assert 0.05 <= strong_score <= 0.95
    assert weak_result.region_count >= 1
    assert change_confidence(weak_result) < strong_score
    assert 0.05 <= change_confidence(detect_change(base, base)) <= 0.95


def structured_scene(size=160):
    """Blocks with sharp edges, where misalignment shows up as false change."""

    image = np.full((3, size, size), 60.0, dtype="float32")
    image[:, 20:70, 20:70] = 180.0
    image[:, 90:140, 40:120] = 120.0
    image[:, 30:60, 100:150] = 220.0
    image += np.random.default_rng(3).normal(0, 2, image.shape).astype("float32")
    return image


def test_one_pixel_misregistration_is_not_reported_as_change():
    base = structured_scene()
    shifted = np.roll(base, 1, axis=2)

    assert detect_change(base, shifted, registration_tolerance_px=0).raw_fraction > 0
    assert detect_change(base, shifted, registration_tolerance_px=1).region_count == 0


def test_real_change_survives_misregistration_tolerance_with_full_extent():
    base = structured_scene()
    after = base.copy()
    after[:, 100:130, 60:100] = 10.0
    after = np.roll(after, 1, axis=1)

    result = detect_change(base, after, registration_tolerance_px=1)

    assert result.region_count == 1
    assert result.regions[0].bbox == (60, 101, 100, 131)
    assert result.regions[0].direction == "darker"


def test_change_touching_the_image_edge_keeps_its_full_extent():
    base = scene()
    after = base + np.random.default_rng(1).normal(0, 2, base.shape)
    after[:, 0:30, 0:40] += 150
    after[:, 170:200, 150:200] -= 150

    result = detect_change(base, after)

    assert sorted(r.bbox for r in result.regions) == [(0, 0, 40, 30), (150, 170, 200, 200)]
    assert sorted(r.area_px for r in result.regions) == [1200, 1500]
