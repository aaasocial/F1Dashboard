"""PHYS-04 — Module D (Hertzian contact + friction) invariants. model_spec.md §D."""
from __future__ import annotations

import numpy as np
import pytest

from f1_core.physics.constants import B_TREAD_F, B_TREAD_R, R_0
from f1_core.physics.defaults import make_nominal_params
from f1_core.physics.module_d import contact_and_friction_step


def test_module_d_returns_three_4vectors():
    p = make_nominal_params()
    f_z = np.array([5000.0, 5000.0, 6000.0, 6000.0])
    t_tread = np.full(4, p.thermal.T_opt)
    a_cp, p_bar, mu = contact_and_friction_step(
        f_z=f_z, t_tread_prev=t_tread, mu_0=p.friction.mu_0_fresh,
        params_friction=p.friction, params_thermal=p.thermal,
    )
    assert a_cp.shape == (4,) and p_bar.shape == (4,) and mu.shape == (4,)
    assert a_cp.dtype == np.float64


def test_module_d_a_cp_formula_sqrt_2_R_0_F_z_over_K_rad():
    """model_spec §D.1: a_cp,i = √(2·R_0·F_z,i/K_rad)."""
    p = make_nominal_params()
    f_z = np.array([3000.0, 4000.0, 5000.0, 6000.0])
    t_tread = np.full(4, p.thermal.T_opt)
    a_cp, _, _ = contact_and_friction_step(
        f_z=f_z, t_tread_prev=t_tread, mu_0=p.friction.mu_0_fresh,
        params_friction=p.friction, params_thermal=p.thermal,
    )
    expected = np.sqrt(2.0 * R_0 * f_z / p.friction.K_rad)
    np.testing.assert_allclose(a_cp, expected, rtol=1e-14)


def test_module_d_p_bar_formula_uses_per_tire_b_tread():
    """model_spec §D.2: p̄_i = F_z,i/(4·a_cp·b_tread); b_tread = 0.15 front, 0.20 rear."""
    p = make_nominal_params()
    f_z = np.array([5000.0, 5000.0, 5000.0, 5000.0])
    t_tread = np.full(4, p.thermal.T_opt)
    a_cp, p_bar, _ = contact_and_friction_step(
        f_z=f_z, t_tread_prev=t_tread, mu_0=p.friction.mu_0_fresh,
        params_friction=p.friction, params_thermal=p.thermal,
    )
    expected_front = 5000.0 / (4.0 * a_cp[0] * B_TREAD_F)
    expected_rear = 5000.0 / (4.0 * a_cp[2] * B_TREAD_R)
    np.testing.assert_allclose(p_bar[0], expected_front, rtol=1e-14)
    np.testing.assert_allclose(p_bar[1], expected_front, rtol=1e-14)
    np.testing.assert_allclose(p_bar[2], expected_rear, rtol=1e-14)
    np.testing.assert_allclose(p_bar[3], expected_rear, rtol=1e-14)


def test_module_d_mu_identity_at_T_opt_and_p_bar_0():
    """model_spec §D.5: μ(T_opt, p̄_0) = μ_0 exactly. PHYS-04 + Criterion 1.

    Construct f_z such that p̄ = p̄_0 on every tire, at T=T_opt.
    """
    p = make_nominal_params()
    # Solve p̄ = p̄_0:
    #   p̄_0 = f_z / (4·√(2·R_0·f_z/K_rad)·b_tread)
    #   => p̄_0 * 4 * b_tread = √(f_z) * √(2·R_0/K_rad)
    #   => f_z = (p̄_0 * 4 * b_tread)² · K_rad / (2·R_0)
    k_rad = p.friction.K_rad
    b_per = np.array([B_TREAD_F, B_TREAD_F, B_TREAD_R, B_TREAD_R])
    # Derivation: p̄ = f_z / (4·a_cp·b) and a_cp = √(2·R_0·f_z/K_rad)
    # => p̄ = √(f_z·K_rad) / (4·b·√(2·R_0))
    # => f_z = (p̄·4·b)² · 2·R_0 / K_rad
    f_z_target = (p.friction.p_bar_0 * 4.0 * b_per) ** 2 * (2.0 * R_0) / k_rad
    t_tread = np.full(4, p.thermal.T_opt)
    _, p_bar, mu = contact_and_friction_step(
        f_z=f_z_target, t_tread_prev=t_tread, mu_0=p.friction.mu_0_fresh,
        params_friction=p.friction, params_thermal=p.thermal,
    )
    # Sanity: p̄ should equal p̄_0 on every tire
    np.testing.assert_allclose(p_bar, np.full(4, p.friction.p_bar_0), rtol=1e-12)
    # Identity: μ = μ_0 exactly
    np.testing.assert_allclose(mu, np.full(4, p.friction.mu_0_fresh), rtol=1e-12)


def test_module_d_grosch_bell_returns_unity_at_T_opt():
    """model_spec §D.4: g(T_opt) = exp(0) = 1. At ref pressure μ = μ_0 · 1 · 1 = μ_0."""
    p = make_nominal_params()
    # Use high K_rad to stay near p̄_0 on nominal f_z
    f_z = np.array([5000.0] * 4)
    t_tread = np.full(4, p.thermal.T_opt)
    _, _, mu = contact_and_friction_step(
        f_z=f_z, t_tread_prev=t_tread, mu_0=1.0,
        params_friction=p.friction, params_thermal=p.thermal,
    )
    # At T_opt, temp factor is 1; mu = pressure_factor only
    _, p_bar, _ = contact_and_friction_step(
        f_z=f_z, t_tread_prev=t_tread, mu_0=1.0,
        params_friction=p.friction, params_thermal=p.thermal,
    )
    expected = (p.friction.p_bar_0 / p_bar) ** (1.0 - p.friction.n)
    np.testing.assert_allclose(mu, expected, rtol=1e-14)


def test_module_d_mu_decays_away_from_T_opt():
    """Temperature factor bell-curve: μ at T_opt + 4σ drops below 2% of peak."""
    p = make_nominal_params()
    f_z = np.full(4, 5000.0)
    t_opt = p.thermal.T_opt
    sig = p.thermal.sigma_T
    t_tread_peak = np.full(4, t_opt)
    t_tread_far = np.full(4, t_opt + 4.0 * sig)
    _, _, mu_peak = contact_and_friction_step(
        f_z=f_z, t_tread_prev=t_tread_peak, mu_0=p.friction.mu_0_fresh,
        params_friction=p.friction, params_thermal=p.thermal,
    )
    _, _, mu_far = contact_and_friction_step(
        f_z=f_z, t_tread_prev=t_tread_far, mu_0=p.friction.mu_0_fresh,
        params_friction=p.friction, params_thermal=p.thermal,
    )
    # exp(-(4σ)²/(2σ²)) = exp(-8) ≈ 3.35e-4
    assert (mu_far < 0.02 * mu_peak).all()


def test_module_d_uses_previous_t_tread_not_current():
    """Pitfall 3: Module D reads t_tread_prev; changing this argument changes the output.
    (If Module D accidentally used a current-step temperature, this test would not catch
    it directly, but the orchestrator test in Plan 06 verifies ordering. This test just
    confirms the parameter is actually consumed.)
    """
    p = make_nominal_params()
    f_z = np.full(4, 5000.0)
    _, _, mu_opt = contact_and_friction_step(
        f_z=f_z, t_tread_prev=np.full(4, p.thermal.T_opt),
        mu_0=p.friction.mu_0_fresh,
        params_friction=p.friction, params_thermal=p.thermal,
    )
    _, _, mu_cold = contact_and_friction_step(
        f_z=f_z, t_tread_prev=np.full(4, p.thermal.T_opt - 40.0),
        mu_0=p.friction.mu_0_fresh,
        params_friction=p.friction, params_thermal=p.thermal,
    )
    assert mu_cold[0] < mu_opt[0], "cold tread must give lower μ than at T_opt"
