---
phase: 02-physics-model-modules-a-g
plan: 06
type: execute
wave: 2
depends_on: [02, 03, 04, 05]
files_modified:
  - packages/core/src/f1_core/physics/orchestrator.py
  - packages/core/src/f1_core/physics/cli.py
  - packages/core/tests/physics/test_orchestrator.py
  - packages/core/tests/physics/test_cli.py
autonomous: true
requirements: [PHYS-08, PHYS-09]
tags: [physics, orchestrator, cli]

must_haves:
  truths:
    - "run_simulation(artifact, params) calls Module A once, then Modules B→C→D→E→F→G per timestep in that exact order"
    - "SimulationState carries (t_tread, t_carc, t_gas, e_tire, mu_0, d_tread) across timesteps, updated in place (mutable)"
    - "Module D reads state.t_tread BEFORE Module F writes to it (Pitfall 3, §D.5)"
    - "run_simulation returns a SimulationResult with per-timestep (N, 4) arrays of f_z, f_y, mu, t_tread, e_tire; per-lap rows; events; per-stint mu_0 history"
    - "f1-simulate CLI loads the canonical stint via load_stint, runs run_simulation, prints a Rich table, exits 0 on success"
    - "CLI exits code 2 on FastF1/load errors, code 3 on physics errors"
  artifacts:
    - path: "packages/core/src/f1_core/physics/orchestrator.py"
      provides: "SimulationResult dataclass + run_simulation(artifact, params) + _initialize_simulation_state + _aggregate_per_lap"
      exports: ["SimulationResult", "run_simulation"]
      min_lines: 150
    - path: "packages/core/src/f1_core/physics/cli.py"
      provides: "Typer app callable via 'f1-simulate YEAR EVENT DRIVER STINT'"
      exports: ["app", "simulate"]
  key_links:
    - from: "packages/core/src/f1_core/physics/orchestrator.py"
      to: "f1_core.physics.module_a.process_stint"
      via: "import + single call at top of run_simulation"
      pattern: "process_stint"
    - from: "packages/core/src/f1_core/physics/orchestrator.py"
      to: "all module_b..g step functions"
      via: "import + per-timestep call in strict order"
      pattern: "wheel_loads_step|force_distribution_step|contact_and_friction_step|slip_inversion_step|thermal_step|degradation_step"
    - from: "packages/core/src/f1_core/physics/cli.py"
      to: "f1_core.ingestion.fastf1_client.load_stint"
      via: "import + single call with positional args"
      pattern: "load_stint"
    - from: "packages/core/pyproject.toml"
      to: "packages/core/src/f1_core/physics/cli.py"
      via: "[project.scripts] f1-simulate = f1_core.physics.cli:app"
      pattern: "f1-simulate"
---

<objective>
Wire Modules A–G into a single `run_simulation` orchestrator that enforces the strict A→B→C→D→E→F→G execution order per timestep (PHYS-09), carries SimulationState across iterations, and produces per-lap summary rows for CLI output. Implement the Typer CLI (`f1-simulate`) as the user-facing entry point per CONTEXT.md D-05.

This plan satisfies PHYS-08 (invariant tests pass through the full pipeline) and PHYS-09 (strict sequence + state-object carry). It is the Wave 2 convergence of Plans 02–05.

Output: Working orchestrator + working CLI + real test files for both.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/02-physics-model-modules-a-g/02-CONTEXT.md
@.planning/phases/02-physics-model-modules-a-g/02-RESEARCH.md
@model_spec.md
@packages/core/src/f1_core/contracts.py
@packages/core/src/f1_core/physics/module_a.py
@packages/core/src/f1_core/physics/module_b.py
@packages/core/src/f1_core/physics/module_c.py
@packages/core/src/f1_core/physics/module_d.py
@packages/core/src/f1_core/physics/module_e.py
@packages/core/src/f1_core/physics/module_f.py
@packages/core/src/f1_core/physics/module_g.py
@packages/core/src/f1_core/ingestion/fastf1_client.py

<interfaces>
<!-- All Phase 2 module signatures the orchestrator must call. -->

Module A (Plan 02):
```python
def process_stint(artifact: StintArtifact, aero_params: AeroParams) -> KinematicState: ...
```

Module B (Plan 03):
```python
def wheel_loads_step(v: float, a_lat: float, a_long: float, params: AeroParams) -> F64Array: ...
```

Module C (Plan 03):
```python
def force_distribution_step(
    f_z: F64Array, v: float, a_lat: float, a_long: float, params: AeroParams,
) -> tuple[F64Array, F64Array]: ...
```

Module D (Plan 04):
```python
def contact_and_friction_step(
    f_z: F64Array, t_tread_prev: F64Array, mu_0: float,
    params_friction: FrictionParams, params_thermal: ThermalParams,
) -> tuple[F64Array, F64Array, F64Array]:  # a_cp, p_bar, mu
    ...
```

Module E (Plan 04):
```python
def slip_inversion_step(
    *, f_y, f_x, mu, f_z, a_cp, v, v_sx_rear, t,
    params: FrictionParams, events: list[StatusEvent],
) -> SlipSample: ...
```

Module F (Plan 05):
```python
DT_THERMAL: float = 0.25

def thermal_step(
    *, t_tread, t_carc, t_gas, p_total, v, t_air, params: ThermalParams,
) -> tuple[F64Array, F64Array, F64Array]: ...
```

Module G (Plan 05):
```python
def degradation_step(
    *, e_tire, mu_0, d_tread, p_total, p_slide, t_tread,
    params: DegradationParams,
) -> tuple[F64Array, float, F64Array]: ...

def delta_t_lap(mu_0_fresh: float, mu_0_now: float, t_lap_ref: float) -> float: ...
```

From f1_core.contracts (mutable for carryover):
```python
@dataclass
class SimulationState:
    t_tread: F64Array; t_carc: F64Array; t_gas: F64Array
    e_tire: F64Array; mu_0: float; d_tread: F64Array
```

From f1_core.ingestion.fastf1_client:
```python
def load_stint(*, year: int, event: str, session_type: str = "R",
               driver_code: str, stint_index: int,
               cache_root: Path | None = None) -> StintArtifact: ...
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement orchestrator with strict-order execution and state carry</name>
  <files>
    packages/core/src/f1_core/physics/orchestrator.py,
    packages/core/tests/physics/test_orchestrator.py
  </files>
  <read_first>
    - model_spec.md §"Execution order at each timestep" (authoritative step sequence)
    - packages/core/src/f1_core/contracts.py (SimulationState — mutable)
    - .planning/phases/02-physics-model-modules-a-g/02-RESEARCH.md §"Pattern 4" + §"Orchestrator loop skeleton"
    - packages/core/src/f1_core/physics/module_a.py (process_stint signature — Plan 02 output)
    - All module_b.py through module_g.py (signatures from Plans 03, 04, 05)
  </read_first>
  <behavior>
    - Test 1: `run_simulation(canonical_stint_artifact, make_nominal_params())` returns a SimulationResult with non-empty per-lap rows
    - Test 2: Execution order — monkeypatch each module's step function to append its letter to a call log; after run_simulation, assert log[0]=='A' and the pattern ['B','C','D','E','F','G'] repeats N times
    - Test 3: Module D reads OLD t_tread, not current — inject a spy on Module D capturing t_tread_prev; assert Module F's output is NOT used by the same-timestep Module D (D's input at step i equals F's output at step i-1, or the initial state for i=0)
    - Test 4: SimulationState mutates across steps (mu_0 at end of first step != initial mu_0_fresh for non-zero beta_therm · mu_0 · 0.25 s)
    - Test 5: Per-lap rows have columns Lap, Compound, Age, Pred_s, Obs_s, Delta_s, Grip_pct, T_tread_C, E_tire_MJ
    - Test 6: `events` list cap holds (MAX_EVENTS=500) — run on canonical fixture, assert len(result.events) ≤ 500
  </behavior>
  <action>
    Create `packages/core/src/f1_core/physics/orchestrator.py`:

    ```python
    """Phase 2 orchestrator — strict A→B→C→D→E→F→G execution (PHYS-09).

    One call to Module A preprocesses the full stint; then Modules B–G execute
    per-timestep in the locked sequence. SimulationState is MUTABLE and carries
    (t_tread, t_carc, t_gas, e_tire, mu_0, d_tread) across iterations.

    model_spec.md §"Execution order at each timestep" is the authoritative
    sequence. This file's docstring is the single human-readable statement of
    that sequence; test_architecture.py (Plan 07) enforces that no module
    bypasses this orchestrator.
    """
    from __future__ import annotations

    from dataclasses import dataclass, field
    from typing import Any

    import numpy as np
    import pandas as pd

    from f1_core.contracts import F64Array, SimulationState
    from f1_core.ingestion.cache import StintArtifact
    from f1_core.physics.defaults import make_nominal_params
    from f1_core.physics.events import StatusEvent
    from f1_core.physics.module_a import process_stint
    from f1_core.physics.module_b import wheel_loads_step
    from f1_core.physics.module_c import force_distribution_step
    from f1_core.physics.module_d import contact_and_friction_step
    from f1_core.physics.module_e import slip_inversion_step
    from f1_core.physics.module_f import DT_THERMAL, thermal_step
    from f1_core.physics.module_g import degradation_step, delta_t_lap
    from f1_core.physics.params import PhysicsParams


    # Nominal initial tread thickness (new racing slick ≈ 8 mm).
    # model_spec.md §G.3 pairs this with k_wear for monotonic wear.
    _INITIAL_D_TREAD_M: float = 0.008

    # Reference lap-time for §G.4 Δt_lap. For Phase 2 we pick the fastest
    # observed lap in the stint as "t_ref"; calibration will refine in Phase 3.
    # If the stint has no parseable lap times, we fall back to 90 s.
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
        mu_0: F64Array           # (N,)  — scalar μ_0 per timestep
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

        T_tread(0) = T_carc(0) = T_gas(0) = T_track + ΔT_blanket.
        """
        # Fetch a track-temp estimate from weather data; fallback to 30°C.
        if not artifact.weather.empty and "TrackTemp" in artifact.weather.columns:
            t_track = float(artifact.weather["TrackTemp"].iloc[0])
        else:
            t_track = 30.0
        t_init = t_track + params.thermal.delta_T_blanket   # °C, (4,)
        t_init_arr = np.full(4, t_init, dtype=np.float64)
        return SimulationState(
            t_tread=t_init_arr.copy(),
            t_carc=t_init_arr.copy(),
            t_gas=t_init_arr.copy(),
            e_tire=np.zeros(4, dtype=np.float64),
            mu_0=params.friction.mu_0_fresh,
            d_tread=np.full(4, _INITIAL_D_TREAD_M, dtype=np.float64),
        )


    def _t_air_at(artifact: StintArtifact, idx: int, t_now: float) -> float:
        """Interpolate air temperature from weather data at current stint time."""
        if artifact.weather.empty or "AirTemp" not in artifact.weather.columns:
            return 25.0
        return float(artifact.weather["AirTemp"].iloc[0])


    def _aggregate_per_lap(
        artifact: StintArtifact,
        sim_t: F64Array,
        f_z: F64Array,
        f_y: F64Array,
        t_tread: F64Array,
        e_tire: F64Array,
        mu_0: F64Array,
        mu_0_fresh: float,
    ) -> list[dict[str, Any]]:
        """Aggregate per-timestep arrays into per-lap summary rows for CLI output.

        Returns list of dicts with keys: Lap, Compound, Age, Pred_s, Obs_s,
        Delta_s, Grip_pct, T_tread_C, E_tire_MJ (D-05 column list).
        """
        laps = artifact.laps
        if laps.empty:
            return []
        rows: list[dict[str, Any]] = []
        # Use simulation timestamps re-based at 0
        sim_t_rel = sim_t - sim_t[0] if len(sim_t) > 0 else sim_t

        # Pick reference lap time as the minimum observed in this stint
        try:
            observed_times_s = laps["LapTime"].apply(
                lambda td: td.total_seconds() if hasattr(td, "total_seconds") else float(td)
            ).dropna()
        except Exception:
            observed_times_s = pd.Series(dtype=float)
        t_ref = float(observed_times_s.min()) if not observed_times_s.empty else _T_LAP_REF_FALLBACK_S

        # Determine per-lap index ranges from cumulative lap times.
        # Each lap's end time (in seconds) relative to stint start.
        cum_time_s = 0.0
        prev_idx = 0
        for lap_row in laps.itertuples(index=False):
            lap_time = getattr(lap_row, "LapTime", None)
            if lap_time is None or pd.isna(lap_time):
                obs_s = float("nan")
                lap_dur = t_ref
            else:
                obs_s = lap_time.total_seconds() if hasattr(lap_time, "total_seconds") else float(lap_time)
                lap_dur = obs_s
            cum_time_s += lap_dur
            # Samples in this lap = sim_t_rel ∈ (prev_end, cum_time_s]
            mask = (sim_t_rel > cum_time_s - lap_dur) & (sim_t_rel <= cum_time_s)
            idx = np.flatnonzero(mask)
            if idx.size == 0:
                continue
            last = idx[-1]
            # Grip% = 100·μ_0(end_of_lap)/μ_0^fresh
            grip_pct = 100.0 * mu_0[last] / mu_0_fresh if mu_0_fresh > 0 else 0.0
            # Predicted lap time = t_ref + Δt_lap at end of lap
            pred_s = t_ref + delta_t_lap(mu_0_fresh, float(mu_0[last]), t_ref)
            delta_s = pred_s - obs_s if np.isfinite(obs_s) else float("nan")
            t_tread_max_C = float(np.max(t_tread[idx]))
            e_tire_mj = float(np.sum(e_tire[last])) / 1e6   # sum across 4 tires, J → MJ
            rows.append({
                "Lap": getattr(lap_row, "LapNumber", len(rows) + 1),
                "Compound": getattr(lap_row, "Compound", ""),
                "Age": getattr(lap_row, "TyreLife", ""),
                "Pred_s": round(pred_s, 3),
                "Obs_s": round(obs_s, 3) if np.isfinite(obs_s) else "",
                "Delta_s": round(delta_s, 3) if np.isfinite(delta_s) else "",
                "Grip_pct": round(grip_pct, 1),
                "T_tread_C": round(t_tread_max_C, 1),
                "E_tire_MJ": round(e_tire_mj, 3),
            })
            prev_idx = last + 1
        return rows


    def run_simulation(
        artifact: StintArtifact,
        params: PhysicsParams,
    ) -> SimulationResult:
        """Forward-simulate a stint end-to-end — model_spec §"Execution order".

        Call order per timestep i (PHYS-09, strict):
          1. B: wheel_loads_step(v[i], a_lat[i], a_long[i])
          2. C: force_distribution_step(f_z, ...)
          3. D: contact_and_friction_step(f_z, state.t_tread, state.mu_0, ...)
          4. E: slip_inversion_step(f_y, f_x, mu, f_z, a_cp, ...)
          5. F: thermal_step(state.t_tread, ..., p_total, ...)  → WRITES state.t_tread
          6. G: degradation_step(state.e_tire, state.mu_0, state.d_tread, ...,
                                 t_tread=state.t_tread [newly updated], ...)

        Note: F writes state.t_tread before G reads it (G's t_tread is the
        CURRENT step's, which is semantically fine because G uses the mean for
        Arrhenius aging, not for friction computation — the causal dependency
        is D's μ using the PREVIOUS T_tread).
        """
        # Module A — one call, full-stint preprocessing (CONTEXT D-01)
        kstate = process_stint(artifact, params.aero)
        n = len(kstate.t)
        if n == 0:
            raise ValueError("Orchestrator: Module A produced zero samples")

        # Pre-allocate outputs — RESEARCH.md A9
        f_z_out = np.empty((n, 4), dtype=np.float64)
        f_y_out = np.empty((n, 4), dtype=np.float64)
        f_x_out = np.empty((n, 4), dtype=np.float64)
        mu_out = np.empty((n, 4), dtype=np.float64)
        t_tread_out = np.empty((n, 4), dtype=np.float64)
        e_tire_out = np.empty((n, 4), dtype=np.float64)
        mu_0_out = np.empty(n, dtype=np.float64)
        events: list[StatusEvent] = []

        # Initial state — model_spec §F.6
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
    ```

    Now rewrite `packages/core/tests/physics/test_orchestrator.py`:

    ```python
    """PHYS-08, PHYS-09 — Orchestrator execution order and state carry."""
    from __future__ import annotations

    import numpy as np
    import pytest

    from f1_core.physics.events import MAX_EVENTS
    from f1_core.physics.orchestrator import SimulationResult, run_simulation


    def test_orchestrator_runs_on_canonical_fixture(canonical_stint_artifact, nominal_params):
        result = run_simulation(canonical_stint_artifact, nominal_params)
        assert isinstance(result, SimulationResult)
        assert len(result.per_lap) >= 1


    def test_orchestrator_per_timestep_array_shapes(canonical_stint_artifact, nominal_params):
        result = run_simulation(canonical_stint_artifact, nominal_params)
        n = len(result.t)
        assert result.f_z.shape == (n, 4)
        assert result.f_y.shape == (n, 4)
        assert result.mu.shape == (n, 4)
        assert result.t_tread.shape == (n, 4)
        assert result.e_tire.shape == (n, 4)
        assert result.mu_0.shape == (n,)


    def test_orchestrator_strict_execution_order(
        canonical_stint_artifact, nominal_params, monkeypatch,
    ):
        """PHYS-09: Module A once, then B→C→D→E→F→G repeated per timestep."""
        call_log: list[str] = []

        # Wrap each module's step function to record its letter
        from f1_core.physics import orchestrator as orch
        orig_a = orch.process_stint
        orig_b = orch.wheel_loads_step
        orig_c = orch.force_distribution_step
        orig_d = orch.contact_and_friction_step
        orig_e = orch.slip_inversion_step
        orig_f = orch.thermal_step
        orig_g = orch.degradation_step

        def wrap(letter, fn):
            def w(*args, **kw):
                call_log.append(letter)
                return fn(*args, **kw)
            return w

        monkeypatch.setattr(orch, "process_stint", wrap("A", orig_a))
        monkeypatch.setattr(orch, "wheel_loads_step", wrap("B", orig_b))
        monkeypatch.setattr(orch, "force_distribution_step", wrap("C", orig_c))
        monkeypatch.setattr(orch, "contact_and_friction_step", wrap("D", orig_d))
        monkeypatch.setattr(orch, "slip_inversion_step", wrap("E", orig_e))
        monkeypatch.setattr(orch, "thermal_step", wrap("F", orig_f))
        monkeypatch.setattr(orch, "degradation_step", wrap("G", orig_g))

        result = run_simulation(canonical_stint_artifact, nominal_params)

        assert call_log[0] == "A", "Module A must be the first call"
        # Remaining calls are groups of six B→C→D→E→F→G
        rest = call_log[1:]
        assert len(rest) % 6 == 0
        stride = ["B", "C", "D", "E", "F", "G"]
        for i in range(0, len(rest), 6):
            assert rest[i:i + 6] == stride, f"Execution out of order at step {i // 6}"


    def test_orchestrator_simulation_state_carries_across_steps(
        canonical_stint_artifact, nominal_params,
    ):
        """State carryover — mu_0 should change from initial after first timestep."""
        result = run_simulation(canonical_stint_artifact, nominal_params)
        # mu_0 at step 0 should be slightly lower than mu_0_fresh due to
        # β_therm·μ_0·Δt aging even at T_ref.
        assert result.mu_0[0] < nominal_params.friction.mu_0_fresh
        # And the trajectory should be monotonically non-increasing.
        assert np.all(np.diff(result.mu_0) <= 1e-15)


    def test_orchestrator_per_lap_rows_have_required_columns(
        canonical_stint_artifact, nominal_params,
    ):
        """D-05 column set."""
        result = run_simulation(canonical_stint_artifact, nominal_params)
        assert len(result.per_lap) > 0
        required = {"Lap", "Compound", "Age", "Pred_s", "Obs_s", "Delta_s",
                    "Grip_pct", "T_tread_C", "E_tire_MJ"}
        for row in result.per_lap:
            assert required.issubset(set(row.keys()))


    def test_orchestrator_events_capped(canonical_stint_artifact, nominal_params):
        """Pitfall 6: events list never exceeds MAX_EVENTS."""
        result = run_simulation(canonical_stint_artifact, nominal_params)
        assert len(result.events) <= MAX_EVENTS


    def test_orchestrator_e_tire_monotonic_on_real_stint(
        canonical_stint_artifact, nominal_params,
    ):
        """PHYS-07 / Criterion 6 through the full pipeline, not just Module G unit."""
        result = run_simulation(canonical_stint_artifact, nominal_params)
        # Cumulative energy per tire must never decrease step-to-step
        for tire in range(4):
            diffs = np.diff(result.e_tire[:, tire])
            assert (diffs >= -1e-9).all(), f"E_tire non-monotonic on tire {tire}"
    ```
  </action>
  <verify>
    <automated>uv run pytest packages/core/tests/physics/test_orchestrator.py -x --benchmark-disable</automated>
  </verify>
  <acceptance_criteria>
    - `uv run pytest packages/core/tests/physics/test_orchestrator.py -x --benchmark-disable` exits 0 with 7 tests passing
    - `grep -c "model_spec.md" packages/core/src/f1_core/physics/orchestrator.py` returns at least 3 references
    - Execution order test `test_orchestrator_strict_execution_order` passes (proves PHYS-09 strict sequence)
    - `grep -q "pytest.skip" packages/core/tests/physics/test_orchestrator.py` returns NO matches
    - `uv run python -c "from f1_core.physics.orchestrator import run_simulation, SimulationResult; print('OK')"` exits 0
  </acceptance_criteria>
  <done>Orchestrator runs full A→G pipeline; PHYS-09 execution order enforced + tested; state carryover verified; per-lap rows generated.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement f1-simulate Typer CLI with Rich table output</name>
  <files>
    packages/core/src/f1_core/physics/cli.py,
    packages/core/tests/physics/test_cli.py
  </files>
  <read_first>
    - .planning/phases/02-physics-model-modules-a-g/02-CONTEXT.md D-05 (CLI shape + columns)
    - .planning/phases/02-physics-model-modules-a-g/02-RESEARCH.md §"Typer CLI entry point" (code example)
    - packages/core/src/f1_core/ingestion/fastf1_client.py (load_stint signature + raises)
    - packages/core/src/f1_core/physics/orchestrator.py (run_simulation — Task 1 output)
    - packages/core/pyproject.toml (verify [project.scripts] entry from Plan 01)
  </read_first>
  <behavior>
    - Test 1: `CliRunner().invoke(app, ["2023", "Bahrain", "VER", "2"])` on a canonical fixture mock exits 0 and stdout contains "Lap", "Compound", "Pred_s"
    - Test 2: Invalid driver code (e.g., "VE1" — 3 chars but not all uppercase letters) triggers validate_driver_code inside load_stint, which raises ValueError; CLI exits code 2
    - Test 3: load_stint raising any exception produces exit code 2 (data loading errors)
    - Test 4: run_simulation raising any exception produces exit code 3 (physics errors)
    - Test 5: With missing stint (stint_index=99 that has no laps) → load_stint ValueError → CLI exit code 2
  </behavior>
  <action>
    Create `packages/core/src/f1_core/physics/cli.py`:

    ```python
    """f1-simulate CLI entry point (CONTEXT D-05, RESEARCH.md §Typer code example).

    Invocation: `f1-simulate <year> <event> <driver> <stint_index>`
    Example:    `f1-simulate 2023 Bahrain VER 2`

    Exit codes (CONTEXT D-05):
      0  success
      2  FastF1 / load_stint error (data availability, validation)
      3  physics / orchestrator error (numerical issues)
    """
    from __future__ import annotations

    import typer
    from rich.console import Console
    from rich.table import Table

    from f1_core.ingestion.fastf1_client import load_stint
    from f1_core.physics.defaults import make_nominal_params
    from f1_core.physics.orchestrator import run_simulation

    app = typer.Typer(add_completion=False, no_args_is_help=True)
    console = Console()


    @app.command()
    def simulate(
        year: int = typer.Argument(..., help="Season year, e.g. 2023"),
        event: str = typer.Argument(..., help="Event name (substring match), e.g. 'Bahrain'"),
        driver: str = typer.Argument(..., help="3-letter driver code, e.g. 'VER'"),
        stint_index: int = typer.Argument(..., help="1-indexed stint number within the race"),
    ) -> None:
        """Simulate a real stint with nominal physics parameters and print a per-lap table."""
        try:
            artifact = load_stint(
                year=year,
                event=event,
                driver_code=driver,
                stint_index=stint_index,
            )
        except Exception as exc:   # noqa: BLE001 — CLI boundary
            console.print(f"[red]Error loading stint:[/red] {exc}")
            raise typer.Exit(code=2)

        try:
            result = run_simulation(artifact, make_nominal_params())
        except Exception as exc:   # noqa: BLE001 — CLI boundary
            console.print(f"[red]Simulation failed:[/red] {exc}")
            raise typer.Exit(code=3)

        table = Table(title=f"{year} {event} {driver} stint {stint_index}")
        for col in ("Lap", "Compound", "Age", "Pred(s)", "Obs(s)", "Δ(s)",
                    "Grip%", "T_tread(°C)", "E_tire(MJ)"):
            table.add_column(col, justify="right")
        for row in result.per_lap_rows():
            table.add_row(*[str(x) for x in row])
        console.print(table)
        console.print(f"\n[dim]Events logged: {len(result.events)}[/dim]")


    if __name__ == "__main__":
        app()


    __all__ = ["app", "simulate"]
    ```

    Now rewrite `packages/core/tests/physics/test_cli.py`:

    ```python
    """D-05 — f1-simulate CLI integration. Uses Typer's CliRunner."""
    from __future__ import annotations

    from unittest.mock import patch

    import pytest
    from typer.testing import CliRunner

    from f1_core.physics.cli import app

    runner = CliRunner()


    def test_cli_help_runs():
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0


    def test_cli_success_on_canonical_fixture(canonical_stint_artifact):
        """Happy path: load_stint returns the canonical fixture → run_simulation → table."""
        with patch("f1_core.physics.cli.load_stint", return_value=canonical_stint_artifact):
            result = runner.invoke(app, ["2023", "Bahrain", "VER", "2"])
        assert result.exit_code == 0, f"stdout: {result.stdout}"
        # Table columns present
        assert "Lap" in result.stdout
        assert "Compound" in result.stdout
        assert "Pred(s)" in result.stdout or "Pred_s" in result.stdout


    def test_cli_exits_2_on_load_stint_failure():
        """FastF1 / data errors exit code 2 (CONTEXT D-05)."""
        with patch(
            "f1_core.physics.cli.load_stint",
            side_effect=ValueError("no such event"),
        ):
            result = runner.invoke(app, ["1999", "NoSuchRace", "VER", "1"])
        assert result.exit_code == 2
        assert "Error loading stint" in result.stdout


    def test_cli_exits_2_on_invalid_driver_code():
        """validate_driver_code regex ^[A-Z]{3}$ failure bubbles up as ValueError → exit 2."""
        with patch(
            "f1_core.physics.cli.load_stint",
            side_effect=ValueError("driver_code must match ^[A-Z]{3}$"),
        ):
            result = runner.invoke(app, ["2023", "Bahrain", "ver", "2"])
        assert result.exit_code == 2


    def test_cli_exits_3_on_physics_failure(canonical_stint_artifact):
        """Runtime physics error exits code 3."""
        with patch("f1_core.physics.cli.load_stint", return_value=canonical_stint_artifact), \
             patch(
                 "f1_core.physics.cli.run_simulation",
                 side_effect=ZeroDivisionError("pathological parameter combo"),
             ):
            result = runner.invoke(app, ["2023", "Bahrain", "VER", "2"])
        assert result.exit_code == 3
        assert "Simulation failed" in result.stdout


    def test_cli_prints_event_count(canonical_stint_artifact):
        """CLI footer reports event count for transparency."""
        with patch("f1_core.physics.cli.load_stint", return_value=canonical_stint_artifact):
            result = runner.invoke(app, ["2023", "Bahrain", "VER", "2"])
        assert result.exit_code == 0
        assert "Events logged" in result.stdout
    ```
  </action>
  <verify>
    <automated>uv run pytest packages/core/tests/physics/test_cli.py -x --benchmark-disable</automated>
  </verify>
  <acceptance_criteria>
    - `uv run pytest packages/core/tests/physics/test_cli.py -x --benchmark-disable` exits 0 with 6 tests passing
    - `uv run f1-simulate --help` exits 0 and prints a help message listing positional args (year, event, driver, stint_index)
    - `grep -q "typer.Exit(code=2)" packages/core/src/f1_core/physics/cli.py` matches
    - `grep -q "typer.Exit(code=3)" packages/core/src/f1_core/physics/cli.py` matches
    - `grep -q "pytest.skip" packages/core/tests/physics/test_cli.py` returns NO matches
    - Full suite: `uv run pytest packages/core/tests/ --benchmark-disable` — all Phase 1 + all Phase 2 non-benchmark tests green
  </acceptance_criteria>
  <done>`f1-simulate` CLI works end-to-end on canonical fixture; exit codes differentiate data vs physics errors; Rich table prints per-lap summary.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| CLI args (year, event, driver, stint_index) → load_stint | Passes through Phase 1's validate_driver_code (`^[A-Z]{3}$`). Year and stint_index forced to `int` by Typer. Event is a string used in FastF1's schedule lookup (already validated upstream). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-15 | Tampering | driver_code path traversal via CLI | mitigate | `load_stint` applies `validate_driver_code` (regex `^[A-Z]{3}$`). CLI does not construct any filesystem path from driver_code. |
| T-02-16 | Information Disclosure | Exception tracebacks leak internal paths | mitigate | CLI catches all exceptions at the boundary and prints only the exception message, not the traceback. For debugging users can `PYTHONDONTWRITEBYTECODE=1 python -m f1_core.physics.cli ...` to see full trace. |
| T-02-17 | Denial of Service | Pathological params cause runaway simulation | accept | Phase 2 uses fixed nominal params from make_nominal_params() — no user-controlled params. CLI blows past <200ms budget but still terminates. Phase 4 adds override-param validation. |
| T-02-18 | Integrity | Events list crosses MAX_EVENTS cap | mitigate | Orchestrator passes a single events list through the pipeline; Module E enforces the cap; test `test_orchestrator_events_capped` verifies on canonical fixture. |
</threat_model>

<verification>
- `uv run pytest packages/core/tests/physics/test_orchestrator.py packages/core/tests/physics/test_cli.py -x --benchmark-disable` — all tests pass
- `uv run pytest packages/core/tests/ --benchmark-disable` — full test suite green (Phase 1 + Phase 2 correctness tests; benchmark still stub)
- `uv run f1-simulate --help` — prints help and exits 0
- PHYS-09 strict execution order enforced by `test_orchestrator_strict_execution_order`
- PHYS-08 invariants flow through the full pipeline (monotonicity test on real fixture)
</verification>

<success_criteria>
- `run_simulation` executes A once, then B→C→D→E→F→G per timestep in that exact order
- SimulationState carries state across iterations, updated in place
- Per-lap summary rows include all D-05 columns
- `f1-simulate` CLI works on canonical fixture, prints Rich table, exits 0
- Exit codes 2 (load) and 3 (physics) differentiated correctly
- Events list capped at MAX_EVENTS; PHYS-08 pipeline-level monotonicity verified
</success_criteria>

<output>
After completion, create `.planning/phases/02-physics-model-modules-a-g/02-06-SUMMARY.md` documenting:
- Per-lap table printed on the canonical fixture (attach sample of first 5 rows as a reference)
- Mean wall-clock time for `run_simulation` on canonical fixture (input for Plan 07 benchmark calibration)
- Any semantic deviations from model_spec.md §"Execution order" (there should be none)
</output>
