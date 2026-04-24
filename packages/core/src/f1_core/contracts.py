"""Physics module contracts - seven typed dataclasses + PhysicsModule Protocol.

Per D-03: plain @dataclass (no Pydantic) for zero-overhead allocation in the 4 Hz hot path.
Per D-04: this module must NOT import pydantic. That lives only in packages/api/.
Per D-05: PhysicsModule is a typing.Protocol (structural subtyping). Implementations
          need not inherit; pyright enforces signatures at static-check time.

Conventions:
- Scalar-per-sample fields:  numpy array shape (N,), where N is the number of
  telemetry samples in the stint (typically ~4 Hz).
- Per-tire-per-sample fields: numpy array shape (N, 4), FL/FR/RL/RR in that order.
- All temperatures in Celsius unless stated.
- All distances/lengths in meters; forces in newtons; powers in watts; pressures in Pa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

# Type alias for readability.
F64Array = NDArray[np.float64]


# ---------------------------------------------------------------------------
# Module A output - Kinematics (model_spec section A.1-A.4)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class KinematicState:
    """Module A output. Scalar-per-sample shape (N,).

    Fields:
        t: timestamps [s]
        v: speed [m/s]
        a_lat: lateral acceleration a_lat = V^2 * kappa [m/s^2]
        a_long: longitudinal acceleration dV/dt via Savitzky-Golay [m/s^2]
        psi: heading [rad]
        v_sx_rear: rear longitudinal slip velocity [m/s]
        kappa: curvature from reference map [1/m]
    """

    t: F64Array
    v: F64Array
    a_lat: F64Array
    a_long: F64Array
    psi: F64Array
    v_sx_rear: F64Array
    kappa: F64Array


# ---------------------------------------------------------------------------
# Module B output - Vertical loads (model_spec section B)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class WheelLoads:
    """Module B output. Per-tire F_z, clipped to minimum 50 N per PHYS-02.

    Fields:
        t: timestamps [s] shape (N,)
        f_z: per-tire vertical load [N] shape (N, 4) FL/FR/RL/RR
    """

    t: F64Array
    f_z: F64Array  # shape (N, 4)


# ---------------------------------------------------------------------------
# Module D output - Hertzian contact + friction (model_spec section D)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ContactPatch:
    """Module D output. Per-tire contact patch geometry + mean pressure.

    Fields:
        t: timestamps [s] shape (N,)
        a_cp: contact-patch half-length [m] shape (N, 4)
        p_bar: mean contact pressure [Pa] shape (N, 4)
    """

    t: F64Array
    a_cp: F64Array  # shape (N, 4)
    p_bar: F64Array  # shape (N, 4)


# ---------------------------------------------------------------------------
# Module E output - Slip inversion + sliding power (model_spec section E)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SlipState:
    """Module E output. Per-tire slip kinematics + dissipated power.

    Fields (all shape (N, 4)):
        theta: normalized slip parameter theta_i = 1 - (1 - |F_y|/mu F_z)^(1/3)
        alpha: slip angle [rad]
        v_sy: lateral slip velocity [m/s]
        p_slide: sliding power [W]
        p_total: total dissipated power [W]
    """

    t: F64Array
    theta: F64Array
    alpha: F64Array
    v_sy: F64Array
    p_slide: F64Array
    p_total: F64Array


# ---------------------------------------------------------------------------
# Module F output - Thermal ODE (model_spec section F)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ThermalState:
    """Module F output. Three-node lumped thermal model per tire.

    Fields (all shape (N, 4), temperatures in Celsius):
        t_tread: tread temperature
        t_carc: carcass temperature
        t_gas: inflation gas temperature
    """

    t: F64Array
    t_tread: F64Array
    t_carc: F64Array
    t_gas: F64Array


# ---------------------------------------------------------------------------
# Module G output - Energy + degradation (model_spec section G)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DegradationState:
    """Module G output. Cumulative energy, Arrhenius-aged friction, tread wear.

    Fields:
        t: timestamps [s] shape (N,)
        e_tire: cumulative tire energy [J] shape (N, 4)
        mu_0: reference friction scalar per timestep [-] shape (N,)
        d_tread: tread thickness [m] shape (N, 4)
    """

    t: F64Array
    e_tire: F64Array  # shape (N, 4)
    mu_0: F64Array  # shape (N,) - scalar per timestep
    d_tread: F64Array  # shape (N, 4)


# ---------------------------------------------------------------------------
# PHYS-09 - SimulationState: the per-tire carryover across timesteps.
# ---------------------------------------------------------------------------
@dataclass
class SimulationState:
    """State carried across timesteps during forward integration (PHYS-09).

    All per-tire fields are shape (4,), FL/FR/RL/RR.

    Fields:
        t_tread: last-known tread temperature [degC]
        t_carc:  last-known carcass temperature [degC]
        t_gas:   last-known gas temperature [degC]
        e_tire:  cumulative energy per tire [J]
        mu_0:    current reference friction [-] (scalar)
        d_tread: current tread thickness [m]
    """

    t_tread: F64Array
    t_carc: F64Array
    t_gas: F64Array
    e_tire: F64Array
    mu_0: float
    d_tread: F64Array


# ---------------------------------------------------------------------------
# PhysicsModule Protocol - structural subtyping (D-05).
# ---------------------------------------------------------------------------
@runtime_checkable
class PhysicsModule(Protocol):
    """Every physics module (A through G) implements this shape.

    Structural typing: implementations need not inherit. pyright/mypy verify the
    signature statically; `@runtime_checkable` also allows isinstance() at runtime.

    Phase 2 modules will typically carry their own `params` dataclass and return
    a typed sub-state (KinematicState, WheelLoads, ...). The orchestrator in
    Phase 2 will call step() on each module in strict A->B->C->D->E->F->G order
    (PHYS-09), feeding the previous module's output into the next.
    """

    def step(
        self,
        state_in: SimulationState,
        telemetry_sample: object,
        params: object,
    ) -> SimulationState: ...


# ---------------------------------------------------------------------------
# Data-integrity report (DATA-05) - lives in contracts.py so Plan 04 can
# import it without cycles. It's a contract, not a physics state.
# ---------------------------------------------------------------------------
class QualityVerdict(StrEnum):
    """Per-stint data quality verdict (DATA-05).

    - OK:      quality score >= 0.9 - use freely
    - WARN:    0.7 <= score < 0.9   - simulate but flag in UI
    - EXCLUDE: 0.4 <= score < 0.7   - exclude from calibration; simulate may still run
    - REFUSE:  score < 0.4          - too broken to simulate
    """

    OK = "ok"
    WARN = "warn"
    EXCLUDE = "exclude"
    REFUSE = "refuse"


@dataclass
class QualityReport:
    """Per-stint data-quality summary (DATA-05).

    Fields:
        score: quality score in [0, 1] (1 = perfect)
        verdict: categorical verdict derived from score + hard rules
        issues: human-readable tags, e.g. "throttle_sentinels=12"
        throttle_sentinel_count: count of samples with Throttle > 100
        nan_lap_time_count: count of laps with NaN LapTime
        compound_mislabel: True if stint has within-stint compound changes or
                           matches a known-issues entry
        missing_position_pct: fraction of samples with NaN X or Y, in [0, 1]
    """

    score: float
    verdict: QualityVerdict
    issues: list[str] = field(default_factory=list[str])
    throttle_sentinel_count: int = 0
    nan_lap_time_count: int = 0
    compound_mislabel: bool = False
    missing_position_pct: float = 0.0


__all__ = [
    "ContactPatch",
    "DegradationState",
    "F64Array",
    "KinematicState",
    "PhysicsModule",
    "QualityReport",
    "QualityVerdict",
    "SimulationState",
    "SlipState",
    "ThermalState",
    "WheelLoads",
]
