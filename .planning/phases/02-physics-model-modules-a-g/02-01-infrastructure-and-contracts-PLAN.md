---
phase: 02-physics-model-modules-a-g
plan: 01
type: execute
wave: 0
depends_on: []
files_modified:
  - packages/core/pyproject.toml
  - pyproject.toml
  - packages/core/src/f1_core/contracts.py
  - packages/core/src/f1_core/physics/__init__.py
  - packages/core/src/f1_core/physics/constants.py
  - packages/core/src/f1_core/physics/params.py
  - packages/core/src/f1_core/physics/defaults.py
  - packages/core/src/f1_core/physics/events.py
  - packages/core/tests/physics/__init__.py
  - packages/core/tests/physics/conftest.py
  - packages/core/tests/physics/test_module_a.py
  - packages/core/tests/physics/test_module_b.py
  - packages/core/tests/physics/test_module_c.py
  - packages/core/tests/physics/test_module_d.py
  - packages/core/tests/physics/test_module_e.py
  - packages/core/tests/physics/test_module_f.py
  - packages/core/tests/physics/test_module_g.py
  - packages/core/tests/physics/test_orchestrator.py
  - packages/core/tests/physics/test_architecture.py
  - packages/core/tests/physics/test_cli.py
  - packages/core/tests/physics/test_benchmark.py
  - packages/core/tests/test_contracts.py
autonomous: true
requirements: [PHYS-08, PHYS-09]
tags: [physics, infrastructure, contracts]

must_haves:
  truths:
    - "make_nominal_params() returns a PhysicsParams with four nested param dataclasses populated from model_spec.md §Parameter registry FIXED + SEMI-CONSTRAINED tables"
    - "contracts.py: WheelLoads, ContactPatch, SlipState, ThermalState, DegradationState are frozen dataclasses; SimulationState remains mutable"
    - "All physics test stubs exist under packages/core/tests/physics/ with xfail markers so the test suite still passes"
    - "typer, pytest-benchmark, hypothesis are installed and resolvable via uv"
    - "f1-simulate console script entry point is declared in packages/core/pyproject.toml [project.scripts]"
  artifacts:
    - path: "packages/core/src/f1_core/physics/params.py"
      provides: "AeroParams, FrictionParams, ThermalParams, DegradationParams, PhysicsParams dataclasses"
      contains: "@dataclass"
    - path: "packages/core/src/f1_core/physics/defaults.py"
      provides: "make_nominal_params() factory"
      exports: ["make_nominal_params"]
    - path: "packages/core/src/f1_core/physics/constants.py"
      provides: "FIXED physical constants (M_DRY, WB, T_F, T_R, R_0, b_tread_f, b_tread_r, C_RR, RHO_AIR, G)"
    - path: "packages/core/src/f1_core/physics/events.py"
      provides: "StatusEvent dataclass for Module E over-demand log"
    - path: "packages/core/tests/physics/conftest.py"
      provides: "shared fixtures nominal_params, canonical_stint_artifact, synthetic_kinematic_state"
  key_links:
    - from: "packages/core/pyproject.toml"
      to: "f1_core.physics.cli:app"
      via: "[project.scripts] f1-simulate entry point"
      pattern: "f1-simulate"
    - from: "packages/core/tests/physics/conftest.py"
      to: "packages/core/tests/fixtures/bahrain_2023_ver_stint2.pkl.gz"
      via: "gzip+pickle load"
      pattern: "bahrain_2023_ver_stint2"
---

<objective>
Wave 0 infrastructure for Phase 2. Installs new dependencies (typer, pytest-benchmark, hypothesis), creates the `f1_core.physics/` package skeleton with parameter dataclasses and nominal defaults, freezes the per-module output contracts in `contracts.py` (while keeping `SimulationState` mutable), creates the StatusEvent dataclass for over-demand logging, and produces test stub files so every downstream task has a ready verification target.

Purpose: Nyquist compliance requires tests exist before implementation. Centralizing params + constants here means Modules A–G can be implemented independently and in parallel in Wave 1 without racing on shared files.

Output: `packages/core/src/f1_core/physics/` package with `__init__.py`, `constants.py`, `params.py`, `defaults.py`, `events.py`; `packages/core/tests/physics/` with conftest + stub test files; `packages/core/pyproject.toml` updated with typer dependency and `f1-simulate` console script; root `pyproject.toml` updated with pytest-benchmark + hypothesis dev deps; `contracts.py` patched to freeze the six output dataclasses.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/02-physics-model-modules-a-g/02-CONTEXT.md
@.planning/phases/02-physics-model-modules-a-g/02-RESEARCH.md
@.planning/phases/02-physics-model-modules-a-g/02-VALIDATION.md
@model_spec.md
@packages/core/src/f1_core/contracts.py
@packages/core/pyproject.toml
@pyproject.toml
@packages/core/tests/conftest.py

<interfaces>
<!-- Existing Phase 1 contracts — Phase 2 must import from here, not redefine. -->

From packages/core/src/f1_core/contracts.py:
```python
F64Array = NDArray[np.float64]

@dataclass
class KinematicState:
    t: F64Array; v: F64Array; a_lat: F64Array; a_long: F64Array
    psi: F64Array; v_sx_rear: F64Array; kappa: F64Array

@dataclass
class WheelLoads:
    t: F64Array; f_z: F64Array  # (N, 4) FL/FR/RL/RR

@dataclass
class ContactPatch:
    t: F64Array; a_cp: F64Array; p_bar: F64Array  # both (N, 4)

@dataclass
class SlipState:
    t: F64Array; theta: F64Array; alpha: F64Array
    v_sy: F64Array; p_slide: F64Array; p_total: F64Array  # all (N, 4)

@dataclass
class ThermalState:
    t: F64Array; t_tread: F64Array; t_carc: F64Array; t_gas: F64Array  # (N, 4)

@dataclass
class DegradationState:
    t: F64Array; e_tire: F64Array; mu_0: F64Array; d_tread: F64Array

@dataclass
class SimulationState:
    t_tread: F64Array; t_carc: F64Array; t_gas: F64Array
    e_tire: F64Array; mu_0: float; d_tread: F64Array

@runtime_checkable
class PhysicsModule(Protocol):
    def step(self, state_in: SimulationState, telemetry_sample: object, params: object) -> SimulationState: ...
```

From packages/core/src/f1_core/ingestion/cache.py:
```python
@dataclass
class StintArtifact:
    key: StintKey
    car_data: pd.DataFrame
    pos_data: pd.DataFrame
    laps: pd.DataFrame
    weather: pd.DataFrame
    track_status: pd.DataFrame
    race_control_messages: pd.DataFrame
    session_metadata: dict[str, Any]
    fastf1_version: str
    preprocessing_version: str
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Install dependencies and declare f1-simulate console script</name>
  <files>packages/core/pyproject.toml, pyproject.toml</files>
  <read_first>
    - packages/core/pyproject.toml (current deps)
    - pyproject.toml (current dev group)
    - .planning/phases/02-physics-model-modules-a-g/02-RESEARCH.md §"Standard Stack" and §"Version verification"
  </read_first>
  <behavior>
    - After task: `uv sync` succeeds from project root
    - `uv run python -c "import typer; import pytest_benchmark; import hypothesis"` exits 0
    - `grep -q 'f1-simulate' packages/core/pyproject.toml` matches
  </behavior>
  <action>
    Edit `packages/core/pyproject.toml`:
    - Append to `[project] dependencies`: `"typer>=0.24,<1"`
    - Add new top-level table after `[project]`:
      ```toml
      [project.scripts]
      f1-simulate = "f1_core.physics.cli:app"
      ```
    - Keep existing `[build-system]` and `[tool.hatch.build.targets.wheel]` intact.

    Edit root `pyproject.toml` `[dependency-groups] dev`:
    - Append:
      ```
      "pytest-benchmark>=5.2,<6",
      "hypothesis>=6,<7",
      ```
    - Keep existing entries (pytest>=8, pytest-cov>=5, ruff>=0.7, pyright>=1.1, httpx>=0.27).

    After edits, run from project root: `uv sync`. This will resolve the new deps and install typer (with Rich as transitive), pytest-benchmark 5.2.3, and hypothesis 6.x.

    NOTE: Do NOT yet create `f1_core/physics/cli.py`. That file lands in Plan 06. The [project.scripts] entry declaring it is fine — `uv sync` resolves scripts lazily; they only need to exist when `uv run f1-simulate` is called.

    NOTE: NEVER skip hooks. If `uv sync` fails due to resolver issues, report the failure; do not add `--no-build` or similar bypass flags.
  </action>
  <verify>
    <automated>uv sync 2>&1 && uv run python -c "import typer, pytest_benchmark, hypothesis; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `packages/core/pyproject.toml` contains the literal string `typer>=0.24,<1`
    - `packages/core/pyproject.toml` contains `[project.scripts]` section with the literal string `f1-simulate = "f1_core.physics.cli:app"`
    - `pyproject.toml` (root) contains literal strings `pytest-benchmark>=5.2,<6` and `hypothesis>=6,<7`
    - `uv run python -c "import typer, pytest_benchmark, hypothesis"` exits 0
    - `uv.lock` has been updated (git status shows `uv.lock` modified)
  </acceptance_criteria>
  <done>New dev dependencies installed; `f1-simulate` console script declared but not yet runnable; `uv sync` green.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Freeze per-module output contracts + update Pydantic regression test</name>
  <files>packages/core/src/f1_core/contracts.py, packages/core/tests/test_contracts.py</files>
  <read_first>
    - packages/core/src/f1_core/contracts.py (current state — all @dataclass decorators)
    - packages/core/tests/test_contracts.py (current regression tests — must not break)
    - .planning/phases/02-physics-model-modules-a-g/02-RESEARCH.md §"Pattern 4: Execution order enforcement" — Mechanism 1
  </read_first>
  <behavior>
    - Test 1: Attempting `WheelLoads(t=..., f_z=...).f_z = new_arr` raises `dataclasses.FrozenInstanceError`
    - Test 2: Same for ContactPatch, SlipState, ThermalState, DegradationState, KinematicState
    - Test 3: `SimulationState(...).mu_0 = 0.5` succeeds (still mutable — it is the carryover state)
    - Test 4: Existing regression test `test_contracts_module_does_not_import_pydantic` still passes (no new imports)
    - Test 5: NEW test `test_f1_core_physics_does_not_import_pydantic` — walks `packages/core/src/f1_core/physics/` and asserts no file imports pydantic (guards D-03 boundary)
  </behavior>
  <action>
    In `packages/core/src/f1_core/contracts.py`, add `frozen=True` to these six dataclasses (and nothing else):
    - `KinematicState` → `@dataclass(frozen=True)`
    - `WheelLoads` → `@dataclass(frozen=True)`
    - `ContactPatch` → `@dataclass(frozen=True)`
    - `SlipState` → `@dataclass(frozen=True)`
    - `ThermalState` → `@dataclass(frozen=True)`
    - `DegradationState` → `@dataclass(frozen=True)`

    Do NOT add `frozen=True` to:
    - `SimulationState` — stays mutable (RESEARCH.md §"Pattern 4", Open Question #1). It is updated in-place across the orchestrator loop.
    - `QualityReport` — Phase 1 concern, unchanged.

    Do NOT add `slots=True`. RESEARCH.md A3 flags risk to Phase 1 tests; keep change minimal.

    In `packages/core/tests/test_contracts.py`, add these new tests AT THE END of the file (do not modify existing tests):

    ```python
    import pytest
    from dataclasses import FrozenInstanceError
    import numpy as np

    @pytest.mark.parametrize("cls_name,kwargs", [
        ("KinematicState", dict(t=np.zeros(1), v=np.zeros(1), a_lat=np.zeros(1),
                                a_long=np.zeros(1), psi=np.zeros(1),
                                v_sx_rear=np.zeros(1), kappa=np.zeros(1))),
        ("WheelLoads",    dict(t=np.zeros(1), f_z=np.zeros((1, 4)))),
        ("ContactPatch",  dict(t=np.zeros(1), a_cp=np.zeros((1, 4)), p_bar=np.zeros((1, 4)))),
        ("SlipState",     dict(t=np.zeros(1), theta=np.zeros((1, 4)), alpha=np.zeros((1, 4)),
                               v_sy=np.zeros((1, 4)), p_slide=np.zeros((1, 4)),
                               p_total=np.zeros((1, 4)))),
        ("ThermalState",  dict(t=np.zeros(1), t_tread=np.zeros((1, 4)),
                               t_carc=np.zeros((1, 4)), t_gas=np.zeros((1, 4)))),
        ("DegradationState", dict(t=np.zeros(1), e_tire=np.zeros((1, 4)),
                                  mu_0=np.zeros(1), d_tread=np.zeros((1, 4)))),
    ])
    def test_module_output_contracts_are_frozen(cls_name, kwargs):
        """PHYS-09 / PHYS-08: per-module outputs are immutable to prevent cross-module mutation."""
        from f1_core import contracts
        cls = getattr(contracts, cls_name)
        obj = cls(**kwargs)
        # Grab first field name to attempt rebind
        first_field = next(iter(kwargs))
        with pytest.raises(FrozenInstanceError):
            setattr(obj, first_field, kwargs[first_field])

    def test_simulation_state_is_mutable():
        """SimulationState is the carryover state — must stay mutable for the orchestrator loop."""
        from f1_core.contracts import SimulationState
        s = SimulationState(
            t_tread=np.zeros(4), t_carc=np.zeros(4), t_gas=np.zeros(4),
            e_tire=np.zeros(4), mu_0=1.8, d_tread=np.full(4, 0.008),
        )
        s.mu_0 = 1.7   # must not raise
        assert s.mu_0 == 1.7

    def test_f1_core_physics_does_not_import_pydantic():
        """D-03 boundary: physics/ subpackage must not import pydantic (same rule as contracts.py)."""
        from pathlib import Path
        phys_dir = Path("packages/core/src/f1_core/physics")
        if not phys_dir.exists():
            pytest.skip("physics/ not yet created")
        for py_file in phys_dir.rglob("*.py"):
            src = py_file.read_text()
            assert "import pydantic" not in src, f"{py_file} imports pydantic"
            assert "from pydantic" not in src, f"{py_file} imports pydantic"
    ```

    Every equation/comment citation convention: this file is pure contracts — no physics equations, so no §section citations needed here. Module files in later plans MUST cite model_spec.md §X.Y per the CONTEXT.md convention.
  </action>
  <verify>
    <automated>uv run pytest packages/core/tests/test_contracts.py -x --benchmark-disable</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "@dataclass(frozen=True)" packages/core/src/f1_core/contracts.py` returns 6
    - `grep "class SimulationState" packages/core/src/f1_core/contracts.py` is followed (within 1 line) by `@dataclass` WITHOUT `frozen=True`
    - `uv run pytest packages/core/tests/test_contracts.py::test_module_output_contracts_are_frozen -x` exits 0 with 6 parametrized cases passing
    - `uv run pytest packages/core/tests/test_contracts.py::test_simulation_state_is_mutable -x` exits 0
    - `uv run pytest packages/core/tests/test_contracts.py -x` exits 0 (all existing regression tests still pass)
  </acceptance_criteria>
  <done>Six module output dataclasses are frozen; SimulationState stays mutable; pydantic-exclusion test extended to cover forthcoming physics subdirectory; full Phase 1 test suite still green.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Create f1_core.physics package with constants, params, defaults, events</name>
  <files>
    packages/core/src/f1_core/physics/__init__.py,
    packages/core/src/f1_core/physics/constants.py,
    packages/core/src/f1_core/physics/params.py,
    packages/core/src/f1_core/physics/defaults.py,
    packages/core/src/f1_core/physics/events.py
  </files>
  <read_first>
    - model_spec.md §"Parameter registry" (FIXED, SEMI-CONSTRAINED, LEARNED tables)
    - model_spec.md §D.5 (μ_0, p̄_0, n, T_opt, σ_T semantics)
    - model_spec.md §F.5 (h_0, h_1 typical values)
    - model_spec.md §G.2 (T_ref=80°C, T_act≈25°C, β_therm)
    - .planning/phases/02-physics-model-modules-a-g/02-CONTEXT.md §"Parameters Structure" D-03, D-04
    - packages/core/src/f1_core/contracts.py (for F64Array type alias — re-import, don't redefine)
  </read_first>
  <action>
    Create each file with the following EXACT content structure. Every field listed must appear with the specified name, type, and default value. Do NOT substitute alternative values or call it a "v1" / placeholder — these ARE the Phase 2 nominal priors per D-04.

    **`packages/core/src/f1_core/physics/__init__.py`:**
    ```python
    """f1_core.physics — seven-module forward simulation pipeline (Phase 2).

    model_spec.md §A–G is the authoritative spec. Every equation in submodules
    must cite its section (e.g., "model_spec.md §B.2") and its source paper.
    """
    from f1_core.physics.events import StatusEvent
    from f1_core.physics.params import (
        AeroParams,
        DegradationParams,
        FrictionParams,
        PhysicsParams,
        ThermalParams,
    )
    from f1_core.physics.defaults import make_nominal_params

    __all__ = [
        "AeroParams",
        "DegradationParams",
        "FrictionParams",
        "PhysicsParams",
        "StatusEvent",
        "ThermalParams",
        "make_nominal_params",
    ]
    ```

    **`packages/core/src/f1_core/physics/constants.py`:**
    ```python
    """FIXED physical constants (model_spec.md §Parameter registry FIXED table).

    These are NOT calibrated — they are regulatory, geometric, or published
    physical constants. Per CONTEXT.md D-04, these live as module-level
    constants rather than fields on any params dataclass.
    """
    from __future__ import annotations

    # Vehicle mass & geometry — model_spec.md §Parameter registry FIXED
    M_DRY: float = 798.0          # kg, minimum car mass incl. driver (FIA regulation)
    WB: float = 3.6               # m, wheelbase
    T_F: float = 1.60             # m, front track width
    T_R: float = 1.60             # m, rear track width
    R_0: float = 0.330            # m, tire nominal radius

    # Tread half-widths — model_spec.md §D.2 (front narrower than rear)
    B_TREAD_F: float = 0.15       # m
    B_TREAD_R: float = 0.20       # m

    # Environment — model_spec.md §B.4
    RHO_AIR: float = 1.20         # kg/m³, nominal air density

    # Rolling resistance — model_spec.md §E.6
    C_RR: float = 0.012

    # Gravitational acceleration
    G: float = 9.81               # m/s²

    # Total mass used for quick nominal load calculations (dry + nominal fuel).
    # Module B will add time-varying fuel mass in Phase 3; for Phase 2 nominal
    # we include ~50 kg mid-race fuel estimate.
    M_FUEL_NOMINAL: float = 50.0  # kg
    M_TOT: float = M_DRY + M_FUEL_NOMINAL  # kg

    # Per-tire tread contact area — used by Module F convection term.
    # Approximated as 2 * a_cp_nominal * b_tread with a_cp_nominal ~= 0.08 m.
    A_TREAD_F: float = 2 * 0.08 * B_TREAD_F   # m² per front tire
    A_TREAD_R: float = 2 * 0.08 * B_TREAD_R   # m² per rear tire
    # Module F uses these as a per-tire (4,) array for convection.

    # Reference temperature for Arrhenius aging — model_spec.md §G.2
    T_REF_AGING: float = 80.0     # °C

    # Carcass convection coefficient (lumped). model_spec.md §F.2 assumes a
    # slower exchange than the tread surface; nominal h_carc=5 W/m²K.
    H_CARC: float = 5.0           # W/m²K
    A_CARC_F: float = 0.18        # m² per front tire, lumped sidewall area
    A_CARC_R: float = 0.22        # m² per rear tire

    __all__ = [
        "A_CARC_F", "A_CARC_R", "A_TREAD_F", "A_TREAD_R",
        "B_TREAD_F", "B_TREAD_R",
        "C_RR", "G", "H_CARC",
        "M_DRY", "M_FUEL_NOMINAL", "M_TOT",
        "RHO_AIR", "R_0",
        "T_F", "T_R", "T_REF_AGING", "WB",
    ]
    ```

    **`packages/core/src/f1_core/physics/params.py`:**
    ```python
    """Physics parameter dataclasses (model_spec.md §Parameter registry LEARNED + SEMI-CONSTRAINED).

    Per CONTEXT.md D-03: four nested dataclasses, one per calibration stage.
    Each physics module receives only its own params dataclass.

    NOTE: These are frozen=True to prevent accidental mutation during a simulation
    run. A new PhysicsParams is built per simulation call.
    """
    from __future__ import annotations

    from dataclasses import dataclass


    @dataclass(frozen=True)
    class AeroParams:
        """Stage 1 calibration target — model_spec.md §B.4 + §Calibration staging Stage 1.

        Fields:
            C_LA: lift coefficient * reference area [m²]  (C_L·A in model_spec)
            C_DA: drag coefficient * reference area [m²]  (C_D·A)
            xi:   aero balance, fraction of downforce on front axle [-] (ξ)
            K_rf_split: front roll-stiffness split K_rf / (K_rf + K_rr) [-]  (model_spec §B.3)
            WD:   static front weight distribution [-]  (semi-constrained, §B.1)
            H_CG: center-of-gravity height [m]  (semi-constrained)
            BB:   brake bias, fraction on front axle [-]  (semi-constrained, §C.3)
        """
        C_LA: float
        C_DA: float
        xi: float
        K_rf_split: float
        WD: float
        H_CG: float
        BB: float


    @dataclass(frozen=True)
    class FrictionParams:
        """Stage 2 calibration target — model_spec.md §D.3–§D.5 + §E.1.

        Fields:
            mu_0_fresh: reference friction of a fresh tire [-]  (§D.3, μ_0^fresh)
            p_bar_0:    reference contact pressure [Pa]          (§D.3, p̄_0)
            n:          load exponent, A_real ∝ p̄^n, typical 0.75–0.85 [-]
            c_py:       brush-model tread lateral stiffness [N/m³]  (§E.1, C_α = c_py·a_cp²)
            K_rad:      tire radial stiffness [N/m]  (semi-constrained, §D.1 δ = F_z/K_rad)
        """
        mu_0_fresh: float
        p_bar_0: float
        n: float
        c_py: float
        K_rad: float


    @dataclass(frozen=True)
    class ThermalParams:
        """Stage 3 calibration target — model_spec.md §D.4, §F.1–§F.6.

        Fields:
            T_opt:      optimal tread temperature [°C]   (§D.4)
            sigma_T:    Grosch bell half-width [°C]     (§D.4)
            C_tread:    tread thermal capacity [J/K]    (§F.1, per tire)
            C_carc:     carcass thermal capacity [J/K]  (§F.2, per tire)
            C_gas:      gas thermal capacity [J/K]      (§F.3, per tire)
            R_tc:       tread-carcass resistance [K/W]  (§F.1)
            R_cg:       carcass-gas resistance [K/W]    (§F.2)
            h_0:        convection base [W/m²K]         (§F.5)
            h_1:        convection V-coeff [W/m²K/(m/s)^0.5]  (§F.5)
            alpha_p:    heat partition fraction into tire [-]  (§F.4)
            delta_T_blanket: initial tread preheat above T_track [°C]  (§F.6, semi-constrained)
        """
        T_opt: float
        sigma_T: float
        C_tread: float
        C_carc: float
        C_gas: float
        R_tc: float
        R_cg: float
        h_0: float
        h_1: float
        alpha_p: float
        delta_T_blanket: float


    @dataclass(frozen=True)
    class DegradationParams:
        """Stage 4 calibration target — model_spec.md §G.2–§G.3.

        Fields:
            beta_therm: Arrhenius-aging rate coefficient [1/s]    (§G.2)
            T_act:      activation temperature scale [°C]         (§G.2)
            k_wear:     mechanical-wear rate per unit sliding power [m·W⁻¹·s⁻¹]  (§G.3)
        """
        beta_therm: float
        T_act: float
        k_wear: float


    @dataclass(frozen=True)
    class PhysicsParams:
        """Thin container grouping the four stage-specific param dataclasses.

        The orchestrator receives PhysicsParams and passes only the relevant
        inner params to each module — never the full container (D-03).
        """
        aero: AeroParams
        friction: FrictionParams
        thermal: ThermalParams
        degradation: DegradationParams


    __all__ = [
        "AeroParams",
        "DegradationParams",
        "FrictionParams",
        "PhysicsParams",
        "ThermalParams",
    ]
    ```

    **`packages/core/src/f1_core/physics/defaults.py`:**
    ```python
    """Nominal parameter priors — model_spec.md §Parameter registry typical values.

    Per CONTEXT.md D-04: single source of default initialization for all
    Phase 2 forward simulations. These values are INTENTIONALLY approximate;
    Phase 3 calibration replaces them with fitted posteriors.

    Citation convention: every value below cites the model_spec.md table or
    section it came from. If you change a default, update the citation.
    """
    from __future__ import annotations

    from f1_core.physics.params import (
        AeroParams,
        DegradationParams,
        FrictionParams,
        PhysicsParams,
        ThermalParams,
    )


    def make_nominal_params() -> PhysicsParams:
        """Return a PhysicsParams populated with mid-range nominal priors.

        Phase 2 uses this for CLI invocations and as the pytest fixture
        baseline. Phase 3 calibration replaces every LEARNED value.
        """
        aero = AeroParams(
            # LEARNED — model_spec.md §Parameter registry LEARNED "C_L A" typical F1 2023+
            C_LA=4.5,          # m², mid-range downforce setup
            C_DA=1.1,          # m², mid-range drag
            # LEARNED — §B.4 aero balance ξ
            xi=0.45,           # 45% front downforce (typical race setup)
            # LEARNED — §B.3 roll-stiffness split
            K_rf_split=0.55,   # K_rf / (K_rf + K_rr) — front-biased roll stiffness
            # SEMI-CONSTRAINED — §B.1 WD 0.43–0.46
            WD=0.445,
            # SEMI-CONSTRAINED — §B range 0.26–0.30 m
            H_CG=0.28,
            # SEMI-CONSTRAINED — §C.3 brake bias 0.55–0.60
            BB=0.575,
        )
        friction = FrictionParams(
            # LEARNED — §D.3 μ_0^fresh typical 1.6–2.0 for F1 slick
            mu_0_fresh=1.8,
            # LEARNED — §D.3 reference pressure 1.5 bar ≈ 1.5e5 Pa
            p_bar_0=1.5e5,
            # LEARNED — §D.3 load exponent typical 0.75–0.85
            n=0.8,
            # LEARNED — §E.1 brush tread stiffness, typical 1e8 N/m³ for racing slick
            c_py=1.0e8,
            # SEMI-CONSTRAINED — §D.1 K_rad 200–300 kN/m
            K_rad=250_000.0,   # N/m
        )
        thermal = ThermalParams(
            # LEARNED — §D.4 T_opt typical 90–105 °C for modern F1 slicks
            T_opt=95.0,
            # LEARNED — §D.4 σ_T typical 18–22 °C
            sigma_T=20.0,
            # LEARNED — §F.1 tread thermal capacity lumped ≈ 6000 J/K per tire
            C_tread=6000.0,
            # LEARNED — §F.2 carcass capacity ≈ 20000 J/K
            C_carc=20000.0,
            # LEARNED — §F.3 gas capacity ≈ 500 J/K
            C_gas=500.0,
            # LEARNED — §F.1 R_tc typical 0.02 K/W (conductive path through rubber)
            R_tc=0.02,
            # LEARNED — §F.2 R_cg typical 0.05 K/W (across inner liner)
            R_cg=0.05,
            # LEARNED — §F.5 typical h_0=10 W/m²K
            h_0=10.0,
            # LEARNED — §F.5 typical h_1=8 W/m²K/(m/s)^0.5
            h_1=8.0,
            # LEARNED — §F.4 α_p ≈ 0.55 for slicks on asphalt
            alpha_p=0.55,
            # SEMI-CONSTRAINED — §F.6 ΔT_blanket 50–70 °C
            delta_T_blanket=60.0,
        )
        degradation = DegradationParams(
            # LEARNED — §G.2 β_therm typical 1e-6 /s (slow aging)
            beta_therm=1.0e-6,
            # LEARNED — §G.2 "every 25°C above T_ref doubles rate"
            T_act=25.0,
            # LEARNED — §G.3 k_wear typical 1e-12 m/(W·s) for slicks
            k_wear=1.0e-12,
        )
        return PhysicsParams(aero=aero, friction=friction, thermal=thermal, degradation=degradation)


    __all__ = ["make_nominal_params"]
    ```

    **`packages/core/src/f1_core/physics/events.py`:**
    ```python
    """Status events emitted by Module E when force demand exceeds grip.

    Per model_spec.md §E.2 clip path and CONTEXT.md §"Common Pitfalls" Pitfall 6:
    the event log is capped at MAX_EVENTS to prevent unbounded memory growth
    on pathological parameter sets.
    """
    from __future__ import annotations

    from dataclasses import dataclass

    # Pitfall 6 (Research §"Common Pitfalls"): cap total events in a run.
    MAX_EVENTS: int = 500


    @dataclass(frozen=True)
    class StatusEvent:
        """A single diagnostic event from Module E over-demand clipping.

        Fields:
            t:         timestamp [s] at which the event was emitted
            tire_index: 0=FL, 1=FR, 2=RL, 3=RR
            kind:      short machine-readable kind code, e.g. "over_demand_lat"
            message:   human-readable description for CLI / UI status log
            ratio:     |F_y|/(μ·F_z) at emission time — >=1.0 means demand ≥ grip
        """
        t: float
        tire_index: int
        kind: str
        message: str
        ratio: float


    __all__ = ["MAX_EVENTS", "StatusEvent"]
    ```

    Also create empty `packages/core/tests/physics/__init__.py` (a single comment line: `# Test package for f1_core.physics`).
  </action>
  <verify>
    <automated>uv run python -c "from f1_core.physics import make_nominal_params, AeroParams, FrictionParams, ThermalParams, DegradationParams, PhysicsParams, StatusEvent; p = make_nominal_params(); assert isinstance(p, PhysicsParams); assert p.aero.C_LA == 4.5; assert p.friction.mu_0_fresh == 1.8; assert p.thermal.T_opt == 95.0; assert p.degradation.beta_therm == 1.0e-6; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - File `packages/core/src/f1_core/physics/__init__.py` exists and exports `make_nominal_params`, `PhysicsParams`, `StatusEvent`, four `*Params` classes
    - `packages/core/src/f1_core/physics/constants.py` contains literal assignments `M_DRY = 798.0`, `WB = 3.6`, `R_0 = 0.330`, `C_RR = 0.012`, `RHO_AIR = 1.20`, `G = 9.81`, `B_TREAD_F = 0.15`, `B_TREAD_R = 0.20`, `T_REF_AGING = 80.0`
    - `packages/core/src/f1_core/physics/params.py` defines exactly five dataclasses (`AeroParams`, `FrictionParams`, `ThermalParams`, `DegradationParams`, `PhysicsParams`), all with `frozen=True`
    - `packages/core/src/f1_core/physics/events.py` defines `StatusEvent` (frozen) with fields `t, tire_index, kind, message, ratio` and module-level `MAX_EVENTS = 500`
    - `uv run python -c "from f1_core.physics import make_nominal_params; p = make_nominal_params(); assert p.friction.mu_0_fresh == 1.8"` exits 0
    - Every numeric default in defaults.py has an inline `# LEARNED` or `# SEMI-CONSTRAINED` comment citing the spec section
  </acceptance_criteria>
  <done>Physics package skeleton exists; nominal params importable; every default value sourced from model_spec.md; Pydantic exclusion test auto-covers the new directory.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 4: Create test stub files and shared conftest fixtures</name>
  <files>
    packages/core/tests/physics/conftest.py,
    packages/core/tests/physics/test_module_a.py,
    packages/core/tests/physics/test_module_b.py,
    packages/core/tests/physics/test_module_c.py,
    packages/core/tests/physics/test_module_d.py,
    packages/core/tests/physics/test_module_e.py,
    packages/core/tests/physics/test_module_f.py,
    packages/core/tests/physics/test_module_g.py,
    packages/core/tests/physics/test_orchestrator.py,
    packages/core/tests/physics/test_architecture.py,
    packages/core/tests/physics/test_cli.py,
    packages/core/tests/physics/test_benchmark.py
  </files>
  <read_first>
    - packages/core/tests/conftest.py (existing fixtures — don't duplicate)
    - packages/core/tests/test_gear_inference.py (fixture loading pattern for canonical stint)
    - .planning/phases/02-physics-model-modules-a-g/02-VALIDATION.md (one-stub-per-row requirement)
    - .planning/phases/02-physics-model-modules-a-g/02-RESEARCH.md §"Pattern 3: Invariant test styles"
  </read_first>
  <action>
    Each stub test file must have real test function names (so pytest collection lists them), but the bodies MUST be `pytest.skip("Pending: Plan 02-0X")` referencing the implementing plan. Do NOT use `pytest.xfail` — research says stubs skip; the RED-GREEN cycle happens when the downstream plan replaces the skip with real assertions.

    **`packages/core/tests/physics/conftest.py`:**
    ```python
    """Shared fixtures for physics tests (Phase 2).

    fixtures:
      - nominal_params: make_nominal_params() baseline
      - canonical_stint_artifact: 2023 Bahrain VER Stint 2 loaded from disk fixture
      - synthetic_kinematic_state: short (N=100) KinematicState with realistic numbers
    """
    from __future__ import annotations

    import gzip
    import pickle
    from collections.abc import Iterator
    from pathlib import Path

    import numpy as np
    import pytest

    from f1_core.contracts import KinematicState
    from f1_core.ingestion.cache import StintArtifact
    from f1_core.physics import PhysicsParams, make_nominal_params

    FIX_DIR = Path(__file__).parent.parent / "fixtures"


    @pytest.fixture
    def nominal_params() -> PhysicsParams:
        return make_nominal_params()


    @pytest.fixture
    def canonical_stint_artifact() -> Iterator[StintArtifact]:
        """2023 Bahrain GP, VER, Stint 2 — canonical fixture pickled in Phase 1."""
        p = FIX_DIR / "bahrain_2023_ver_stint2.pkl.gz"
        if not p.exists():
            pytest.skip("canonical fixture missing — run Phase 1 fixture generation")
        with gzip.open(p, "rb") as f:
            artifact = pickle.load(f)
        yield artifact


    @pytest.fixture
    def synthetic_kinematic_state() -> KinematicState:
        """Hand-built (N=100) kinematic state — steady 70 m/s, κ=0, no lateral accel.

        Useful for module unit tests that need shape-compatible input without
        requiring a real fixture.
        """
        n = 100
        t = np.arange(n) * 0.25
        v = np.full(n, 70.0)
        kappa = np.zeros(n)
        return KinematicState(
            t=t,
            v=v,
            a_lat=v * v * kappa,
            a_long=np.zeros(n),
            psi=np.zeros(n),
            v_sx_rear=np.zeros(n),
            kappa=kappa,
        )
    ```

    **`packages/core/tests/physics/test_module_a.py`:**
    ```python
    """PHYS-01 — Module A (Kinematics preprocessor) invariants. Implemented by Plan 02."""
    import pytest


    def test_module_a_process_stint_produces_kinematic_state_of_correct_shape():
        pytest.skip("Pending: Plan 02 implements Module A")


    def test_module_a_a_lat_equals_v_squared_kappa():
        """model_spec.md §A.2: a_lat(t) = V(t)² · κ(s(t))."""
        pytest.skip("Pending: Plan 02 implements Module A")


    def test_module_a_a_long_matches_savgol_derivative():
        """model_spec.md §A.2: a_long = dV/dt via Savitzky-Golay window=9 order=3."""
        pytest.skip("Pending: Plan 02 implements Module A")


    def test_module_a_v_sx_rear_from_rpm_and_gear_ratios():
        """model_spec.md §A.4: V_sx,r = V_wheel,r − V."""
        pytest.skip("Pending: Plan 02 implements Module A")


    def test_module_a_on_canonical_fixture_completes(canonical_stint_artifact, nominal_params):
        """Smoke test on real fixture — Plan 02 wires up."""
        pytest.skip("Pending: Plan 02 implements Module A")
    ```

    **`packages/core/tests/physics/test_module_b.py`:**
    ```python
    """PHYS-02 — Module B (Vertical loads) invariants. Implemented by Plan 03."""
    import pytest


    def test_module_b_vertical_force_balance_closure():
        """model_spec.md §B.5: ΣF_z,i = M·g + F_aero(V), rtol=1e-10 on synthetic inputs (clip-free range)."""
        pytest.skip("Pending: Plan 03 implements Module B")


    def test_module_b_per_tire_shape_is_4():
        pytest.skip("Pending: Plan 03 implements Module B")


    def test_module_b_50n_floor_clips_below_threshold():
        """model_spec.md §B.5 floor: F_z,i ≥ 50 N."""
        pytest.skip("Pending: Plan 03 implements Module B")


    def test_module_b_hypothesis_invariant_holds_in_non_clip_range():
        """hypothesis: ∀ v∈[20,90], a_lat∈[-30,30], a_long∈[-40,20], ΣF_z ≈ M·g + F_aero."""
        pytest.skip("Pending: Plan 03 implements Module B")
    ```

    **`packages/core/tests/physics/test_module_c.py`:**
    ```python
    """PHYS-03 — Module C (Force distribution) invariants. Implemented by Plan 03."""
    import pytest


    def test_module_c_sum_f_y_equals_m_a_lat_exactly():
        """model_spec.md §C.2: ΣF_y,i = F_y,G = M·a_lat (load-proportional allocation is exact)."""
        pytest.skip("Pending: Plan 03 implements Module C")


    def test_module_c_power_on_rear_only_rwd():
        """model_spec.md §C.3: F_x^power=0 for FL,FR; all positive longitudinal on rear."""
        pytest.skip("Pending: Plan 03 implements Module C")


    def test_module_c_brake_bias_applied_when_decelerating():
        """model_spec.md §C.3: brake component scales by BB on fronts, (1-BB) on rears when F_x,G < 0."""
        pytest.skip("Pending: Plan 03 implements Module C")
    ```

    **`packages/core/tests/physics/test_module_d.py`:**
    ```python
    """PHYS-04 — Module D (Hertzian contact + friction) invariants. Implemented by Plan 04."""
    import pytest


    def test_module_d_mu_identity_at_reference_point():
        """model_spec.md §D.5: μ(T_opt, p̄_0) = μ_0 exactly."""
        pytest.skip("Pending: Plan 04 implements Module D")


    def test_module_d_a_cp_scales_as_sqrt_f_z():
        """model_spec.md §D.1: a_cp,i = √(2·R_0·F_z,i/K_rad)."""
        pytest.skip("Pending: Plan 04 implements Module D")


    def test_module_d_p_bar_equals_f_z_over_4a_cp_b_tread():
        """model_spec.md §D.2: p̄_i = F_z,i / (4·a_cp,i·b_tread)."""
        pytest.skip("Pending: Plan 04 implements Module D")


    def test_module_d_grosch_bell_returns_unity_at_t_opt():
        """model_spec.md §D.4: g(T_opt) = 1.0."""
        pytest.skip("Pending: Plan 04 implements Module D")
    ```

    **`packages/core/tests/physics/test_module_e.py`:**
    ```python
    """PHYS-05 — Module E (Slip inversion + events) invariants. Implemented by Plan 04."""
    import pytest


    def test_module_e_theta_identity_when_force_equals_grip():
        """model_spec.md §E.2: |F_y|=μ·F_z ⇒ Θ = 1."""
        pytest.skip("Pending: Plan 04 implements Module E")


    def test_module_e_clips_theta_at_1_on_over_demand():
        """model_spec.md §E.2 validity check: |F_y| > μ·F_z ⇒ Θ clipped to 1."""
        pytest.skip("Pending: Plan 04 implements Module E")


    def test_module_e_emits_event_on_over_demand():
        """PHYS-05: over-demand logs a StatusEvent to the events list."""
        pytest.skip("Pending: Plan 04 implements Module E")


    def test_module_e_event_log_caps_at_max_events():
        """Pitfall 6: events list capped at MAX_EVENTS=500 with truncated flag."""
        pytest.skip("Pending: Plan 04 implements Module E")


    def test_module_e_p_slide_nonnegative():
        """model_spec.md §E.5: P_slide,i = |F_y|·|V_sy| + |F_x|·|V_sx| ≥ 0."""
        pytest.skip("Pending: Plan 04 implements Module E")
    ```

    **`packages/core/tests/physics/test_module_f.py`:**
    ```python
    """PHYS-06 — Module F (Thermal ODE) invariants. Implemented by Plan 05."""
    import pytest


    def test_module_f_forward_euler_delta_t_is_0_25s():
        """model_spec.md §F.7: Δt = 0.25 s forward Euler."""
        pytest.skip("Pending: Plan 05 implements Module F")


    def test_module_f_steady_state_dT_equals_zero():
        """model_spec.md §F + Criterion 4: with chosen P_total such that RHS=0, T stays constant."""
        pytest.skip("Pending: Plan 05 implements Module F")


    def test_module_f_60_lap_synthetic_stint_no_divergence():
        """Criterion 4: 60-lap synthetic stint at fixed kinematics does not blow up."""
        pytest.skip("Pending: Plan 05 implements Module F")


    def test_module_f_initial_conditions_from_track_temp_plus_blanket():
        """model_spec.md §F.6: T_tread(0) = T_track + ΔT_blanket."""
        pytest.skip("Pending: Plan 05 implements Module F")
    ```

    **`packages/core/tests/physics/test_module_g.py`:**
    ```python
    """PHYS-07 — Module G (Degradation) invariants. Implemented by Plan 05."""
    import pytest


    def test_module_g_e_tire_monotonically_non_decreasing():
        """model_spec.md §G.1 + Criterion 6: ΔE_tire = P_total·Δt ≥ 0."""
        pytest.skip("Pending: Plan 05 implements Module G")


    def test_module_g_d_tread_monotonically_non_increasing():
        """model_spec.md §G.3 + Criterion 6: dd_tread/dt = -k_wear·P_slide ≤ 0."""
        pytest.skip("Pending: Plan 05 implements Module G")


    def test_module_g_mu_0_declines_under_sustained_high_temperature():
        """model_spec.md §G.2 + Criterion 6: sustained T_tread > T_ref drives μ_0 down."""
        pytest.skip("Pending: Plan 05 implements Module G")


    def test_module_g_delta_t_lap_scales_with_mu_loss():
        """model_spec.md §G.4: Δt_lap = (t_ref/2)·(μ_0^fresh − μ_0(t))/μ_0^fresh."""
        pytest.skip("Pending: Plan 05 implements Module G")
    ```

    **`packages/core/tests/physics/test_orchestrator.py`:**
    ```python
    """PHYS-08, PHYS-09 — Execution order and state carry. Implemented by Plan 06."""
    import pytest


    def test_orchestrator_calls_module_a_once_then_b_to_g_per_timestep():
        """PHYS-09: one A call, then B→C→D→E→F→G repeated per sample."""
        pytest.skip("Pending: Plan 06 implements orchestrator")


    def test_orchestrator_module_d_reads_previous_t_tread():
        """Pitfall 3 / model_spec §D.5: D reads state.t_tread BEFORE F updates it."""
        pytest.skip("Pending: Plan 06 implements orchestrator")


    def test_orchestrator_simulation_state_is_mutable_carryover():
        """SimulationState updates in place across timesteps, module outputs frozen."""
        pytest.skip("Pending: Plan 06 implements orchestrator")
    ```

    **`packages/core/tests/physics/test_architecture.py`:**
    ```python
    """PHYS-08, PHYS-09 — Architecture linter-style tests. Implemented by Plan 07."""
    import pytest


    def test_per_timestep_modules_have_no_per_tire_for_loops():
        """AST check: modules b-g use numpy broadcasts, no Python for i in range(4)."""
        pytest.skip("Pending: Plan 07 implements AST linter test")


    def test_physics_modules_do_not_import_each_other():
        """AST check: module_b.py must not import module_c; only orchestrator.py may."""
        pytest.skip("Pending: Plan 07 implements AST linter test")


    def test_physics_modules_do_not_import_fastf1():
        """Boundary: FastF1 only in ingestion layer; physics modules receive typed inputs."""
        pytest.skip("Pending: Plan 07 implements AST linter test")
    ```

    **`packages/core/tests/physics/test_cli.py`:**
    ```python
    """D-05 — f1-simulate CLI integration. Implemented by Plan 06."""
    import pytest


    def test_cli_prints_per_lap_table_on_canonical_fixture():
        """`f1-simulate 2023 Bahrain VER 2` prints table, exit 0."""
        pytest.skip("Pending: Plan 06 implements CLI")


    def test_cli_exits_nonzero_on_invalid_driver_code():
        """validate_driver_code regex ^[A-Z]{3}$ enforced via load_stint."""
        pytest.skip("Pending: Plan 06 implements CLI")


    def test_cli_exits_nonzero_on_unknown_event():
        """FastF1 get_event_schedule returns no match → typer.Exit(code=2)."""
        pytest.skip("Pending: Plan 06 implements CLI")
    ```

    **`packages/core/tests/physics/test_benchmark.py`:**
    ```python
    """Criterion 2 — <200 ms forward simulation on canonical fixture. Implemented by Plan 07."""
    import pytest


    @pytest.mark.benchmark(group="physics_pipeline_dev_laptop")
    def test_full_stint_under_200ms_dev_laptop(benchmark):
        pytest.skip("Pending: Plan 07 implements benchmark")


    @pytest.mark.benchmark(group="physics_pipeline_ci")
    def test_full_stint_under_600ms_ci(benchmark):
        pytest.skip("Pending: Plan 07 implements benchmark")
    ```
  </action>
  <verify>
    <automated>uv run pytest packages/core/tests/physics/ -x --benchmark-disable --co -q 2>&1 | grep -cE "test_" && uv run pytest packages/core/tests/physics/ --benchmark-disable -q 2>&1 | tail -5</automated>
  </verify>
  <acceptance_criteria>
    - `uv run pytest packages/core/tests/physics/ --collect-only --benchmark-disable -q` collects at least 30 test IDs (one per function in the 10 stub files + conftest's implied)
    - `uv run pytest packages/core/tests/physics/ --benchmark-disable -q` exits 0 with every test reporting as `s` (skipped) — no `F` (failed) and no `E` (errored)
    - `grep -rn "pytest.skip" packages/core/tests/physics/` returns at least 30 matches (one per stub test function body)
    - `packages/core/tests/physics/conftest.py` defines fixtures `nominal_params`, `canonical_stint_artifact`, and `synthetic_kinematic_state`
    - `uv run pytest packages/core/tests/ --benchmark-disable -q` (full suite) exits 0 (all existing Phase 1 tests still pass, all new stubs skip cleanly)
  </acceptance_criteria>
  <done>11 stub test files + conftest + __init__.py exist under packages/core/tests/physics/; every stub test skips with a pointer to its implementing plan; full test suite green.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| CLI args → load_stint | driver_code, year, event, stint_index pass through Typer to Phase 1's validated load_stint. Not introduced in this plan. |
| pyproject.toml → uv sync | Dependency resolution from PyPI. uv verifies lock hashes. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-01 | Tampering | `uv sync` resolves typer/pytest-benchmark/hypothesis from PyPI | accept | uv writes sha256 to `uv.lock` (rechecked each sync). Plans only version-pin; no pre-release or git-URL sources added. |
| T-02-02 | Denial of Service | Event log unbounded growth (Research Pitfall 6) | mitigate | `packages/core/src/f1_core/physics/events.py` defines `MAX_EVENTS = 500` as a hard cap used by Plan 04's Module E. |
| T-02-03 | Tampering | New pickle load paths | accept | Phase 2 adds NO new pickle load paths. `canonical_stint_artifact` fixture reads only from the repo-controlled `tests/fixtures/` directory (same pattern as Phase 1 T-01-05 mitigation). |
| T-02-04 | Information Disclosure | New physics package could accidentally import secrets-laden modules | accept | Physics subpackage imports only numpy, scipy, pandas, and Phase 1 f1_core modules. `test_f1_core_physics_does_not_import_pydantic` extends Phase 1's boundary test to the new directory. |
</threat_model>

<verification>
- `uv sync` succeeds from project root with typer, pytest-benchmark, hypothesis resolved
- `uv run python -c "from f1_core.physics import make_nominal_params; make_nominal_params()"` exits 0
- `uv run pytest packages/core/tests/test_contracts.py -x` exits 0 (frozen + Pydantic boundary tests green)
- `uv run pytest packages/core/tests/physics/ --benchmark-disable` collects all stubs and every test skips (no failures)
- `uv run pytest packages/core/tests/ --benchmark-disable` — full test suite still green
- `grep 'f1-simulate' packages/core/pyproject.toml` finds the `[project.scripts]` entry
</verification>

<success_criteria>
- New deps (typer, pytest-benchmark, hypothesis) installed; `uv.lock` updated
- `f1_core.physics/` package exists with `__init__.py`, `constants.py`, `params.py`, `defaults.py`, `events.py`
- Six per-module output dataclasses frozen in `contracts.py`; `SimulationState` remains mutable
- All 11 test stub files + `conftest.py` + `__init__.py` exist under `packages/core/tests/physics/`
- Every default value in `defaults.py` cites its model_spec.md section
- `f1-simulate` console script declared in `packages/core/pyproject.toml`
- Full Phase 1 + Phase 2 stub test suite green (skips for unimplemented; no errors)
</success_criteria>

<output>
After completion, create `.planning/phases/02-physics-model-modules-a-g/02-01-SUMMARY.md` documenting:
- New deps added (exact versions resolved by uv)
- Frozen contracts list
- Test stub files created
- Any deviations from planned values (flag to Plan 02+ if nominal params changed)
</output>
