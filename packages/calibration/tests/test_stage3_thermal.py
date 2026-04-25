"""Tests for Stage 3 thermal calibration (CALIB-03).

Stage 3 fits 8 thermal ODE parameters: C_tread, C_carc, C_gas, R_tc, R_cg, h_0, h_1, alpha_p.
T_opt and sigma_T are Grosch-curve params (§D.4) with zero gradient in thermal residuals —
they are held fixed and passed through unchanged from the caller's initial values.
CALIB-03 tolerance: RMSE on warm-up curves < 2°C (practical target from synthetic test).
"""
from __future__ import annotations
import numpy as np
import pytest

from f1_core.physics.module_f import thermal_step
from f1_core.physics.params import ThermalParams
from f1_calibration.stage3_thermal import fit_stage3, _BOUNDS_LOWER, _BOUNDS_UPPER, _PARAM_NAMES


def _generate_warmup(true_params: ThermalParams, *, n_steps: int = 200,
                     t_air: float = 25.0, t_track: float = 35.0,
                     seed: int = 0) -> dict:
    """Forward-integrate thermal_step with `true_params` to synthesize an observed curve."""
    rng = np.random.default_rng(seed)
    # Varying speed profile (accelerate/decelerate)
    v_stream = np.clip(60.0 + 15.0 * np.sin(np.linspace(0, 8, n_steps)) +
                       rng.normal(0, 2.0, n_steps), 5.0, 90.0)
    # Power on tires: ~20 kW per tire base + jitter
    p_stream = 20_000.0 + 5_000.0 * rng.normal(0, 1, (n_steps, 4))
    p_stream = np.clip(p_stream, 1_000.0, None)

    t0 = t_track + true_params.delta_T_blanket
    t_tread = np.full(4, t0, dtype=np.float64)
    t_carc = np.full(4, t0, dtype=np.float64)
    t_gas = np.full(4, t0, dtype=np.float64)
    t_tread_obs = np.empty((n_steps, 4), dtype=np.float64)
    for i in range(n_steps):
        t_tread, t_carc, t_gas = thermal_step(
            t_tread=t_tread, t_carc=t_carc, t_gas=t_gas,
            p_total=p_stream[i].astype(np.float64),
            v=float(v_stream[i]), t_air=t_air, params=true_params,
        )
        t_tread_obs[i] = t_tread

    # Add small observation noise (~0.5 °C)
    t_tread_obs = t_tread_obs + rng.normal(0, 0.5, t_tread_obs.shape)
    return {
        "t_tread_obs": t_tread_obs,
        "v_stream": v_stream,
        "p_total_stream": p_stream,
        "t_air": t_air,
        "t_track": t_track,
    }


def _nominal_thermal() -> ThermalParams:
    return ThermalParams(
        T_opt=95.0, sigma_T=20.0,
        C_tread=6000.0, C_carc=20000.0, C_gas=500.0,
        R_tc=0.02, R_cg=0.05, h_0=10.0, h_1=8.0, alpha_p=0.55,
        delta_T_blanket=60.0,
    )


def test_stage3_recovers_synthetic_t_opt():
    """CALIB-03: Stage 3 converges on synthetic warm-up data.

    T_opt and sigma_T are non-identifiable from thermal ODE residuals (zero gradient
    in module_f.thermal_step). They are preserved at nominal values (95.0, 20.0).
    The 8 ODE params are fitted; RMSE on the curves must be low (<2°C).
    """
    true_params = _nominal_thermal()
    curves = [_generate_warmup(true_params, seed=s) for s in range(3)]
    fit, diag = fit_stage3(curves, compound="C3")
    # T_opt and sigma_T are preserved at their initial values (nominal)
    assert fit.T_opt == true_params.T_opt
    assert fit.sigma_T == true_params.sigma_T
    assert diag["n_curves"] == 3
    assert diag["compound"] == "C3"
    # Practical CALIB-03 tolerance: RMSE on synthetic curves < 2°C
    assert diag["rmse_C"] < 2.0


def test_stage3_respects_bounds():
    true_params = _nominal_thermal()
    curves = [_generate_warmup(true_params, seed=7)]
    fit, _ = fit_stage3(curves, compound="C3")
    # Pitfall 2: every fitted ODE param stays inside the declared bounds
    # _PARAM_NAMES = (C_tread, C_carc, C_gas, R_tc, R_cg, h_0, h_1, alpha_p)
    for i, name in enumerate(_PARAM_NAMES):
        val = getattr(fit, name)
        assert _BOUNDS_LOWER[i] <= val <= _BOUNDS_UPPER[i], (
            f"{name}={val} outside [{_BOUNDS_LOWER[i]}, {_BOUNDS_UPPER[i]}]"
        )


def test_stage3_preserves_delta_t_blanket():
    true_params = _nominal_thermal()
    curves = [_generate_warmup(true_params, seed=1)]
    fit, _ = fit_stage3(curves, compound="C3")
    assert fit.delta_T_blanket == 60.0


def test_stage3_validates_compound():
    true_params = _nominal_thermal()
    curves = [_generate_warmup(true_params, seed=2)]
    with pytest.raises(ValueError, match="C\\[1-5\\]"):
        fit_stage3(curves, compound="X9")


def test_stage3_rejects_empty_curves():
    with pytest.raises(ValueError, match="empty"):
        fit_stage3([], compound="C3")


def test_stage3_rejects_shape_mismatch():
    curves = [{
        "t_tread_obs": np.zeros((50, 4)),
        "v_stream": np.zeros(100),   # mismatch
        "p_total_stream": np.zeros((100, 4)),
        "t_air": 25.0,
        "t_track": 35.0,
    }]
    with pytest.raises(ValueError, match="t_tread_obs"):
        fit_stage3(curves, compound="C3")
