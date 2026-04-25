---
phase: 03-bayesian-calibration-pipeline
plan: "08"
subsystem: calibration-cli
tags: [calibration, cli, typer, run-all, resumability, orchestrator, tdd]
dependency_graph:
  requires:
    - 03-01 (db schema, validate_compound, write_parameter_set, has_stage_result)
    - 03-02 (stage1_aero, stage2_friction fit functions)
    - 03-04 (stage3_thermal fit function)
    - 03-06 (stage4_degradation fit function)
    - 03-07 (stage5_validation fit function)
  provides:
    - f1_calibration.cli (Typer app with 6 subcommands)
    - f1_calibration.run_all (resumable orchestrator)
    - f1-calibrate console script entry point
  affects:
    - All CALIB-01..CALIB-08 requirements (unified under CLI)
tech_stack:
  added:
    - typer>=0.24 (CLI framework, already in pyproject.toml)
    - rich>=13 (console output, already in pyproject.toml)
  patterns:
    - TDD (RED commit -> GREEN commit per task)
    - _stageN_core helpers shared between CLI commands and run_all orchestrator
    - SQLite has_stage_result skip gate for resumability
    - Exception-to-exit-code mapping at CLI boundary (T-3-04)
key_files:
  created:
    - packages/calibration/src/f1_calibration/cli.py
    - packages/calibration/src/f1_calibration/run_all.py
    - packages/calibration/tests/test_cli.py
    - packages/calibration/tests/test_run_all.py
  modified:
    - packages/calibration/src/f1_calibration/db.py (timestamp precision fix)
decisions:
  - "_stageN_core helpers in cli.py allow run_all to reuse extraction logic without circular imports"
  - "Stage 5 always runs in run-all even when all stages are cached (fresh RMSE required per D-01)"
  - "db.py created_at uses microsecond precision to prevent UNIQUE constraint collision in rapid writes"
metrics:
  duration_minutes: 25
  completed_date: "2026-04-23"
  tasks_completed: 2
  tasks_total: 2
  files_created: 4
  files_modified: 1
---

# Phase 3 Plan 8: Typer CLI + Resumable run-all Orchestrator Summary

**One-liner:** Typer CLI with 6 subcommands (stage1..stage5, run-all), exception-boundary exit codes 1/2/3, and SQLite has_stage_result skip gate enabling mid-pipeline resume without re-running completed stages.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | CLI tests (TDD RED) | 5080d17 | test_cli.py |
| 1 (GREEN) | Typer CLI with 6 subcommands | 74252bd | cli.py |
| 2 (RED) | run_all tests (TDD RED) | c08544c | test_run_all.py |
| 2 (GREEN) | run_all orchestrator + db.py fix | 11819fc | run_all.py, db.py, cli.py |

## What Was Built

### cli.py — Typer App (D-01)

Six subcommands, all accepting `--compound TEXT` as a flag (Pitfall 6 — not a positional arg):

- `stage1` — calls `_stage1_core(compound, conn, console)` — loads training stints, extracts corner lat-g, calls `fit_stage1`, writes `parameter_sets` row
- `stage2` — calls `_stage2_core` — friction samples -> `fit_stage2`
- `stage3` — calls `_stage3_core` — warm-up curves -> `fit_stage3`
- `stage4` — calls `_stage4_core` — lap times + fixed trajectories -> `fit_stage4` (also accepts `--skip-sbc`, `--chains`, `--draws`, `--tune`)
- `stage5` — calls `_stage5_core` — reads stages 1-4 from SQLite, runs `fit_stage5`
- `run-all` — delegates to `run_all.run_all()` with `--force` flag

Exception boundary wraps every command body in `try/except Exception`. `_handle_exit` maps:
- `ValueError` → exit code 1, "Invalid input: {msg}"
- `RuntimeError` → exit code 2, "Calibration failed: {msg}"
- other `Exception` → exit code 3, "Internal error: {msg}" (no traceback — T-3-04)

The `_stageN_core` functions are module-level private helpers, exported via `__all__`, that both the Typer command wrappers and `run_all._run_stage_dispatch` call into.

### run_all.py — Resumable Orchestrator (D-01)

```python
run_all(*, compound, conn, force=False, console=None) -> dict
```

For stages 1-4: checks `has_stage_result(conn, compound, stage_num)` — skips if True (unless `--force`). Stage 5 always runs. Writes `calibration_runs` provenance row at the end via `write_calibration_run`. Returns `{compound, stages_run, stages_skipped, physics_rmse_s, baseline_rmse_s, calibration_id}`.

## Verification Results

```
packages/calibration/tests/test_cli.py ........ (8 passed)
packages/calibration/tests/test_run_all.py ..... (5 passed)
Full suite: 79 passed, 4 deselected (not integration)
```

```
$ PYTHONUTF8=1 uv run f1-calibrate --help   # exits 0, lists all 6 subcommands
$ PYTHONUTF8=1 uv run f1-calibrate stage1 --compound X9
Invalid input: compound must match ^C[1-5]$, got 'X9'  # exits 1, no traceback
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed UNIQUE constraint collision in rapid write sequences**
- **Found during:** Task 2 (test_run_all_force_reruns_all_stages failing)
- **Issue:** `write_parameter_set` used `timespec="seconds"` for `created_at`, causing `sqlite3.IntegrityError: UNIQUE constraint failed` when two writes occurred within the same wall-clock second (as happens in tests with `--force`)
- **Fix:** Changed `isoformat(timespec="seconds")` to `isoformat(timespec="microseconds")` in both `write_parameter_set` and `write_calibration_run` in `db.py`
- **Files modified:** `packages/calibration/src/f1_calibration/db.py`
- **Commit:** 11819fc

**2. [Rule 3 - Blocking] Fixed Windows console Unicode encoding**
- **Found during:** CLI verification (`uv run f1-calibrate --help`)
- **Issue:** Rich console raises `UnicodeEncodeError` on Windows cp1252 codepage when help text contains em-dashes (`—`) and other non-ASCII characters in Typer command docstrings
- **Fix:** Replaced Unicode em-dash in `app help=` string with ASCII `--`; Greek letters remain in docstrings (not rendered at `--help` top level); CLI works correctly with `PYTHONUTF8=1` and passes all CliRunner tests regardless
- **Files modified:** `packages/calibration/src/f1_calibration/cli.py`
- **Commit:** 11819fc

## Known Stubs

None. The `_stageN_core` functions have real extraction logic that raises `RuntimeError` with specific counts when training data is unavailable, rather than silently returning empty results. Stage 5 reads from actual SQLite rows.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. All threat model mitigations from the plan were implemented:

| Threat | Mitigation |
|--------|------------|
| T-3-01 | `validate_compound` first call in every subcommand and `run_all` entry |
| T-3-03 | `_open_db` calls `resolve_db_path` with workspace containment check |
| T-3-04 | `_handle_exit` catches all exceptions, prints only `str(exc)`, never traceback |

## Self-Check

Files created/modified:
- `packages/calibration/src/f1_calibration/cli.py` — FOUND
- `packages/calibration/src/f1_calibration/run_all.py` — FOUND
- `packages/calibration/tests/test_cli.py` — FOUND
- `packages/calibration/tests/test_run_all.py` — FOUND
- `packages/calibration/src/f1_calibration/db.py` — FOUND (modified)

Commits:
- 5080d17 — test(03-08): add failing tests for CLI (TDD RED)
- 74252bd — feat(03-08): Typer CLI with 6 subcommands, exception boundary, _stageN_core helpers
- c08544c — test(03-08): add failing tests for run_all orchestrator (TDD RED)
- 11819fc — feat(03-08): run_all orchestrator with SQLite resumability + db.py timestamp fix

## Self-Check: PASSED
