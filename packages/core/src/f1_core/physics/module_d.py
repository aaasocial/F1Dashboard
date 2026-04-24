"""Module D — Hertzian contact geometry + friction (model_spec.md §D.1–§D.5).

Sources:
  §D.1 contact geometry: Gim (1988) via Ozerem & Morrey (2019)
  §D.3 load-dep friction: Greenwood & Williamson (1966)
  §D.4 temperature dep:   Grosch (1963) + Williams–Landel–Ferry (1955)
  §D.5 complete μ:        combines D.3 and D.4

Per CONTEXT.md Pitfall 3: T_tread passed IN is from the previous timestep
(state.t_tread), NOT the current step's freshly-integrated value. The
orchestrator is responsible for calling D BEFORE F each timestep.
"""
from __future__ import annotations

import numpy as np

from f1_core.contracts import F64Array
from f1_core.physics.constants import B_TREAD_F, B_TREAD_R, R_0
from f1_core.physics.params import FrictionParams, ThermalParams

# Per-tire tread half-widths (FL, FR, RL, RR). Fronts narrower, rears wider.
_B_TREAD_PER_TIRE: F64Array = np.array(
    [B_TREAD_F, B_TREAD_F, B_TREAD_R, B_TREAD_R], dtype=np.float64
)


def contact_and_friction_step(
    f_z: F64Array,              # (4,) from Module B
    t_tread_prev: F64Array,     # (4,) from SimulationState.t_tread (prev step)
    mu_0: float,                # current reference friction from SimulationState
    params_friction: FrictionParams,
    params_thermal: ThermalParams,
) -> tuple[F64Array, F64Array, F64Array]:
    """Compute contact-patch geometry and complete friction coefficient.

    Returns:
        a_cp:  (4,) contact-patch half-length [m]           — §D.1
        p_bar: (4,) mean contact pressure [Pa]               — §D.2
        mu:    (4,) complete friction coefficient [-]        — §D.5

    Equation references (all from model_spec.md):
        §D.1: a_cp,i = √(2·R_0·F_z,i/K_rad)
        §D.2: p̄_i = F_z,i / (4·a_cp,i·b_tread)
        §D.3: μ^pressure(p̄) = μ_0·(p̄_0/p̄)^(1−n)   [Greenwood-Williamson 1966]
        §D.4: g(T) = exp(−(T−T_opt)²/(2·σ_T²))    [Grosch 1963]
        §D.5: μ_i = μ_0(t)·(p̄_0/p̄_i)^(1−n)·g(T_tread,i)
    """
    # model_spec.md §D.1 — contact patch half-length (Gim 1988)
    a_cp = np.sqrt(2.0 * R_0 * f_z / params_friction.K_rad)

    # model_spec.md §D.2 — mean Hertzian contact pressure
    p_bar = f_z / (4.0 * a_cp * _B_TREAD_PER_TIRE)

    # model_spec.md §D.3 — load-dependent friction (Greenwood-Williamson 1966)
    # exponent (1 − n); at p̄=p̄_0 this factor equals 1.0 (identity at ref pressure)
    pressure_factor = (params_friction.p_bar_0 / p_bar) ** (1.0 - params_friction.n)

    # model_spec.md §D.4 — Grosch bell-curve temperature factor; g(T_opt) = 1.0
    dT = t_tread_prev - params_thermal.T_opt
    temp_factor = np.exp(-(dT * dT) / (2.0 * params_thermal.sigma_T * params_thermal.sigma_T))

    # model_spec.md §D.5 — complete friction coefficient
    mu = mu_0 * pressure_factor * temp_factor

    return a_cp.astype(np.float64), p_bar.astype(np.float64), mu.astype(np.float64)


__all__ = ["contact_and_friction_step"]
