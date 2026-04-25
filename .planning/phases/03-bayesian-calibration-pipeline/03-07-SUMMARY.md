---
phase: 03-bayesian-calibration-pipeline
plan: "07"
subsystem: calibration
tags: [calibration, stage5, validation, baseline, csv, rmse, tdd]
requires:
  - 03-01  # DB schema, write_parameter_set, read_latest_parameter_set
  - 03-02  # Stage 1 aero + Stage 2 friction calibration
  - 03-03  # linear baseline (fit_baseline_batch, rmse_per_lap)
  - 03-04  # Stage 3 thermal calibration
  - 03-06  # Stage 4 Bayesian degradation fit
provides:
  - stage5_validation  # fit_stage5, CircuitRow — held-out RMSE + baseline comparison + per-circuit CSV
affects:
  - 03-08  # CLI run-all uses fit_stage5 output to populate calibration_runs table
tech_stack:
  added: []
  patterns:
    - TDD (RED → GREEN): test file committed before implementation
    - MAD outlier filter for Pitfall 4 (SC/VSC lap exclusion)
    - resolve_db_path T-3-03 workspace containment on CSV output
    - validate_compound T-3-01 at function entry
key_files:
  created:
    - packages/calibration/src/f1_calibration/stage5_validation.py
    - packages/calibration/tests/test_stage5_validation.py
  modified: []
decisions:
  - "MAD filter threshold set at 3x MAD (|resid - median| > 3·MAD): conservative enough to keep tight compound clusters, aggressive enough to catch 30s SC laps"
  - "obs validity pre-filter: rows with non-finite Obs_s (empty string from per_lap_rows when LapTime is missing) are excluded before MAD filter runs"
  - "baseline_rmse_s = NaN when skip_baseline=True rather than 0.0 — NaN is honest; 0.0 would imply a baseline was computed"
  - "csv_path in return dict is str (not Path) for JSON serialization compatibility"
metrics:
  duration: "~15 minutes"
  completed: "2026-04-23"
  tasks_completed: 1
  files_created: 2
  files_modified: 0
---

# Phase 03 Plan 07: Stage 5 Cross-Validation + Baseline Comparison Summary

**One-liner:** Stage 5 reads stages 1-4 posterior means from SQLite, runs physics forward simulation on 2024 validation stints, reports per-lap RMSE with MAD outlier filtering, and compares against a linear baseline fit on the same held-out data.

## What Was Built

### `packages/calibration/src/f1_calibration/stage5_validation.py`

Public surface:
- `fit_stage5(compound, db_conn, *, validation_stints, validation_dir, skip_baseline, skip_csv) -> dict`
- `CircuitRow` TypedDict: `{circuit, n_stints, rmse_s, mean_delta_s, worst_lap}`

Internal helpers:
- `_assemble_params(db_conn, compound)` — reads stages 1-4 from SQLite via `read_latest_parameter_set`; raises `RuntimeError("missing stage N params for compound C3")` if any row is absent
- `_mad_filter(residuals, threshold=3.0)` — Pitfall 4 mitigation; excludes laps where `|resid - median| > 3·MAD`; returns bool mask (True = keep)
- `_clean_laps_from_stint(stint_result)` — extracts `(pred, obs, ages, circuit)` from `per_lap_rows()` tuples, applies `is_normal_racing_lap` flag if available on the stint, falls back to MAD filter

### `packages/calibration/tests/test_stage5_validation.py`

Six tests, all passing:

| Test | What it validates |
|------|-----------------|
| `test_stage5_rmse_on_noise_free_synthetic` | RMSE < 1e-10 on perfect predictions; baseline also fits exactly |
| `test_stage5_beats_baseline_on_noisy_synthetic` | physics RMSE < 0.10; baseline > 0; physics within 10% of baseline |
| `test_stage5_csv_format` | exact 5-column header; one row per circuit; file exists |
| `test_stage5_rejects_csv_dir_outside_workspace` | T-3-03: `ValueError` with "outside workspace" on tmp_path |
| `test_stage5_missing_stage_raises` | RuntimeError("missing stage 2") when stages 2/3/4 absent |
| `test_stage5_mad_filter_excludes_outliers` | 30s SC lap outlier filtered; final RMSE < 1.0s |

## Deviations from Plan

### Auto-fixed Issues

None — plan executed as written.

**Minor adaptations (not deviations):**

1. The plan's `_clean_laps_from_stint` used `is_normal_racing_lap` from `stint.is_normal_racing_lap`. Added a pre-filter step to exclude rows where `Obs_s` is empty string or non-finite — the real `SimulationResult.per_lap_rows()` emits `""` for laps with missing observed times. Without this guard, `float("")` would raise `ValueError` before MAD filter runs.

2. `csv_path` in the return dict is `str(csv_path_abs)` (the workspace-resolved absolute path), not the candidate path. This ensures callers always get a valid, resolvable path.

## Known Stubs

None. `fit_stage5` is fully wired: SQLite reads → `run_simulation` forward pass → RMSE computation → baseline comparison → CSV write. The `validation_stints=None` code path calls `iter_training_stints(years=(2024,), compound=compound)` which requires FastF1 network access — but that code path is not exercised in tests (tests inject synthetic stints via the `validation_stints` argument).

## Threat Flags

None. No new network endpoints, auth paths, or file access patterns introduced beyond what the plan's threat model already covers (T-3-01, T-3-03).

## Self-Check: PASSED

- `packages/calibration/src/f1_calibration/stage5_validation.py` — FOUND
- `packages/calibration/tests/test_stage5_validation.py` — FOUND
- `def fit_stage5(` — FOUND in stage5_validation.py
- `from f1_core.physics.orchestrator import run_simulation` — FOUND
- `from f1_calibration.baseline import fit_baseline_batch` — FOUND
- `csv.DictWriter` — FOUND
- `fieldnames=["circuit", "n_stints", "rmse_s", "mean_delta_s", "worst_lap"]` — FOUND
- `_mad_filter` — FOUND
- All 6 tests PASSED (`uv run pytest packages/calibration/tests/test_stage5_validation.py -x` exits 0)
- Commits: `29bf1f7` (test RED), `4890b76` (feat GREEN)
