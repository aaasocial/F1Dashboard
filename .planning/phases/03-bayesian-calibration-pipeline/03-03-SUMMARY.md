---
phase: 03-bayesian-calibration-pipeline
plan: "03"
subsystem: calibration
tags: [calibration, baseline, sbc, sklearn, scipy]
completed: "2026-04-23T10:32:02Z"
duration_minutes: 15
tasks_completed: 2
tasks_total: 2
files_created: 4
files_modified: 0
requirements: [CALIB-06, CALIB-08]

dependency_graph:
  requires:
    - 03-01 (packages/calibration/src/f1_calibration/common.py — get_logger)
  provides:
    - fit_baseline_per_stint / fit_baseline_batch (CALIB-08) — consumed by Plan 07 (Stage 5)
    - run_sbc / sbc_uniformity_test (CALIB-06) — consumed by Plan 06 (Stage 4 pre-flight)
  affects: []

tech_stack:
  added:
    - sklearn.linear_model.LinearRegression (baseline per-stint linear fit)
    - scipy.stats.kstest / uniform (SBC rank uniformity test)
  patterns:
    - TDD: RED (import error) -> GREEN (implementation) -> verify per task
    - TypedDict return types for structured dicts (StintBaseline, BatchBaseline, SBCResult)
    - Local import of pymc inside run_sbc to avoid 3s module-load penalty at import time

key_files:
  created:
    - packages/calibration/src/f1_calibration/baseline.py
    - packages/calibration/src/f1_calibration/sbc.py
    - packages/calibration/tests/test_baseline.py
    - packages/calibration/tests/test_sbc.py
  modified: []

decisions:
  - "forward_fn is a required positional parameter in run_sbc (not optional) to structurally prevent Pitfall 7 (prior-only SBC)"
  - "biased-rank test uses all-maximum ranks (np.full(..., 500)) rather than low-range uniform — more reliable KS rejection"
  - "pymc imported locally inside run_sbc to avoid slow top-level import in unit test runs"

metrics:
  duration_minutes: 15
  completed: "2026-04-23"
  commits:
    - hash: "254461d"
      message: "feat(03-03): linear baseline model per stint (CALIB-08)"
    - hash: "82937d2"
      message: "feat(03-03): SBC harness with correct joint sampling (CALIB-06)"
---

# Phase 03 Plan 03: Linear Baseline + SBC Infrastructure Summary

**One-liner:** sklearn LinearRegression baseline per stint (CALIB-08) + Talts et al. SBC harness with mandatory forward_fn (CALIB-06 Pitfall 7 mitigation).

## What Was Built

### Task 1: Linear Baseline Model (CALIB-08)

`packages/calibration/src/f1_calibration/baseline.py` provides:

- `fit_baseline_per_stint(tire_ages, lap_times_s) -> StintBaseline` — fits `lap_time = slope * tire_age + intercept` via `sklearn.linear_model.LinearRegression`; returns `slope_s_per_lap`, `intercept_s`, `rmse_s`, `n_laps`
- `fit_baseline_batch(stints) -> BatchBaseline` — iterates per-stint fits, computes combined RMSE as `sqrt(sum(sq_err) / total_n_laps)`
- `rmse_per_lap(y_true, y_pred) -> float` — utility returning `sqrt(mean((y_true - y_pred)**2))`

Validation: on synthetic data `lap_time = 0.05 * age + 90 + N(0, 0.05)`, slope recovery is within 0.01 and intercept within 0.2. Noise-free data produces RMSE < 1e-10.

### Task 2: SBC Harness (CALIB-06)

`packages/calibration/src/f1_calibration/sbc.py` provides:

- `run_sbc(build_model_fn, forward_fn, prior_sample_fn, *, param_names, ...)` — implements the correct Talts et al. 2018 joint-sampling loop: (1) sample theta from prior, (2) generate y from forward model (Pitfall 7 mitigation), (3) fit MCMC posterior, (4) compute rank of theta in posterior draws
- `sbc_uniformity_test(ranks, *, param_names, alpha=0.05)` — KS test on normalized rank statistics vs Uniform(0,1); returns `ks_p_value` dict and `uniformity_ok` bool

Integration test (`@pytest.mark.integration`) tests end-to-end on a 1-parameter Gaussian model with analytically-known posterior — skipped in unit-only mode.

## Tests

| File | Tests | Mode |
|------|-------|------|
| test_baseline.py | 7 passing | Fast (< 3s) |
| test_sbc.py | 5 fast passing + 1 integration (skipped by default) | Fast / Integration |

Combined fast run: `uv run pytest ... -m "not integration"` → 12 passed in 1.52s.

## Commits

| Hash | Message |
|------|---------|
| `254461d` | feat(03-03): linear baseline model per stint (CALIB-08) |
| `82937d2` | feat(03-03): SBC harness with correct joint sampling (CALIB-06) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed unreliable "biased ranks" test assertion**
- **Found during:** Task 2 test design
- **Issue:** Plan's test used `rng.integers(0, 50, size=(500,1))` claiming it was "biased low" — but 0-49 uniform integers normalized by max (49) span [0,1] uniformly; KS test would pass, not fail. Assertion `ks_p_value < 0.01` would be flaky.
- **Fix:** Replaced with `np.full((500, 1), 500, dtype=np.int64)` — all ranks at maximum value; strongly non-uniform against Uniform(0,1); `uniformity_ok is False` is deterministic.
- **Files modified:** packages/calibration/tests/test_sbc.py
- **Commit:** 82937d2

## Known Stubs

None. Both modules are fully wired — baseline returns real sklearn fit results; SBC computes real rank statistics. No placeholder data flows to any consumer.

## Threat Flags

None. Both modules are numeric-only (NDArray in, TypedDict out). No new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

- [x] `packages/calibration/src/f1_calibration/baseline.py` — FOUND
- [x] `packages/calibration/src/f1_calibration/sbc.py` — FOUND
- [x] `packages/calibration/tests/test_baseline.py` — FOUND
- [x] `packages/calibration/tests/test_sbc.py` — FOUND
- [x] Commit `254461d` — FOUND
- [x] Commit `82937d2` — FOUND
- [x] 12 fast tests pass in 1.52s
- [x] Import check `from f1_calibration.baseline import fit_baseline_batch; from f1_calibration.sbc import run_sbc` prints `ok`
