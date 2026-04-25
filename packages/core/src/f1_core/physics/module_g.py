"""Module G — Cumulative energy + degradation (model_spec.md §G.1–§G.4).

Sources:
  §G.1 cumulative energy: Todd et al. (2025); Castellano (2021)
  §G.2 thermal aging:     Arrhenius-style; typical T_act ≈ 25°C halves/doubles
                          rate every ±25°C from T_ref
  §G.3 mechanical wear:   Wear proportional to sliding power (classical Archard-like)
  §G.4 lap-time penalty:  First-order expansion V ∝ √μ

Per CONTEXT.md §Specifics: μ_0 is a SCALAR that ages the same for all four tires.
The T_tread used in §G.2 is the MEAN tread temperature across the four tires.

Per RESEARCH.md Pitfall 4: the Arrhenius exponent is clamped to prevent
numerical overflow when T_tread drifts unreasonably high.
"""
from __future__ import annotations

import numpy as np

from f1_core.contracts import F64Array
from f1_core.physics.constants import DT_THERMAL, T_REF_AGING
from f1_core.physics.params import DegradationParams

# Pitfall 4: hard cap on the Arrhenius exponent to prevent overflow.
# exp(20) ≈ 4.9e8 — already absurd; anything larger is a numerical bug.
ARRHENIUS_EXP_CLAMP: float = 20.0


def degradation_step(
    *,
    e_tire: F64Array,           # (4,) previous cumulative tire energy [J]
    mu_0: float,                 # scalar previous reference friction
    d_tread: F64Array,          # (4,) previous tread thickness [m]
    p_total: F64Array,          # (4,) total dissipated power this step [W]
    p_slide: F64Array,          # (4,) sliding power this step [W]
    t_tread: F64Array,          # (4,) current tread temperature [°C] from Module F output
    params: DegradationParams,
) -> tuple[F64Array, float, F64Array]:
    """One forward Euler step of energy, μ_0 aging, and wear.

    Returns (e_tire_new, mu_0_new, d_tread_new).

    Equations:
      §G.1  E_tire(t+Δt) = E_tire(t) + P_total·Δt
      §G.2  dμ_0/dt     = −β_therm·μ_0·exp((T_tread_mean − T_ref)/T_act)
      §G.3  dd_tread/dt = −k_wear·P_slide
    """
    # §G.1 — per-tire cumulative energy (non-decreasing because P_total ≥ 0 from E.7)
    e_tire_new = e_tire + p_total * DT_THERMAL

    # §G.2 — μ_0 scalar ages using the MEAN tread temperature across all four tires.
    # Pitfall 4: clamp exponent to prevent exp() overflow on runaway thermal states.
    t_tread_mean = float(np.mean(t_tread))
    arg = (t_tread_mean - T_REF_AGING) / params.T_act
    arg_clamped = float(np.clip(arg, -ARRHENIUS_EXP_CLAMP, ARRHENIUS_EXP_CLAMP))
    d_mu_0_dt = -params.beta_therm * mu_0 * np.exp(arg_clamped)
    mu_0_new = mu_0 + DT_THERMAL * d_mu_0_dt
    # Safety floor: μ_0 should not go negative in physically reasonable time
    mu_0_new = max(mu_0_new, 0.0)

    # §G.3 — per-tire wear, non-increasing (P_slide ≥ 0 per E.5)
    d_tread_new = d_tread - DT_THERMAL * params.k_wear * p_slide
    # Floor wear at zero — fully worn tire
    d_tread_new = np.maximum(d_tread_new, 0.0)

    return (
        e_tire_new.astype(np.float64),
        float(mu_0_new),
        d_tread_new.astype(np.float64),
    )


def delta_t_lap(
    mu_0_fresh: float,
    mu_0_now: float,
    t_lap_ref: float,
) -> float:
    """model_spec §G.4: Δt_lap ≈ (t_ref/2)·(μ_0^fresh − μ_0(t))/μ_0^fresh.

    Args:
        mu_0_fresh: initial μ_0 at start of fresh stint
        mu_0_now:   current μ_0
        t_lap_ref:  reference fresh-tire lap time [s]
    Returns:
        predicted lap-time penalty [s] relative to fresh-tire baseline
    """
    if mu_0_fresh <= 0.0:
        return 0.0
    return 0.5 * t_lap_ref * (mu_0_fresh - mu_0_now) / mu_0_fresh


__all__ = ["ARRHENIUS_EXP_CLAMP", "degradation_step", "delta_t_lap"]
