"""Module E — Brush-model slip inversion + sliding power (model_spec.md §E.1–§E.7).

Sources:
  §E.1 cornering stiffness: Pacejka (2012), Ch. 3
  §E.2 brush model:        Pacejka (2012), Ch. 3
  §E.5 sliding power:      Kobayashi et al. (2019); Castellano et al. (2021)

Returns a SlipSample dataclass (local, per-timestep container) carrying the
slip kinematics and dissipated power per tire. The caller appends to a
shared events: list[StatusEvent] that is capped at MAX_EVENTS (Pitfall 6).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from f1_core.contracts import F64Array
from f1_core.physics.constants import C_RR
from f1_core.physics.events import MAX_EVENTS, StatusEvent
from f1_core.physics.params import FrictionParams

_TIRE_NAMES: tuple[str, ...] = ("FL", "FR", "RL", "RR")


@dataclass(frozen=True)
class SlipSample:
    """Per-timestep output of Module E (4,) arrays."""
    theta: F64Array     # brush-model slip parameter [0, 1]
    alpha: F64Array     # slip angle [rad]
    v_sy: F64Array      # lateral slip velocity [m/s]
    p_slide: F64Array   # sliding power per tire [W]
    p_rr: F64Array      # rolling-resistance power per tire [W]
    p_total: F64Array   # P_slide + P_rr [W]


def _v_sx_per_tire(v_sx_rear: float) -> F64Array:
    """Distribute V_sx across tires.

    For RWD, fronts have V_sx ≈ 0 in steady cornering; only rears carry the
    driven-wheel slip. During braking all four tires slip, but Phase 2 uses
    the kinematic rear V_sx estimate as the rear magnitude and zeros on fronts.
    This is an approximation noted in model_spec.md §A.4 last paragraph.
    """
    return np.array([0.0, 0.0, v_sx_rear, v_sx_rear], dtype=np.float64)


def slip_inversion_step(
    *,
    f_y: F64Array,             # (4,) from Module C
    f_x: F64Array,             # (4,) from Module C
    mu: F64Array,              # (4,) from Module D
    f_z: F64Array,             # (4,) from Module B
    a_cp: F64Array,            # (4,) from Module D
    v: float,                  # scalar speed
    v_sx_rear: float,          # scalar rear long slip velocity (Module A)
    t: float,                  # timestamp [s] for event timestamps
    params: FrictionParams,
    events: list[StatusEvent],  # mutable event log (capped at MAX_EVENTS)
) -> SlipSample:
    """Invert the brush model and compute dissipated power per tire.

    Equation references (model_spec.md):
        model_spec.md §E.1: C_α,i = c_py · a_cp,i²   (Pacejka 2012 Ch. 3)
        model_spec.md §E.2: Θ_i = 1 − (1 − |F_y|/(μ·F_z))^(1/3), clipped to 1 on over-demand
        model_spec.md §E.3: α_i = sgn(F_y) · arctan(3·μ·F_z·Θ / C_α)
        model_spec.md §E.4: V_sy,i = V · sin(α)
        model_spec.md §E.5: P_slide,i = |F_y|·|V_sy| + |F_x|·|V_sx|
        model_spec.md §E.6: P_rr,i   = C_RR · F_z · V
        model_spec.md §E.7: P_total  = P_slide + P_rr
    """
    # Grip capacity per tire — denominator of the brush-model ratio
    grip_capacity = mu * f_z
    # Guard against division by zero (F_z floor in Module B prevents this, but defense in depth)
    safe_grip = np.where(grip_capacity > 0, grip_capacity, 1.0)
    ratio = np.abs(f_y) / safe_grip   # (4,), >= 0

    # model_spec.md §E.2 — detect over-demand and append events (PHYS-05, Criterion 3)
    over_demand_mask = ratio > 1.0
    if over_demand_mask.any() and len(events) < MAX_EVENTS:
        # Append one event per over-demanded tire at this timestep
        for tire_idx in np.flatnonzero(over_demand_mask):
            if len(events) >= MAX_EVENTS:
                break
            events.append(StatusEvent(
                t=float(t),
                tire_index=int(tire_idx),
                kind="over_demand_lat",
                message=(
                    f"Tire {_TIRE_NAMES[tire_idx]} lateral force demand "
                    f"exceeds grip at t={t:.2f}s (ratio={float(ratio[tire_idx]):.3f})"
                ),
                ratio=float(ratio[tire_idx]),
            ))

    # model_spec.md §E.2 — Θ with clip at 1.0
    clipped_ratio = np.clip(ratio, 0.0, 1.0)
    theta = 1.0 - np.cbrt(1.0 - clipped_ratio)
    # When ratio > 1, clipped_ratio = 1, so 1 - cbrt(0) = 1 — already exact; no separate clip needed.

    # model_spec.md §E.1 — cornering stiffness per tire (Pacejka 2012)
    c_alpha = params.c_py * a_cp * a_cp

    # model_spec.md §E.3 — slip angle (guard against c_alpha=0)
    safe_c_alpha = np.where(c_alpha > 0, c_alpha, 1.0)
    alpha_mag = np.arctan(3.0 * mu * f_z * theta / safe_c_alpha)
    alpha = np.sign(f_y) * alpha_mag

    # model_spec.md §E.4 — lateral slip velocity
    v_sy = v * np.sin(alpha)

    # model_spec.md §E.5 — sliding power per tire (Kobayashi 2019, Castellano 2021)
    v_sx_per = _v_sx_per_tire(v_sx_rear)
    p_slide = np.abs(f_y) * np.abs(v_sy) + np.abs(f_x) * np.abs(v_sx_per)

    # model_spec.md §E.6 — rolling resistance
    p_rr = C_RR * f_z * v

    # model_spec.md §E.7 — total dissipated power
    p_total = p_slide + p_rr

    return SlipSample(
        theta=theta.astype(np.float64),
        alpha=alpha.astype(np.float64),
        v_sy=v_sy.astype(np.float64),
        p_slide=p_slide.astype(np.float64),
        p_rr=p_rr.astype(np.float64),
        p_total=p_total.astype(np.float64),
    )


__all__ = ["SlipSample", "slip_inversion_step"]
