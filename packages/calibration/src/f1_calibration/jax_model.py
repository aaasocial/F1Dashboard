"""JAX-native Modules F + G rewrite for Stage 4 MCMC (CONTEXT D-06).

CRITICAL: this file is a PARITY COPY of
  - packages/core/src/f1_core/physics/module_f.thermal_step  (full thermal ODE)
  - packages/core/src/f1_core/physics/module_g.degradation_step  (Arrhenius + wear)
The NumPy production path in packages/core/ is untouched (D-06).

Pitfall 1: jax_enable_x64 MUST be set before any tracing to avoid silent
float32 precision divergence that corrupts Stage 4 posterior.

Pitfall 4 (from module_g): Arrhenius exponent is clamped at +/-20 to prevent
exp() overflow on runaway thermal states.

Design: because Stages 1-3 pre-compute T_tread_traj and P_slide_traj as FIXED
inputs, Stage 4 only steps mu_0 (scalar) and d_tread ((4,) per-tire). This is a
minimal 3-parameter scan — ideal for jax.lax.scan and extremely fast per MCMC
sample.
"""
from __future__ import annotations

import jax

jax.config.update("jax_enable_x64", True)  # Pitfall 1 — must be at module load

import jax.numpy as jnp
from jax import lax

# Parity constants (match packages/core/src/f1_core/physics/constants.py + module_g)
DT: float = 0.25  # DT_THERMAL — forward Euler timestep [s]
T_REF_AGING: float = 80.0  # model_spec §G.2 — reference temperature for Arrhenius [°C]
ARRHENIUS_EXP_CLAMP: float = 20.0  # module_g.ARRHENIUS_EXP_CLAMP — Pitfall 4


def simulate_mu_0(
    beta_therm: jnp.ndarray | float,
    T_act: jnp.ndarray | float,
    k_wear: jnp.ndarray | float,
    *,
    t_tread_traj: jnp.ndarray,  # (N, 4) fixed tread temperature from Stage 3 [°C]
    p_slide_traj: jnp.ndarray,  # (N, 4) fixed sliding power from Stage 3 [W]
    mu_0_init: float,
    d_tread_init: jnp.ndarray,  # (4,) initial per-tire tread thickness [m]
) -> jnp.ndarray:
    """Return (N,) mu_0 trajectory by stepping only Arrhenius aging + mechanical wear.

    Since T_tread is FIXED from Stages 1-3, we only need to step the scalar mu_0
    and per-tire d_tread. This is a 3-parameter scan — ideal for jax.lax.scan and
    extremely fast per MCMC sample (D-06 design constraint).

    Equations (equation-for-equation parity with module_g.degradation_step):
      §G.2  dmu_0/dt = -beta_therm * mu_0 * exp(clip((T_mean - T_ref) / T_act, -20, 20))
            mu_0_new = max(mu_0 + DT * dmu_0/dt, 0.0)
      §G.3  d_tread_new = max(d_tread - DT * k_wear * p_slide, 0.0)
    """
    # Cast all inputs to float64 to match x64 mode and production NumPy float64 arrays
    beta_therm = jnp.asarray(beta_therm, dtype=jnp.float64)
    T_act = jnp.asarray(T_act, dtype=jnp.float64)
    k_wear = jnp.asarray(k_wear, dtype=jnp.float64)
    t_tread_traj = jnp.asarray(t_tread_traj, dtype=jnp.float64)
    p_slide_traj = jnp.asarray(p_slide_traj, dtype=jnp.float64)
    d_tread_init = jnp.asarray(d_tread_init, dtype=jnp.float64)
    mu_0_init_j = jnp.asarray(mu_0_init, dtype=jnp.float64)

    def _step(carry, step_inputs):
        """One lax.scan step: carry = (mu_0, d_tread); inputs = (t_tread_row, p_slide_row).

        Parameters beta_therm, T_act, k_wear are closed over from the outer scope.
        This pattern is required for JAX to trace them as constants during scan.
        """
        mu_0, d_tread = carry
        t_tread_row, p_slide_row = step_inputs

        # §G.2 — Arrhenius aging on MEAN tread temperature (parity with module_g)
        t_tread_mean = jnp.mean(t_tread_row)
        arg = jnp.clip(
            (t_tread_mean - T_REF_AGING) / T_act,
            -ARRHENIUS_EXP_CLAMP,
            ARRHENIUS_EXP_CLAMP,
        )
        d_mu_0_dt = -beta_therm * mu_0 * jnp.exp(arg)
        mu_0_new = jnp.maximum(mu_0 + DT * d_mu_0_dt, 0.0)

        # §G.3 — per-tire wear, non-increasing (P_slide >= 0)
        d_tread_new = jnp.maximum(d_tread - DT * k_wear * p_slide_row, 0.0)

        new_carry = (mu_0_new, d_tread_new)
        return new_carry, mu_0_new  # emit mu_0_new at each step

    init_carry = (mu_0_init_j, d_tread_init)
    _, mu_0_traj = lax.scan(_step, init_carry, (t_tread_traj, p_slide_traj))
    return mu_0_traj  # shape (N,)


def thermal_scan(
    *,
    thermal_params: tuple,
    v_traj: jnp.ndarray,  # (N,) speed [m/s]
    t_air: float,
    p_total_traj: jnp.ndarray,  # (N, 4) total dissipated power [W]
    t0: float,  # initial tread/carcass/gas temperature [°C]
    A_tread: jnp.ndarray,  # (4,) per-tire tread convective areas [m²]
    A_carc: jnp.ndarray,  # (4,) per-tire carcass convective areas [m²]
    H_CARC: float = 5.0,
) -> jnp.ndarray:
    """Full thermal scan — optional; NOT in the Stage 4 likelihood path.

    Parity copy of module_f.thermal_step equations (§F.1–§F.7). Available for
    sanity checks or future v2 joint F+G Stage 4 experiments.

    Returns (N, 4) t_tread trajectory.
    """
    C_tread, C_carc, C_gas, R_tc, R_cg, h_0, h_1, alpha_p = thermal_params

    A_tread_j = jnp.asarray(A_tread, dtype=jnp.float64)
    A_carc_j = jnp.asarray(A_carc, dtype=jnp.float64)
    C_tread_j = jnp.asarray(C_tread, dtype=jnp.float64)
    C_carc_j = jnp.asarray(C_carc, dtype=jnp.float64)
    C_gas_j = jnp.asarray(C_gas, dtype=jnp.float64)
    R_tc_j = jnp.asarray(R_tc, dtype=jnp.float64)
    R_cg_j = jnp.asarray(R_cg, dtype=jnp.float64)
    h_0_j = jnp.asarray(h_0, dtype=jnp.float64)
    h_1_j = jnp.asarray(h_1, dtype=jnp.float64)
    alpha_p_j = jnp.asarray(alpha_p, dtype=jnp.float64)
    H_CARC_j = jnp.asarray(H_CARC, dtype=jnp.float64)
    t_air_j = jnp.asarray(t_air, dtype=jnp.float64)
    v_traj_j = jnp.asarray(v_traj, dtype=jnp.float64)
    p_total_traj_j = jnp.asarray(p_total_traj, dtype=jnp.float64)

    init_t = jnp.full((4,), t0, dtype=jnp.float64)

    def _thermal_step(carry, step_inputs):
        t_tread, t_carc, t_gas = carry
        v, p_total = step_inputs

        # §F.5 — speed-dependent convection coefficient
        v_safe = jnp.maximum(v, 0.0)
        h_air = h_0_j + h_1_j * jnp.sqrt(v_safe)

        # §F.1 — tread node
        q_heat = alpha_p_j * p_total
        q_conv_tread = h_air * A_tread_j * (t_tread - t_air_j)
        q_tc = (t_tread - t_carc) / R_tc_j
        dT_tread = (q_heat - q_conv_tread - q_tc) / C_tread_j

        # §F.2 — carcass node
        q_conv_carc = H_CARC_j * A_carc_j * (t_carc - t_air_j)
        q_cg = (t_carc - t_gas) / R_cg_j
        dT_carc = (q_tc - q_conv_carc - q_cg) / C_carc_j

        # §F.3 — gas node
        dT_gas = q_cg / C_gas_j

        # §F.7 — forward Euler
        t_tread_new = t_tread + DT * dT_tread
        t_carc_new = t_carc + DT * dT_carc
        t_gas_new = t_gas + DT * dT_gas

        new_carry = (t_tread_new, t_carc_new, t_gas_new)
        return new_carry, t_tread_new

    init_carry = (init_t, init_t, init_t)
    _, t_tread_traj = lax.scan(_thermal_step, init_carry, (v_traj_j, p_total_traj_j))
    return t_tread_traj  # (N, 4)


def log_likelihood_f_g(
    beta_therm,
    T_act,
    k_wear,
    sigma_obs,
    *,
    obs_lap_times: jnp.ndarray,  # (L,) observed per-lap times [s]
    lap_boundary_idx: jnp.ndarray,  # (L+1,) indices into (N,) mu_0 trajectory at lap starts
    t_tread_traj: jnp.ndarray,  # (N, 4)
    p_slide_traj: jnp.ndarray,  # (N, 4)
    mu_0_init: float,
    d_tread_init: jnp.ndarray,  # (4,)
    t_lap_ref: float,
) -> jnp.ndarray:
    """Per-lap Gaussian log-likelihood on lap-time predictions (model_spec §G.4).

    Stage 4 MCMC target — called from PyMC pm.Potential via pytensor Op wrapper.

    §G.4 lap-time penalty: Δt_lap = (t_ref/2) * (mu_0_init - mu_0(t)) / mu_0_init
    Predicted lap time = t_lap_ref + Δt_lap
    Log-likelihood = sum(-0.5 * ((obs - pred) / sigma_obs)^2)

    Returns a scalar jnp array (shape = ()).
    """
    sigma_obs_j = jnp.asarray(sigma_obs, dtype=jnp.float64)
    obs_lap_times_j = jnp.asarray(obs_lap_times, dtype=jnp.float64)
    mu_0_init_j = float(mu_0_init)
    t_lap_ref_j = jnp.asarray(t_lap_ref, dtype=jnp.float64)

    mu_0_traj = simulate_mu_0(
        beta_therm,
        T_act,
        k_wear,
        t_tread_traj=t_tread_traj,
        p_slide_traj=p_slide_traj,
        mu_0_init=mu_0_init_j,
        d_tread_init=d_tread_init,
    )

    # Take mu_0 at the END of each lap (last step before next lap boundary)
    # lap_boundary_idx has L+1 entries: [0, end_lap1, end_lap2, ..., N]
    end_idx = jnp.asarray(lap_boundary_idx[1:] - 1, dtype=jnp.int32)
    mu_0_end = mu_0_traj[end_idx]  # (L,)

    # §G.4 — first-order lap-time penalty from grip degradation
    pred_lap_times = (
        t_lap_ref_j
        + 0.5 * t_lap_ref_j * (mu_0_init_j - mu_0_end) / mu_0_init_j
    )

    resid = (obs_lap_times_j - pred_lap_times) / sigma_obs_j
    return jnp.sum(-0.5 * resid**2)  # scalar


__all__ = [
    "DT",
    "T_REF_AGING",
    "ARRHENIUS_EXP_CLAMP",
    "simulate_mu_0",
    "thermal_scan",
    "log_likelihood_f_g",
]
