"""Module C — Force distribution (model_spec.md §C.1–§C.3).

Source: Castellano et al. (2021), Eqs. 10–27.

Distributes total lateral + longitudinal forces proportionally to vertical
load share per tire. Brake bias scales front/rear during braking; power is
applied to rear axle only (RWD per CONTEXT.md constraints).

Per-tire index convention: 0=FL, 1=FR, 2=RL, 3=RR.
"""
from __future__ import annotations

import numpy as np

from f1_core.contracts import F64Array
from f1_core.physics.constants import M_TOT, RHO_AIR
from f1_core.physics.params import AeroParams


def force_distribution_step(
    f_z: F64Array,            # shape (4,) from Module B
    v: float,
    a_lat: float,
    a_long: float,
    params: AeroParams,
) -> tuple[F64Array, F64Array]:
    """Distribute total F_y and F_x across the four tires.

    Args:
        f_z:    (4,) per-tire vertical loads from Module B (FL/FR/RL/RR)
        v:      scalar speed [m/s]
        a_lat:  scalar lateral accel [m/s²]
        a_long: scalar long accel [m/s²]
        params: AeroParams carrying C_DA, BB

    Returns:
        (f_y, f_x): each (4,) ndarray, FL/FR/RL/RR.
        ΣF_y = M·a_lat exactly.
        ΣF_x = M·a_long − F_drag(V).

    Citations (model_spec.md):
      §C.1 total forces from Newton's 2nd law, minus drag
      §C.2 load-proportional lateral distribution (Castellano Eq. 10–14)
      §C.3 brake-bias + RWD longitudinal distribution (Castellano Eq. 15–27)
    """
    # model_spec.md §C.1 — total lateral force from Newton's 2nd law
    f_y_total = M_TOT * a_lat

    # model_spec.md §C.1 — total longitudinal force (includes aerodynamic drag subtraction)
    # F_drag = ½·ρ·C_D·A·V²  (Castellano Eq. 15)
    f_drag = 0.5 * RHO_AIR * params.C_DA * v * v
    f_x_total = M_TOT * a_long - f_drag

    # model_spec.md §C.2 — load fractions (Castellano Eq. 10)
    # Used by lateral distribution and (with axle re-split) longitudinal.
    f_z_sum = f_z.sum()
    load_frac = f_z / f_z_sum   # (4,), sums to 1.0

    # model_spec.md §C.2 — lateral force, purely load-proportional (Castellano Eq. 11–14)
    # ΣF_y = f_y_total * Σload_frac = f_y_total * 1.0 = M·a_lat  (exact identity)
    f_y = f_y_total * load_frac

    # model_spec.md §C.3 — longitudinal: brake component
    # Active when f_x_total < 0 (net deceleration including drag).
    # Front axle receives BB fraction, rear axle receives (1-BB) fraction.
    # Within each axle, split L/R by relative vertical load on that axle.
    # (Castellano Eq. 15–18)
    if f_x_total < 0.0:
        f_x_front_axle = params.BB * f_x_total         # negative (braking)
        f_x_rear_axle = (1.0 - params.BB) * f_x_total  # negative (braking)
        f_z_front_sum = f_z[0] + f_z[1]
        f_z_rear_sum = f_z[2] + f_z[3]
        if f_z_front_sum > 0.0 and f_z_rear_sum > 0.0:
            f_x_brake = np.array([
                f_x_front_axle * (f_z[0] / f_z_front_sum),  # FL
                f_x_front_axle * (f_z[1] / f_z_front_sum),  # FR
                f_x_rear_axle * (f_z[2] / f_z_rear_sum),    # RL
                f_x_rear_axle * (f_z[3] / f_z_rear_sum),    # RR
            ], dtype=np.float64)
        else:
            f_x_brake = np.zeros(4, dtype=np.float64)
    else:
        f_x_brake = np.zeros(4, dtype=np.float64)

    # model_spec.md §C.3 — longitudinal: power component (RWD)
    # Active when f_x_total > 0 (net positive thrust after drag).
    # Front tires carry zero driving force (Castellano Eq. 19–27).
    # Rear tires split by relative rear-axle load fraction.
    if f_x_total > 0.0:
        f_z_rear_sum = f_z[2] + f_z[3]
        if f_z_rear_sum > 0.0:
            f_x_power = np.array([
                0.0,                                              # FL: zero (RWD)
                0.0,                                              # FR: zero (RWD)
                f_x_total * (f_z[2] / f_z_rear_sum),             # RL
                f_x_total * (f_z[3] / f_z_rear_sum),             # RR
            ], dtype=np.float64)
        else:
            f_x_power = np.zeros(4, dtype=np.float64)
    else:
        f_x_power = np.zeros(4, dtype=np.float64)

    f_x = f_x_brake + f_x_power

    return f_y.astype(np.float64), f_x.astype(np.float64)


__all__ = ["force_distribution_step"]
