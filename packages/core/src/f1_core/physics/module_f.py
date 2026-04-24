"""Module F — Thermal ODE (model_spec.md §F.1–§F.7).

Sources:
  §F.1–§F.3: Three-node lumped model — Sorniotti (2009); Farroni et al. (2015);
             Kenins et al. (2019)
  §F.4:      Heat partition α_p — Farroni et al. (2015)
  §F.5:      Speed-dependent convection — Reynolds analogy flat-plate
  §F.7:      Forward Euler, Δt = 0.25 s (per CONTEXT.md D-06)

Three coupled linear ODEs per tire, all four tires updated in one vectorized
expression. RESEARCH.md §"Pattern 2" is the canonical implementation shape.
"""
from __future__ import annotations

import numpy as np

from f1_core.contracts import F64Array
from f1_core.physics.constants import (
    A_CARC_F,
    A_CARC_R,
    A_TREAD_F,
    A_TREAD_R,
    DT_THERMAL,
    H_CARC,
)
from f1_core.physics.params import ThermalParams

# Per-tire convective areas (FL, FR, RL, RR) — fronts and rears differ.
_A_TREAD_PER_TIRE: F64Array = np.array(
    [A_TREAD_F, A_TREAD_F, A_TREAD_R, A_TREAD_R], dtype=np.float64
)
_A_CARC_PER_TIRE: F64Array = np.array(
    [A_CARC_F, A_CARC_F, A_CARC_R, A_CARC_R], dtype=np.float64
)


def thermal_step(
    *,
    t_tread: F64Array,          # (4,) previous tread temperature [°C]
    t_carc: F64Array,           # (4,) previous carcass temperature [°C]
    t_gas: F64Array,            # (4,) previous gas temperature [°C]
    p_total: F64Array,          # (4,) total dissipated power this step [W]
    v: float,                    # scalar speed [m/s]
    t_air: float,                # scalar ambient air temperature [°C]
    params: ThermalParams,
) -> tuple[F64Array, F64Array, F64Array]:
    """One forward Euler step of the three-node thermal ODE (model_spec §F.7).

    Returns (t_tread_new, t_carc_new, t_gas_new), each (4,).

    Equations (all per-tire, elementwise on (4,) arrays):
      §F.1  C_tread·dT_tread/dt = α_p·P_total
                                  − h_air(V)·A_tread·(T_tread − T_air)
                                  − (T_tread − T_carc)/R_tc
      §F.2  C_carc·dT_carc/dt   = (T_tread − T_carc)/R_tc
                                  − h_carc·A_carc·(T_carc − T_air)
                                  − (T_carc − T_gas)/R_cg
      §F.3  C_gas·dT_gas/dt     = (T_carc − T_gas)/R_cg
      §F.5  h_air(V)            = h_0 + h_1·√max(V, 0)
      §F.7  T(t+Δt)             = T(t) + Δt·Ṫ(t)
    """
    # §F.5 — convection coefficient (scalar); guard sqrt against negative/NaN v
    v_safe = max(float(v), 0.0)
    h_air = params.h_0 + params.h_1 * np.sqrt(v_safe)

    # §F.1 — tread node RHS (4,)
    q_heat = params.alpha_p * p_total
    q_conv_tread = h_air * _A_TREAD_PER_TIRE * (t_tread - t_air)
    q_tc = (t_tread - t_carc) / params.R_tc
    dT_tread = (q_heat - q_conv_tread - q_tc) / params.C_tread

    # §F.2 — carcass node RHS (4,)
    q_conv_carc = H_CARC * _A_CARC_PER_TIRE * (t_carc - t_air)
    q_cg = (t_carc - t_gas) / params.R_cg
    dT_carc = (q_tc - q_conv_carc - q_cg) / params.C_carc

    # §F.3 — gas node RHS (4,)
    dT_gas = q_cg / params.C_gas

    # §F.7 — forward Euler (Δt=0.25s)
    t_tread_new = t_tread + DT_THERMAL * dT_tread
    t_carc_new = t_carc + DT_THERMAL * dT_carc
    t_gas_new = t_gas + DT_THERMAL * dT_gas

    return (
        t_tread_new.astype(np.float64),
        t_carc_new.astype(np.float64),
        t_gas_new.astype(np.float64),
    )


__all__ = ["thermal_step"]
