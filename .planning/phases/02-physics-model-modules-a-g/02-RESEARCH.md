# Phase 2: Physics Model (Modules A–G) - Research

**Researched:** 2026-04-23
**Domain:** Python numerical pipeline packaging, per-timestep physics simulation, invariant testing
**Confidence:** HIGH for stack/tooling choices; HIGH for architecture patterns; MEDIUM for performance estimates (need to be validated empirically during the benchmark task)

## Summary

Phase 2 turns seven equation-level physics specs into a CLI-invokable forward simulator of tire state. The math is already locked in `model_spec.md` and CONTEXT.md fixes the execution model (hybrid: A preprocesses, B–G step per timestep), parameter layout (four nested dataclasses), integration scheme (forward Euler @ 0.25s), and CLI shape. This research focuses purely on *how to implement* that reliably.

The central implementation questions have clean answers from the existing codebase:

1. **Directory layout** — one file per module under `packages/core/src/f1_core/physics/`, plus `orchestrator.py`, `params.py`, `defaults.py`, `cli.py`. Matches CONTEXT.md D-04 exactly.
2. **CLI framework** — **Typer** (not Click). Project is FastAPI-based (Tiangolo ecosystem); the existing `validate_driver_code` already raises `ValueError` which Typer handles natively; and positional-arg signatures in CONTEXT.md D-05 map trivially to Typer function args. Click is the lower-level alternative; no reason to prefer it here.
3. **Benchmark** — `pytest-benchmark 5.2.3` with `@pytest.mark.benchmark(group="physics_pipeline")` and an in-test wall-clock assertion `assert stats["mean"] < 0.200`. CI runs with `--benchmark-only` on a dedicated job.
4. **Invariant tests** — `numpy.testing.assert_allclose` for ΣF_z/ΣF_y closure (rtol=1e-10 is feasible — these are pure algebraic identities, not floating-point approximations), `np.all(np.diff(x) >= -tol)` for monotonicity of E_tire and d_tread. `hypothesis` for randomized invariant checks (Module B closure over random kinematic states).
5. **Execution-order enforcement** — two-layer approach: (a) `frozen=True` dataclasses for Phase 1's existing contracts so a module physically cannot mutate another module's output; (b) a single orchestrator test that imports each module-output dataclass and verifies they are frozen, plus a test that runs the pipeline and asserts state objects are NOT identity-equal between module calls.
6. **Numba** — do NOT add preemptively. Profile first. CONTEXT.md correctly marks it as MEDIUM confidence optional optimization. NumPy vectorization over the 4-tire axis is likely sufficient given telemetry is only ~8000 samples for a 22-lap stint.
7. **Vectorization strategy** — Module A returns (N,) arrays; Modules B–D have closed-form algebraic formulas that are naturally expressible as (4,) array broadcasts inside the per-timestep scalar state slice. Module E's inversion is also closed-form (one cube-root and one arctan per tire). Module F is the ODE update. No loops in the hot path — everything is numpy elementwise per tire.

**Primary recommendation:** Go straight to the layout described in CONTEXT.md D-04, use Typer for the CLI, `pytest-benchmark` for the 200ms budget, plain `numpy.testing.assert_allclose` for algebraic invariants, and treat Numba as a gap-closure lever only if Task 02-08 (the benchmark) fails.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Module Execution Model (D-01, D-02)**
- Module A is a stint preprocessor exposing `process_stint(artifact: StintArtifact, params: AeroParams) -> KinematicState`. It runs Savitzky-Golay (window=9, order=3) on speed, computes a_lat and a_long, and returns shape-(N,) arrays for every kinematic signal.
- Modules B–G expose a `step(...)` signature for the per-timestep orchestrator loop. Module A satisfies a *separate* protocol (`StintPreprocessor`, name at planner discretion) — not the existing `PhysicsModule` protocol.
- Module A imports `compute_curvature_map` from `f1_core.curvature` and builds κ(s) inside `process_stint()` from the stint's session fastest-20% laps. The map is built per call, not passed in.

**Parameter Structure (D-03, D-04)**
- Four nested params dataclasses: `AeroParams` (C_LA, C_DA, ξ, K_rf_split), `FrictionParams` (μ_0_fresh, p̄_0, n, c_py), `ThermalParams` (T_opt, σ_T, C_tread, C_carc, C_gas, R_tc, R_cg, h_0, h_1, α_p), `DegradationParams` (β_therm, T_act, k_wear). These group into a `PhysicsParams` container.
- Each module receives *only* its own params dataclass. The orchestrator passes the appropriate slice.
- FIXED constants hardcoded as class-level attributes: M_dry=798 kg, WB=3.6 m, T_f=T_r=1.60 m, R_0=0.330 m, b_tread_f=0.15 m, b_tread_r=0.20 m, C_rr=0.012, ρ=1.20 kg/m³.
- SEMI-CONSTRAINED nominals: WD=0.445, H_CG=0.28 m, K_rad=250 kN/m, ΔT_blanket=60°C, BB=0.575.
- `make_nominal_params() -> PhysicsParams` in `f1_core/physics/defaults.py` is the single source for default initialization.

**CLI (D-05)**
- `simulate <year> <event> <driver> <stint_index>` (all positional)
- Loads via `load_stint()`, runs A→G with nominal params, prints a per-lap table: `Lap | Compound | Age | Pred(s) | Obs(s) | Δ(s) | Grip% | T_tread(°C) | E_tire(MJ)`
- Uses canonical fixture (2023 Bahrain VER stint 2).
- Exit 0 on success, nonzero on error.
- **No parameter override flags in Phase 2** (that's a Phase 4 API concern).

**Numerical Integration (D-06)**
- Forward Euler Δt=0.25s throughout. Thermal ODE uses `T(t+Δt) = T(t) + Ṫ(t)·Δt`. RK4 deferred to gap-closure.

### Claude's Discretion
- Savgol params: window=9, order=3 (locked).
- File layout: `packages/core/src/f1_core/physics/` with `module_a.py` through `module_g.py` + `orchestrator.py` + `defaults.py`.
- Benchmark: `@pytest.mark.benchmark` on canonical fixture, < 200 ms.
- Module A reuses `f1_core.gear_inference` (same import pattern as curvature).
- CLI entry point: `f1-simulate` in `packages/core/pyproject.toml` console script.

### Deferred Ideas (OUT OF SCOPE)
None — CONTEXT.md deferred nothing. RK4 thermal integration, parameter-override flags, per-compound parameter variants, and API wiring are all Phase 3+ concerns.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PHYS-01 | Module A kinematics (a_lat, a_long via Savgol, ψ, V_sx) | `f1_core.filters.savgol_velocity` exists; `compute_curvature_map` + `infer_gear_ratios` exist. Module A wires them into `process_stint`. |
| PHYS-02 | Module B vertical loads with per-axle aero split and clip-50N floor | Closed-form algebra over a (4,)-shaped vector. Vectorizes naturally. See "Pattern 1: Per-tire closed-form" below. |
| PHYS-03 | Module C force distribution (load-proportional F_y, brake-bias/RWD F_x) | Same pattern as B. Identity test: ΣF_y = M·a_lat exactly (no clipping involved). |
| PHYS-04 | Module D Hertzian + friction (complete μ formula) | Closed-form; identity check μ(T_opt, p̄_0) = μ_0 follows from the equation structure. |
| PHYS-05 | Module E brush inversion + sliding power + over-demand event log | Closed-form; clip Θ=1 with an `events: list[StatusEvent]` channel on the orchestrator to satisfy Criterion 3. |
| PHYS-06 | Module F thermal ODE with three-node lumped model | Three coupled linear ODEs per tire → forward Euler is stable per model_spec §F.7. Four-tire broadcast, one matmul per step. |
| PHYS-07 | Module G cumulative energy + Arrhenius aging + wear + Δt_lap | Scalar state updates + (4,) broadcasts. Monotonicity is a property of the update direction (sign check). |
| PHYS-08 | Per-module invariant unit tests | See "Pattern 3: Invariant test styles" below. Approach depends on which invariant (algebraic identity vs. monotonicity vs. steady state). |
| PHYS-09 | Strict A→B→C→D→E→F→G sequence, no inner-timestep iteration | Enforced by (a) frozen output dataclasses, (b) orchestrator test that proves the sequence, (c) architecture test forbidding inner loops. See "Pattern 4: Execution order enforcement" below. |

## Project Constraints (from ./CLAUDE.md)

The project root `CLAUDE.md` locks the backend stack already:

- **Python 3.12** (NOT 3.13 — pyproject.toml already pins `>=3.12,<3.13`) [VERIFIED: root `pyproject.toml` line 3]
- **NumPy ≥ 2.1, SciPy ≥ 1.17** — already pinned in `packages/core/pyproject.toml` [VERIFIED]
- **Pydantic v2** — but physics modules are explicitly NOT allowed to import Pydantic. `contracts.py` has a regression test `test_contracts_module_does_not_import_pydantic()`. Phase 2 modules must follow the same boundary: plain `@dataclass`, no Pydantic imports in `f1_core`.
- **No `scipy.integrate.odeint`** — use `solve_ivp` (or explicit Euler as locked by D-06). SciPy 1.17 will eventually deprecate odeint.
- **WAT framework discipline** (from `c:\Users\Eason\Desktop\CC\CLAUDE.md`): reasoning belongs in the agent layer (orchestrator), deterministic code in tool layer (individual modules). Matches this phase's physical-module-as-pure-function design perfectly.
- **GSD Workflow Enforcement**: plans must run through `/gsd-execute-phase`. No ad-hoc edits.

## Standard Stack

### Core (already in pyproject, no changes needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| NumPy | 2.1+ | Per-tire (4,) broadcasts, all array math | Project baseline. Already pinned. [VERIFIED: pyproject.toml] |
| SciPy | 1.17+ | `scipy.signal.savgol_filter` via `f1_core.filters`. No `solve_ivp` needed — D-06 locks Euler | Project baseline. `savgol_velocity()` already exists. [VERIFIED: filters.py] |
| pandas | 2.2+ | `StintArtifact.laps[…]` access for CLI output table; per-lap slicing | Project baseline. FastF1 returns DataFrames. [VERIFIED: pyproject.toml] |

### Phase 2 Additions (will be added to `packages/core/pyproject.toml`)

| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| **typer** | 0.24.1 (latest Feb 2026) | CLI entry point `f1-simulate` | HIGH [VERIFIED: PyPI — release Feb 21 2026] |
| **rich** | 14.x | `rich.table.Table` for the per-lap stdout table (pulled in automatically by Typer ≥ 0.12) | HIGH [VERIFIED: Typer docs] |

### Dev-group Additions (added to root `[dependency-groups].dev`)

| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| **pytest-benchmark** | 5.2.3 (latest Mar 2026) | `@pytest.mark.benchmark` + JSON/CI regression detection for the 200ms budget | HIGH [VERIFIED: PyPI — release Mar 26 2026] |
| **hypothesis** | 6.x | Property-based randomized checks on Module B invariants (load closure) and Module D identity (μ(T_opt, p̄_0)=μ_0 for random p̄_0) | HIGH — standard tool, integrates with pytest cleanly |

### Explicitly NOT added (rejection reasons)

| Rejected | Reason |
|----------|--------|
| **Click** | Typer wraps Click and is Tiangolo's (same author as FastAPI) preferred CLI. Zero benefit to using Click directly when CLI is trivial (4 positional args). |
| **Numba** | CONTEXT.md notes it as MEDIUM-confidence optional optimization. Do NOT add preemptively — compile overhead (~seconds on first call) is bad for CLI UX. Keep as gap-closure lever only. |
| **jax / diffrax** | Phase 3 calibration concern; out-of-scope for Phase 2. |
| **tabulate** | Redundant with Rich (already a Typer transitive dep). |
| **pydantic** | Explicitly forbidden in `f1_core/` by test in `test_contracts.py`. |
| **scipy.integrate.solve_ivp** | D-06 locks forward Euler. solve_ivp also has ~20x overhead on small systems per the SciPy maintainers [CITED: scipy/scipy#8257]. |

### Version verification

```bash
uv add typer                          # expect 0.24.1
uv add --dev pytest-benchmark         # expect 5.2.3
uv add --dev hypothesis               # expect 6.x
```

**Final pyproject.toml diff — `packages/core/pyproject.toml`:**

```toml
[project]
dependencies = [
    "fastf1==3.8.2",
    "numpy>=2.1,<3",
    "scipy>=1.17,<2",
    "pandas>=2.2,<3",
    "pyyaml>=6",
    "typer>=0.24,<1",         # NEW
]

[project.scripts]
f1-simulate = "f1_core.physics.cli:app"   # NEW
```

**Root `pyproject.toml` dev group addition:**

```toml
[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-cov>=5",
    "pytest-benchmark>=5.2,<6",   # NEW
    "hypothesis>=6,<7",           # NEW
    "ruff>=0.7",
    "pyright>=1.1",
    "httpx>=0.27",
]
```

## Architecture Patterns

### Recommended Project Structure

```
packages/core/src/f1_core/
├── physics/                    # NEW — all Phase 2 code
│   ├── __init__.py             # Re-exports: PhysicsParams, make_nominal_params, run_simulation
│   ├── params.py               # AeroParams, FrictionParams, ThermalParams, DegradationParams, PhysicsParams
│   ├── defaults.py             # make_nominal_params() — single source of default priors
│   ├── constants.py            # FIXED parameters (M_dry, WB, R_0, C_rr, etc.)
│   ├── module_a.py             # process_stint(artifact, aero_params) -> KinematicState
│   ├── module_b.py             # wheel_loads_step(kstate_i, aero_params) -> F_z (4,)
│   ├── module_c.py             # force_distribution_step(...)
│   ├── module_d.py             # contact_and_friction_step(...)
│   ├── module_e.py             # slip_inversion_step(...) + event logging
│   ├── module_f.py             # thermal_step(...) — forward Euler, returns updated ThermalState
│   ├── module_g.py             # degradation_step(...) — energy, mu_0 aging, tread wear
│   ├── orchestrator.py         # run_simulation(artifact, params) — A→B→C→D→E→F→G loop
│   ├── events.py               # StatusEvent dataclass for PHYS-05 over-demand log
│   └── cli.py                  # Typer app: f1-simulate entry point
└── (existing files unchanged)

packages/core/tests/
├── physics/                    # NEW — one test file per module + integration
│   ├── __init__.py
│   ├── test_module_a.py        # kinematics: a_lat = V²κ, a_long shape, ψ range
│   ├── test_module_b.py        # ΣF_z = M·g + F_aero invariant (Criterion 1)
│   ├── test_module_c.py        # ΣF_y = M·a_lat identity (Criterion 1)
│   ├── test_module_d.py        # μ(T_opt, p̄_0) = μ_0 identity (Criterion 1)
│   ├── test_module_e.py        # Θ=1 clipping + event emission (Criterion 3)
│   ├── test_module_f.py        # steady-state dT/dt=0 verification (Criterion 4)
│   ├── test_module_g.py        # E_tire monotonicity + d_tread monotonicity (Criterion 6)
│   ├── test_orchestrator.py    # execution order, SimulationState carry (Criterion 5)
│   ├── test_cli.py             # Typer CliRunner on canonical fixture
│   └── test_benchmark.py       # pytest-benchmark: < 200 ms on canonical stint (Criterion 2)
```

### Pattern 1: Per-tire closed-form (Modules B, C, D, E, G per-step)

Every per-timestep module takes a scalar kinematic slice and returns a (4,) force/pressure/friction vector via pure numpy array algebra — no loops.

```python
# Module B: module_b.py
import numpy as np
from f1_core.physics.constants import M_TOT, WB, T_F, T_R, H_CG, WD, RHO_AIR
from f1_core.physics.params import AeroParams

def wheel_loads_step(
    v: float,                   # scalar speed [m/s]
    a_lat: float,               # scalar lateral accel [m/s^2]
    a_long: float,              # scalar longitudinal accel [m/s^2]
    params: AeroParams,
) -> np.ndarray:                # shape (4,), FL/FR/RL/RR
    """Module B — vertical loads per tire. model_spec.md §B."""
    # Static loads (scalars) — model_spec §B.1
    sl_f = M_TOT * WD / 2.0
    sl_r = M_TOT * (1.0 - WD) / 2.0

    # Longitudinal transfer (scalar) — §B.2
    dfz_long = (M_TOT * a_long * H_CG) / WB

    # Lateral transfer (per axle, scalar) — §B.3
    k_split = params.K_rf_split  # K_rf / (K_rf + K_rr)
    dfz_lat_f = (M_TOT * a_lat * H_CG / T_F) * k_split
    dfz_lat_r = (M_TOT * a_lat * H_CG / T_R) * (1.0 - k_split)

    # Aero (scalar) — §B.4
    fz_aero = 0.5 * RHO_AIR * params.C_LA * v * v
    fz_aero_f = params.xi * fz_aero
    fz_aero_r = (1.0 - params.xi) * fz_aero

    # Per-tire (4,) — §B.5, sign convention: a_lat > 0 loads LEFT
    f_z = np.array([
        sl_f - dfz_long + dfz_lat_f + 0.5 * fz_aero_f,   # FL
        sl_f - dfz_long - dfz_lat_f + 0.5 * fz_aero_f,   # FR
        sl_r + dfz_long + dfz_lat_r + 0.5 * fz_aero_r,   # RL
        sl_r + dfz_long - dfz_lat_r + 0.5 * fz_aero_r,   # RR
    ])
    # Floor clip — model_spec §B.5 "Floor"
    return np.maximum(f_z, 50.0)
```

**Key property:** no Python `for` over the 4 tires. The array constructor IS the vectorization.

### Pattern 2: ODE step function (Module F thermal)

Three-node lumped model per tire, closed-form Euler update, broadcasts over the 4-tire axis.

```python
# Module F: module_f.py
import numpy as np
from f1_core.contracts import F64Array
from f1_core.physics.params import ThermalParams

DT = 0.25  # seconds; locked by D-06

def thermal_step(
    t_tread: F64Array,          # (4,) previous tread temp [°C]
    t_carc: F64Array,           # (4,)
    t_gas: F64Array,            # (4,)
    p_total: F64Array,          # (4,) total dissipated power this step [W]
    v: float,                   # scalar speed [m/s]
    t_air: float,               # scalar ambient [°C]
    params: ThermalParams,
) -> tuple[F64Array, F64Array, F64Array]:
    """Module F — forward Euler, Δt=0.25s. model_spec.md §F.1-F.7.

    All four tires updated in a single vectorized expression.
    """
    h_air = params.h_0 + params.h_1 * np.sqrt(max(v, 0.0))   # scalar

    # Per-tire ODE RHS — §F.1-F.3, all operations are elementwise (4,)
    dT_tread = (
        params.alpha_p * p_total
        - h_air * A_TREAD * (t_tread - t_air)
        - (t_tread - t_carc) / params.R_tc
    ) / params.C_tread

    dT_carc = (
        (t_tread - t_carc) / params.R_tc
        - H_CARC * A_CARC * (t_carc - t_air)
        - (t_carc - t_gas) / params.R_cg
    ) / params.C_carc

    dT_gas = (t_carc - t_gas) / (params.R_cg * params.C_gas)

    # Forward Euler step — §F.7
    return (
        t_tread + DT * dT_tread,
        t_carc + DT * dT_carc,
        t_gas + DT * dT_gas,
    )
```

### Pattern 3: Invariant test styles (Criterion 1, 3, 4, 6)

Map the six success criteria to test styles — different invariants need different approaches.

| Invariant | Test Style | Tolerance |
|-----------|------------|-----------|
| ΣF_z = M_tot·g + F_aero (Crit 1) | `np.testing.assert_allclose(f_z.sum(), M_TOT*G + 0.5*RHO*C_LA*V**2, rtol=1e-10)` | Algebraic identity → 1e-10 rtol |
| ΣF_y = M_tot·a_lat (Crit 1) | Same style. Module C is purely load-proportional allocation. | 1e-10 rtol |
| μ(T_opt, p̄_0) = μ_0 (Crit 1) | Construct `ContactPatch` with `p_bar = p_bar_0`, `ThermalState` with `t_tread = T_opt`; call Module D; assert μ_i ≈ μ_0_fresh | 1e-12 rtol |
| Θ=1 when \|F_y\|>μ·F_z (Crit 3) | Construct over-demand synthetic sample; assert Θ_i = 1.0 exactly; assert `events` list non-empty | Exact (clipping) |
| Thermal steady state dT/dt=0 (Crit 4) | Run simulator 60 synthetic laps with P_total chosen so RHS=0; assert T_tread stays within 0.01°C of initial | Numerical — 1e-2 abs tolerance acceptable |
| E_tire monotonic (Crit 6) | `assert np.all(np.diff(e_tire, axis=0) >= -1e-12)` across full stint | Tight: P_total ≥ 0 by construction |
| d_tread monotonic non-increasing (Crit 6) | `assert np.all(np.diff(d_tread, axis=0) <= 1e-12)` | Tight |
| μ_0 declines under sustained T (Crit 6) | Simulate 10 laps at T_tread = T_opt + 50°C, assert μ_0[final] < μ_0[initial] | Qualitative |

Example invariant test with hypothesis:

```python
# tests/physics/test_module_b.py
from hypothesis import given, strategies as st
import numpy as np
from f1_core.physics.module_b import wheel_loads_step
from f1_core.physics.defaults import make_nominal_params
from f1_core.physics.constants import M_TOT, G, RHO_AIR

@given(
    v=st.floats(min_value=20.0, max_value=100.0, allow_nan=False),
    a_lat=st.floats(min_value=-40.0, max_value=40.0, allow_nan=False),
    a_long=st.floats(min_value=-50.0, max_value=20.0, allow_nan=False),
)
def test_module_b_vertical_force_balance_invariant(v, a_lat, a_long):
    """PHYS-02 / Criterion 1: ΣF_z = M·g + F_aero for any kinematic state."""
    params = make_nominal_params().aero
    f_z = wheel_loads_step(v=v, a_lat=a_lat, a_long=a_long, params=params)
    expected_aero = 0.5 * RHO_AIR * params.C_LA * v * v
    # Clipping floor at 50N may trip at extreme a_lat — allow a small slack
    # or restrict hypothesis ranges such that no tire clips.
    np.testing.assert_allclose(
        f_z.sum(), M_TOT * G + expected_aero, rtol=1e-10,
    )
```

> **Gotcha:** the 50 N floor in Module B breaks the ΣF_z identity when a tire would go negative. The planner should either (a) restrict the hypothesis input range so no tire clips, or (b) compute ΣF_z *without* the clip for the invariant test (call an unclipped variant internally, or subtract the clip-lift from the sum). Locked-floor + exact-closure cannot both be true simultaneously at extreme inputs.

### Pattern 4: Execution order enforcement (PHYS-09 / Criterion 5)

Success Criterion 5 says: *"a linter/test rejects any inner-timestep iteration or mutation of prior-module outputs."* Three compounding mechanisms make this airtight:

**Mechanism 1: `frozen=True` on the seven output dataclasses.**

Phase 1's existing contracts are NOT frozen (they can be mutated post-hoc). Phase 2 should either:
- Add `frozen=True` to `KinematicState`, `WheelLoads`, `ContactPatch`, `SlipState`, `ThermalState`, `DegradationState` — requires a tiny plan entry to update `contracts.py`; OR
- Add frozen wrapper dataclasses under `f1_core.physics.states` and have modules produce *those* instead.

Recommendation: freeze in place. It's a one-line change per dataclass and enforces the invariant at the language level. `SimulationState` (the carryover) should remain mutable because it updates across timesteps, but the per-module *outputs* must be frozen.

```python
# contracts.py (modified)
@dataclass(frozen=True, slots=True)  # NEW: frozen + slots
class WheelLoads:
    t: F64Array
    f_z: F64Array
```

A test verifies frozen-ness:

```python
# tests/physics/test_orchestrator.py
import pytest
from dataclasses import FrozenInstanceError
from f1_core.contracts import WheelLoads
import numpy as np

def test_wheel_loads_is_frozen():
    wl = WheelLoads(t=np.zeros(3), f_z=np.zeros((3, 4)))
    with pytest.raises(FrozenInstanceError):
        wl.f_z = np.ones((3, 4))
```

> **Subtle:** `frozen=True` prevents *attribute rebinding* but does NOT prevent mutation of the underlying numpy array contents. For defense-in-depth, also set `.setflags(write=False)` on the arrays stored in frozen contracts before returning. Worth considering but may slow allocation — leave as an open question for the planner.

**Mechanism 2: Orchestrator structure test.**

```python
def test_orchestrator_execution_order(canonical_stint_artifact):
    """PHYS-09: A→B→C→D→E→F→G in that exact order, no inner iteration."""
    # Monkeypatch each module's step() to append to a call log
    calls = []
    # ... patch module_a.process_stint, module_b.wheel_loads_step, etc.
    from f1_core.physics.orchestrator import run_simulation
    result = run_simulation(canonical_stint_artifact, make_nominal_params())
    # Per timestep, expect ["B","C","D","E","F","G"] repeated
    # Before loop, expect exactly one "A"
    assert calls[0] == "A"
    stride = ["B", "C", "D", "E", "F", "G"]
    for i in range(1, len(calls), 6):
        assert calls[i:i+6] == stride
```

**Mechanism 3: Architecture linter (ruff rule + custom AST check).**

The phrase "rejects any inner-timestep iteration" is best enforced as a custom test that parses each `module_?.py` file and walks its AST:
- Any `step()` function must contain NO `for` loop whose target iterates per-tire. Per-tire work must be numpy.
- No module (except the orchestrator) may import another module.

```python
# tests/physics/test_architecture.py
import ast
from pathlib import Path

MODULES = ["module_b", "module_c", "module_d", "module_e", "module_f", "module_g"]

def test_modules_do_not_import_each_other():
    phys = Path("packages/core/src/f1_core/physics")
    for mod in MODULES:
        src = (phys / f"{mod}.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                targets = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                for target in targets:
                    assert not any(f"physics.{other}" in target for other in MODULES if other != mod), (
                        f"{mod} imports sibling module — modules must stay isolated"
                    )

def test_step_functions_have_no_per_tire_for_loops():
    # Walk AST of each module_?.py step function; forbid `for i in range(4)` / `for tire in ...`
    ...
```

This satisfies Criterion 5's "linter/test rejects" wording directly.

### Anti-Patterns to Avoid

- **`for i in range(4)` inside any step function** — kills performance and violates Criterion 5. Use numpy array algebra.
- **Mutating `state_in` instead of returning a new state.** The `PhysicsModule.step()` Protocol returns `SimulationState`, implying a new object. Mutation is a footgun that breaks the pipeline's testability (you can't compare pre/post state).
- **Importing Pydantic in `f1_core.physics`.** Regression-tested in `test_contracts.py`; Phase 2 must extend this test to cover the new `physics/` subdirectory.
- **Raising inside `step()` for physical over-demand.** Criterion 3 says "emits an event in the status log" — over-demand is a data property, not an exception. Use the `events: list[StatusEvent]` channel.
- **Caching per-stint results inside module functions.** The simulation cache is a Phase 4 concern. Module functions must be pure.
- **Invoking FastF1 from module code.** `load_stint()` is only called from the CLI. Modules receive already-loaded `StintArtifact`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI argument parsing | `sys.argv` splits | **Typer** | Type hints → args automatically; built-in `--help`; matches FastAPI ecosystem (same author). |
| Per-lap stdout table | Manual f-string padding | **rich.table.Table** (transitively via Typer) | Column alignment, color-coding for Δ(s) (green when < ref), Unicode-safe. |
| Wall-clock timing assertion | `time.perf_counter()` + manual stats | **pytest-benchmark** | Proper warmup, outlier rejection, min/median/std statistics, JSON output for CI regression detection. [CITED: pytest-benchmark 5.2.3 docs] |
| Random invariant inputs | Hand-rolled test loops over ranges | **hypothesis** | Shrinks counterexamples, reproducible, @given strategies map naturally to parameter ranges. |
| Savitzky-Golay derivative | `numpy.gradient` + custom smoothing | `f1_core.filters.savgol_velocity` | Already implemented; Phase 1 locked the window/order. Import, do not reimplement. |
| Curvature from XY | `np.gradient` twice | `f1_core.curvature.compute_curvature_map` | Already implemented with CubicSpline; handles monotonicity edge cases. |
| Gear-ratio lookup | Hardcoded per-team table | `f1_core.gear_inference.infer_gear_ratios` | Already infers from RPM vs V at full throttle. |
| Atomic pickle write of intermediate results | `open(w) + rename` | `f1_core.ingestion.cache._atomic_write` pattern (if needed) | Already handles fsync before rename. Phase 2 likely doesn't need caching, but if the benchmark requires it later, reuse this. |

**Key insight:** Phase 1 delivered every utility Phase 2 needs. Module A is mostly a thin orchestrator of existing functions (savgol → curvature → gear inference). The *novel* code is the per-timestep physics math itself.

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | **None** — Phase 2 writes no database rows. Per-stint simulation cache (SQLite) is a Phase 4 concern. Phase 1's FastF1 pickle cache is unchanged. | None |
| Live service config | **None** — no external services touched. | None |
| OS-registered state | **None** — no scheduled tasks, no launchd, no systemd. | None |
| Secrets/env vars | `F1_CACHE_DIR` already in use by Phase 1; Phase 2 CLI reads it via `load_stint()`. No new secrets. | None |
| Build artifacts | The new `f1-simulate` console script entry in `packages/core/pyproject.toml` requires `uv pip install -e packages/core` (or `uv sync`) after the pyproject edit. Otherwise `f1-simulate` command will not resolve. | Plan must include a "reinstall core package" step after adding the `[project.scripts]` entry. |

## Common Pitfalls

### Pitfall 1: Out-lap / in-lap contaminate the force balance
**What goes wrong:** The stint fixture's first and last laps include pit entry/exit, where V drops below physical validity and aero downforce goes to zero. If Module B's invariant test uses real stint data, ΣF_z may legitimately differ from M·g + F_aero because of gradient-driven errors in a_long at pit speeds.
**Why it happens:** PHYS-02's invariant is *physical*: the tire loads must sum to vehicle weight plus downforce. In pit-speed samples, the savgol-derived a_long is noisy and the kinematic inputs aren't physically meaningful.
**How to avoid:** Use synthetic kinematic inputs (hypothesis-generated) for the *invariant test*. Use real data for the *integration test* (checking that simulation completes, produces finite outputs, matches shape contracts). Don't require algebraic identity on real telemetry.
**Warning signs:** Invariant test flakes with NaN or > 1% error on specific samples.

### Pitfall 2: Negative F_z clip breaks ΣF_z exactness
**What goes wrong:** model_spec §B.5 mandates `F_z,i ≥ 50 N` as a floor. When extreme a_lat would push an inside tire negative, the clip lifts it to 50 N, violating ΣF_z = M·g + F_aero.
**Why it happens:** The clip is a numerical guard, not a physical identity.
**How to avoid:** The invariant test should either (a) restrict hypothesis ranges so no clip fires, or (b) assert the invariant on a *pre-clip* inner function (`_wheel_loads_step_unclipped`) and separately test the clip behavior.
**Warning signs:** `ΣF_z - (M·g + F_aero) ≈ 50` (one clip fired), `≈ 100` (two fired), etc.

### Pitfall 3: Module D's temperature state is "previous timestep"
**What goes wrong:** Model_spec §D.5: "T_tread,i is from the previous timestep's thermal state." Naively using the *current* step's freshly-integrated T_tread creates an implicit algebraic loop that forward Euler doesn't handle.
**Why it happens:** Easy to forget because `SimulationState` is mutable — the orchestrator must read T_tread *before* calling Module F.
**How to avoid:** Orchestrator order is strict: D reads `state.t_tread` (from previous step), E runs, F updates `state.t_tread`, G runs. Never swap F and D. The test in Pattern 4 catches this.
**Warning signs:** Thermal oscillation, or suspiciously fast temperature tracking.

### Pitfall 4: Arrhenius numerical overflow
**What goes wrong:** `exp((T_tread - T_ref) / T_act)` with T_tread > 200°C and T_act = 25 yields `exp(4.8) ≈ 121`, which *times* a tiny β_therm is fine — but if a numerical bug pushes T_tread to 500°C, you get `exp(17) ≈ 2.4e7`, and μ_0 crashes to zero in one step.
**Why it happens:** Unbounded ODE at high temperatures.
**How to avoid:** (a) Cap the thermal-state outputs at a reasonable ceiling (say 250°C) with a warning event emitted. (b) Hypothesis tests for Module G must bound `t_tread` inputs. (c) Use `np.expm1` and clamp the exponent argument to e.g. 10 to avoid overflow.
**Warning signs:** μ_0 drops below 0.1 within a stint; grip% column in CLI shows near-zero.

### Pitfall 5: `np.maximum(f_z, 50.0)` breaks gradient for Phase 3
**What goes wrong:** In Phase 2 this is fine. But Phase 3 calibration needs gradients (for JAX/NumPyro). `np.maximum` has zero gradient at the clip, which will trip NUTS in Phase 3.
**Why it happens:** Non-smooth clip.
**How to avoid:** Phase 2 should log a note in `module_b.py` docstring: "Clip uses np.maximum; if Phase 3 calibration needs smooth gradients, swap for softplus(f_z - 50) + 50." Don't do it now — premature.
**Warning signs:** Phase 3 gradient-based sampler fails to converge on aero parameters.

### Pitfall 6: Event-list memory growth over long stints
**What goes wrong:** Module E's `events.append(StatusEvent(...))` for over-demand clipping. A poorly-tuned parameter set could over-demand on *every* timestep, appending 8000+ events to a single list.
**Why it happens:** Parameter error in calibration-less Phase 2 is the norm, not the exception.
**How to avoid:** Dedupe consecutive over-demand events into a single `StatusEvent(start_t, end_t, tire_index, count)` range object. Or cap the list at N=500 and set a `truncated=True` flag.
**Warning signs:** CLI stdout shows thousands of "over-demand" lines; mem grows during simulation.

### Pitfall 7: pytest-benchmark variance across CI machines
**What goes wrong:** 200ms budget on a developer laptop (M1 Max / Ryzen 7) may become 600ms on a GitHub Actions shared runner (which has ~2 vCPU).
**Why it happens:** Criterion 2 says "on a developer laptop" but Criterion 2 also says "committed to CI." These may conflict.
**How to avoid:** Two-tier threshold: (a) a `@pytest.mark.benchmark(group="dev_laptop")` test with `assert stats["mean"] < 0.200` runnable locally; (b) a separate `@pytest.mark.benchmark(group="ci")` test with `< 0.600` for CI. Alternatively use [pytest-codspeed](https://codspeed.io/) which uses CPU instruction count instead of wall time to get deterministic numbers in CI — but that adds a dependency. For v1, the two-tier threshold is simpler.
**Warning signs:** Benchmark green locally, red in CI.

## Code Examples

### Typer CLI entry point

```python
# packages/core/src/f1_core/physics/cli.py
"""f1-simulate CLI — D-05.

Invocation: f1-simulate 2023 Bahrain VER 2
"""
from __future__ import annotations

import sys
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
    event: str = typer.Argument(..., help="Event name, e.g. 'Bahrain'"),
    driver: str = typer.Argument(..., help="3-letter driver code, e.g. 'VER'"),
    stint_index: int = typer.Argument(..., help="1-indexed stint number"),
) -> None:
    """Simulate a real stint with nominal physics parameters."""
    try:
        artifact = load_stint(
            year=year, event=event, driver_code=driver, stint_index=stint_index,
        )
    except Exception as exc:
        console.print(f"[red]Error loading stint:[/red] {exc}")
        raise typer.Exit(code=2)

    try:
        result = run_simulation(artifact, make_nominal_params())
    except Exception as exc:
        console.print(f"[red]Simulation failed:[/red] {exc}")
        raise typer.Exit(code=3)

    table = Table(title=f"{year} {event} {driver} stint {stint_index}")
    for col in ("Lap", "Compound", "Age", "Pred(s)", "Obs(s)", "Δ(s)",
                "Grip%", "T_tread(°C)", "E_tire(MJ)"):
        table.add_column(col, justify="right")
    for row in result.per_lap_rows():
        table.add_row(*[str(x) for x in row])
    console.print(table)


if __name__ == "__main__":
    app()
```

**Source:** [Typer docs](https://typer.tiangolo.com/), [Rich tables](https://rich.readthedocs.io/en/stable/tables.html)

### pytest-benchmark test for the <200ms budget

```python
# packages/core/tests/physics/test_benchmark.py
"""PHYS / Criterion 2: <200ms forward simulation on canonical fixture."""
import pytest
from f1_core.physics.defaults import make_nominal_params
from f1_core.physics.orchestrator import run_simulation


@pytest.mark.benchmark(group="physics_pipeline_dev_laptop", min_rounds=5)
def test_full_stint_simulation_under_200ms_dev_laptop(
    benchmark, canonical_stint_artifact,
):
    params = make_nominal_params()
    result = benchmark(run_simulation, canonical_stint_artifact, params)
    # Functional check after timing
    assert len(result.per_lap_rows()) > 0
    # Hard wall-clock assertion (dev laptop only)
    assert benchmark.stats["mean"] < 0.200, (
        f"Full stint simulation took {benchmark.stats['mean']*1000:.1f} ms, budget is 200 ms"
    )


@pytest.mark.benchmark(group="physics_pipeline_ci")
def test_full_stint_simulation_under_600ms_ci(
    benchmark, canonical_stint_artifact,
):
    """Relaxed threshold for shared CI runners (see Pitfall 7)."""
    params = make_nominal_params()
    benchmark(run_simulation, canonical_stint_artifact, params)
    assert benchmark.stats["mean"] < 0.600
```

**Source:** [pytest-benchmark 5.2.3 usage docs](https://pytest-benchmark.readthedocs.io/en/latest/usage.html)

### Orchestrator loop skeleton

```python
# packages/core/src/f1_core/physics/orchestrator.py
"""Phase 2 orchestrator — A→B→C→D→E→F→G at each telemetry sample.

PHYS-09: strict sequence, SimulationState carried across timesteps.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from f1_core.contracts import SimulationState, F64Array
from f1_core.ingestion.cache import StintArtifact
from f1_core.physics.params import PhysicsParams
from f1_core.physics.module_a import process_stint
from f1_core.physics.module_b import wheel_loads_step
from f1_core.physics.module_c import force_distribution_step
from f1_core.physics.module_d import contact_and_friction_step
from f1_core.physics.module_e import slip_inversion_step
from f1_core.physics.module_f import thermal_step
from f1_core.physics.module_g import degradation_step
from f1_core.physics.events import StatusEvent


@dataclass
class SimulationResult:
    """Per-timestep outputs + per-lap summary rows."""
    f_z: F64Array          # (N, 4)
    f_y: F64Array          # (N, 4)
    t_tread: F64Array      # (N, 4)
    e_tire: F64Array       # (N, 4)
    mu_0: F64Array         # (N,)
    events: list[StatusEvent]
    per_lap: list[dict]    # for CLI table

    def per_lap_rows(self) -> list[tuple]:
        ...


def run_simulation(
    artifact: StintArtifact,
    params: PhysicsParams,
) -> SimulationResult:
    # Module A — preprocessing (full-stint arrays)
    kstate = process_stint(artifact, params.aero)
    n = len(kstate.t)

    # Pre-allocate outputs
    f_z_out = np.empty((n, 4))
    f_y_out = np.empty((n, 4))
    t_tread_out = np.empty((n, 4))
    e_tire_out = np.empty((n, 4))
    mu_0_out = np.empty(n)
    events: list[StatusEvent] = []

    # Initial state (from F.6)
    state = _initialize_simulation_state(artifact, params)

    for i in range(n):
        # B — vertical loads
        f_z = wheel_loads_step(
            v=kstate.v[i], a_lat=kstate.a_lat[i], a_long=kstate.a_long[i],
            params=params.aero,
        )
        # C — force distribution
        f_y, f_x = force_distribution_step(
            f_z=f_z, v=kstate.v[i], a_lat=kstate.a_lat[i], a_long=kstate.a_long[i],
            params=params.aero,
        )
        # D — contact + friction (uses PREVIOUS step's t_tread from state)
        a_cp, p_bar, mu = contact_and_friction_step(
            f_z=f_z, t_tread_prev=state.t_tread, mu_0=state.mu_0,
            params=params.friction,
        )
        # E — slip inversion + power
        e_out = slip_inversion_step(
            f_y=f_y, f_x=f_x, mu=mu, f_z=f_z, a_cp=a_cp,
            v=kstate.v[i], v_sx_rear=kstate.v_sx_rear[i],
            params=params.friction,
            events=events, t=kstate.t[i],
        )
        # F — thermal update (writes back into state.t_tread/t_carc/t_gas)
        state.t_tread, state.t_carc, state.t_gas = thermal_step(
            t_tread=state.t_tread, t_carc=state.t_carc, t_gas=state.t_gas,
            p_total=e_out.p_total, v=kstate.v[i],
            t_air=_t_air_at(artifact, i), params=params.thermal,
        )
        # G — energy + aging + wear
        state.e_tire, state.mu_0, state.d_tread = degradation_step(
            e_tire=state.e_tire, mu_0=state.mu_0, d_tread=state.d_tread,
            p_total=e_out.p_total, p_slide=e_out.p_slide,
            t_tread_current=state.t_tread,
            params=params.degradation,
        )
        # Record
        f_z_out[i] = f_z
        f_y_out[i] = f_y
        t_tread_out[i] = state.t_tread
        e_tire_out[i] = state.e_tire
        mu_0_out[i] = state.mu_0

    return SimulationResult(
        f_z=f_z_out, f_y=f_y_out, t_tread=t_tread_out,
        e_tire=e_tire_out, mu_0=mu_0_out, events=events,
        per_lap=_aggregate_per_lap(artifact, f_z_out, f_y_out, t_tread_out, e_tire_out, mu_0_out),
    )
```

**Source:** model_spec.md §Execution order + CONTEXT.md D-01, D-03, D-06.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `scipy.integrate.odeint` | `scipy.integrate.solve_ivp` | 2018 | SciPy docs explicitly recommend `solve_ivp` for new code. **Phase 2 uses neither** — D-06 locks explicit Euler because Δt=0.25s is well inside the stability region for the ~5s thermal time constants. |
| `argparse` + hand-rolled CLI | Typer | ~2020 (FastAPI ecosystem) | Auto-generates `--help`, type conversions, subcommands from type hints. Matches FastAPI ergonomics. |
| Python `for i in range(4)` per-tire | NumPy (4,) vector algebra | forever in scientific Python | 10-100x faster; essential to hit <200ms on 8000 samples. |
| Pydantic v1 dataclasses | Plain `@dataclass` with numpy fields | Phase 1 D-03 | Zero Pydantic in `f1_core/`. Pydantic is strictly an API-boundary concern. |
| Custom benchmarking with `time.perf_counter` | pytest-benchmark | 2017+ | Proper statistics, CI integration, JSON output for regression detection. |
| `assert a == b` on floats | `numpy.testing.assert_allclose(a, b, rtol=..., atol=...)` | standard numpy since 1.5 | Explicit tolerance semantics; broadcasting-safe. |

**Deprecated/outdated:**
- `odeint` — still works but "recommended for new code: use solve_ivp" per SciPy docs.
- `unittest.TestCase`-style physics tests — pytest + numpy.testing is the 2025 norm.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Typer's transitive dep on Rich is version-compatible with NumPy 2.1 | Standard Stack | LOW — Rich has no numpy dependency. Just need to verify `uv sync` resolves. |
| A2 | 200ms target is achievable with pure numpy on 8000 samples × 7 modules | Summary | MEDIUM — needs to be empirically validated in Task 02-08 (benchmark). If missed, fallback is Numba on hot paths (Modules B/D/E are prime candidates). |
| A3 | `dataclass(frozen=True)` on existing Phase 1 contracts won't break any Phase 1 tests | Pattern 4 | LOW — Phase 1 tests construct but don't mutate. Still, planner must re-run Phase 1 test suite after freezing. |
| A4 | `numpy.maximum(f_z, 50.0)` is sufficient for the clip (vs softplus) | Pitfall 5 | LOW for Phase 2. MEDIUM for Phase 3 if the same code is used for calibration gradients. |
| A5 | pytest-benchmark CI variance can be handled by two-tier threshold | Pitfall 7 | MEDIUM — if CI variance is very high (Windows runner, etc.), may need pytest-codspeed. |
| A6 | Forward Euler at Δt=0.25s is numerically stable for all physically-plausible ThermalParams | D-06 | HIGH-confidence it IS stable for nominal params (spec confirms). LOW risk of instability for extreme calibrated params in Phase 3 — not Phase 2's problem. |
| A7 | The orchestrator loop in Python (per-sample, 4 Hz, ~8000 iters) won't be the bottleneck vs. numpy math | Pattern per-tire | MEDIUM — 8000 Python iterations at ~1 μs each is 8 ms, well under budget. If inner numpy overhead dominates (~25 μs per sample due to numpy array creation), total is 200 ms exactly — risky. Mitigation in A9. |
| A8 | The canonical fixture (Bahrain 2023 VER stint 2) has the same telemetry shape (~8060 samples) at Phase 2 time as when Phase 1 captured it | Criterion 2 | LOW — StintArtifact is pickled on disk. Shape is stable. |
| A9 | Pre-allocating output arrays (`np.empty((n,4))`) before the loop is the right pattern, vs. appending | Code Examples | HIGH — standard practice, no realistic alternative. |
| A10 | `make_nominal_params()` values from model_spec.md "typical values" produce a stable forward simulation over a full 22-lap stint with nominal priors | Criterion 1, 4, 6 | MEDIUM — nominal friction parameters may put a real stint mildly outside the μ(T_opt,p̄_0)=μ_0 operating point. The identity test uses synthetic inputs, not real data, so this doesn't break Criterion 1. But integration tests (CLI on canonical fixture) could show large Δ(s) from observed — that's expected and not a bug in Phase 2. |

## Open Questions

1. **Should `SimulationState` fields be numpy arrays updated in-place, or immutable frozen copies returned per step?**
   - What we know: CONTEXT.md D-01 says "carrying `SimulationState` across iterations." The existing `SimulationState` dataclass is not frozen.
   - What's unclear: Per Pattern 4, module *outputs* should be frozen for enforcement. But the carryover state is inherently mutable across time.
   - Recommendation: Keep `SimulationState` mutable (not frozen). Freeze only the per-module *output* dataclasses (KinematicState, WheelLoads, ContactPatch, SlipState, ThermalState, DegradationState). Document the distinction in `orchestrator.py` docstring.

2. **Should Module A use `process_stint` (single call) or can it also expose a per-timestep `step()` for symmetry?**
   - What we know: CONTEXT.md D-01 locks A as preprocessor.
   - What's unclear: What happens when Phase 4's API wants to stream per-timestep outputs? Does A remain a one-shot?
   - Recommendation: Keep A as one-shot in Phase 2. Phase 4 can slice the (N,)-length arrays as needed. No action required now.

3. **How does the orchestrator handle mixed-length lap data in a stint?**
   - What we know: `StintArtifact.laps` is a DataFrame; per-lap telemetry has varying sample counts.
   - What's unclear: Does Module A concat all laps into one long (N,) array, or keep them segmented?
   - Recommendation: Concat (already done by Phase 1 ingestion in `_extract_artifact`). Per-lap aggregation is a post-processing step in `_aggregate_per_lap` using lap boundaries from `artifact.laps["Time"]` end timestamps.

4. **Event log dedup policy?**
   - What we know: Pitfall 6 flags this.
   - Recommendation: Planner decision. Simplest: cap events at N=500, set `truncated=True`. Defer dedup to Phase 4 when events are API-visible.

5. **Floor clip F_z=50 N vs. invariant tests — which of the two mitigations in Pattern 3 / Pitfall 2?**
   - Recommendation: Planner should pick option (a) — restrict hypothesis ranges so no clip fires. Easier to reason about; maintains the single code path.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | All of Phase 2 | ✓ | 3.12 (pyproject.toml line 3) | — |
| NumPy 2.1+ | Every module | ✓ | already pinned | — |
| SciPy 1.17+ | `savgol_filter` via Phase 1 | ✓ | already pinned | — |
| fastf1 3.8.2 | CLI `load_stint` | ✓ | already pinned | — |
| **typer ≥0.24** | CLI | ✗ | — | Fall back to argparse (ugly but works). Strongly prefer installing. |
| **pytest-benchmark ≥5.2** | Benchmark test | ✗ | — | Fall back to `time.perf_counter` inside a test — lose regression detection. Strongly prefer installing. |
| **hypothesis ≥6** | Property-based invariant tests | ✗ | — | Fall back to parametrized pytest over a coarse grid. Less thorough but acceptable. |
| uv | Workspace install | ✓ | CONTEXT.md Phase 1 outcomes mention uv workspace | — |
| pyright | Type check | ✓ | already pinned | — |
| ruff | Lint | ✓ | already pinned | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** All three new deps (typer, pytest-benchmark, hypothesis) have fallbacks but the fallbacks reduce quality materially — the plan must add them via `uv add` in Task 02-01 (pyproject setup).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest 8.x` + `pytest-benchmark 5.2.3` + `hypothesis 6.x` |
| Config file | root `pyproject.toml` `[tool.pytest.ini_options]` (already exists) |
| Quick run command | `uv run pytest packages/core/tests/physics/ -x --benchmark-disable` |
| Full suite command | `uv run pytest packages/core/tests/ --benchmark-only` (run benchmarks) and `uv run pytest packages/core/tests/` (correctness, skip benchmarks) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PHYS-01 | Module A Savgol a_long, a_lat=V²κ, ψ, V_sx | unit | `pytest packages/core/tests/physics/test_module_a.py -x` | Wave 0 |
| PHYS-02 | Module B per-tire F_z + ΣF_z closure + 50N floor | unit+property | `pytest packages/core/tests/physics/test_module_b.py -x` | Wave 0 |
| PHYS-03 | Module C ΣF_y=M·a_lat, brake-bias split | unit+property | `pytest packages/core/tests/physics/test_module_c.py -x` | Wave 0 |
| PHYS-04 | Module D μ(T_opt, p̄_0)=μ_0 identity | unit | `pytest packages/core/tests/physics/test_module_d.py -x` | Wave 0 |
| PHYS-05 | Module E Θ=1 clip + event emission on over-demand | unit | `pytest packages/core/tests/physics/test_module_e.py -x` | Wave 0 |
| PHYS-06 | Module F steady-state dT/dt=0 | unit+integration | `pytest packages/core/tests/physics/test_module_f.py -x` | Wave 0 |
| PHYS-07 | Module G monotonic E_tire, monotonic d_tread, Arrhenius decline | unit | `pytest packages/core/tests/physics/test_module_g.py -x` | Wave 0 |
| PHYS-08 | All seven invariant tests listed above pass | unit aggregation | same as each row | Wave 0 |
| PHYS-09 | Orchestrator calls A once then B-G in order per timestep, no inner iteration | architecture | `pytest packages/core/tests/physics/test_orchestrator.py -x packages/core/tests/physics/test_architecture.py` | Wave 0 |
| Criterion 2 | <200ms full-stint forward pass on canonical fixture | benchmark | `pytest packages/core/tests/physics/test_benchmark.py --benchmark-only` | Wave 0 |
| Criterion 5 | State-object carryover + execution order linter-enforceable | architecture | same as PHYS-09 | Wave 0 |
| CLI end-to-end | `f1-simulate 2023 Bahrain VER 2` prints table, exits 0 | integration | `pytest packages/core/tests/physics/test_cli.py -x` (uses Typer's `CliRunner`) | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest packages/core/tests/physics/ -x --benchmark-disable` (runs everything except benchmarks, fast)
- **Per wave merge:** `uv run pytest packages/core/tests/ --benchmark-only` then full suite
- **Phase gate:** Full suite green (including benchmark) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `packages/core/tests/physics/__init__.py` — test package marker
- [ ] `packages/core/tests/physics/conftest.py` — shared fixtures (`canonical_stint_artifact`, `synthetic_kinematic_state`, `nominal_params`)
- [ ] `packages/core/tests/physics/test_module_a.py` through `test_module_g.py` — one per module
- [ ] `packages/core/tests/physics/test_orchestrator.py` — execution order + state carry
- [ ] `packages/core/tests/physics/test_architecture.py` — no-inner-for-loop + no-sibling-imports AST checks
- [ ] `packages/core/tests/physics/test_cli.py` — Typer CliRunner
- [ ] `packages/core/tests/physics/test_benchmark.py` — 200ms budget
- [ ] `.github/workflows/benchmark.yml` or equivalent CI job (Criterion 2 requires "committed to CI")
- [ ] Framework install: `uv add --dev pytest-benchmark hypothesis` and `uv add typer` (in packages/core)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 2 is CLI + physics library, no users. |
| V3 Session Management | no | No sessions. |
| V4 Access Control | no | No authorization boundary. |
| V5 Input Validation | yes | Typer CLI accepts `driver_code` — must go through `validate_driver_code` (already enforced by `load_stint`). Year and stint_index are `int` (Typer enforces). Event name is a string passed to `fastf1.get_event_schedule`, which already validates upstream. |
| V6 Cryptography | no | No cryptographic operations. |
| V14 Config | partial | The `f1-simulate` entry point is added to `pyproject.toml` — do not hardcode paths, let `F1_CACHE_DIR` drive cache location (already Phase 1 pattern). |

### Known Threat Patterns for {Python CLI + FastF1}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Arbitrary event-name string reaches `fastf1.get_session` | Tampering / Info Disclosure | FastF1 validates against the season schedule. Invalid events raise; the CLI maps to `typer.Exit(code=2)`. No user-provided paths. |
| Pickle deserialization of user-controlled input | Tampering | Phase 1 T-01-05 pattern: layer-2 cache only reads pickles under `F1_CACHE_DIR` that our code wrote. Phase 2 does not add any pickle load path. |
| Path traversal via driver_code | Tampering | `validate_driver_code` regex `^[A-Z]{3}$` already enforced in `load_stint`. |
| Unbounded memory growth via event log (Pitfall 6) | Denial of Service | Cap events at N=500 with `truncated=True` flag. |
| CLI help text injection | Info Disclosure | Typer escapes all argument help; Rich table renders via Console which escapes control characters. Not a concern. |

**Security posture:** Phase 2 is a *library + CLI*, not a network-exposed surface. All external inputs (year, event, driver, stint_index) go through Phase 1's already-validated `load_stint`. No new threat surface is added.

## Sources

### Primary (HIGH confidence)
- **model_spec.md §A–G + §Execution order + §Parameter registry** — authoritative physics spec. Every equation in Phase 2 code must cite a section.
- **packages/core/src/f1_core/contracts.py** — seven locked dataclass output contracts + `PhysicsModule` Protocol + `SimulationState`. [VERIFIED: file read in full]
- **packages/core/src/f1_core/curvature.py** — `compute_curvature_map()` for Module A's κ(s). [VERIFIED]
- **packages/core/src/f1_core/gear_inference.py** — `infer_gear_ratios()` for Module A's V_sx. [VERIFIED]
- **packages/core/src/f1_core/filters.py** — `savgol_velocity()` window=9 order=3 locked default. [VERIFIED]
- **packages/core/pyproject.toml** — version pins for numpy/scipy/pandas/fastf1/python 3.12. [VERIFIED]
- **root pyproject.toml** — pytest config, workspace layout, dev-group deps, `--import-mode=importlib`. [VERIFIED]
- **.planning/REQUIREMENTS.md** — PHYS-01 through PHYS-09 full text. [VERIFIED]
- **.planning/phases/02-physics-model-modules-a-g/02-CONTEXT.md** — user-locked decisions D-01 through D-06. [VERIFIED]
- **Typer docs** ([typer.tiangolo.com](https://typer.tiangolo.com/)) — Feb 2026 release 0.24.1. [CITED]
- **pytest-benchmark 5.2.3 docs** ([readthedocs](https://pytest-benchmark.readthedocs.io/en/latest/usage.html)) — Mar 2026 release. [CITED]
- **SciPy `solve_ivp` documentation** — confirms forward Euler is acceptable for non-stiff low-frequency thermal systems; `solve_ivp` has 20x overhead on small systems [CITED: scipy/scipy#8257].

### Secondary (MEDIUM confidence)
- [Click vs Typer 2025 comparison (pyinns.com)](https://www.pyinns.com/tools/click-vs-typer) — Typer preferred for FastAPI-ecosystem projects.
- [Hypothesis stateful testing docs](https://hypothesis.readthedocs.io/en/latest/stateful.html) — property-based invariant pattern.
- [NumPy broadcasting docs](https://numpy.org/doc/stable/user/basics.broadcasting.html) — scalar×(4,)-array overhead is minimal.
- [Numba performance tips](https://numba.readthedocs.io/en/stable/user/performance-tips.html) — confirms JIT overhead is wasteful for small hot paths; vectorization first.
- [Rich tables docs](https://rich.readthedocs.io/en/stable/tables.html) — CLI table rendering.

### Tertiary (LOW confidence, noted for planner)
- pytest-codspeed as alternative to pytest-benchmark for deterministic CI timing. Not adopted; listed as a fallback if Pitfall 7 materializes.

## Metadata

**Confidence breakdown:**
- Standard stack (Typer, pytest-benchmark, hypothesis, Rich): HIGH — all verified via PyPI dates ≤ 1 month old. Versions current as of April 2026.
- Architecture patterns (per-tire closed-form, orchestrator loop, frozen contracts): HIGH — derived directly from model_spec.md §Execution order, Phase 1 contracts, CONTEXT.md D-01/D-03.
- Pitfalls: MEDIUM-HIGH — derived from spec + numerical-methods common knowledge + the 50N floor + Arrhenius overflow are real issues from the equations themselves.
- Performance budget (200ms on 8000 samples): MEDIUM — needs empirical validation. The estimate is "8000 samples × ~25μs of numpy work each ≈ 200ms." Could go either way ±50% depending on per-sample overhead. Numba is the documented fallback.
- Execution-order enforcement approach: HIGH — `frozen=True` + AST test is a standard pattern for this class of constraint.

**Research date:** 2026-04-23
**Valid until:** 2026-05-23 (30 days — stack versions may update, but core patterns are stable)
