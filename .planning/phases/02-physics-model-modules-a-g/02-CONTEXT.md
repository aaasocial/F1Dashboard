# Phase 2: Physics Model (Modules A–G) - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 implements all seven physics modules (A through G) as a working forward-simulation pipeline, exercised by a `simulate` CLI and covered by physical-invariant unit tests. It does NOT include Bayesian calibration (Phase 3), the `/simulate` API endpoint (Phase 4), or any frontend work.

The deliverable: a developer can run `simulate <year> <event> <driver> <stint_index>` against any cached FastF1 stint and see a per-lap table of predicted lap times, grip, temperatures, and cumulative energy — computed by the full A→B→C→D→E→F→G pipeline with nominal parameter priors.

</domain>

<decisions>
## Implementation Decisions

### Module Execution Model
- **D-01: Hybrid execution — Module A is a stint preprocessor; Modules B–G are per-timestep.**
  - Module A exposes `process_stint(artifact: StintArtifact, params: AeroParams) -> KinematicState`. It receives the full stint arrays and runs Savitzky-Golay filtering on the speed channel (window=9, order=3) before computing a_lat and a_long. It returns full arrays (shape N,) for all kinematic signals.
  - Modules B through G expose `step(...)` signatures compatible with a per-timestep orchestrator loop. The orchestrator slices KinematicState arrays at each timestep index and passes the slice to B→C→D→E→F→G in strict order, carrying `SimulationState` across iterations.
  - The existing `PhysicsModule` Protocol's `step()` applies to B–G only. Module A satisfies a separate `StintPreprocessor` protocol (or is typed independently — planner decides the exact protocol name).

- **D-02: Module A reuses Phase 1's curvature infrastructure directly.**
  - Module A imports `compute_curvature_map` from `f1_core.curvature` and calls it inside `process_stint()` to build κ(s) from the stint's session laps (fastest 20%). The curvature map is built once per stint call, not passed as a parameter.

### Parameters Structure
- **D-03: Per-stage nested dataclasses, matching Phase 3's calibration stages.**
  - `AeroParams` — C_LA, C_DA, ξ, K_rf_split (fitted in Stage 1)
  - `FrictionParams` — μ_0_fresh, p_bar_0, n, c_py (fitted in Stage 2)
  - `ThermalParams` — T_opt, sigma_T, C_tread, C_carc, C_gas, R_tc, R_cg, h_0, h_1, alpha_p (fitted in Stage 3)
  - `DegradationParams` — beta_therm, T_act, k_wear (fitted in Stage 4)
  - Each module receives only its own params dataclass. The orchestrator assembles a `PhysicsParams` container (a thin dataclass-of-dataclasses) that groups the four stage params together for passing through the pipeline.
  - This maps cleanly to Phase 3's sequential calibration stages — each stage writes/updates one nested dataclass without touching the others.

- **D-04: Default values sourced from model_spec.md's FIXED and SEMI-CONSTRAINED tables.**
  - FIXED params hardcoded as class-level constants (M_dry=798 kg, WB=3.6 m, T_f=T_r=1.60 m, R_0=0.330 m, b_tread_f=0.15 m, b_tread_r=0.20 m, C_rr=0.012, ρ=1.20 kg/m³).
  - SEMI-CONSTRAINED params initialized to mid-range nominal values (WD=0.445, H_CG=0.28 m, K_rad=250 kN/m, ΔT_blanket=60°C, BB=0.575).
  - Calibrated params initialized to physically reasonable mid-range priors (μ_0_fresh≈1.8, T_opt≈95°C, σ_T≈20°C, etc.) derived from the spec's "typical values" and literature. These are intentionally approximate — Phase 3 replaces them with fitted posteriors.
  - A `defaults.py` module in `f1_core/physics/` exposes `make_nominal_params() -> PhysicsParams` as the single source for default initialization.

### Simulate CLI
- **D-05: Full working CLI that produces per-lap table output on stdout.**
  - Invocation: `simulate <year> <event> <driver> <stint_index>` (all positional).
  - Loads the stint via Phase 1's `load_stint()`, runs the full A→G pipeline with nominal params, and prints a human-readable per-lap table:
    ```
    Lap | Compound | Age | Pred(s) | Obs(s) | Δ(s)  | Grip% | T_tread(°C) | E_tire(MJ)
    ```
  - Uses the canonical fixture (2023 Bahrain VER stint 2) as the integration test / benchmark baseline.
  - Exit code 0 on success, non-zero on FastF1 or physics error.
  - No parameter override flags in Phase 2 — that is a Phase 4 API concern.

### Numerical Integration
- **D-06: Forward Euler at Δt=0.25s throughout.**
  - The thermal ODE (Module F) uses `T(t+Δt) = T(t) + Ṫ(t)·Δt`. The spec explicitly confirms stability for Δt=0.25s since all thermal time constants exceed 5 seconds.
  - Cumulative energy integration (Module G) also uses the same Euler step.
  - RK4 is noted in the spec as a "higher accuracy upgrade" — Phase 2 does not implement it. If calibration in Phase 3 reveals systematic temperature bias, Phase 4 or a gap-closure plan can upgrade.

### Claude's Discretion
- Savitzky-Golay filter: window=9 samples, polynomial order=3 (midpoint of spec's 7–11 range; order 3 gives better derivative accuracy over order 2 at this window size for 4 Hz data).
- Module file layout: `packages/core/src/f1_core/physics/` subdirectory with one file per module (`module_a.py` through `module_g.py`) plus `orchestrator.py` and `defaults.py`.
- Benchmark test: `@pytest.mark.benchmark` on the canonical fixture, asserting full A→G pass < 200 ms. Committed to CI.
- Gear-ratio inference: Module A uses Phase 1's `gear_inference.py` for `G_ratio(gear)` and `G_final`, same import pattern as `curvature.py`.
- `simulate` CLI entry point: defined in `packages/core/pyproject.toml` as a console script (`f1-simulate`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Physics Model Specification
- `model_spec.md` — Seven-module architecture, all equations with source paper citations. The authoritative spec for Module A–G implementation. Every equation in code must cite the section (e.g., "model_spec.md §A.2", "Castellano et al. 2021 Eq. 12").
- `model_v1_complete.html` — Extended version of model_spec.md with additional derivation detail. Read alongside model_spec.md when section references are unclear.

### Parameter Registry
- `model_spec.md §"Parameter registry"` — FIXED, SEMI-CONSTRAINED, and LEARNED parameter tables. These are the authoritative source for D-04 default values.

### Phase 1 Contracts (Phase 2 must implement these)
- `packages/core/src/f1_core/contracts.py` — Seven typed dataclass contracts (KinematicState, WheelLoads, ContactPatch, SlipState, ThermalState, DegradationState, SimulationState) plus PhysicsModule Protocol. Phase 2 modules must produce instances of these types.
- `packages/core/src/f1_core/curvature.py` — compute_curvature_map() — imported by Module A (D-02).
- `packages/core/src/f1_core/gear_inference.py` — gear ratio inference — imported by Module A for V_sx,r computation.
- `packages/core/src/f1_core/ingestion/cache.py` — StintArtifact — the input type consumed by Module A's process_stint().
- `packages/core/src/f1_core/ingestion/fastf1_client.py` — load_stint() — the CLI's data-fetch entry point.

### Project Requirements
- `.planning/REQUIREMENTS.md` — Phase 2 covers PHYS-01 through PHYS-09. Read the full text of each requirement before planning.
- `.planning/ROADMAP.md` — Phase 2 success criteria (6 items). These are the acceptance checklist.

### Development Fixture
- Canonical fixture: 2023 Bahrain Grand Prix, VER, Stint 2 (MEDIUM compound, laps 16–38). Confirmed in Phase 1 CONTEXT.md (D-06). Use as the integration test baseline and benchmark target.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `f1_core.curvature.compute_curvature_map()` — imported directly by Module A (D-02). Already accepts (laps_xy, grid_meters) → κ array. Module A builds laps_xy from StintArtifact.pos_data.
- `f1_core.gear_inference` — infers per-team gear ratios from RPM vs speed. Module A calls this to compute V_wheel,r and V_sx,r (model_spec §A.4).
- `f1_core.contracts` — the seven output dataclass types that Module A–G must return. Phase 2 must not redefine them — import from here.
- `f1_core.ingestion.fastf1_client.load_stint()` — the `simulate` CLI's data entry point. Takes (year, event, driver_code, stint_index) → StintArtifact.
- `f1_core.filters` — Savitzky-Golay filter wrapper already exists from Phase 1. Module A should import from here rather than calling scipy.signal.savgol_filter directly.

### Established Patterns
- `@dataclass` for all state and params objects (D-03 from Phase 1). No Pydantic in `packages/core/`.
- `typing.Protocol` for structural subtyping (D-05 from Phase 1). Module A's `StintPreprocessor` protocol follows the same pattern as `PhysicsModule`.
- `__all__` export list in every module (established in contracts.py).
- Type alias `F64Array = NDArray[np.float64]` defined in contracts.py — import and reuse.

### Integration Points
- `packages/core/src/f1_core/physics/` — new subdirectory for Phase 2 code. Does not exist yet.
- The `simulate` CLI entry point wires `load_stint()` → Module A → orchestrator loop → stdout table. No database writes in Phase 2.
- Phase 4's `/simulate` endpoint will import the orchestrator from `f1_core.physics.orchestrator` — keep that import path stable.

</code_context>

<specifics>
## Specific Ideas

- **Hybrid execution pattern:** Module A returns full (N,) arrays; the orchestrator loops `for i in range(N): step B,C,D,E,F,G with array[i]`. State carry (`SimulationState`) is updated in-place inside the loop. At end of each lap, the orchestrator records the per-lap summary row.
- **Per-lap summary:** Predicted lap time uses Module G's `Δt_lap` formula from model_spec.md §G.4. Observed lap time comes from `StintArtifact.laps["LapTime"]`. The delta column directly shows model accuracy even before calibration.
- **Nominal defaults fixture:** `make_nominal_params()` is also the fixture factory in `tests/conftest.py` so unit tests don't duplicate default values.
- **Module G Arrhenius:** `T_tread,i` used in G.2 is the **mean** tread temperature across all four tires (scalar), not per-tire. `μ_0` is a scalar that ages the same for all four tires — per the spec's Module G.2 formulation.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-physics-model-modules-a-g*
*Context gathered: 2026-04-23*
