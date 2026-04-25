"""Stage 1 aero fit accuracy on synthetic data (CALIB-01: ±10% C_LA, ±15% C_DA)."""
from __future__ import annotations
import numpy as np
import pytest
from f1_calibration.stage1_aero import fit_stage1


def _synthetic_corner_data(c_la_true: float, seed: int = 0):
    rng = np.random.default_rng(seed)
    # 10 corners at realistic F1 speeds (40–70 m/s ≈ 150–250 km/h)
    v = np.linspace(40.0, 70.0, 10)
    M_total = 838.0
    mu_grip = 1.8
    rho, g = 1.20, 9.81
    F_aero = 0.5 * rho * c_la_true * v ** 2
    lat_g_clean = mu_grip * (g * M_total + F_aero) / (g * M_total)
    # Tiny noise (~1%) to simulate measurement jitter
    noise = rng.normal(0, 0.02, v.size)
    return lat_g_clean + noise, v, M_total


def test_stage1_recovers_synthetic_c_la():
    c_la_true = 5.0
    obs, v, M = _synthetic_corner_data(c_la_true, seed=1)
    params, diag = fit_stage1(obs, v, M_total=M)
    rel_err = abs(params.C_LA - c_la_true) / c_la_true
    assert rel_err < 0.10, f"C_LA {params.C_LA} off from {c_la_true} by {rel_err:.1%}"
    assert diag["n_corners"] == 10
    assert diag["rmse"] < 0.5


def test_stage1_preserves_nominal_semi_constrained():
    obs, v, M = _synthetic_corner_data(c_la_true=4.5)
    params, _ = fit_stage1(obs, v, M_total=M)
    assert params.K_rf_split == 0.55
    assert params.WD == 0.445
    assert params.H_CG == 0.28
    assert params.BB == 0.575


def test_stage1_respects_bounds():
    # Synthetic data that would drive C_LA >> 7 without bounds
    v = np.linspace(50.0, 80.0, 10)
    obs = np.full_like(v, 5.0)  # unrealistic lat g
    params, _ = fit_stage1(obs, v, M_total=838.0)
    assert 3.0 <= params.C_LA <= 7.0
    assert 0.8 <= params.C_DA <= 1.8
    assert 0.40 <= params.xi <= 0.50


def test_stage1_rejects_shape_mismatch():
    with pytest.raises(ValueError, match="shape mismatch"):
        fit_stage1(np.array([1.0, 2.0, 3.0]), np.array([40.0, 50.0]), M_total=838.0)


def test_stage1_rejects_too_few_corners():
    with pytest.raises(ValueError, match="at least 3"):
        fit_stage1(np.array([1.5, 1.6]), np.array([40.0, 50.0]), M_total=838.0)
