---
phase: 01-foundation-data-pipeline-module-contracts
plan: 02
subsystem: physics-contracts
tags: [contracts, dataclass, protocol, phys-08, phys-09, data-05]
requires:
  - uv workspace from Plan 01-01
  - numpy 2.x, pytest 8+
  - pyright 1.1+ strict on packages/core/src/f1_core/contracts.py (root pyproject.toml)
provides:
  - f1_core.contracts.KinematicState (Module A output)
  - f1_core.contracts.WheelLoads (Module B output)
  - f1_core.contracts.ContactPatch (Module D output)
  - f1_core.contracts.SlipState (Module E output)
  - f1_core.contracts.ThermalState (Module F output)
  - f1_core.contracts.DegradationState (Module G output)
  - f1_core.contracts.SimulationState (PHYS-09 per-tire carryover)
  - f1_core.contracts.PhysicsModule (runtime_checkable Protocol)
  - f1_core.contracts.QualityReport + QualityVerdict (DATA-05)
  - f1_core.contracts.F64Array type alias
affects:
  - Phase 2 physics modules (A-G) will import these contracts
  - Plan 01-04 data-integrity will import QualityReport/QualityVerdict
tech-stack:
  added:
    - numpy.typing.NDArray for strict-mode type aliases
    - typing.Protocol + @runtime_checkable
    - enum.StrEnum (Python 3.11+)
  patterns:
    - Plain @dataclass (no slots) per pitfall P1 (mypy-Protocol interaction risk, avoided)
    - F64Array = NDArray[np.float64] alias for consistent strict typing
key-files:
  created:
    - packages/core/src/f1_core/contracts.py (256 lines, pyright-strict)
    - packages/core/tests/test_contracts.py (138 lines, 9 tests)
    - packages/core/tests/conftest.py (22 lines, 2 fixtures)
  modified: []
decisions:
  - QualityVerdict uses StrEnum (Python 3.11+) instead of (str, Enum) — ruff UP042 compliance; tests still pass since .value still returns string literals
  - list[str] default_factory typed as list[str] (not bare list) for pyright strict compliance
  - DegradationState.mu_0 is shape (N,) per-timestep, SimulationState.mu_0 is scalar float (model_spec distinction preserved)
metrics:
  duration: 8 minutes
  completed: 2026-04-23
  tasks: 2/2
  tests: 9 passed, 0 failed
---

# Phase 01 Plan 02: Physics Module Contracts Summary

Shipped the seven typed `@dataclass` state contracts, the `PhysicsModule` Protocol, and the `QualityReport`/`QualityVerdict` types that Phase 2 physics modules and Plan 01-04 data integrity will consume — zero Pydantic imports, pyright-strict clean.

## What Was Built

### `packages/core/src/f1_core/contracts.py`

Seven `@dataclass` state objects with numpy-typed fields:

| Dataclass | Module | Fields | Shapes |
|-----------|--------|--------|--------|
| `KinematicState` | A (Kinematics) | t, v, a_lat, a_long, psi, v_sx_rear, kappa | all (N,) |
| `WheelLoads` | B (Vertical loads) | t, f_z | t:(N,), f_z:(N,4) |
| `ContactPatch` | D (Hertzian) | t, a_cp, p_bar | t:(N,), a_cp/p_bar:(N,4) |
| `SlipState` | E (Slip inversion) | t, theta, alpha, v_sy, p_slide, p_total | t:(N,), others:(N,4) |
| `ThermalState` | F (Thermal ODE) | t, t_tread, t_carc, t_gas | t:(N,), temps:(N,4) |
| `DegradationState` | G (Degradation) | t, e_tire, mu_0, d_tread | t:(N,), e_tire/d_tread:(N,4), mu_0:(N,) |
| `SimulationState` | (carryover, PHYS-09) | t_tread, t_carc, t_gas, e_tire, mu_0, d_tread | per-tire arrays:(4,), mu_0: float scalar |

### `PhysicsModule` Protocol

```python
@runtime_checkable
class PhysicsModule(Protocol):
    def step(
        self,
        state_in: SimulationState,
        telemetry_sample: object,
        params: object,
    ) -> SimulationState:
        ...
```

- Structural typing (D-05): Phase 2 modules need not inherit.
- `@runtime_checkable` allows isinstance() at runtime for defensive checks.

### `QualityReport` / `QualityVerdict` (DATA-05)

- `QualityVerdict`: StrEnum with members `OK` ("ok"), `WARN` ("warn"), `EXCLUDE` ("exclude"), `REFUSE` ("refuse").
- `QualityReport`: dataclass with `score`, `verdict`, `issues` (list[str]), `throttle_sentinel_count`, `nan_lap_time_count`, `compound_mislabel`, `missing_position_pct`.
- Placed in `contracts.py` (not a separate module) so Plan 01-04 data-integrity can import without cycles.

### `packages/core/tests/test_contracts.py`

Nine tests, all green:
1. `test_placeholder_satisfies_protocol` — `@runtime_checkable` acceptance
2. `test_non_conforming_class_fails_protocol` — negative case
3. `test_all_seven_contracts_importable_from_single_module`
4. `test_simulation_state_shape` — (4,) per-tire + scalar mu_0
5. `test_contracts_module_does_not_import_pydantic` — D-04 boundary check (reload + sys.modules scan)
6. `test_quality_report_verdict_enum_values` — "ok"/"warn"/"exclude"/"refuse"
7. `test_quality_report_default_construction`
8. `test_kinematic_state_field_shape_contract`
9. `test_wheel_loads_per_tire_shape`

### `packages/core/tests/conftest.py`

Two fixtures reused by later Phase 1 plans:
- `temp_cache_dir` — `tmp_path`-backed FastF1 cache dir, sets `F1_CACHE_DIR`
- `fixtures_dir` — path to `packages/core/tests/fixtures/`

## Verification Outputs

```
$ uv run pytest packages/core/tests/test_contracts.py -v
============================== 9 passed in 0.12s ==============================

$ uv run ruff check packages/core/src/f1_core/contracts.py
All checks passed!

$ uv run pyright packages/core/src/f1_core/contracts.py
0 errors, 0 warnings, 0 informations

$ grep -n pydantic packages/core/src/f1_core/contracts.py
(no match — D-04 boundary confirmed)

$ uv run python -c "from f1_core.contracts import KinematicState, WheelLoads, ContactPatch, SlipState, ThermalState, DegradationState, SimulationState, PhysicsModule, QualityReport, QualityVerdict; print('all 10 imports ok')"
all 10 imports ok
```

## Threat Model Coverage

| Threat ID | Status | Mitigation |
|-----------|--------|------------|
| T-01-03 (downstream blast radius from contract tampering) | Mitigated | `contracts.py` is under `[tool.pyright] strict = [...]` in root `pyproject.toml`. Pyright strict passes with 0 errors; any type-incompatible change to this file will fail CI. Confirmed locally. |

No new trust boundaries introduced — contracts.py is pure type definitions with zero runtime I/O.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] pyright strict error on untyped `list` default_factory**
- **Found during:** Task 2 verification (pyright run)
- **Issue:** `issues: list[str] = field(default_factory=list)` — pyright strict reported `Type of "issues" is partially unknown (list[Unknown])` because `list` (the builtin) is generic and `default_factory=list` loses the element type.
- **Fix:** Changed to `default_factory=list[str]` (Python 3.9+ parameterized generic alias supported as callable).
- **Files modified:** `packages/core/src/f1_core/contracts.py` line 237
- **Commit:** 8e7e6a8

**2. [Rule 1 - Bug] ruff UP042: QualityVerdict inheritance replaced**
- **Found during:** Task 2 verification (ruff run)
- **Issue:** `class QualityVerdict(str, Enum)` triggers UP042 ("Inherit from StrEnum").
- **Fix:** Changed to `class QualityVerdict(StrEnum)` and imported `StrEnum` instead of `Enum`. Test `test_quality_report_verdict_enum_values` still passes — `.value` access semantics are identical for StrEnum.
- **Files modified:** `packages/core/src/f1_core/contracts.py` lines 18, 205
- **Commit:** 8e7e6a8

**3. [Rule 1 - Bug] ruff RUF003: ambiguous em-dash characters**
- **Found during:** Task 2 verification (ruff run)
- **Issue:** Section-divider comments and docstrings used en/em dashes and the degree sign, which ruff flags as ambiguous Unicode.
- **Fix:** Replaced em-dashes (—) with plain hyphens (-), section symbols (§) with "section", and °C with "degC" across comments/docstrings. Semantics preserved.
- **Files modified:** `packages/core/src/f1_core/contracts.py` (docstrings, comments)
- **Commit:** 8e7e6a8

**4. [Rule 1 - Bug] ruff RUF022: unsorted `__all__`**
- **Found during:** Task 2 verification (ruff run)
- **Issue:** `__all__` was ordered by concept, not alphabetically.
- **Fix:** Sorted alphabetically (ContactPatch, DegradationState, F64Array, KinematicState, PhysicsModule, QualityReport, QualityVerdict, SimulationState, SlipState, ThermalState, WheelLoads).
- **Files modified:** `packages/core/src/f1_core/contracts.py` lines 244-256
- **Commit:** 8e7e6a8

All four fixes are cosmetic / type-system strictness; none changed behavior. All deviations were required by the project's own tooling (ruff config + pyright strict mode pinned on this exact file) — so they fall under Rule 1 (fix correctness blockers to satisfy configured strict checks).

### Deviation from plan-supplied code snippet

The plan included verbatim source for `contracts.py`. The final committed file differs from that snippet only in the four auto-fixes above (pyright/ruff compliance) plus ASCII-safe replacements of the ambiguous Unicode characters. No fields, no type aliases, no class names, no ordering of the 7 dataclasses changed. Field set for each class matches `model_spec.md` and RESEARCH.md Pattern 2 exactly.

## Known Stubs

None. All contracts are complete definitions; they have no "data source" to wire because they are pure type contracts consumed by Phase 2.

## Commits

| Hash | Type | Message |
|------|------|---------|
| bb043c7 | test | test(01-02): add failing contracts + simulation state tests |
| 8e7e6a8 | feat | feat(01-02): implement 7 physics contracts + PhysicsModule protocol |

## Success Criteria Status

- [x] 9/9 tests in test_contracts.py pass
- [x] `grep pydantic contracts.py` returns no match (D-04 boundary)
- [x] `uv run pyright contracts.py` reports 0 errors in strict mode
- [x] Placeholder satisfies PhysicsModule via runtime isinstance() check
- [x] PHYS-08 (contract portion) complete
- [x] PHYS-09 (state-object portion) complete
- [x] Phase 2 can begin on these contracts

## Self-Check: PASSED

Files exist:
- FOUND: packages/core/src/f1_core/contracts.py
- FOUND: packages/core/tests/test_contracts.py
- FOUND: packages/core/tests/conftest.py

Commits exist in branch:
- FOUND: bb043c7 test(01-02): add failing contracts + simulation state tests
- FOUND: 8e7e6a8 feat(01-02): implement 7 physics contracts + PhysicsModule protocol
