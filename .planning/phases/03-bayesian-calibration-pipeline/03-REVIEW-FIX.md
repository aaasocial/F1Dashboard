---
phase: 03-bayesian-calibration-pipeline
fixed_at: 2026-04-23T12:08:36Z
review_path: .planning/phases/03-bayesian-calibration-pipeline/03-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 03: Code Review Fix Report

**Fixed at:** 2026-04-23T12:08:36Z
**Source review:** .planning/phases/03-bayesian-calibration-pipeline/03-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (2 Critical, 5 Warning)
- Fixed: 7
- Skipped: 0

## Fixed Issues

### CR-01: SBC rank normalization uses empirical max — biased KS test rejects well-calibrated models

**Files modified:** `packages/calibration/src/f1_calibration/sbc.py`
**Commit:** 3c5c3a8
**Applied fix:** Added `n_posterior_draws: int | None = None` parameter to `sbc_uniformity_test`. When supplied, the normalizer is the fixed `float(n_posterior_draws)` rather than the empirical `ranks.max()`. When `None`, falls back to `ranks.max() + 1` (conservative upper bound). Updated `run_sbc` to pass `n_posterior_draws=draws * chains` so the caller always provides the correct theoretical maximum.

---

### CR-02: `write_calibration_run` workspace-containment check bypassed for relative paths

**Files modified:** `packages/calibration/src/f1_calibration/db.py`
**Commit:** 5e625ce
**Applied fix:** Added `_validate_stored_path(raw, field)` helper that resolves relative paths against `WORKSPACE_ROOT` before calling `resolve_db_path`, which enforces the symlink and containment checks. Replaced the previous conditional `if Path(netcdf_path).is_absolute(): resolve_db_path(...)` guard (which silently skipped relative paths) with unconditional calls to `_validate_stored_path` for both `netcdf_path` and `stage5_csv_path` at the top of `write_calibration_run`.

---

### WR-01: `assert cur.lastrowid is not None` silently disabled under Python `-O`

**Files modified:** `packages/calibration/src/f1_calibration/db.py`
**Commit:** f1cf0a1
**Applied fix:** Replaced both bare `assert cur.lastrowid is not None` statements (in `write_parameter_set` and `write_calibration_run`) with explicit `if cur.lastrowid is None: raise RuntimeError("INSERT did not return a lastrowid — database may be read-only")`. These checks are now active regardless of the `-O` optimization flag.

---

### WR-02: Monaco 2023 compound map entry contradicts its own comment

**Files modified:** `packages/calibration/src/f1_calibration/compound_map.py`
**Commit:** a77259a
**Applied fix:** Corrected `(2023, 6)` from `{"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"}` to `{"SOFT": "C5", "MEDIUM": "C4", "HARD": "C3"}`, matching the inline comment "C3/C4/C5 per Pirelli" and the official Pirelli 2023 Monaco allocation (softest compounds: C5 Soft, C4 Medium, C3 Hard).

---

### WR-03: `raise _handle_exit(exc)` traps `SystemExit` from nested `sys.exit()` calls

**Files modified:** `packages/calibration/src/f1_calibration/cli.py`
**Commit:** e2b869d
**Applied fix:** Added `except SystemExit: raise` before `except Exception as exc` in all six CLI command handlers (`stage1`, `stage2`, `stage3`, `stage4`, `stage5`, `run_all_cmd`). This ensures a `SystemExit` raised by PyMC, JAX, or any nested `sys.exit()` call propagates naturally instead of being intercepted and re-raised as exit code 3.

---

### WR-04: `print()` in production MCMC path bypasses the logging framework

**Files modified:** `packages/calibration/src/f1_calibration/stage4_degradation.py`
**Commit:** 5af99a3
**Applied fix:** Replaced `print("Compiling JAX model (one-time, ~30s)...", flush=True)` with `_log.info("Compiling JAX model (one-time, ~30s)...")`. The message now respects `F1_LOG_LEVEL` filtering and is suppressed in captured test output like all other log messages in the module.

---

_Fixed: 2026-04-23T12:08:36Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
