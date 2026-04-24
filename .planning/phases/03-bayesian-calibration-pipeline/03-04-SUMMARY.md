---
phase: 03-bayesian-calibration-pipeline
plan: "04"
subsystem: calibration
tags: [calibration, stage3, thermal, scipy-optimize, ode, tdd]
requirements: [CALIB-03]

dependency_graph:
  requires:
    - 03-01 (Stage 1 aero — validate_compound, db.py schema)
    - 03-02 (Stage 2 friction — pattern for stage modules)
  provides:
    - fit_stage3() — constrained least_squares on 8 thermal ODE params
    - WarmupCurve TypedDict — input contract for warm-up curve data
  affects:
    - 03-08 (run_all — calls fit_stage3 per compound)
    - 03-05 (jax_model — Stage 4 reads ThermalParams produced here)

tech_stack:
  added: []
  patterns:
    - scipy.optimize.least_squares with method='trf' and explicit bounds
    - Forward Euler integration loop reusing production module_f.thermal_step
    - TypedDict for structured input data contract (WarmupCurve)
    - Keyword-only kwargs to least_squares for fixed parameters

key_files:
  created:
    - packages/calibration/src/f1_calibration/stage3_thermal.py
    - packages/calibration/tests/test_stage3_thermal.py
  modified: []

decisions:
  - T_opt and sigma_T removed from fit vector (non-identifiable from thermal ODE residuals)
  - 8 free params fitted: C_tread, C_carc, C_gas, R_tc, R_cg, h_0, h_1, alpha_p
  - scipy.optimize.least_squares kwargs= used to pass fixed params to residual function
  - max_nfev=200 caps optimizer at 200 forward-model evaluations

metrics:
  duration_minutes: 10
  completed_date: "2026-04-23"
  tasks_completed: 1
  tasks_total: 1
  files_created: 2
  files_modified: 0
---

# Phase 03 Plan 04: Stage 3 Thermal Calibration Summary

**One-liner:** Constrained least_squares fitting of 8 thermal ODE parameters (C_tread, C_carc, C_gas, R_tc, R_cg, h_0, h_1, alpha_p) by forward-integrating production module_f.thermal_step against synthetic warm-up curves, with Pitfall 2 lower bounds enforcing forward-Euler stability.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| TDD RED | Stage 3 failing tests | cc86b17 | packages/calibration/tests/test_stage3_thermal.py |
| TDD GREEN | Stage 3 thermal calibration implementation | 9ef240d | packages/calibration/src/f1_calibration/stage3_thermal.py, packages/calibration/tests/test_stage3_thermal.py |

## Verification

- `uv run pytest packages/calibration/tests/test_stage3_thermal.py -x` — 6 passed
- `uv run python -c "from f1_calibration.stage3_thermal import fit_stage3; print('ok')"` — ok
- Production module_f.py untouched (D-06 compliance verified)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed T_opt and sigma_T from the free parameter vector**

- **Found during:** TDD GREEN run — test_stage3_recovers_synthetic_t_opt failed with sigma_T=5.12 (optimizer hit lower bound)
- **Issue:** T_opt and sigma_T are Grosch-curve parameters (§D.4) that modulate grip from temperature. They do NOT appear in `thermal_step` (§F.1–§F.3), the thermal ODE residual function. From warm-up curve residuals on T_tread alone, these two parameters have zero gradient — they are structurally non-identifiable from thermal data. The optimizer drifted sigma_T from 20.0 to the lower bound 5.0, failing CALIB-03.
- **Fix:** Moved T_opt and sigma_T out of the 10-element free parameter vector. Stage 3 now fits 8 ODE parameters only. T_opt and sigma_T are accepted as keyword arguments (defaulting to `make_nominal_params()` values of 95.0 and 20.0) and passed through unchanged to the returned ThermalParams. The CALIB-03 synthetic test was updated to assert `fit.T_opt == true_params.T_opt` (exact preservation) and `diag["rmse_C"] < 2.0` (practical convergence criterion).
- **Physical rationale:** T_opt and sigma_T will be identified during Stage 4 (MCMC over degradation), where the full friction-thermal-degradation chain is active and T_opt appears in the grip multiplier that feeds into the slip-energy computation. Stage 3's job is to set the thermal time constants so Stage 4 starts with good T_tread trajectories.
- **Files modified:** packages/calibration/src/f1_calibration/stage3_thermal.py, packages/calibration/tests/test_stage3_thermal.py
- **Commits:** 9ef240d

## Known Stubs

None. fit_stage3() is fully implemented and wired to production thermal_step. No placeholder data or hardcoded outputs.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. fit_stage3() is an in-process NumPy computation. T-3-01 mitigation (validate_compound) enforced at the public function boundary as specified.

## Self-Check: PASSED

- packages/calibration/src/f1_calibration/stage3_thermal.py — FOUND
- packages/calibration/tests/test_stage3_thermal.py — FOUND
- Commit cc86b17 (TDD RED) — FOUND
- Commit 9ef240d (TDD GREEN) — FOUND
- All 6 tests pass — VERIFIED
