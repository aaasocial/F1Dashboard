"""Unit tests for static compound map (CALIB-05 — D-05 compound filter)."""
import pytest
from f1_calibration.compound_map import COMPOUND_MAP, lookup, races_for_compound


def test_bahrain_2023_mapping():
    assert lookup(2023, 1, "SOFT") == "C3"
    assert lookup(2023, 1, "MEDIUM") == "C2"
    assert lookup(2023, 1, "HARD") == "C1"


def test_case_insensitive_fia_compound():
    assert lookup(2023, 1, "soft") == "C3"


def test_unknown_race_raises():
    with pytest.raises(KeyError, match="2099"):
        lookup(2099, 99, "SOFT")


def test_invalid_fia_compound_raises():
    with pytest.raises(ValueError, match="SOFT"):
        lookup(2023, 1, "ULTRASOFT")


def test_races_for_compound_returns_tuples_for_c3_in_2023():
    result = races_for_compound("C3", years=(2023,))
    assert (2023, 1) in result
    assert all(isinstance(t, tuple) and len(t) == 2 for t in result)


def test_races_for_compound_rejects_invalid_target():
    with pytest.raises(ValueError, match="C1..C5"):
        races_for_compound("X9", years=(2023,))


def test_compound_map_covers_2022_2024():
    years = {yr for (yr, _) in COMPOUND_MAP.keys()}
    # Must cover at least partial 2022, 2023, 2024
    assert 2022 in years
    assert 2023 in years
    assert 2024 in years
