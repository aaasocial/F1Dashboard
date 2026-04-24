"""DATA-04 tests."""

from __future__ import annotations

import gzip
import pickle
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from f1_core.gear_inference import R_0_M, infer_gear_ratios

FIX_DIR = Path(__file__).parent / "fixtures"


def test_infer_gear_ratios_rejects_missing_columns() -> None:
    df = pd.DataFrame({"Speed": [100, 200]})
    with pytest.raises(ValueError):
        infer_gear_ratios(df)


def test_infer_gear_ratios_ignores_low_throttle() -> None:
    df = pd.DataFrame(
        {
            "Speed": [100.0] * 40,
            "RPM": [8000.0] * 40,
            "Throttle": [50.0] * 40,  # below threshold
            "nGear": [5] * 40,
        }
    )
    result = infer_gear_ratios(df)
    assert result == {}


def test_infer_gear_ratios_synthetic_fixed_ratio() -> None:
    # For gear=5 with ratio r, V = 2*pi*R0*RPM/(60*r).
    # Pick r=4.0, RPM=12000 -> V ~ 18.7 m/s ~ 67 km/h (> 50 km/h threshold).
    ratio_true = 4.0
    rpm = 12000.0
    v_mps = 2 * np.pi * R_0_M * rpm / (60.0 * ratio_true)
    v_kmh = v_mps * 3.6
    df = pd.DataFrame(
        {
            "Speed": [v_kmh] * 40,
            "RPM": [rpm] * 40,
            "Throttle": [100.0] * 40,
            "nGear": [5] * 40,
        }
    )
    result = infer_gear_ratios(df)
    assert 5 in result
    assert abs(result[5] - ratio_true) < 0.05


def test_infer_gear_ratios_bahrain_2023_ver_canonical() -> None:
    p = FIX_DIR / "bahrain_2023_ver_stint2.pkl.gz"
    if not p.exists():
        pytest.skip("canonical fixture missing")
    with gzip.open(p, "rb") as f:
        a = pickle.load(f)
    ratios = infer_gear_ratios(a.car_data)
    # Expect at least 4 gears inferred on a full stint
    assert len(ratios) >= 4, f"Only {len(ratios)} gears inferred: {ratios}"
    # Higher gears must have LOWER combined ratio (taller gear -> smaller number)
    gears_sorted = sorted(ratios.keys())
    for g1, g2 in pairwise(gears_sorted):
        assert ratios[g2] < ratios[g1], (
            f"Expected ratio[gear={g2}] < ratio[gear={g1}]: got {ratios[g2]} vs {ratios[g1]}"
        )
