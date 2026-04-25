"""PHYS-07 — Module G (Energy + Degradation) invariants. model_spec.md §G."""
from __future__ import annotations

import numpy as np

from f1_core.physics.constants import T_REF_AGING
from f1_core.physics.defaults import make_nominal_params
from f1_core.physics.module_f import DT_THERMAL
from f1_core.physics.module_g import (
    ARRHENIUS_EXP_CLAMP,
    degradation_step,
    delta_t_lap,
)


def test_module_g_returns_correct_shapes():
    p = make_nominal_params()
    e_tire = np.zeros(4)
    d_tread = np.full(4, 0.008)
    e_new, mu_new, d_new = degradation_step(
        e_tire=e_tire, mu_0=1.8, d_tread=d_tread,
        p_total=np.full(4, 1000.0), p_slide=np.full(4, 500.0),
        t_tread=np.full(4, T_REF_AGING),
        params=p.degradation,
    )
    assert e_new.shape == (4,)
    assert isinstance(mu_new, float)
    assert d_new.shape == (4,)


def test_module_g_e_tire_monotonically_non_decreasing():
    """model_spec §G.1 + Criterion 6: ΔE = P_total·Δt ≥ 0 for P_total ≥ 0."""
    p = make_nominal_params()
    e_tire = np.zeros(4)
    d_tread = np.full(4, 0.008)
    mu = 1.8
    for _ in range(100):
        prev = e_tire.copy()
        e_tire, mu, d_tread = degradation_step(
            e_tire=e_tire, mu_0=mu, d_tread=d_tread,
            p_total=np.full(4, 1000.0), p_slide=np.full(4, 500.0),
            t_tread=np.full(4, 90.0),
            params=p.degradation,
        )
        assert (e_tire >= prev).all(), "E_tire must be non-decreasing step-to-step"


def test_module_g_d_tread_monotonically_non_increasing():
    """model_spec §G.3 + Criterion 6: dd/dt = -k_wear·P_slide ≤ 0."""
    p = make_nominal_params()
    e_tire = np.zeros(4)
    d_tread = np.full(4, 0.008)
    mu = 1.8
    for _ in range(100):
        prev = d_tread.copy()
        e_tire, mu, d_tread = degradation_step(
            e_tire=e_tire, mu_0=mu, d_tread=d_tread,
            p_total=np.full(4, 1000.0), p_slide=np.full(4, 500.0),
            t_tread=np.full(4, 90.0),
            params=p.degradation,
        )
        assert (d_tread <= prev).all(), "d_tread must be non-increasing"


def test_module_g_e_tire_formula_verified():
    """§G.1: E(t+Δt) = E(t) + P·Δt."""
    p = make_nominal_params()
    e_tire = np.full(4, 100.0)
    p_total = np.array([1000.0, 1500.0, 2000.0, 2500.0])
    e_new, _, _ = degradation_step(
        e_tire=e_tire, mu_0=1.8, d_tread=np.full(4, 0.008),
        p_total=p_total, p_slide=np.zeros(4),
        t_tread=np.full(4, T_REF_AGING), params=p.degradation,
    )
    expected = e_tire + p_total * DT_THERMAL
    np.testing.assert_allclose(e_new, expected, rtol=1e-14)


def test_module_g_mu_0_declines_at_reference_temperature():
    """§G.2: At T_tread_mean = T_ref, dμ_0/dt = -β_therm·μ_0·exp(0) = -β_therm·μ_0."""
    p = make_nominal_params()
    mu_initial = 1.8
    _, mu_new, _ = degradation_step(
        e_tire=np.zeros(4), mu_0=mu_initial, d_tread=np.full(4, 0.008),
        p_total=np.zeros(4), p_slide=np.zeros(4),
        t_tread=np.full(4, T_REF_AGING),  # exp(0) = 1
        params=p.degradation,
    )
    expected = mu_initial + DT_THERMAL * (-p.degradation.beta_therm * mu_initial)
    assert mu_new < mu_initial
    np.testing.assert_allclose(mu_new, expected, rtol=1e-10)


def test_module_g_mu_0_declines_faster_at_high_temperature():
    """Criterion 6: sustained T_tread > T_ref drives μ_0 down faster."""
    p = make_nominal_params()
    mu_initial = 1.8
    # 1000 steps at T_ref + 4·T_act (= 180 °C with nominal T_act=25)
    mu = mu_initial
    for _ in range(1000):
        _, mu, _ = degradation_step(
            e_tire=np.zeros(4), mu_0=mu, d_tread=np.full(4, 0.008),
            p_total=np.zeros(4), p_slide=np.zeros(4),
            t_tread=np.full(4, T_REF_AGING + 4.0 * p.degradation.T_act),
            params=p.degradation,
        )
    # Should drop more than the T_ref case would
    mu_at_ref = mu_initial
    for _ in range(1000):
        _, mu_at_ref, _ = degradation_step(
            e_tire=np.zeros(4), mu_0=mu_at_ref, d_tread=np.full(4, 0.008),
            p_total=np.zeros(4), p_slide=np.zeros(4),
            t_tread=np.full(4, T_REF_AGING),
            params=p.degradation,
        )
    assert mu < mu_at_ref
    assert mu < mu_initial


def test_module_g_arrhenius_overflow_clamped():
    """Pitfall 4: T_tread → 400°C must not overflow exp()."""
    p = make_nominal_params()
    _, mu_new, _ = degradation_step(
        e_tire=np.zeros(4), mu_0=1.8, d_tread=np.full(4, 0.008),
        p_total=np.zeros(4), p_slide=np.zeros(4),
        t_tread=np.full(4, 400.0),  # way above T_ref
        params=p.degradation,
    )
    assert np.isfinite(mu_new)
    assert 0.0 <= mu_new <= 1.8   # floor applied, still finite


def test_module_g_delta_t_lap_formula():
    """model_spec §G.4: Δt_lap = (t_ref/2)·(μ^fresh - μ(t))/μ^fresh."""
    dt = delta_t_lap(mu_0_fresh=1.8, mu_0_now=1.5, t_lap_ref=90.0)
    expected = 0.5 * 90.0 * (1.8 - 1.5) / 1.8
    np.testing.assert_allclose(dt, expected, rtol=1e-14)


def test_module_g_delta_t_lap_zero_when_fresh():
    dt = delta_t_lap(mu_0_fresh=1.8, mu_0_now=1.8, t_lap_ref=90.0)
    np.testing.assert_allclose(dt, 0.0, atol=1e-14)


def test_module_g_clamp_constant_is_20():
    assert ARRHENIUS_EXP_CLAMP == 20.0
