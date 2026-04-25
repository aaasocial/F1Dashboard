"""Module B — Vertical loads per tire (model_spec.md §B.1–§B.5).

Source: Castellano et al. (2021), Eqs. 1–9, with simplified elastic lateral
transfer (CONTEXT.md §Specifics) because roll-angle sensors are unavailable.

Per-tire index convention: 0=FL, 1=FR, 2=RL, 3=RR.
Sign conventions (model_spec.md §B.5):
  - a_lat > 0  → right turn, loads LEFT tires  (FL, RL)
  - a_long > 0 → acceleration,  loads REAR tires (RL, RR)

This module is pure numpy — no Python for-loop over tires. RESEARCH.md
§"Pattern 1" and PHYS-09 architecture test enforce this.
"""
from __future__ import annotations

import numpy as np

from f1_core.contracts import F64Array
from f1_core.physics.constants import G, M_TOT, RHO_AIR, T_F, T_R, WB
from f1_core.physics.params import AeroParams

# Clip floor — model_spec.md §B.5 "Floor". Prevents division-by-zero in
# Modules D/E when vertical curvature produces near-zero loads at crests.
F_Z_FLOOR_N: float = 50.0


def _wheel_loads_step_unclipped(
    v: float,
    a_lat: float,
    a_long: float,
    params: AeroParams,
) -> F64Array:
    """Per-tire F_z BEFORE the 50 N floor clip.

    Used by invariant tests where the algebraic identity
    ΣF_z = M_tot·g + F_aero must hold exactly (Pitfall 2, RESEARCH.md).
    """
    # model_spec.md §B.1 — static loads (Castellano 2021 Eq. 1)
    # Forces [N] = M·g·WD/2 per tire; WD is the front weight fraction.
    sl_f = M_TOT * G * params.WD / 2.0                  # per front tire [N]
    sl_r = M_TOT * G * (1.0 - params.WD) / 2.0          # per rear tire [N]

    # model_spec.md §B.2 — longitudinal load transfer (Castellano Eq. 3)
    # a_long > 0 → acceleration → loads rear (positive adds to rear, subtracts from front)
    dfz_long = (M_TOT * a_long * params.H_CG) / WB

    # model_spec.md §B.3 — lateral load transfer (elastic approximation)
    # Castellano's full form needs roll-angle sensors (unavailable); elastic split used.
    # a_lat > 0 → right turn → loads LEFT side tires
    k_split = params.K_rf_split  # K_rf / (K_rf + K_rr)
    dfz_lat_f = (M_TOT * a_lat * params.H_CG / T_F) * k_split
    dfz_lat_r = (M_TOT * a_lat * params.H_CG / T_R) * (1.0 - k_split)

    # model_spec.md §B.4 — aerodynamic downforce: F_z,aero = ½·ρ·C_L·A·V²
    fz_aero_total = 0.5 * RHO_AIR * params.C_LA * v * v
    fz_aero_front = params.xi * fz_aero_total         # split by aero balance ξ
    fz_aero_rear = (1.0 - params.xi) * fz_aero_total
    # model_spec.md §B.4 last sentence: within each axle, split L/R equally
    fz_aero_per_front_tire = 0.5 * fz_aero_front
    fz_aero_per_rear_tire = 0.5 * fz_aero_rear

    # model_spec.md §B.5 — per-tire vertical load assembly (Castellano Eqs. 4–9)
    f_z = np.array([
        sl_f - dfz_long + dfz_lat_f + fz_aero_per_front_tire,   # FL
        sl_f - dfz_long - dfz_lat_f + fz_aero_per_front_tire,   # FR
        sl_r + dfz_long + dfz_lat_r + fz_aero_per_rear_tire,    # RL
        sl_r + dfz_long - dfz_lat_r + fz_aero_per_rear_tire,    # RR
    ], dtype=np.float64)
    return f_z


def wheel_loads_step(
    v: float,
    a_lat: float,
    a_long: float,
    params: AeroParams,
) -> F64Array:
    """Module B step — per-tire F_z with 50 N floor (model_spec §B.5).

    Args:
        v:      scalar speed [m/s]
        a_lat:  scalar lateral accel [m/s²]  (convention: > 0 = right turn)
        a_long: scalar long. accel  [m/s²]   (convention: > 0 = accelerate)
        params: AeroParams carrying C_LA, ξ, K_rf_split, WD, H_CG

    Returns:
        (4,) ndarray, FL/FR/RL/RR order, F_z ≥ 50 N each tire.

    Note: The clip uses np.maximum which has zero gradient at F_z=50 N. If
    Phase 3 calibration needs smooth gradients, swap for softplus (Pitfall 5,
    RESEARCH.md). Phase 2 does not need smooth gradients.
    """
    f_z_raw = _wheel_loads_step_unclipped(v, a_lat, a_long, params)
    return np.maximum(f_z_raw, F_Z_FLOOR_N)


__all__ = ["F_Z_FLOOR_N", "_wheel_loads_step_unclipped", "wheel_loads_step"]
