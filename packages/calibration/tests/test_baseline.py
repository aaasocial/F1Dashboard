"""Tests for linear baseline (CALIB-08)."""
from __future__ import annotations
import numpy as np
import pytest
from f1_calibration.baseline import (
    fit_baseline_per_stint,
    fit_baseline_batch,
    rmse_per_lap,
)


def _synthetic_stint(slope: float, intercept: float, n_laps: int, seed: int = 0):
    rng = np.random.default_rng(seed)
    ages = np.arange(n_laps, dtype=np.float64)
    lap_times = slope * ages + intercept + rng.normal(0, 0.05, n_laps)
    return ages, lap_times


def test_baseline_fits_linear_trend():
    ages, laps = _synthetic_stint(slope=0.05, intercept=90.0, n_laps=30, seed=1)
    fit = fit_baseline_per_stint(ages, laps)
    assert abs(fit["slope_s_per_lap"] - 0.05) < 0.01
    assert abs(fit["intercept_s"] - 90.0) < 0.2
    assert fit["n_laps"] == 30
    assert fit["rmse_s"] < 0.1


def test_baseline_rmse_is_zero_on_noise_free():
    ages = np.arange(20, dtype=np.float64)
    laps = 0.03 * ages + 85.0
    fit = fit_baseline_per_stint(ages, laps)
    assert fit["rmse_s"] < 1e-10


def test_baseline_rejects_short_stint():
    with pytest.raises(ValueError, match="at least 3"):
        fit_baseline_per_stint(np.array([0.0, 1.0]), np.array([90.0, 90.1]))


def test_baseline_rejects_shape_mismatch():
    with pytest.raises(ValueError, match="shape mismatch"):
        fit_baseline_per_stint(np.arange(10), np.arange(5))


def test_baseline_batch_aggregates_rmse():
    stints = []
    for seed in range(5):
        ages, laps = _synthetic_stint(slope=0.04, intercept=89.5, n_laps=25, seed=seed)
        stints.append({"tire_ages": ages, "lap_times_s": laps, "compound": "C3"})
    result = fit_baseline_batch(stints)
    assert len(result["per_stint"]) == 5
    assert result["total_n_laps"] == 125
    # Combined RMSE should be near 0.05 (noise level)
    assert 0.02 < result["combined_rmse_s"] < 0.1


def test_baseline_batch_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        fit_baseline_batch([])


def test_rmse_per_lap_utility():
    y_true = np.array([1.0, 2.0, 3.0])
    y_pred = np.array([1.1, 1.9, 3.2])
    assert rmse_per_lap(y_true, y_pred) == pytest.approx(np.sqrt((0.01 + 0.01 + 0.04) / 3))
