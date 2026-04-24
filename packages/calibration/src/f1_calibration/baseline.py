"""Baseline linear degradation model (CALIB-08).

Fits lap_time = slope · tire_age + intercept per stint using
sklearn.linear_model.LinearRegression. Stage 5 (Plan 07) compares the
physics model's per-lap RMSE against this baseline's RMSE on the 2024 holdout.
"""
from __future__ import annotations

from typing import Any, TypedDict

import numpy as np
from numpy.typing import NDArray
from sklearn.linear_model import LinearRegression


class StintBaseline(TypedDict):
    slope_s_per_lap: float
    intercept_s: float
    rmse_s: float
    n_laps: int


class BatchBaseline(TypedDict):
    per_stint: list[StintBaseline]
    combined_rmse_s: float
    total_n_laps: int


def rmse_per_lap(
    y_true: NDArray[np.float64],
    y_pred: NDArray[np.float64],
) -> float:
    yt = np.asarray(y_true, dtype=np.float64)
    yp = np.asarray(y_pred, dtype=np.float64)
    if yt.shape != yp.shape:
        raise ValueError(f"shape mismatch: y_true {yt.shape} vs y_pred {yp.shape}")
    return float(np.sqrt(np.mean((yt - yp) ** 2)))


def fit_baseline_per_stint(
    tire_ages: NDArray[np.int64] | NDArray[np.float64],
    lap_times_s: NDArray[np.float64],
) -> StintBaseline:
    ages = np.asarray(tire_ages, dtype=np.float64).ravel()
    y = np.asarray(lap_times_s, dtype=np.float64).ravel()
    if ages.shape != y.shape:
        raise ValueError(f"shape mismatch: tire_ages {ages.shape} vs lap_times_s {y.shape}")
    if ages.size < 3:
        raise ValueError(f"need at least 3 laps per stint, got {ages.size}")

    X = ages.reshape(-1, 1)
    model = LinearRegression().fit(X, y)
    y_pred = model.predict(X)
    return StintBaseline(
        slope_s_per_lap=float(model.coef_[0]),
        intercept_s=float(model.intercept_),
        rmse_s=rmse_per_lap(y, y_pred),
        n_laps=int(ages.size),
    )


def fit_baseline_batch(stints: list[dict[str, Any]]) -> BatchBaseline:
    """Fit one LinearRegression per stint and aggregate RMSE across all laps.

    Each stint dict must have `tire_ages` and `lap_times_s` (NDArray).
    Optional `compound` field is preserved but not required (CALIB-08 is fit per-stint).
    """
    if not stints:
        raise ValueError("stints list is empty")

    per_stint: list[StintBaseline] = []
    total_sq_err = 0.0
    total_n = 0
    for stint in stints:
        ages = np.asarray(stint["tire_ages"], dtype=np.float64).ravel()
        y = np.asarray(stint["lap_times_s"], dtype=np.float64).ravel()
        fit = fit_baseline_per_stint(ages, y)
        per_stint.append(fit)
        # Recompute residuals to aggregate cross-stint combined RMSE
        X = ages.reshape(-1, 1)
        slope = fit["slope_s_per_lap"]
        intercept = fit["intercept_s"]
        y_pred = slope * X.ravel() + intercept
        total_sq_err += float(np.sum((y - y_pred) ** 2))
        total_n += int(ages.size)

    combined_rmse = float(np.sqrt(total_sq_err / total_n)) if total_n > 0 else 0.0
    return BatchBaseline(
        per_stint=per_stint,
        combined_rmse_s=combined_rmse,
        total_n_laps=total_n,
    )


__all__ = ["StintBaseline", "BatchBaseline", "fit_baseline_per_stint", "fit_baseline_batch", "rmse_per_lap"]
