"""Phase 2 orchestrator — strict A->B->C->D->E->F->G execution (PHYS-09).

One call to Module A preprocesses the full stint; then Modules B-G execute
per-timestep in the locked sequence. SimulationState is MUTABLE and carries
(t_tread, t_carc, t_gas, e_tire, mu_0, d_tread) across iterations.

model_spec.md §"Execution order at each timestep" is the authoritative
sequence. This file's docstring is the single human-readable statement of
that sequence; test_architecture.py (Plan 07) enforces that no module
bypasses this orchestrator.

Call order per timestep i (PHYS-09, strict):
  1. B: wheel_loads_step(v[i], a_lat[i], a_long[i])
  2. C: force_distribution_step(f_z, ...)
  3. D: contact_and_friction_step(f_z, state.t_tread, state.mu_0, ...)
         NOTE (Pitfall 3): D reads state.t_tread BEFORE F writes to it.
         D's input at step i equals F's output at step i-1, or the initial
         state at i=0. This is intentional — friction depends on the
         PREVIOUS step's tread temperature, not the freshly-integrated value.
  4. E: slip_inversion_step(f_y, f_x, mu, f_z, a_cp, ...)
  5. F: thermal_step(state.t_tread, ...) WRITES state.t_tread
  6. G: degradation_step(state.e_tire, state.mu_0, state.d_tread,
                         t_tread=state.t_tread [newly updated], ...)
         G's t_tread is the current step's thermally-updated value, which is
         semantically correct: Arrhenius aging and Archard wear use the
         current thermal state, not the friction-computation state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from f1_core.contracts import F64Array, SimulationState
from f1_core.ingestion.cache import StintArtifact
from f1_core.physics.defaults import make_nominal_params  # noqa: F401 — re-export for tests
from f1_core.physics.events import StatusEvent
from f1_core.physics.module_a import process_stint
from f1_core.physics.module_b import wheel_loads_step
from f1_core.physics.module_c import force_distribution_step
from f1_core.physics.module_d import contact_and_friction_step
from f1_core.physics.module_e import slip_inversion_step
from f1_core.physics.module_f import thermal_step
from f1_core.physics.module_g import degradation_step, delta_t_lap
from f1_core.physics.params import PhysicsParams


# Nominal initial tread thickness (new racing slick ~8 mm).
# model_spec.md §G.3 pairs this with k_wear for monotonic wear.
_INITIAL_D_TREAD_M: float = 0.008

# Reference lap-time fallback for model_spec.md §G.4 delta_t_lap.
# If the stint has no parseable lap times we fall back to 90 s.
_T_LAP_REF_FALLBACK_S: float = 90.0


@dataclass
class SimulationResult:
    """Full forward-simulation output.

    Per-timestep arrays are (N, 4) for tire-indexed fields, (N,) for scalars.
    """
    # Per-timestep outputs
    t: F64Array              # (N,)
    f_z: F64Array            # (N, 4)
    f_y: F64Array            # (N, 4)
    f_x: F64Array            # (N, 4)
    mu: F64Array             # (N, 4)
    t_tread: F64Array        # (N, 4)
    e_tire: F64Array         # (N, 4)
    mu_0: F64Array           # (N,)  — scalar mu_0 per timestep
    # Per-lap summary rows (list[dict])
    per_lap: list[dict[str, Any]] = field(default_factory=list)
    # Diagnostic events (capped at MAX_EVENTS)
    events: list[StatusEvent] = field(default_factory=list)

    def per_lap_rows(self) -> list[tuple[Any, ...]]:
        """Convert per-lap dicts to tuples for CLI table (D-05 column order)."""
        cols = ("Lap", "Compound", "Age", "Pred_s", "Obs_s", "Delta_s",
                "Grip_pct", "T_tread_C", "E_tire_MJ")
        return [tuple(row.get(c, "") for c in cols) for row in self.per_lap]


def _initialize_simulation_state(
    artifact: StintArtifact, params: PhysicsParams,
) -> SimulationState:
    """Build SimulationState from model_spec.md §F.6 initial conditions.

    T_tread(0) = T_carc(0) = T_gas(0) = T_track + DT_blanket.
    """
    # Fetch a track-temp estimate from weather data; fallback to 30 C.
    if not artifact.weather.empty and "TrackTemp" in artifact.weather.columns:
        t_track = float(artifact.weather["TrackTemp"].iloc[0])
    else:
        t_track = 30.0
    t_init = t_track + params.thermal.delta_T_blanket   # degC, scalar
    t_init_arr = np.full(4, t_init, dtype=np.float64)
    return SimulationState(
        t_tread=t_init_arr.copy(),
        t_carc=t_init_arr.copy(),
        t_gas=t_init_arr.copy(),
        e_tire=np.zeros(4, dtype=np.float64),
        mu_0=params.friction.mu_0_fresh,
        d_tread=np.full(4, _INITIAL_D_TREAD_M, dtype=np.float64),
    )


def _t_air_at(artifact: StintArtifact, idx: int, t_now: float) -> float:  # noqa: ARG001
    """Interpolate air temperature from weather data at current stint time."""
    if artifact.weather.empty or "AirTemp" not in artifact.weather.columns:
        return 25.0
    return float(artifact.weather["AirTemp"].iloc[0])


def _aggregate_per_lap(
    artifact: StintArtifact,
    sim_t: F64Array,
    f_z: F64Array,      # noqa: ARG001 — reserved for future per-lap load stats
    f_y: F64Array,      # noqa: ARG001 — reserved for future per-lap force stats
    t_tread: F64Array,
    e_tire: F64Array,
    mu_0: F64Array,
    mu_0_fresh: float,
) -> list[dict[str, Any]]:
    """Aggregate per-timestep arrays into per-lap summary rows for CLI output.

    Returns list of dicts with keys: Lap, Compound, Age, Pred_s, Obs_s,
    Delta_s, Grip_pct, T_tread_C, E_tire_MJ (D-05 column list).

    Implementation note: FastF1 car_data["Time"] is per-lap (resets to 0 at
    each lap boundary), so `sim_t` is non-monotonic across laps. We therefore
    partition samples using cumulative per-lap sample counts derived from the
    telemetry rate (dt = median sample interval), not by time comparison.
    """
    laps = artifact.laps
    if laps.empty:
        return []
    n_total = len(sim_t)
    rows: list[dict[str, Any]] = []

    # Pick reference lap time as the minimum observed in this stint.
    try:
        observed_times_s = laps["LapTime"].apply(
            lambda td: td.total_seconds() if hasattr(td, "total_seconds") else float(td)
        ).dropna()
    except Exception:  # noqa: BLE001
        observed_times_s = pd.Series(dtype=float)
    t_ref = float(observed_times_s.min()) if not observed_times_s.empty else _T_LAP_REF_FALLBACK_S

    # Determine per-lap sample counts using the median inter-sample interval.
    # The telemetry rate is nominally 4 Hz (dt=0.25 s), but we infer it from
    # the data to be robust to resampled fixtures.
    if n_total >= 2:
        dt_median = float(np.median(np.abs(np.diff(sim_t))))
        if dt_median <= 0 or not np.isfinite(dt_median):
            dt_median = 0.25
    else:
        dt_median = 0.25

    # Build the per-lap sample-index boundaries.
    # Each lap's sample count = round(obs_lap_time / dt_median), clamped so
    # the sum never exceeds n_total.
    sample_start = 0
    for lap_row in laps.itertuples(index=False):
        if sample_start >= n_total:
            break
        lap_time = getattr(lap_row, "LapTime", None)
        if lap_time is None or (hasattr(lap_time, "__class__") and pd.isna(lap_time)):
            obs_s = float("nan")
            lap_dur = t_ref
        else:
            try:
                obs_s = lap_time.total_seconds() if hasattr(lap_time, "total_seconds") else float(lap_time)
                lap_dur = obs_s
            except Exception:  # noqa: BLE001
                obs_s = float("nan")
                lap_dur = t_ref

        # How many samples belong to this lap?
        n_lap = max(1, round(lap_dur / dt_median))
        sample_end = min(sample_start + n_lap, n_total)
        last = sample_end - 1

        # Grip% = 100 * mu_0(end_of_lap)/mu_0_fresh
        grip_pct = 100.0 * mu_0[last] / mu_0_fresh if mu_0_fresh > 0 else 0.0
        # Predicted lap time = t_ref + delta_t_lap at end of lap
        pred_s = t_ref + delta_t_lap(mu_0_fresh, float(mu_0[last]), t_ref)
        delta_s = pred_s - obs_s if np.isfinite(obs_s) else float("nan")
        t_tread_max_c = float(np.max(t_tread[sample_start:sample_end]))
        # sum across 4 tires at last sample, J -> MJ
        e_tire_mj = float(np.sum(e_tire[last])) / 1e6
        rows.append({
            "Lap": getattr(lap_row, "LapNumber", len(rows) + 1),
            "Compound": getattr(lap_row, "Compound", ""),
            "Age": getattr(lap_row, "TyreLife", ""),
            "Pred_s": round(pred_s, 3),
            "Obs_s": round(obs_s, 3) if np.isfinite(obs_s) else "",
            "Delta_s": round(delta_s, 3) if np.isfinite(delta_s) else "",
            "Grip_pct": round(grip_pct, 1),
            "T_tread_C": round(t_tread_max_c, 1),
            "E_tire_MJ": round(e_tire_mj, 3),
        })
        sample_start = sample_end
    return rows


def run_simulation(
    artifact: StintArtifact,
    params: PhysicsParams,
) -> SimulationResult:
    """Forward-simulate a stint end-to-end — model_spec.md §"Execution order".

    Call order per timestep i (PHYS-09, strict):
      1. B: wheel_loads_step(v[i], a_lat[i], a_long[i])
      2. C: force_distribution_step(f_z, ...)
      3. D: contact_and_friction_step(f_z, state.t_tread, state.mu_0, ...)
      4. E: slip_inversion_step(f_y, f_x, mu, f_z, a_cp, ...)
      5. F: thermal_step(state.t_tread, ...)  -> WRITES state.t_tread
      6. G: degradation_step(state.e_tire, state.mu_0, state.d_tread, ...,
                             t_tread=state.t_tread [newly updated], ...)

    model_spec.md §D.5 (Pitfall 3): Module D reads state.t_tread BEFORE
    Module F writes to it. D's input at step i equals F's output at step i-1
    (or the initial state at i=0). This is intentional.
    """
    # Module A — one call, full-stint preprocessing (CONTEXT D-01)
    kstate = process_stint(artifact, params.aero)
    n = len(kstate.t)
    if n == 0:
        raise ValueError("Orchestrator: Module A produced zero samples")

    # Pre-allocate outputs — RESEARCH.md A9 (avoid per-step list appends)
    f_z_out = np.empty((n, 4), dtype=np.float64)
    f_y_out = np.empty((n, 4), dtype=np.float64)
    f_x_out = np.empty((n, 4), dtype=np.float64)
    mu_out = np.empty((n, 4), dtype=np.float64)
    t_tread_out = np.empty((n, 4), dtype=np.float64)
    e_tire_out = np.empty((n, 4), dtype=np.float64)
    mu_0_out = np.empty(n, dtype=np.float64)
    events: list[StatusEvent] = []

    # Initial state — model_spec.md §F.6
    state = _initialize_simulation_state(artifact, params)

    for i in range(n):
        v_i = float(kstate.v[i])
        a_lat_i = float(kstate.a_lat[i])
        a_long_i = float(kstate.a_long[i])
        t_i = float(kstate.t[i])

        # 1. B — vertical loads
        f_z = wheel_loads_step(
            v=v_i, a_lat=a_lat_i, a_long=a_long_i, params=params.aero,
        )

        # 2. C — force distribution
        f_y, f_x = force_distribution_step(
            f_z=f_z, v=v_i, a_lat=a_lat_i, a_long=a_long_i,
            params=params.aero,
        )

        # 3. D — contact + friction (reads PREVIOUS step's T_tread — Pitfall 3)
        a_cp, p_bar, mu = contact_and_friction_step(
            f_z=f_z,
            t_tread_prev=state.t_tread,
            mu_0=state.mu_0,
            params_friction=params.friction,
            params_thermal=params.thermal,
        )

        # 4. E — slip inversion + power + events
        slip = slip_inversion_step(
            f_y=f_y, f_x=f_x, mu=mu, f_z=f_z, a_cp=a_cp,
            v=v_i, v_sx_rear=float(kstate.v_sx_rear[i]),
            t=t_i, params=params.friction, events=events,
        )

        # 5. F — thermal update (WRITES state.t_tread for the NEXT step)
        t_air = _t_air_at(artifact, i, t_i)
        state.t_tread, state.t_carc, state.t_gas = thermal_step(
            t_tread=state.t_tread, t_carc=state.t_carc, t_gas=state.t_gas,
            p_total=slip.p_total, v=v_i, t_air=t_air,
            params=params.thermal,
        )

        # 6. G — energy + Arrhenius aging + wear
        state.e_tire, state.mu_0, state.d_tread = degradation_step(
            e_tire=state.e_tire, mu_0=state.mu_0, d_tread=state.d_tread,
            p_total=slip.p_total, p_slide=slip.p_slide,
            t_tread=state.t_tread,
            params=params.degradation,
        )

        # Record per-timestep outputs
        f_z_out[i] = f_z
        f_y_out[i] = f_y
        f_x_out[i] = f_x
        mu_out[i] = mu
        t_tread_out[i] = state.t_tread
        e_tire_out[i] = state.e_tire
        mu_0_out[i] = state.mu_0

    per_lap = _aggregate_per_lap(
        artifact, kstate.t, f_z_out, f_y_out, t_tread_out, e_tire_out,
        mu_0_out, mu_0_fresh=params.friction.mu_0_fresh,
    )

    return SimulationResult(
        t=kstate.t.copy(),
        f_z=f_z_out,
        f_y=f_y_out,
        f_x=f_x_out,
        mu=mu_out,
        t_tread=t_tread_out,
        e_tire=e_tire_out,
        mu_0=mu_0_out,
        per_lap=per_lap,
        events=events,
    )


__all__ = ["SimulationResult", "run_simulation"]
