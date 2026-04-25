"""Parity tests: JAX rewrite must match NumPy Module G to 1e-6 (CALIB-04 correctness guard)."""
from __future__ import annotations

import math

import numpy as np
import pytest


def test_constants_match_numpy():
    """JAX constants must exactly mirror production NumPy constants."""
    from f1_core.physics.constants import DT_THERMAL, T_REF_AGING
    from f1_core.physics.module_g import ARRHENIUS_EXP_CLAMP

    from f1_calibration.jax_model import (
        ARRHENIUS_EXP_CLAMP as JAX_CLAMP,
        DT,
        T_REF_AGING as JAX_T_REF,
    )

    assert DT == DT_THERMAL
    assert JAX_CLAMP == ARRHENIUS_EXP_CLAMP
    assert JAX_T_REF == T_REF_AGING


def test_x64_enabled():
    """Pitfall 1: x64 must be on before any tracing to avoid silent divergence."""
    import jax

    from f1_calibration import jax_model  # noqa: F401 — ensure module is loaded

    assert jax.config.read("jax_enable_x64") is True


def test_simulate_mu_0_single_step_closed_form():
    """On a single step with known inputs, simulate_mu_0 must match hand-computed value."""
    from f1_calibration.jax_model import simulate_mu_0

    beta_therm, T_act, k_wear = 1e-6, 25.0, 1e-12
    mu_0_init = 1.8
    d_tread_init = np.full(4, 0.010)
    # Single step: T_tread = 100 °C uniform → arg = (100-80)/25 = 0.8
    t_tread_traj = np.full((1, 4), 100.0)
    p_slide_traj = np.full((1, 4), 5000.0)

    mu_0_traj = simulate_mu_0(
        beta_therm,
        T_act,
        k_wear,
        t_tread_traj=t_tread_traj,
        p_slide_traj=p_slide_traj,
        mu_0_init=mu_0_init,
        d_tread_init=d_tread_init,
    )
    # Hand-compute: arg = 0.8, d_mu_0_dt = -1e-6 * 1.8 * exp(0.8)
    expected = max(mu_0_init + 0.25 * (-beta_therm * mu_0_init * math.exp(0.8)), 0.0)
    assert abs(float(mu_0_traj[0]) - expected) < 1e-10, (
        f"got {mu_0_traj[0]}, want {expected}"
    )


def test_parity_with_numpy_module_g():
    """THE parity test: JAX simulate_mu_0 must match NumPy module_g.degradation_step for 200 steps."""
    from f1_core.physics.module_g import degradation_step
    from f1_core.physics.params import DegradationParams

    from f1_calibration.jax_model import simulate_mu_0

    rng = np.random.default_rng(42)
    n_steps = 200
    # Synthesize a reasonable trajectory
    t_tread_traj = 70.0 + 30.0 * rng.random((n_steps, 4))  # 70..100 °C
    p_slide_traj = np.abs(rng.normal(2000.0, 500.0, (n_steps, 4)))  # ~W
    p_total_traj = np.abs(rng.normal(10000.0, 2000.0, (n_steps, 4)))  # unused in simulate_mu_0
    beta_therm, T_act, k_wear = 2e-6, 22.0, 5e-13
    mu_0_init = 1.85
    d_tread_init = np.full(4, 0.012)

    # JAX path
    mu_0_jax = simulate_mu_0(
        beta_therm,
        T_act,
        k_wear,
        t_tread_traj=t_tread_traj,
        p_slide_traj=p_slide_traj,
        mu_0_init=mu_0_init,
        d_tread_init=d_tread_init,
    )

    # NumPy reference loop using production module_g.degradation_step
    deg_params = DegradationParams(beta_therm=beta_therm, T_act=T_act, k_wear=k_wear)
    mu_0_np = np.full(n_steps, np.nan)
    mu_0 = float(mu_0_init)
    d_tread = d_tread_init.astype(np.float64).copy()
    e_tire = np.zeros(4, dtype=np.float64)
    for i in range(n_steps):
        e_tire, mu_0, d_tread = degradation_step(
            e_tire=e_tire,
            mu_0=mu_0,
            d_tread=d_tread,
            p_total=p_total_traj[i].astype(np.float64),
            p_slide=p_slide_traj[i].astype(np.float64),
            t_tread=t_tread_traj[i].astype(np.float64),
            params=deg_params,
        )
        mu_0_np[i] = mu_0

    max_err = float(np.max(np.abs(np.asarray(mu_0_jax) - mu_0_np)))
    assert max_err < 1e-6, f"JAX/NumPy parity error {max_err} exceeds 1e-6 tolerance"


def test_parity_with_clamped_arrhenius():
    """Regression: if T_tread shoots to 1000 °C, both paths must clamp exp arg to 20."""
    from f1_core.physics.module_g import degradation_step
    from f1_core.physics.params import DegradationParams

    from f1_calibration.jax_model import simulate_mu_0

    beta_therm, T_act, k_wear = 1e-6, 25.0, 1e-12
    mu_0_init = 1.8
    d_tread_init = np.full(4, 0.010)
    t_tread_traj = np.full((10, 4), 1000.0)  # absurdly high; exp arg would be 36.8
    p_slide_traj = np.full((10, 4), 1000.0)
    p_total_traj = np.full((10, 4), 1000.0)

    mu_0_jax = simulate_mu_0(
        beta_therm,
        T_act,
        k_wear,
        t_tread_traj=t_tread_traj,
        p_slide_traj=p_slide_traj,
        mu_0_init=mu_0_init,
        d_tread_init=d_tread_init,
    )
    # NumPy reference
    deg_params = DegradationParams(beta_therm=beta_therm, T_act=T_act, k_wear=k_wear)
    mu_0 = mu_0_init
    d_tread = d_tread_init.copy()
    e_tire = np.zeros(4)
    mu_0_last_np = mu_0
    for i in range(10):
        e_tire, mu_0, d_tread = degradation_step(
            e_tire=e_tire,
            mu_0=mu_0,
            d_tread=d_tread,
            p_total=p_total_traj[i],
            p_slide=p_slide_traj[i],
            t_tread=t_tread_traj[i],
            params=deg_params,
        )
        mu_0_last_np = mu_0
    assert abs(float(mu_0_jax[-1]) - mu_0_last_np) < 1e-6


def test_log_likelihood_returns_scalar():
    """log_likelihood_f_g must return a scalar jnp array (not (N,) or tuple)."""
    import jax.numpy as jnp

    from f1_calibration.jax_model import log_likelihood_f_g

    n_steps, n_laps = 120, 6
    t_tread_traj = np.full((n_steps, 4), 90.0)
    p_slide_traj = np.full((n_steps, 4), 2000.0)
    lap_boundary_idx = np.linspace(0, n_steps, n_laps + 1, dtype=np.int64)
    obs_lap_times = np.full(n_laps, 92.0)

    ll = log_likelihood_f_g(
        1e-6,
        25.0,
        1e-12,
        0.2,
        obs_lap_times=obs_lap_times,
        lap_boundary_idx=lap_boundary_idx,
        t_tread_traj=t_tread_traj,
        p_slide_traj=p_slide_traj,
        mu_0_init=1.8,
        d_tread_init=np.full(4, 0.010),
        t_lap_ref=90.0,
    )
    # jax scalar: shape is ()
    assert jnp.ndim(ll) == 0
    assert jnp.isfinite(ll)


def test_uses_lax_scan():
    """Structural check: simulate_mu_0 must use jax.lax.scan (not Python for-loop)."""
    import inspect

    from f1_calibration import jax_model

    source = inspect.getsource(jax_model)
    assert "lax.scan(" in source, "jax_model.py must use lax.scan in simulate_mu_0"
