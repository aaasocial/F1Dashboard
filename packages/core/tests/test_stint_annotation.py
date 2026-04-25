"""DATA-06 tests: per-lap annotation on fixtures + synthetic inputs."""

from __future__ import annotations

import gzip
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from f1_core.stint_annotation import annotate_stint

FIX_DIR = Path(__file__).parent / "fixtures"


def _load(name: str):
    p = FIX_DIR / name
    if not p.exists():
        pytest.skip(f"Fixture missing: {p}")
    with gzip.open(p, "rb") as f:
        return pickle.load(f)


def test_annotate_stint_produces_lap_per_input() -> None:
    a = _load("bahrain_2023_ver_stint2.pkl.gz")
    out = annotate_stint(a, year=2023, round_number=a.key.round)
    assert len(out.laps) == len(a.laps)


def test_annotate_stint_compound_letter_mapped() -> None:
    """Canonical Bahrain 2023 VER stint 2 is a SOFT-compound stint.

    Per compound_mapping.yaml "2023-01": SOFT=C3.
    The original plan wording said MEDIUM->C2, but the canonical fixture's
    stint 2 is actually a SOFT stint. Compound letter mapping must still work
    correctly; assert on whichever compound(s) the fixture actually contains.
    """
    a = _load("bahrain_2023_ver_stint2.pkl.gz")
    out = annotate_stint(a, year=2023, round_number=a.key.round)
    compounds_seen = {lap.compound.upper() for lap in out.laps if lap.compound}
    assert compounds_seen, "fixture must contain at least one compound label"
    expected = {"SOFT": "C3", "MEDIUM": "C2", "HARD": "C1"}
    for lap in out.laps:
        if not lap.compound:
            continue
        want = expected.get(lap.compound.upper())
        assert want is not None, f"Unexpected compound in fixture: {lap.compound!r}"
        assert lap.compound_letter == want, (
            f"Lap {lap.lap_number} ({lap.compound}): expected {want}, got {lap.compound_letter!r}"
        )


def test_annotate_stint_fuel_estimate_monotonic() -> None:
    a = _load("bahrain_2023_ver_stint2.pkl.gz")
    out = annotate_stint(a, year=2023, round_number=a.key.round)
    fuels = [lap.fuel_estimate_kg for lap in out.laps]
    for i in range(1, len(fuels)):
        assert fuels[i] <= fuels[i - 1], (
            f"Fuel must decrease: lap {i - 1} = {fuels[i - 1]}, lap {i} = {fuels[i]}"
        )


def test_annotate_stint_in_out_lap_flags() -> None:
    a = _load("bahrain_2023_ver_stint2.pkl.gz")
    out = annotate_stint(a, year=2023, round_number=a.key.round)
    # Stint 2 begins with an out-lap (pit exit after stop) - expect at least one out-lap flag
    assert any(lap.is_out_lap for lap in out.laps)
    # exclude_from_degradation must be True on in/out laps
    for lap in out.laps:
        if lap.is_in_lap or lap.is_out_lap:
            assert lap.exclude_from_degradation is True


def test_annotate_stint_sc_vsc_synthetic() -> None:
    """Synthetic test: mutate track_status to force SC overlap on one lap."""
    a = _load("bahrain_2023_ver_stint2.pkl.gz")
    # Pick the middle lap of the stint and plant a SC status row inside its timespan
    lap_row = a.laps.iloc[len(a.laps) // 2]
    lap_start = lap_row.get("LapStartTime", lap_row["Time"])
    lap_end = lap_row["Time"]
    mid = lap_start + (lap_end - lap_start) / 2
    a.track_status = pd.DataFrame({"Time": [mid], "Status": [4]})
    out = annotate_stint(a, year=2023, round_number=a.key.round)
    flagged = [lap for lap in out.laps if lap.is_sc_vsc]
    assert len(flagged) >= 1


def test_savgol_velocity_shape() -> None:
    from f1_core.filters import savgol_velocity

    v = np.arange(100, dtype=float) * 0.25
    out = savgol_velocity(v)
    assert out.shape == v.shape


def test_savgol_velocity_rejects_even_window() -> None:
    from f1_core.filters import savgol_velocity

    with pytest.raises(ValueError):
        savgol_velocity(np.arange(50, dtype=float), window=8)
