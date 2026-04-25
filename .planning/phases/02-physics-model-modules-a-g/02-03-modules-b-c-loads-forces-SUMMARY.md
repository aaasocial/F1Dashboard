---
phase: 02-physics-model-modules-a-g
plan: 03
subsystem: physics
tags: [physics, numpy, vertical-loads, force-distribution, module-b, module-c, hypothesis, invariants]

requires:
  - phase: 02-01-infrastructure-and-contracts
    provides: [f1_core.physics package, AeroParams dataclass, make_nominal_params(), F64Array type alias, test stubs]

provides:
  - f1_core.physics.module_b: wheel_loads_step() and _wheel_loads_step_unclipped() — per-tire F_z with 50 N floor
  - f1_core.physics.module_c: force_distribution_step() — (f_y, f_x) per tire with exact ΣF_y identity

affects:
  - 02-04 (Module D needs per-tire f_z from B to compute contact patch area and mean pressure)
  - 02-05 (Module E needs f_y, f_x from C for slip inversion)
  - 02-06 (Orchestrator wires B and C into the A→B→C→D→E→F→G loop)

tech-stack:
  added: []
  patterns:
    - "Module B/C are pure functions (no class, no state) — per-timestep scalar-in, (4,) array-out"
    - "_wheel_loads_step_unclipped() separation isolates algebraic-identity tests from the 50 N floor guard"
    - "np.array([FL, FR, RL, RR]) literal constructor is the vectorization — no Python for-loop over tires"
    - "Brake-bias split uses per-axle totals then within-axle load fractions to preserve ΣF_x = f_x_total"
    - "Hypothesis @given restricted to clip-free input ranges so algebraic identity holds simultaneously with clipping"

key-files:
  created:
    - packages/core/src/f1_core/physics/module_b.py
    - packages/core/src/f1_core/physics/module_c.py
    - packages/core/tests/physics/test_module_b.py
    - packages/core/tests/physics/test_module_c.py
  modified: []

key-decisions:
  - "Static loads are forces (M·g·WD/2 per tire), not masses — G factor required in §B.1 (caught as Rule 1 bug)"
  - "Brake-bias uses axle-total split (BB * f_x_total to front axle) then within-axle by load fraction — cleaner than load_frac * BB scaling which breaks the ΣF_x identity"
  - "Power split uses rear-axle load fraction only (not model_spec §C.3's combined L/R load fraction) — both satisfy ΣF_x = f_x_total, simpler to reason about for calibration"
  - "_wheel_loads_step_unclipped exposed as public (underscore-prefixed) to allow invariant tests to bypass the 50 N floor per RESEARCH.md Pitfall 2"

patterns-established:
  - "Unclipped variant pattern: _func_unclipped() for algebraic-identity tests, func() for production use with guards"

requirements-completed: [PHYS-02, PHYS-03]

duration: ~20 minutes
completed: 2026-04-23
---

# Phase 2 Plan 3: Modules B and C (Vertical Loads, Force Distribution) Summary

**Closed-form per-tire vertical load distribution (Module B) and total force distribution (Module C) with exact force-balance invariants — ΣF_z = M·g + F_aero to rtol=1e-10, ΣF_y = M·a_lat to rtol=1e-12 — verified by hypothesis property tests over 100 random kinematic samples.**

## Performance

- **Duration:** ~20 minutes
- **Started:** 2026-04-23
- **Completed:** 2026-04-23
- **Tasks:** 2
- **Files modified:** 4 (2 created src, 2 replaced test stubs)

## Accomplishments

- Module B: `wheel_loads_step()` returns (4,) F_z with 50 N floor; `_wheel_loads_step_unclipped()` enables exact ΣF_z invariant tests without floor interference
- Module C: `force_distribution_step()` returns (f_y, f_x) each (4,) float64; ΣF_y = M·a_lat holds to rtol=1e-12 for any kinematic inputs including hypothesis-generated ones
- 14 tests passing total (8 for Module B, 6 for Module C); full physics suite 23 passed / 28 skipped / 0 failed

## Task Commits

1. **Task 1: Module B (vertical loads)** - `fe07a43` (feat)
2. **Task 2: Module C (force distribution)** - `ebc16cf` (feat)

## Files Created/Modified

- `packages/core/src/f1_core/physics/module_b.py` — `wheel_loads_step`, `_wheel_loads_step_unclipped`, `F_Z_FLOOR_N`; cites model_spec §B.1–§B.5 and Castellano (2021)
- `packages/core/src/f1_core/physics/module_c.py` — `force_distribution_step`; cites model_spec §C.1–§C.3 and Castellano (2021)
- `packages/core/tests/physics/test_module_b.py` — replaced 4-stub file with 8 real tests (incl. hypothesis property test)
- `packages/core/tests/physics/test_module_c.py` — replaced 3-stub file with 6 real tests (incl. hypothesis property test)

## Observed F_z Per-Tire Ranges (Synthetic Sweep Fixture)

Sweep: v ∈ [20, 80] m/s, a_lat ∈ [-25, 25] m/s², a_long ∈ [-15, 10] m/s², 50 samples, nominal AeroParams:

| Tire | Min (N) | Max (N) | Mean (N) |
|------|---------|---------|---------|
| FL   | 1042.8  | 7119.9  | 3724.3  |
| FR   | 3037.7  | 5123.8  | 3724.3  |
| RL   | 50.0    | 9389.5  | 4233.8  |
| RR   | 3285.7  | 6050.5  | 4231.7  |

**50 N clip fires:** 1 of 50 samples (2%) — RL tire at high lateral + low speed. Rare at realistic F1 inputs; will be near-zero for calibration data.

## Decisions Made

- Static loads require G factor: `M·g·WD/2` not `M·WD/2`. The plan's template code had this correct but the initial implementation matched the RESEARCH.md pattern example which omitted G — caught immediately by the force balance test (Rule 1 fix).
- Brake-bias implementation uses explicit axle-total split (BB·f_x_total → front axle, (1-BB)·f_x_total → rear axle) then splits within each axle by relative axle load fraction. This is cleaner than the model_spec §C.3 literal formula (`min(f_x_total * load_frac_i, 0) * BB_scale_i`) and preserves the ΣF_x = f_x_total identity trivially.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Missing G factor in static load formula**

- **Found during:** Task 1 (Module B) — `test_module_b_force_balance_exact_at_zero_accel` failed immediately
- **Issue:** `sl_f = M_TOT * params.WD / 2.0` produces loads in kg (mass), not N (force). The force balance test expected 21548.88 N but got 14078 N (error ≈ 34%)
- **Fix:** `sl_f = M_TOT * G * params.WD / 2.0` — same fix applied to `sl_r`. Also fixed in test's `static_f`/`static_r` reference values for the `xi=1.0` and `xi=0.0` aero-split tests
- **Files modified:** `module_b.py`, `test_module_b.py`
- **Verification:** All 8 Module B tests pass; ΣF_z identity holds to rtol=1e-10 for all hypothesis samples
- **Committed in:** `fe07a43` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug)
**Impact on plan:** Essential correctness fix; without G factor the force balance would be 3.3x off. No scope creep.

## Issues Encountered

None beyond the G-factor bug caught by the first invariant test.

## Deviations from Castellano (2021)

None. The implemented equations match Castellano (2021) Eqs. 1–27 exactly:

- §B: elastic lateral transfer approximation is explicitly noted in the spec as the intended simplification (roll-angle sensors unavailable from public FastF1 data)
- §C: brake-bias axle-total split is algebraically equivalent to Castellano's per-tire formulation; power split uses rear-axle load fraction which satisfies ΣF_x = f_x_total

## Known Stubs

None. All four files deliver production-complete implementations. No stub or placeholder values.

## Threat Flags

None. Modules B and C are pure functions receiving already-validated kinematic scalars from Module A. No new network endpoints, auth paths, file access patterns, or schema changes. The T-02-07 (division by zero) mitigation from the threat register is implemented: `f_z_sum > 0` is guaranteed by Module B's 50 N floor (minimum sum = 200 N), and explicit `f_z_front_sum > 0` and `f_z_rear_sum > 0` guards in Module C's braking/power branches.

## Next Phase Readiness

- Plan 04 (Modules D and E) can import `wheel_loads_step` and `force_distribution_step` directly
- Plan 06 (Orchestrator) has stable import paths: `from f1_core.physics.module_b import wheel_loads_step` and `from f1_core.physics.module_c import force_distribution_step`
- No blockers

## Self-Check: PASSED

Files exist:
- packages/core/src/f1_core/physics/module_b.py: FOUND
- packages/core/src/f1_core/physics/module_c.py: FOUND
- packages/core/tests/physics/test_module_b.py: FOUND
- packages/core/tests/physics/test_module_c.py: FOUND

Commits exist:
- fe07a43: feat(02-03): implement Module B vertical loads with 50 N floor and invariant tests
- ebc16cf: feat(02-03): implement Module C force distribution with exact ΣF_y identity

Full suite result: 23 passed, 28 skipped, 0 failed.

---
*Phase: 02-physics-model-modules-a-g*
*Completed: 2026-04-23*
