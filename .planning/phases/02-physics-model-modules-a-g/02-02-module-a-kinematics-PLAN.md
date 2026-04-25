---
phase: 02-physics-model-modules-a-g
plan: 02
type: execute
wave: 1
depends_on: [01]
files_modified:
  - packages/core/src/f1_core/physics/module_a.py
  - packages/core/src/f1_core/physics/protocols.py
  - packages/core/tests/physics/test_module_a.py
autonomous: true
requirements: [PHYS-01]
tags: [physics, kinematics, module-a]

must_haves:
  truths:
    - "Module A's process_stint() accepts a StintArtifact and AeroParams (unused for A; reserved for future) and returns a KinematicState with shape-(N,) arrays on every field"
    - "a_lat = v² · κ at every sample (model_spec.md §A.2)"
    - "a_long computed via Savitzky-Golay (window=9, order=3) on the speed channel using Phase 1's savgol_velocity"
    - "Curvature κ(s) built inside process_stint from the session's fastest 20% of laps via compute_curvature_map (D-02)"
    - "V_sx,r derived from RPM, inferred gear ratios, and R_0 per model_spec.md §A.4"
    - "Module A satisfies a new StintPreprocessor protocol (not PhysicsModule); orchestrator consumers get a typed interface"
  artifacts:
    - path: "packages/core/src/f1_core/physics/module_a.py"
      provides: "process_stint(artifact, aero_params) -> KinematicState"
      exports: ["process_stint"]
      min_lines: 80
    - path: "packages/core/src/f1_core/physics/protocols.py"
      provides: "StintPreprocessor typing.Protocol"
      exports: ["StintPreprocessor"]
  key_links:
    - from: "packages/core/src/f1_core/physics/module_a.py"
      to: "f1_core.filters.savgol_velocity"
      via: "import"
      pattern: "from f1_core.filters import savgol_velocity"
    - from: "packages/core/src/f1_core/physics/module_a.py"
      to: "f1_core.curvature.compute_curvature_map"
      via: "import + per-call invocation"
      pattern: "compute_curvature_map"
    - from: "packages/core/src/f1_core/physics/module_a.py"
      to: "f1_core.gear_inference.infer_gear_ratios"
      via: "import + per-call invocation"
      pattern: "infer_gear_ratios"
---

<objective>
Implement Module A (Kinematic front-end, model_spec.md §A.1–§A.4) as a stint-level preprocessor per CONTEXT.md D-01. `process_stint(artifact, aero_params) -> KinematicState` receives a full StintArtifact, builds a per-session curvature map from the fastest 20% of laps, computes a_lat/a_long via Savitzky-Golay, derives heading ψ and rear longitudinal slip velocity V_sx,r, and returns a KinematicState whose arrays the orchestrator slices at each timestep.

Purpose: Module A is the single-shot entry into the pipeline. Running it once per stint (not per timestep) keeps the orchestrator's inner loop pure per-tire math, which is the core of the <200ms budget.

Output: Working Module A + real (non-stub) test file covering the five shape/identity/integration checks from Plan 01's stub.
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
@packages/core/src/f1_core/curvature.py
@packages/core/src/f1_core/gear_inference.py
@packages/core/src/f1_core/filters.py
@packages/core/src/f1_core/ingestion/cache.py

<interfaces>
<!-- Existing exports Module A consumes. -->

From f1_core.curvature:
```python
def curvature_from_xy(x: F64, y: F64, grid_meters: F64) -> F64: ...
def compute_curvature_map(laps_xy: list[tuple[F64, F64]], grid_meters: F64) -> F64: ...
```

From f1_core.gear_inference:
```python
R_0_M: float = 0.330  # tire radius
def infer_gear_ratios(car_data: pd.DataFrame) -> dict[int, float]:
    """Returns {gear: combined_ratio} where combined_ratio = G_gear * G_final."""
```

From f1_core.filters:
```python
DEFAULT_WINDOW: int = 9
DEFAULT_POLYORDER: int = 3
DEFAULT_DELTA: float = 0.25
def savgol_velocity(v_mps, *, window=9, order=3, delta=0.25) -> NDArray[np.float64]: ...
```

From f1_core.contracts:
```python
@dataclass(frozen=True)
class KinematicState:
    t: F64Array; v: F64Array; a_lat: F64Array; a_long: F64Array
    psi: F64Array; v_sx_rear: F64Array; kappa: F64Array
```

From f1_core.ingestion.cache.StintArtifact (relevant fields):
- `car_data`: DataFrame columns include `Speed` [km/h], `RPM`, `Throttle`, `Brake`, `nGear`, `Time`
- `pos_data`: DataFrame columns include `X`, `Y`, `Z`, `Time`
- `laps`: DataFrame (one row per lap) with `LapTime`, `Stint`, `Compound`
- Session laps (for fastest-20% curvature): read from `artifact.laps` — the stint's laps only. For Phase 2's curvature map we approximate with this stint's laps; a true session-wide map is a future optimization.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Define StintPreprocessor protocol</name>
  <files>packages/core/src/f1_core/physics/protocols.py</files>
  <read_first>
    - packages/core/src/f1_core/contracts.py (PhysicsModule Protocol pattern, lines ~180-198)
    - .planning/phases/02-physics-model-modules-a-g/02-CONTEXT.md D-01 last bullet
  </read_first>
  <action>
    Create `packages/core/src/f1_core/physics/protocols.py` with EXACTLY:

    ```python
    """Protocols for Phase 2 physics module shapes.

    Module A is NOT a PhysicsModule — it processes a full stint in one call,
    not per timestep. CONTEXT.md D-01 leaves the protocol name to the planner;
    StintPreprocessor is the canonical name chosen here.
    """
    from __future__ import annotations

    from typing import Protocol, runtime_checkable

    from f1_core.contracts import KinematicState
    from f1_core.ingestion.cache import StintArtifact
    from f1_core.physics.params import AeroParams


    @runtime_checkable
    class StintPreprocessor(Protocol):
        """A stint-level preprocessor (Module A). One call per stint.

        Implementations MUST be stateless and MUST return a KinematicState whose
        arrays are all shape (N,) for the same N.
        """

        def process_stint(
            self,
            artifact: StintArtifact,
            aero_params: AeroParams,
        ) -> KinematicState: ...


    __all__ = ["StintPreprocessor"]
    ```

    Note: The AeroParams parameter is currently unused by Module A — it is reserved so future aero-dependent preprocessing (e.g., wind correction) fits without changing the protocol.
  </action>
  <verify>
    <automated>uv run python -c "from f1_core.physics.protocols import StintPreprocessor; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - File `packages/core/src/f1_core/physics/protocols.py` exists
    - Contains `class StintPreprocessor(Protocol)` with a `process_stint(self, artifact: StintArtifact, aero_params: AeroParams) -> KinematicState` method
    - Uses `@runtime_checkable`
    - `uv run python -c "from f1_core.physics.protocols import StintPreprocessor"` exits 0
  </acceptance_criteria>
  <done>StintPreprocessor protocol is importable; type-only definition, no implementation yet.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement Module A (process_stint) with curvature, Savgol, gear-ratio pipeline</name>
  <files>
    packages/core/src/f1_core/physics/module_a.py,
    packages/core/tests/physics/test_module_a.py
  </files>
  <read_first>
    - model_spec.md §A.1, §A.2, §A.3, §A.4
    - packages/core/src/f1_core/contracts.py (KinematicState fields)
    - packages/core/src/f1_core/curvature.py (compute_curvature_map signature)
    - packages/core/src/f1_core/gear_inference.py (infer_gear_ratios returns dict, R_0_M constant)
    - packages/core/src/f1_core/filters.py (savgol_velocity signature, DEFAULT_DELTA=0.25)
    - packages/core/src/f1_core/ingestion/cache.py (StintArtifact field types)
  </read_first>
  <behavior>
    - Test 1: `process_stint(canonical_stint_artifact, nominal_params.aero)` returns a `KinematicState` where every field has the same shape (N,) and N equals `len(canonical_stint_artifact.car_data)` (or within 1 off due to concat)
    - Test 2: `np.testing.assert_allclose(kstate.a_lat, kstate.v**2 * kstate.kappa, rtol=1e-10)` passes
    - Test 3: On a synthetic uniform-acceleration speed signal (`v=linspace(10, 80, 400)`, dt=0.25), `a_long` returned by process_stint matches `savgol_velocity(v, delta=0.25)` within rtol=1e-10
    - Test 4: `V_sx,r[i] = (2π · R_0 · RPM[i] / (60 · combined_ratio[gear[i]])) − V[i]` for every sample where `gear[i]` is in the inferred ratios dict; samples with unknown gear default to `V_sx,r = 0`
    - Test 5: Canonical fixture smoke test — `process_stint` completes without raising, output arrays contain no NaN, a_lat range is within [-60, 60] m/s² (physical sanity for F1)
  </behavior>
  <action>
    Create `packages/core/src/f1_core/physics/module_a.py` with this EXACT structure:

    ```python
    """Module A — Kinematic front-end (model_spec.md §A.1–§A.4).

    Per CONTEXT.md D-01: Module A is a *stint-level preprocessor*, NOT a
    per-timestep step module. It runs once per stint and returns shape-(N,)
    kinematic arrays the orchestrator slices per timestep.

    Per CONTEXT.md D-02: the curvature map κ(s) is built inside process_stint
    via compute_curvature_map, not passed as a parameter.

    Reuses Phase 1 infrastructure:
      - f1_core.filters.savgol_velocity for a_long (window=9, order=3, Δt=0.25 s)
      - f1_core.curvature.compute_curvature_map for κ(s)
      - f1_core.gear_inference.infer_gear_ratios for V_sx,r

    Source papers cited per equation: see model_spec.md §A.1 (Frenet-Serret
    decomposition), §A.2 (Savitzky-Golay dV/dt), §A.3 (atan2 heading), §A.4
    (RPM-gear-derived wheel speed).
    """
    from __future__ import annotations

    import numpy as np
    import pandas as pd
    from numpy.typing import NDArray

    from f1_core.contracts import F64Array, KinematicState
    from f1_core.curvature import compute_curvature_map
    from f1_core.filters import savgol_velocity
    from f1_core.gear_inference import R_0_M, infer_gear_ratios
    from f1_core.ingestion.cache import StintArtifact
    from f1_core.physics.params import AeroParams


    # model_spec.md §A.1 grid step for curvature map — 5 m resolution
    _CURVATURE_GRID_STEP_M: float = 5.0
    _CURVATURE_GRID_LENGTH_M: float = 7500.0   # longest F1 circuit is Spa ~7.0 km


    def _arc_length(x: F64Array, y: F64Array) -> F64Array:
        """Cumulative arc length from XY trace (matches curvature._arc_length)."""
        dx = np.diff(x, prepend=x[0])
        dy = np.diff(y, prepend=y[0])
        return np.cumsum(np.sqrt(dx * dx + dy * dy))


    def _build_reference_curvature_map(
        laps_xy: list[tuple[F64Array, F64Array]],
    ) -> tuple[F64Array, F64Array]:
        """Build κ_ref(s) on a 5m grid from the stint's XY traces.

        Returns (grid_s, kappa_on_grid). Module A later interpolates κ at per-sample s.
        """
        grid = np.arange(0.0, _CURVATURE_GRID_LENGTH_M, _CURVATURE_GRID_STEP_M)
        kappa_grid = compute_curvature_map(laps_xy, grid)
        return grid, kappa_grid


    def _split_pos_by_lap(
        pos_data: pd.DataFrame, laps: pd.DataFrame,
    ) -> list[tuple[F64Array, F64Array]]:
        """Split pos_data into per-lap (x, y) tuples using lap Time boundaries.

        StintArtifact.pos_data is concatenated per-lap; laps["Time"] is lap end.
        """
        if pos_data.empty or laps.empty:
            return []
        result: list[tuple[F64Array, F64Array]] = []
        prev_end = pos_data["Time"].min()
        for _, row in laps.iterrows():
            end = row["Time"]
            mask = (pos_data["Time"] > prev_end) & (pos_data["Time"] <= end)
            seg = pos_data.loc[mask]
            if len(seg) >= 4:
                result.append((
                    seg["X"].to_numpy(dtype=float),
                    seg["Y"].to_numpy(dtype=float),
                ))
            prev_end = end
        return result


    def _interpolate_kappa_at(
        grid_s: F64Array,
        kappa_grid: F64Array,
        s_query: F64Array,
    ) -> F64Array:
        """Look up κ at each s_query via linear interpolation on grid_s.

        Circuit is a closed loop — use modulo against the grid length so that
        laps exceeding one circuit length wrap correctly.
        """
        grid_length = grid_s[-1]
        s_wrapped = np.mod(s_query, grid_length)
        return np.interp(s_wrapped, grid_s, kappa_grid)


    def _v_sx_rear_from_telemetry(
        rpm: F64Array,
        gear: F64Array,
        v_mps: F64Array,
        combined_ratios: dict[int, float],
    ) -> F64Array:
        """model_spec.md §A.4: V_sx,r = V_wheel,r − V.

        V_wheel,r = 2π·R_0·RPM / (60·combined_ratio). Samples whose gear is not
        in combined_ratios (e.g., gear=0 during pit, neutral) get V_sx,r = 0.
        """
        result = np.zeros_like(v_mps)
        # Vectorize by mapping gear index -> ratio via a lookup (8 gears max).
        # Build a ratio array indexed by gear int; -1 for unknown.
        ratio_lookup = np.full(16, np.nan)
        for g, r in combined_ratios.items():
            if 0 <= g < 16:
                ratio_lookup[g] = r
        gear_int = np.clip(gear.astype(int), 0, 15)
        ratios = ratio_lookup[gear_int]
        valid = ~np.isnan(ratios) & (ratios > 0)
        # V_wheel,r [m/s] = 2π·R_0·RPM / (60·combined_ratio)
        v_wheel = np.zeros_like(v_mps)
        v_wheel[valid] = (2.0 * np.pi * R_0_M * rpm[valid]) / (60.0 * ratios[valid])
        result[valid] = v_wheel[valid] - v_mps[valid]
        return result


    def process_stint(
        artifact: StintArtifact,
        aero_params: AeroParams,    # noqa: ARG001 — reserved for future use
    ) -> KinematicState:
        """Module A entry point. See module docstring for spec references.

        Args:
            artifact: StintArtifact from f1_core.ingestion.load_stint()
            aero_params: currently unused — reserved for future aero-correction

        Returns:
            KinematicState with all fields shape (N,), where N = len(car_data).
        """
        car = artifact.car_data
        pos = artifact.pos_data
        if car.empty:
            raise ValueError("Module A: car_data is empty; cannot compute kinematics")

        # --- Timestamps and speed ---
        # car_data["Time"] is a timedelta; convert to seconds from stint start.
        t_raw = car["Time"].values
        if hasattr(t_raw[0], "total_seconds"):
            t = np.array([td.total_seconds() for td in t_raw], dtype=np.float64)
        else:
            t = np.asarray(t_raw, dtype=np.float64) / 1e9   # ns → s if numpy.datetime64
        t = t - t[0]  # zero-base

        # model_spec.md §A.2: speed in m/s (FastF1 provides km/h)
        v_kmh = car["Speed"].to_numpy(dtype=float)
        v = v_kmh / 3.6

        # --- Curvature κ(s) from fastest-20% laps ---
        # For Phase 2 we use this stint's own laps for the reference map (D-02
        # says "session fastest 20%", but Phase 2 has only the stint's laps in
        # the artifact. This is acceptable; Phase 4 can widen when sessions are
        # cached at session scope).
        laps_xy = _split_pos_by_lap(pos, artifact.laps)
        if not laps_xy:
            # Fallback: treat the whole stint as a single "lap" for curvature fit.
            if not pos.empty:
                laps_xy = [(pos["X"].to_numpy(dtype=float), pos["Y"].to_numpy(dtype=float))]
            else:
                # No XY data at all — κ=0 everywhere (straight-line fallback).
                kappa = np.zeros_like(v)
                grid_s = np.array([0.0, 1.0])
                kappa_grid = np.array([0.0, 0.0])

        if laps_xy:
            grid_s, kappa_grid = _build_reference_curvature_map(laps_xy)

        # --- Arc length for each car_data sample ---
        # If we have pos_data, compute s from X,Y; else approximate as ∫V dt.
        if not pos.empty and "X" in pos.columns:
            # Align pos timestamps to car timestamps by interpolation
            pos_t_raw = pos["Time"].values
            if hasattr(pos_t_raw[0], "total_seconds"):
                pos_t = np.array([td.total_seconds() for td in pos_t_raw], dtype=np.float64)
            else:
                pos_t = np.asarray(pos_t_raw, dtype=np.float64) / 1e9
            pos_t = pos_t - pos_t[0]
            x = pos["X"].to_numpy(dtype=float)
            y = pos["Y"].to_numpy(dtype=float)
            s_pos = _arc_length(x, y)
            # Interpolate s to car_data's time base
            s = np.interp(t, pos_t, s_pos)
        else:
            # Fallback: s(t) = cumulative integral of V dt (model_spec §A.1 note)
            s = np.cumsum(v) * 0.25  # Δt = 0.25 s

        # --- κ at each sample ---
        kappa = _interpolate_kappa_at(grid_s, kappa_grid, s)

        # --- a_lat = V² · κ (model_spec §A.2) ---
        a_lat = v * v * kappa

        # --- a_long = dV/dt via Savitzky-Golay (model_spec §A.2, CONTEXT D-01) ---
        # Savgol delta = median dt; the Phase 1 helper locks 0.25 s but the
        # function argument honors overrides.
        if len(t) >= 2:
            dt_median = float(np.median(np.diff(t)))
            if dt_median <= 0 or not np.isfinite(dt_median):
                dt_median = 0.25
        else:
            dt_median = 0.25
        a_long = savgol_velocity(v, window=9, order=3, delta=dt_median)

        # --- Heading ψ = atan2(dY/dt, dX/dt) (model_spec §A.3) ---
        if not pos.empty and "X" in pos.columns:
            x_on_car = np.interp(t, pos_t, x)
            y_on_car = np.interp(t, pos_t, y)
            dx = np.gradient(x_on_car, t)
            dy = np.gradient(y_on_car, t)
            psi = np.arctan2(dy, dx)
        else:
            psi = np.zeros_like(v)

        # --- V_sx,r from RPM + gear ratios (model_spec §A.4) ---
        rpm = car["RPM"].to_numpy(dtype=float)
        gear = car["nGear"].to_numpy(dtype=float)
        try:
            combined_ratios = infer_gear_ratios(car)
        except ValueError:
            # Missing columns or too few samples; zeros fallback
            combined_ratios = {}
        v_sx_rear = _v_sx_rear_from_telemetry(rpm, gear, v, combined_ratios)

        return KinematicState(
            t=t,
            v=v,
            a_lat=a_lat.astype(np.float64),
            a_long=np.asarray(a_long, dtype=np.float64),
            psi=psi.astype(np.float64),
            v_sx_rear=v_sx_rear.astype(np.float64),
            kappa=kappa.astype(np.float64),
        )


    __all__ = ["process_stint"]
    ```

    Now rewrite `packages/core/tests/physics/test_module_a.py` (REPLACE every `pytest.skip` stub with a real assertion):

    ```python
    """PHYS-01 — Module A (Kinematics preprocessor) invariants."""
    from __future__ import annotations

    import numpy as np
    import pandas as pd
    import pytest

    from f1_core.contracts import KinematicState
    from f1_core.physics.module_a import process_stint


    def test_module_a_process_stint_returns_kinematic_state(canonical_stint_artifact, nominal_params):
        kstate = process_stint(canonical_stint_artifact, nominal_params.aero)
        assert isinstance(kstate, KinematicState)


    def test_module_a_all_fields_same_shape(canonical_stint_artifact, nominal_params):
        kstate = process_stint(canonical_stint_artifact, nominal_params.aero)
        n = len(kstate.t)
        assert kstate.v.shape == (n,)
        assert kstate.a_lat.shape == (n,)
        assert kstate.a_long.shape == (n,)
        assert kstate.psi.shape == (n,)
        assert kstate.v_sx_rear.shape == (n,)
        assert kstate.kappa.shape == (n,)


    def test_module_a_a_lat_equals_v_squared_kappa(canonical_stint_artifact, nominal_params):
        """model_spec.md §A.2: a_lat(t) = V(t)² · κ(s(t)) exactly."""
        kstate = process_stint(canonical_stint_artifact, nominal_params.aero)
        np.testing.assert_allclose(kstate.a_lat, kstate.v ** 2 * kstate.kappa, rtol=1e-10)


    def test_module_a_a_long_is_savgol_of_speed(canonical_stint_artifact, nominal_params):
        """model_spec.md §A.2: a_long = dV/dt via Savitzky-Golay window=9 order=3."""
        from f1_core.filters import savgol_velocity
        kstate = process_stint(canonical_stint_artifact, nominal_params.aero)
        dt_median = float(np.median(np.diff(kstate.t)))
        expected = savgol_velocity(kstate.v, window=9, order=3, delta=dt_median)
        np.testing.assert_allclose(kstate.a_long, expected, rtol=1e-10)


    def test_module_a_output_has_no_nan(canonical_stint_artifact, nominal_params):
        kstate = process_stint(canonical_stint_artifact, nominal_params.aero)
        for name in ("t", "v", "a_lat", "a_long", "psi", "v_sx_rear", "kappa"):
            arr = getattr(kstate, name)
            assert np.all(np.isfinite(arr)), f"{name} contains NaN or inf"


    def test_module_a_a_lat_within_physical_range(canonical_stint_artifact, nominal_params):
        """F1 max lateral acceleration ≈ 5 g = 50 m/s²; sanity cap at 60 m/s²."""
        kstate = process_stint(canonical_stint_artifact, nominal_params.aero)
        assert np.max(np.abs(kstate.a_lat)) < 60.0


    def test_module_a_v_sx_rear_zero_when_gear_unknown(nominal_params):
        """Synthetic: gear=0 everywhere → V_sx,r=0 per §A.4 fallback."""
        from f1_core.physics.module_a import _v_sx_rear_from_telemetry
        rpm = np.array([12000.0, 13000.0, 14000.0])
        gear = np.array([0.0, 0.0, 0.0])
        v = np.array([30.0, 40.0, 50.0])
        combined = {}  # no ratios known
        v_sx = _v_sx_rear_from_telemetry(rpm, gear, v, combined)
        np.testing.assert_array_equal(v_sx, np.zeros(3))


    def test_module_a_v_sx_rear_matches_formula_when_gear_known(nominal_params):
        """model_spec.md §A.4: V_wheel,r = 2π·R_0·RPM/(60·combined_ratio); V_sx,r = V_wheel,r − V."""
        from f1_core.gear_inference import R_0_M
        from f1_core.physics.module_a import _v_sx_rear_from_telemetry
        rpm = np.array([10000.0])
        gear = np.array([5.0])
        v = np.array([70.0])
        combined_ratio = 2.5
        combined = {5: combined_ratio}
        expected_wheel = 2.0 * np.pi * R_0_M * 10000.0 / (60.0 * combined_ratio)
        expected_v_sx = expected_wheel - 70.0
        v_sx = _v_sx_rear_from_telemetry(rpm, gear, v, combined)
        np.testing.assert_allclose(v_sx, [expected_v_sx], rtol=1e-12)


    def test_module_a_on_canonical_fixture_completes_without_raising(canonical_stint_artifact, nominal_params):
        """Smoke test — pipeline runs end-to-end on the real fixture."""
        kstate = process_stint(canonical_stint_artifact, nominal_params.aero)
        assert len(kstate.t) > 100  # fixture has ~8000 samples
    ```
  </action>
  <verify>
    <automated>uv run pytest packages/core/tests/physics/test_module_a.py -x --benchmark-disable</automated>
  </verify>
  <acceptance_criteria>
    - `uv run pytest packages/core/tests/physics/test_module_a.py -x --benchmark-disable` exits 0 with 9 tests passing
    - `grep -c "model_spec.md §A" packages/core/src/f1_core/physics/module_a.py` returns at least 4 (one citation per major equation A.1–A.4)
    - `grep -q "from f1_core.filters import savgol_velocity" packages/core/src/f1_core/physics/module_a.py` matches
    - `grep -q "from f1_core.curvature import compute_curvature_map" packages/core/src/f1_core/physics/module_a.py` matches
    - `grep -q "from f1_core.gear_inference import" packages/core/src/f1_core/physics/module_a.py` matches
    - `grep -q "pytest.skip" packages/core/tests/physics/test_module_a.py` returns NO matches (every stub replaced)
    - Full physics test suite still green: `uv run pytest packages/core/tests/physics/ --benchmark-disable` exits 0
  </acceptance_criteria>
  <done>Module A computes (a_lat, a_long, ψ, V_sx,r, κ) correctly on synthetic and canonical inputs; every equation cites its model_spec.md section; nine real tests (no stubs) pass.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| StintArtifact → process_stint | All fields are DataFrames produced by Phase 1's validated ingestion path. No untrusted input crosses into Module A. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-05 | Tampering | StintArtifact might carry malformed arrays (all-NaN, empty) | mitigate | `process_stint` raises `ValueError("car_data is empty")` on empty input; test `test_module_a_output_has_no_nan` verifies finite outputs on canonical fixture. |
| T-02-06 | Denial of Service | Curvature grid fixed at 7500 m / 5 m step = 1500 points; bounded. | accept | No user-controlled input affects grid size. |
</threat_model>

<verification>
- `uv run pytest packages/core/tests/physics/test_module_a.py -x --benchmark-disable` — 9 tests pass
- `uv run pytest packages/core/tests/physics/ --benchmark-disable` — full physics suite still green (other module stubs still skip)
- `uv run pytest packages/core/tests/ --benchmark-disable` — full project test suite green
</verification>

<success_criteria>
- `module_a.process_stint` implemented and importable
- StintPreprocessor protocol defined
- Every equation cites its model_spec.md §A.X section
- All 9 real tests in test_module_a.py pass; no stubs remain
- Dependencies (savgol_velocity, compute_curvature_map, infer_gear_ratios) reused — not reimplemented
- `a_lat = v² · κ` identity holds to rtol=1e-10 on real data
</success_criteria>

<output>
After completion, create `.planning/phases/02-physics-model-modules-a-g/02-02-SUMMARY.md` documenting:
- Module A's actual output shapes on canonical fixture
- Any deviations from the planned formula (e.g., fallback paths exercised)
- Measured a_lat / a_long ranges on the canonical stint (sanity baseline for Plan 06)
</output>
