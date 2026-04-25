"""DATA-03: per-circuit reference curvature map kappa(s) from fastest 20% of laps.

Algorithm (model_spec section A.1, pitfall P8 of RESEARCH.md):
1. Select fastest 20% of laps in the session.
2. For each lap, align samples by cumulative arc length s.
3. Fit CubicSpline(s, X), CubicSpline(s, Y).
4. Evaluate kappa(s) = X'(s) * Y''(s) - Y'(s) * X''(s) on a shared grid.
5. Take median across laps per s (robust to single-lap noise).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.interpolate import CubicSpline

F64 = NDArray[np.float64]


def _arc_length(x: F64, y: F64) -> F64:
    dx = np.diff(x, prepend=x[0])
    dy = np.diff(y, prepend=y[0])
    return np.cumsum(np.sqrt(dx * dx + dy * dy))


def curvature_from_xy(x: F64, y: F64, grid_meters: F64) -> F64:
    """Compute kappa at each point of grid_meters from a single (x, y) trace."""
    s = _arc_length(x, y)
    # Enforce strict monotonic s
    mask = np.concatenate(([True], np.diff(s) > 0))
    s = s[mask]
    x = x[mask]
    y = y[mask]
    if len(s) < 4:
        raise ValueError(
            f"Lap has only {len(s)} unique arc-length samples after monotonicity filter "
            "(need >= 4 for CubicSpline); skipping this lap"
        )
    cs_x = CubicSpline(s, x)
    cs_y = CubicSpline(s, y)
    # Clip grid to the spline domain
    grid = np.clip(grid_meters, s[0], s[-1])
    dx = cs_x(grid, 1)
    ddx = cs_x(grid, 2)
    dy = cs_y(grid, 1)
    ddy = cs_y(grid, 2)
    return np.asarray(dx * ddy - dy * ddx, dtype=np.float64)


def compute_curvature_map(
    laps_xy: list[tuple[F64, F64]],
    grid_meters: F64,
) -> F64:
    """Given a list of per-lap (x_array, y_array), return median kappa on grid.

    `laps_xy`: list of (x, y) arrays. Typically the fastest 20% of laps in a session.
    `grid_meters`: 1D array of arc-length sample points (e.g. np.arange(0, 5500, 5.0)).
    """
    if not laps_xy:
        raise ValueError("laps_xy must contain at least one lap")
    per_lap = []
    for x, y in laps_xy:
        if len(x) < 4 or len(y) < 4:
            continue
        try:
            per_lap.append(
                curvature_from_xy(
                    np.asarray(x, dtype=float),
                    np.asarray(y, dtype=float),
                    np.asarray(grid_meters, dtype=float),
                )
            )
        except ValueError:
            # Lap had >= 4 raw points but shrank below 4 after the monotonicity
            # filter (repeated arc-length values from noisy telemetry). Skip it.
            continue
    if not per_lap:
        raise ValueError("no lap had enough samples to compute curvature")
    stacked = np.stack(per_lap, axis=0)
    return np.asarray(np.median(stacked, axis=0), dtype=np.float64)
