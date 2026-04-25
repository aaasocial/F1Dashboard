"""Stage 3 — Thermal parameter calibration (CALIB-03).

Fits 8 thermal ODE params by forward-integrating production Module F against observed
out-lap warm-up curves from training stints filtered to the target compound (D-05).

Per RESEARCH.md: reuse f1_core.physics.module_f.thermal_step; DO NOT re-implement.
The NumPy production path IS the physics — the JAX rewrite (jax_model.py, Plan 05)
is a parity copy for Stage 4 ONLY.

Pitfall 2: explicit lower bounds on thermal capacities prevent optimizer from
driving τ = C·R below 0.5 s (forward Euler stability at Δt=0.25 s).

Note on T_opt and sigma_T:
  These are Grosch-curve parameters (§D.4) that modulate grip from temperature —
  they do NOT appear in the thermal ODE (§F.1–§F.3). From warm-up curve residuals
  on T_tread alone, T_opt and sigma_T have zero gradient and are structurally
  non-identifiable. They are held fixed at their initial values (passed in from
  the caller or defaulting to make_nominal_params()) and preserved in the returned
  ThermalParams. Stage 3 only fits the 8 ODE parameters:
  (C_tread, C_carc, C_gas, R_tc, R_cg, h_0, h_1, alpha_p).

Input warm-up curves are pre-extracted by the caller (Plan 08 run_all) from
laps 1-3 of each stint — the warm-up transient.
"""
from __future__ import annotations

from typing import Any, TypedDict

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import least_squares

from f1_core.physics.constants import DT_THERMAL  # noqa: F401 — used by callers for context
from f1_core.physics.defaults import make_nominal_params
from f1_core.physics.module_f import thermal_step
from f1_core.physics.params import ThermalParams

from f1_calibration.db import validate_compound


class WarmupCurve(TypedDict):
    t_tread_obs: NDArray[np.float64]     # (N_steps, 4) observed tread T per tire
    v_stream: NDArray[np.float64]        # (N_steps,) speed m/s
    p_total_stream: NDArray[np.float64]  # (N_steps, 4) dissipated power per tire
    t_air: float                          # scalar ambient
    t_track: float                        # scalar track (for initial condition)


# Free parameters fitted by this stage (8 thermal ODE params; T_opt and sigma_T
# are Grosch-curve parameters not identifiable from thermal residuals alone).
_PARAM_NAMES: tuple[str, ...] = (
    "C_tread", "C_carc", "C_gas",
    "R_tc", "R_cg", "h_0", "h_1", "alpha_p",
)

# Pitfall 2: lower bounds enforce τ = C·R > 2·Δt for forward-Euler stability
_BOUNDS_LOWER: tuple[float, ...] = (
    2000.0, 8000.0, 200.0, 0.005, 0.01, 2.0, 2.0, 0.30,
)
_BOUNDS_UPPER: tuple[float, ...] = (
    15000.0, 50000.0, 2000.0, 0.10, 0.20, 30.0, 30.0, 0.80,
)


def _theta_to_params(
    theta: NDArray[np.float64],
    *,
    t_opt: float,
    sigma_t: float,
    delta_T_blanket: float,
) -> ThermalParams:
    """Unpack the 8-element free-parameter vector into a ThermalParams dataclass.

    T_opt, sigma_T, and delta_T_blanket are injected from the caller — they are not
    in the free vector because they have zero gradient in thermal ODE residuals.
    """
    return ThermalParams(
        T_opt=t_opt,
        sigma_T=sigma_t,
        C_tread=float(theta[0]),
        C_carc=float(theta[1]),
        C_gas=float(theta[2]),
        R_tc=float(theta[3]),
        R_cg=float(theta[4]),
        h_0=float(theta[5]),
        h_1=float(theta[6]),
        alpha_p=float(theta[7]),
        delta_T_blanket=delta_T_blanket,
    )


def _forward_curve(
    theta: NDArray[np.float64],
    curve: WarmupCurve,
    *,
    t_opt: float,
    sigma_t: float,
    delta_T_blanket: float,
) -> NDArray[np.float64]:
    """Forward-integrate Module F across one warm-up curve. Returns (N_steps, 4) predicted T_tread."""
    params = _theta_to_params(theta, t_opt=t_opt, sigma_t=sigma_t, delta_T_blanket=delta_T_blanket)
    n_steps = int(curve["v_stream"].shape[0])

    # Initial condition: §F.6 T_tread = T_carc = T_gas = T_track + ΔT_blanket
    t0 = float(curve["t_track"]) + delta_T_blanket
    t_tread = np.full(4, t0, dtype=np.float64)
    t_carc = np.full(4, t0, dtype=np.float64)
    t_gas = np.full(4, t0, dtype=np.float64)

    pred = np.empty((n_steps, 4), dtype=np.float64)
    v_stream = curve["v_stream"]
    p_stream = curve["p_total_stream"]
    t_air = float(curve["t_air"])
    for i in range(n_steps):
        t_tread, t_carc, t_gas = thermal_step(
            t_tread=t_tread, t_carc=t_carc, t_gas=t_gas,
            p_total=p_stream[i].astype(np.float64),
            v=float(v_stream[i]), t_air=t_air, params=params,
        )
        pred[i] = t_tread
    return pred


def _residuals(
    theta: NDArray[np.float64],
    curves: list[WarmupCurve],
    *,
    t_opt: float,
    sigma_t: float,
    delta_T_blanket: float,
) -> NDArray[np.float64]:
    """Flattened residual vector across all curves × all 4 tires × all timesteps."""
    chunks: list[NDArray[np.float64]] = []
    for curve in curves:
        pred = _forward_curve(
            theta, curve,
            t_opt=t_opt, sigma_t=sigma_t, delta_T_blanket=delta_T_blanket,
        )
        chunks.append((pred - curve["t_tread_obs"]).ravel())
    return np.concatenate(chunks) if chunks else np.array([])


def fit_stage3(
    warmup_curves: list[WarmupCurve],
    *,
    compound: str,
    t_opt: float | None = None,
    sigma_t: float | None = None,
    delta_T_blanket: float | None = None,
) -> tuple[ThermalParams, dict[str, Any]]:
    """Fit 8 thermal ODE parameters via constrained least_squares. Compound-specific (D-05).

    Fits: C_tread, C_carc, C_gas, R_tc, R_cg, h_0, h_1, alpha_p.
    Fixed (non-identifiable from thermal residuals): T_opt, sigma_T, delta_T_blanket.

    Args:
        warmup_curves: List of warm-up curve dicts (each with t_tread_obs, v_stream,
            p_total_stream, t_air, t_track) extracted from laps 1-3 of training stints
            filtered to the target compound.
        compound: Pirelli compound code (e.g. 'C3'). Validated via validate_compound
            (T-3-01 mitigation) before any computation.
        t_opt: Grosch optimal temperature [°C]. Not fitted from thermal residuals —
            passed through to the returned ThermalParams. Defaults to nominal 95.0.
        sigma_t: Grosch half-width [°C]. Same: not fitted, passed through. Defaults to 20.0.
        delta_T_blanket: Initial blanket temperature offset above T_track [°C].
            Semi-constrained (§F.6); defaults to nominal 60.0.

    Returns:
        Tuple of (ThermalParams, diagnostics) where diagnostics contains:
            rmse_C: RMS residual in °C across all curves/tires/steps
            n_curves: Number of warm-up curves used
            n_steps_total: Total forward integration steps
            optimizer_status: scipy least_squares result.status
            compound: Validated compound code

    Raises:
        ValueError: If compound is invalid, warmup_curves is empty, or any curve
            has inconsistent shapes between t_tread_obs, v_stream, and p_total_stream.
    """
    compound = validate_compound(compound)   # T-3-01 mitigation

    if not warmup_curves:
        raise ValueError("warmup_curves list is empty")

    # Consistency checks
    for idx, curve in enumerate(warmup_curves):
        n = curve["v_stream"].shape[0]
        if curve["t_tread_obs"].shape != (n, 4):
            raise ValueError(
                f"curve {idx}: t_tread_obs shape {curve['t_tread_obs'].shape} != ({n}, 4)"
            )
        if curve["p_total_stream"].shape != (n, 4):
            raise ValueError(
                f"curve {idx}: p_total_stream shape {curve['p_total_stream'].shape} != ({n}, 4)"
            )

    nominal = make_nominal_params().thermal
    if t_opt is None:
        t_opt = nominal.T_opt           # 95.0
    if sigma_t is None:
        sigma_t = nominal.sigma_T       # 20.0
    if delta_T_blanket is None:
        delta_T_blanket = nominal.delta_T_blanket   # 60.0

    x0 = np.array([
        nominal.C_tread, nominal.C_carc, nominal.C_gas,
        nominal.R_tc, nominal.R_cg,
        nominal.h_0, nominal.h_1, nominal.alpha_p,
    ], dtype=np.float64)

    result = least_squares(
        _residuals, x0=x0,
        bounds=(_BOUNDS_LOWER, _BOUNDS_UPPER),
        method="trf",
        args=(warmup_curves,),
        kwargs={"t_opt": t_opt, "sigma_t": sigma_t, "delta_T_blanket": delta_T_blanket},
        max_nfev=200,   # cap at 200 forward-model evaluations
    )

    rmse = float(np.sqrt(np.mean(result.fun ** 2)))
    n_steps_total = int(sum(c["v_stream"].shape[0] for c in warmup_curves))
    params = _theta_to_params(
        result.x, t_opt=t_opt, sigma_t=sigma_t, delta_T_blanket=delta_T_blanket,
    )
    diagnostics: dict[str, Any] = {
        "rmse_C": rmse,
        "n_curves": len(warmup_curves),
        "n_steps_total": n_steps_total,
        "optimizer_status": int(result.status),
        "compound": compound,
    }
    return params, diagnostics


__all__ = ["WarmupCurve", "fit_stage3"]
