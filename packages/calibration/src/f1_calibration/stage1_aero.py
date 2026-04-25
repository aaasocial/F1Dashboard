"""Stage 1 — Aero calibration (CALIB-01).

Fits C_LA (downforce area), C_DA (drag area), xi (aero balance) from
observed peak lateral-g at fast corners using scipy.optimize.least_squares.

Observables (extracted from training stints in Plan 08's run_all):
  obs_corner_lat_g: peak lateral g at K corners across training races
  v_at_corner:      speed through those corners (m/s)
  M_total:          vehicle + fuel mass (kg)

Un-fit AeroParams fields (K_rf_split, WD, H_CG, BB) remain at nominal values
from make_nominal_params() — per model_spec they are SEMI-CONSTRAINED, not fit by Stage 1.
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import least_squares

from f1_core.physics.params import AeroParams
from f1_core.physics.defaults import make_nominal_params

# Nominal prior centers (also the initial guess for the optimizer)
_NOMINAL_C_LA: float = 4.5
_NOMINAL_C_DA: float = 1.1
_NOMINAL_XI: float = 0.45

# Physical bounds for the fit — see CLAUDE.md and model_spec.md §B.4
_BOUNDS_LOWER: tuple[float, float, float] = (3.0, 0.8, 0.40)
_BOUNDS_UPPER: tuple[float, float, float] = (7.0, 1.8, 0.50)

_MU_GRIP_PRIOR: float = 1.8   # μ₀^fresh nominal (used only as a prior; Stage 2 refines)
_RHO_AIR: float = 1.20        # kg/m³
_G: float = 9.81              # m/s²


def _residuals(
    theta: NDArray[np.float64],
    obs_lat_g: NDArray[np.float64],
    v_corner: NDArray[np.float64],
    M_total: float,
) -> NDArray[np.float64]:
    """Residuals between predicted and observed peak lateral-g at K corners.

    Predicted: μ_grip · (M·g + 0.5·ρ·C_LA·V²) / (M·g)
    """
    C_LA, _C_DA, _xi = theta  # C_DA, xi enter via Stage 3 joint fit only
    F_aero = 0.5 * _RHO_AIR * C_LA * v_corner ** 2
    predicted = _MU_GRIP_PRIOR * (_G * M_total + F_aero) / (_G * M_total)
    return obs_lat_g - predicted


def fit_stage1(
    obs_corner_lat_g: NDArray[np.float64],
    v_at_corner: NDArray[np.float64],
    M_total: float = 798.0 + 40.0,   # car dry + ~40 kg fuel mid-race
) -> tuple[AeroParams, dict[str, float | int]]:
    """Fit aero params from corner lateral-g. Compound-agnostic (D-05)."""
    obs = np.asarray(obs_corner_lat_g, dtype=np.float64).ravel()
    v = np.asarray(v_at_corner, dtype=np.float64).ravel()
    if obs.shape != v.shape:
        raise ValueError(
            f"shape mismatch: obs_corner_lat_g {obs.shape} vs v_at_corner {v.shape}"
        )
    if obs.size < 3:
        raise ValueError(f"need at least 3 corners, got {obs.size}")

    x0 = np.array([_NOMINAL_C_LA, _NOMINAL_C_DA, _NOMINAL_XI], dtype=np.float64)
    result = least_squares(
        _residuals,
        x0=x0,
        bounds=(_BOUNDS_LOWER, _BOUNDS_UPPER),
        method="trf",
        args=(obs, v, M_total),
    )
    rmse = float(np.sqrt(np.mean(result.fun ** 2)))
    residual_max = float(np.max(np.abs(result.fun)))

    nominal = make_nominal_params().aero
    params = AeroParams(
        C_LA=float(result.x[0]),
        C_DA=float(result.x[1]),
        xi=float(result.x[2]),
        # Semi-constrained fields: keep nominal (not fit here)
        K_rf_split=nominal.K_rf_split,
        WD=nominal.WD,
        H_CG=nominal.H_CG,
        BB=nominal.BB,
    )
    diagnostics: dict[str, float | int] = {
        "rmse": rmse,
        "n_corners": int(obs.size),
        "residual_max": residual_max,
        "optimizer_status": int(result.status),
    }
    return params, diagnostics


__all__ = ["fit_stage1"]
