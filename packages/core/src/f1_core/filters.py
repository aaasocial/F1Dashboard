"""Numerical filters (Savitzky-Golay for velocity differentiation)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.signal import savgol_filter

# Locked defaults for 4 Hz telemetry (pitfall P4). dt = 0.25 s.
DEFAULT_WINDOW = 9
DEFAULT_POLYORDER = 3
DEFAULT_DELTA = 0.25


def savgol_velocity(
    v_mps: NDArray[np.float64],
    *,
    window: int = DEFAULT_WINDOW,
    order: int = DEFAULT_POLYORDER,
    delta: float = DEFAULT_DELTA,
) -> NDArray[np.float64]:
    """Compute dV/dt [m/s^2] from a speed signal using Savitzky-Golay (pitfall P4).

    Requires window to be odd and > order. Raises ValueError otherwise.
    """
    if window % 2 == 0:
        raise ValueError(f"window must be odd (got {window})")
    if order >= window:
        raise ValueError(f"order ({order}) must be < window ({window})")
    if len(v_mps) < window:
        # Not enough samples - fall back to np.gradient
        return np.gradient(v_mps, delta)
    return savgol_filter(
        v_mps, window_length=window, polyorder=order, deriv=1, delta=delta, mode="interp"
    )
