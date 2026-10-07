from datetime import date

from backend.app.ingestion.info import (
    Bounds,
    Modality,
    PairType,
    RasterInfo,
    check_pair,
    detect_modality,
    parse_acquisition_date,
)

BOUNDS = Bounds(left=77.0, bottom=27.0, right=78.0, top=28.0)


def make_info(modality=Modality.OPTICAL, when=None, **overrides):
    values = dict(
        width=100,
        height=100,
        bands=3,
        dtype="uint16",
        crs="EPSG:4326",
        bounds=BOUNDS,
        pixel_size=(0.01, 0.01),
        modality=modality,
        modality_confidence="high",
        modality_reason="test",
        acquisition_date=when,
    )
    values.update(overrides)
    return RasterInfo(**values)


def test_sar_hint_in_filename_wins_over_band_count():
    modality, confidence, _ = detect_modality(4, "uint16", "scene_vv.tif")
    assert modality == Modality.SAR and confidence == "high"


def test_rgb_bands_are_optical():
    assert detect_modality(3, "uint8", "scene.tif")[0] == Modality.OPTICAL


def test_many_bands_are_multispectral():
    assert detect_modality(12, "uint16", "")[0] == Modality.MULTISPECTRAL


def test_single_band_without_hints_is_ambiguous():
    modality, confidence, _ = detect_modality(1, "uint16", "pan.tif")
    assert modality == Modality.SINGLE_BAND and confidence == "low"


def test_two_float_bands_look_like_dual_pol_sar_with_low_confidence():
    modality, confidence, _ = detect_modality(2, "float32", "")
    assert modality == Modality.SAR and confidence == "low"


def test_word_boundaries_avoid_false_sar_hits():
    assert detect_modality(3, "uint8", "kansas_hhighway.tif")[0] == Modality.OPTICAL


def test_acquisition_date_priority():
    assert parse_acquisition_date(
        {"ACQUISITION_DATE": "2024-03-05"}, "x_20200101.tif"
    ) == (date(2024, 3, 5), "tag:acquisition_date")
    assert parse_acquisition_date({}, "S2_20230112_scene.tif") == (
        date(2023, 1, 12),
        "filename",
    )
    parsed, source = parse_acquisition_date(
        {"TIFFTAG_DATETIME": "2022:07:01 10:00:00"}, "x.tif"
    )
    assert parsed == date(2022, 7, 1) and "weak" in source
    assert parse_acquisition_date({}, "x.tif") == (None, None)


def test_optical_sar_pair_detected():
    report = check_pair(
        make_info(Modality.OPTICAL, date(2023, 1, 1)),
        make_info(Modality.SAR, date(2023, 1, 2)),
    )
    assert report.pair_type == PairType.OPTICAL_SAR
    assert report.co_registered


def test_bitemporal_pair_detected():
    report = check_pair(
        make_info(when=date(2023, 1, 1)), make_info(when=date(2024, 1, 1))
    )
    assert report.pair_type == PairType.BITEMPORAL
    assert report.bitemporal is True


def test_unknown_dates_reported():
    report = check_pair(make_info(), make_info())
    assert report.bitemporal is None
    assert any("date" in issue for issue in report.issues)


def test_different_crs_is_not_co_registered():
    report = check_pair(make_info(), make_info(crs="EPSG:32644"))
    assert not report.same_crs and not report.co_registered


def test_shifted_extent_is_not_co_registered():
    shifted = Bounds(left=77.4, bottom=27.0, right=78.4, top=28.0)
    report = check_pair(make_info(), make_info(bounds=shifted))
    assert not report.co_registered


def test_disjoint_extents_are_unrelated():
    far = Bounds(left=10.0, bottom=10.0, right=11.0, top=11.0)
    report = check_pair(make_info(), make_info(bounds=far))
    assert report.pair_type == PairType.UNRELATED
