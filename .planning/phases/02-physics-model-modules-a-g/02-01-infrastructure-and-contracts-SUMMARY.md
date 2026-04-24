---
phase: 02-physics-model-modules-a-g
plan: 01
subsystem: physics-infrastructure
tags: [physics, infrastructure, contracts, dependencies, testing]
dependency_graph:
  requires: [phase-01-foundation]
  provides: [f1_core.physics package, frozen contracts, nominal params, test stubs]
  affects: [02-02 through 02-07 (all Wave 1 physics modules)]
tech_stack:
  added:
    - typer 0.24.2 (CLI framework, f1-core dependency)
    - pytest-benchmark 5.2.3 (dev dependency, benchmark harness)
    - hypothesis 6.152.1 (dev dependency, property-based testing)
    - rich 15.0.0 (transitive via typer, per-lap table rendering)
  patterns:
    - frozen=True dataclasses for per-module output contracts (PHYS-08/09)
    - Four-stage nested params dataclasses (AeroParams, FrictionParams, ThermalParams, DegradationParams)
    - make_nominal_params() single-source factory for default priors
    - pytest.skip stubs (not xfail) for TDD RED phase in downstream plans
key_files:
  created:
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
  modified:
    - packages/core/pyproject.toml (typer dep + [project.scripts])
    - pyproject.toml (pytest-benchmark, hypothesis in dev group)
    - uv.lock (updated with 3 new packages + transitive deps)
    - packages/core/src/f1_core/contracts.py (frozen=True on 6 dataclasses)
    - packages/core/tests/test_contracts.py (new immutability + pydantic boundary tests)
decisions:
  - "SimulationState kept mutable (carryover state); six output dataclasses frozen"
  - "pytest.skip stubs (not xfail): downstream plans replace skip with real assertions in RED phase"
  - "make_nominal_params() uses model_spec.md FIXED/SEMI-CONSTRAINED/LEARNED table values verbatim"
  - "MAX_EVENTS=500 cap on StatusEvent list (Pitfall 6 mitigation)"
metrics:
  duration: ~25 minutes
  completed: 2026-04-23
  tasks: 4
  files_created: 19
  files_modified: 5
---

# Phase 2 Plan 1: Infrastructure and Contracts Summary

Wave 0 infrastructure for Phase 2 physics model. Installed new dev dependencies, froze the six per-module output dataclasses in contracts.py, created the f1_core.physics package skeleton with parameter dataclasses and nominal defaults, and produced 40 test stub files so every Wave 1 task has a ready verification target.

## What Was Built

### Task 1: Dependencies and f1-simulate Console Script
- Added `typer>=0.24,<1` to `packages/core/pyproject.toml` dependencies
- Added `[project.scripts] f1-simulate = "f1_core.physics.cli:app"` (cli.py lands in Plan 06)
- Added `pytest-benchmark>=5.2,<6` and `hypothesis>=6,<7` to root dev group
- Resolved versions: typer 0.24.2, pytest-benchmark 5.2.3, hypothesis 6.152.1, rich 15.0.0 (transitive)
- `uv lock --upgrade-package typer` was needed to regenerate the lock file after pyproject edit (the existing lock satisfied the old requirements without re-resolving)

### Task 2: Frozen Contracts
Six dataclasses in `packages/core/src/f1_core/contracts.py` received `frozen=True`:
- `KinematicState`, `WheelLoads`, `ContactPatch`, `SlipState`, `ThermalState`, `DegradationState`

`SimulationState` deliberately left mutable — it carries state across timesteps in the orchestrator loop.

New tests added to `test_contracts.py`:
- `test_module_output_contracts_are_frozen` (6 parametrized cases, one per frozen class)
- `test_simulation_state_is_mutable` (confirms orchestrator carryover works)
- `test_f1_core_physics_does_not_import_pydantic` (D-03 boundary extended to physics/ subpackage)

### Task 3: f1_core.physics Package Skeleton
Five files created under `packages/core/src/f1_core/physics/`:
- `__init__.py`: re-exports make_nominal_params, PhysicsParams, StatusEvent, four *Params classes
- `constants.py`: FIXED physical constants (M_DRY=798.0, WB=3.6, R_0=0.330, C_RR=0.012, RHO_AIR=1.20, G=9.81, B_TREAD_F=0.15, B_TREAD_R=0.20, T_REF_AGING=80.0, plus derived M_TOT, A_TREAD_*, A_CARC_*, H_CARC)
- `params.py`: AeroParams, FrictionParams, ThermalParams, DegradationParams, PhysicsParams (all frozen=True)
- `defaults.py`: make_nominal_params() with inline LEARNED/SEMI-CONSTRAINED citations to model_spec.md sections
- `events.py`: StatusEvent (frozen) with MAX_EVENTS=500 module-level cap

### Task 4: Test Stub Files
Twelve files created under `packages/core/tests/physics/`:
- `conftest.py`: nominal_params, canonical_stint_artifact, synthetic_kinematic_state fixtures
- `test_module_a.py` through `test_module_g.py`: 5/4/3/4/5/4/4 stub tests respectively
- `test_orchestrator.py`: 3 stubs (PHYS-09)
- `test_architecture.py`: 3 stubs (AST linter tests, Plan 07)
- `test_cli.py`: 3 stubs (D-05 CLI integration)
- `test_benchmark.py`: 2 stubs (Criterion 2, 200ms budget)

Total: 40 stub tests, all skip cleanly with `pytest.skip("Pending: Plan 02-0X...")`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Windows encoding error in pydantic boundary test**
- **Found during:** Task 4 full suite run
- **Issue:** `test_f1_core_physics_does_not_import_pydantic` called `py_file.read_text()` without specifying encoding. On Windows (cp1252 default), the physics files containing UTF-8 §/μ/α characters raised `UnicodeDecodeError`
- **Fix:** Changed `py_file.read_text()` to `py_file.read_text(encoding="utf-8")`
- **Files modified:** `packages/core/tests/test_contracts.py`
- **Commit:** 23e6a95

**2. [Rule 3 - Blocking] uv sync did not install typer after pyproject.toml edit**
- **Found during:** Task 1 verification
- **Issue:** The existing `uv.lock` already "satisfied" workspace requirements without re-resolving after the pyproject.toml edit. `uv sync` reported "Audited 22 packages" and typer was absent
- **Fix:** Ran `uv lock --upgrade-package typer` to force re-resolution, then `uv sync --all-packages` to install all workspace member deps
- **Impact:** No code changes; lock file update only. This is expected behavior in uv workspaces where the root package has no direct dependencies on workspace members' deps

## Known Stubs

All 40 stub tests in `packages/core/tests/physics/` are intentional stubs. Each references its implementing plan. No stubs exist in production code — `make_nominal_params()` returns fully populated values, all constants are set, all dataclasses are complete.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced. `events.py` MAX_EVENTS=500 mitigates T-02-02 (DoS via unbounded event list) as specified in the threat register.

## Self-Check: PASSED

Files exist:
- packages/core/src/f1_core/physics/__init__.py: FOUND
- packages/core/src/f1_core/physics/constants.py: FOUND
- packages/core/src/f1_core/physics/params.py: FOUND
- packages/core/src/f1_core/physics/defaults.py: FOUND
- packages/core/src/f1_core/physics/events.py: FOUND
- packages/core/tests/physics/conftest.py: FOUND
- 11 test stub files: FOUND

Commits exist:
- b9bfbf6: chore(02-01): install typer, pytest-benchmark, hypothesis; declare f1-simulate script
- 0f633b6: feat(02-01): freeze six per-module output contracts; add immutability tests
- a9d90fc: feat(02-01): create f1_core.physics package skeleton with params, defaults, constants, events
- 23e6a95: feat(02-01): create physics test stubs (40 tests, all skip) + shared conftest fixtures

Full suite result: 69 passed, 40 skipped, 0 failed.
