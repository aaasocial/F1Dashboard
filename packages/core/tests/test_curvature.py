"""DATA-03 tests."""

from __future__ import annotations

import numpy as np
import pytest
from f1_core.curvature import compute_curvature_map, curvature_from_xy


def _circle_lap(radius: float, n: int = 400) -> tuple[np.ndarray, np.ndarray]:
    theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return radius * np.cos(theta), radius * np.sin(theta)


def test_curvature_from_xy_synthetic_circle() -> None:
    x, y = _circle_lap(radius=100.0, n=400)
    # Arc length of a circle of radius 100 is 2*pi*100 ~ 628
    grid = np.linspace(5, 620, 100)
    kappa = curvature_from_xy(x, y, grid)
    # Drop edges where cubic spline extrapolates
    interior = kappa[10:-10]
    # Expected |kappa| = 1/R = 0.01
    assert np.all(np.abs(interior) > 0.005), (
        f"min |kappa| = {np.abs(interior).min()} (expected ~0.01)"
    )
    assert np.all(np.abs(interior) < 0.015), (
        f"max |kappa| = {np.abs(interior).max()} (expected ~0.01)"
    )


def test_compute_curvature_map_deterministic() -> None:
    # Two identical laps -> identical output
    x, y = _circle_lap(100.0)
    laps = [(x, y), (x.copy(), y.copy())]
    grid = np.linspace(5, 620, 50)
    k1 = compute_curvature_map(laps, grid)
    k2 = compute_curvature_map(laps, grid)
    np.testing.assert_array_equal(k1, k2)


def test_compute_curvature_map_shape() -> None:
    x, y = _circle_lap(100.0)
    laps = [(x, y)]
    grid = np.arange(5.0, 620.0, 10.0)
    k = compute_curvature_map(laps, grid)
    assert k.shape == grid.shape


def test_compute_curvature_map_raises_on_empty() -> None:
    with pytest.raises(ValueError):
        compute_curvature_map([], np.linspace(0, 100, 10))


def test_compute_curvature_map_cross_lap_median() -> None:
    # Three clean laps at R=100 plus one noisy outlier at R=110. With an
    # odd number of laps the per-point median is drawn from the clean
    # band, so |kappa| remains near 0.01 despite the outlier.
    rng = np.random.default_rng(0)
    x1, y1 = _circle_lap(100.0)
    x2, y2 = _circle_lap(100.0)
    x3, y3 = _circle_lap(100.0)
    x4, y4 = _circle_lap(110.0)
    x4 = x4 + rng.normal(0, 2.0, size=x4.shape)
    y4 = y4 + rng.normal(0, 2.0, size=y4.shape)
    grid = np.linspace(5, 620, 50)
    k = compute_curvature_map([(x1, y1), (x2, y2), (x3, y3), (x4, y4)], grid)
    # Median |kappa| should remain in a reasonable band around 0.01
    interior = np.abs(k[10:-10])
    assert 0.004 < interior.mean() < 0.020, f"|kappa| mean = {interior.mean()} (expected ~0.01)"
