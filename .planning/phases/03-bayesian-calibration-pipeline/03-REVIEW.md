---
phase: 03-bayesian-calibration-pipeline
reviewed: 2026-04-23T11:38:15Z
depth: standard
files_reviewed: 28
files_reviewed_list:
  - packages/calibration/src/f1_calibration/baseline.py
  - packages/calibration/src/f1_calibration/cli.py
  - packages/calibration/src/f1_calibration/common.py
  - packages/calibration/src/f1_calibration/compound_map.py
  - packages/calibration/src/f1_calibration/db.py
  - packages/calibration/src/f1_calibration/jax_model.py
  - packages/calibration/src/f1_calibration/priors.py
  - packages/calibration/src/f1_calibration/run_all.py
  - packages/calibration/src/f1_calibration/sbc.py
  - packages/calibration/src/f1_calibration/stage1_aero.py
  - packages/calibration/src/f1_calibration/stage2_friction.py
  - packages/calibration/src/f1_calibration/stage3_thermal.py
  - packages/calibration/src/f1_calibration/stage4_degradation.py
  - packages/calibration/src/f1_calibration/stage5_validation.py
  - packages/calibration/src/f1_calibration/training.py
  - packages/calibration/tests/conftest.py
  - packages/calibration/tests/test_baseline.py
  - packages/calibration/tests/test_cli.py
  - packages/calibration/tests/test_compound_map.py
  - packages/calibration/tests/test_db.py
  - packages/calibration/tests/test_jax_model.py
  - packages/calibration/tests/test_run_all.py
  - packages/calibration/tests/test_sbc.py
  - packages/calibration/tests/test_stage1_aero.py
  - packages/calibration/tests/test_stage2_friction.py
  - packages/calibration/tests/test_stage3_thermal.py
  - packages/calibration/tests/test_stage4_degradation.py
  - packages/calibration/tests/test_stage5_validation.py
findings:
  critical: 2
  warning: 5
  info: 4
  total: 11
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-04-23T11:38:15Z
**Depth:** standard
**Files Reviewed:** 28
**Status:** issues_found

## Summary

The Phase 3 calibration pipeline is well-structured with clear separation of concerns across the five stages. Security mitigations (T-3-01 through T-3-06) are consistently applied: compound validation, parameterized SQL, and workspace-containment checks appear at every public entry point. The SBC pre-flight, convergence diagnostics, and NetCDF provenance chain are all present and correctly wired.

Two critical bugs require fixes before production use: a statistical correctness error in the SBC rank normalization (which will cause false-negative SBC failures on well-calibrated models), and a path-traversal bypass in `write_calibration_run` that nullifies the workspace containment check for relative paths. Five warnings cover production code quality issues including `assert` used as a runtime guard (silently disabled by `-O`), a data accuracy error in the Monaco 2023 compound map, and a `print()` call leaking to stdout in the production MCMC path. Four info-level items note minor style and robustness improvements.

---

## Critical Issues

### CR-01: SBC rank normalization uses empirical max — biased KS test rejects well-calibrated models

**File:** `packages/calibration/src/f1_calibration/sbc.py:56-60`

**Issue:** `sbc_uniformity_test` normalizes ranks by the empirical maximum rank observed across all trials (`max_rank = float(ranks.max())`), then KS-tests the normalized values against `Uniform(0, 1)`. The theoretical SBC rank for parameter `theta*` sampled from `n_draws * n_chains` posterior draws lies in `[0, n_draws*n_chains]`. The correct normalizer is that fixed integer, not the empirical maximum from one realization.

When a well-calibrated model has `theta*` happen to fall below the largest posterior draw in every trial (as is statistically likely), `max_rank < n_draws*n_chains`. The normalized distribution is then supported on `[0, max_rank/(n_draws*n_chains)] ⊊ [0, 1]`, and the KS test against `Uniform(0,1)` will reject it — a false failure. The `run_sbc` caller passes ranks computed as `int(np.sum(posterior_samples < theta_true[name]))` (line 116), which ranges from 0 to `len(posterior_samples)` = `draws * chains`. That upper bound must be the normalizer.

**Fix:** Accept `n_posterior_draws` as a parameter to `sbc_uniformity_test`, or compute it from `ranks + 1` (since the maximum possible rank equals the number of posterior samples). The simplest correct fix:

```python
def sbc_uniformity_test(
    ranks: NDArray[np.int64],
    *,
    param_names: list[str] | None = None,
    alpha: float = 0.05,
    n_posterior_draws: int | None = None,   # add this parameter
) -> dict[str, Any]:
    ...
    # Use the known maximum (n_posterior_draws) if supplied; fall back to
    # ranks.max() + 1 as a conservative estimate that includes the upper boundary.
    if n_posterior_draws is not None:
        normalizer = float(n_posterior_draws)
    else:
        normalizer = float(ranks.max() + 1) if ranks.size > 0 else 1.0

    for i, name in enumerate(param_names):
        normalized = ranks[:, i].astype(np.float64) / normalizer
        ...
```

`run_sbc` should pass `n_posterior_draws=draws * chains` to `sbc_uniformity_test`.

---

### CR-02: `write_calibration_run` workspace-containment check bypassed for relative paths

**File:** `packages/calibration/src/f1_calibration/db.py:295-297`

**Issue:** The T-3-02/T-3-03 path containment check is skipped entirely for relative `netcdf_path` values:

```python
if Path(netcdf_path).is_absolute():
    resolve_db_path(netcdf_path)  # raises ValueError if outside workspace
```

A caller passing `netcdf_path="../../outside/evil.nc"` writes the value into the `calibration_runs` table without any validation. The `stage5_csv_path` column has the same gap (line 314, no check at all). While neither value is used as a filesystem write target inside `write_calibration_run` itself, a downstream reader that trusts these DB-stored paths and opens them without re-validating is exposed to directory traversal. The documented security contract (T-3-03) states paths are validated before storage.

**Fix:** Always resolve relative paths against `WORKSPACE_ROOT` and apply `resolve_db_path`:

```python
def _validate_stored_path(raw: str, field: str) -> str:
    """Resolve raw path (absolute or relative-to-workspace) and assert it stays inside workspace."""
    p = Path(raw)
    if not p.is_absolute():
        p = WORKSPACE_ROOT / p
    resolve_db_path(p)   # raises ValueError if outside workspace or is a symlink
    return raw  # store the original string, not the resolved absolute form

# In write_calibration_run:
netcdf_path = _validate_stored_path(netcdf_path, "netcdf_path")
stage5_csv_path = _validate_stored_path(stage5_csv_path, "stage5_csv_path")
```

---

## Warnings

### WR-01: `assert cur.lastrowid is not None` silently disabled under Python `-O`

**File:** `packages/calibration/src/f1_calibration/db.py:203` and `db.py:328`

**Issue:** Both `write_parameter_set` and `write_calibration_run` use bare `assert` to guard the post-insert row ID. Python's `-O` (optimize) flag strips all `assert` statements, meaning under optimized execution the functions silently return `None` instead of raising. Callers (e.g. `run_all.py`) cast the return value with `int(row["parameter_set_id"])`, which would produce a `TypeError` much later and far from the actual failure point.

**Fix:**
```python
# Replace:
assert cur.lastrowid is not None
return cur.lastrowid

# With:
if cur.lastrowid is None:
    raise RuntimeError("INSERT did not return a lastrowid — database may be read-only")
return cur.lastrowid
```

Apply to both occurrences (lines 203 and 328).

---

### WR-02: Monaco 2023 compound map entry contradicts its own comment

**File:** `packages/calibration/src/f1_calibration/compound_map.py:51`

**Issue:**
```python
(2023, 6):  {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Monaco — C3/C4/C5 per Pirelli
```

The inline comment says "C3/C4/C5 per Pirelli" (the soft end of the range), but the dict maps SOFT→C4, MEDIUM→C3, HARD→C2 (the medium range). Pirelli's official 2023 Monaco allocation was C3 (Hard), C4 (Medium), C5 (Soft). The data contradicts the comment and is incorrect: Monaco uses the softest compounds on the calendar because it is a low-speed street circuit. The error will cause all C5 training stints that should include Monaco 2023 to be omitted, and will incorrectly include Monaco 2023 data in C2 training, degrading Stage 3/4 calibration for those compounds.

**Fix:**
```python
(2023, 6):  {"SOFT": "C5", "MEDIUM": "C4", "HARD": "C3"},   # Monaco — C3/C4/C5 per Pirelli
```

---

### WR-03: `raise _handle_exit(exc)` raises `typer.Exit`, which is not an exception

**File:** `packages/calibration/src/f1_calibration/cli.py:309-410` (all five stage commands and `run-all`)

**Issue:** Every CLI command body does:
```python
except Exception as exc:
    raise _handle_exit(exc)
```

`_handle_exit` returns `typer.Exit(code=N)`, which Typer uses as a signal object, not a true Python exception hierarchy value. Raising it works because `typer.Exit` inherits from `Exception`, but the pattern conflates "raise" with "return exit code". The more significant problem is that `except Exception` catches `KeyboardInterrupt` in Python 3.8+ is not an issue (KeyboardInterrupt is BaseException, not Exception), but it DOES catch `SystemExit`, meaning a nested `sys.exit()` call (e.g., inside PyMC or JAX) will be trapped and re-raised as exit code 3 ("Internal error"), losing the intended exit code from the nested call.

**Fix:** Separate the exit-code mapping from the raise, and narrow the exception handler:

```python
except (ValueError, RuntimeError) as exc:
    raise _handle_exit(exc)
except Exception as exc:   # noqa: BLE001
    raise _handle_exit(exc)
```

Or more robustly, use `except Exception` but re-raise `SystemExit` explicitly:

```python
except SystemExit:
    raise
except Exception as exc:   # noqa: BLE001
    raise _handle_exit(exc)
```

---

### WR-04: `print()` in production MCMC path bypasses the logging framework

**File:** `packages/calibration/src/f1_calibration/stage4_degradation.py:387`

**Issue:**
```python
print("Compiling JAX model (one-time, ~30s)...", flush=True)  # Pitfall 1 UX
```

All other modules use `_log = get_logger(__name__)` and emit `_log.info(...)`. This bare `print()` bypasses log-level filtering, cannot be suppressed by setting `F1_LOG_LEVEL=WARNING`, and will appear in captured output during tests (even with `progressbar=False`). The comment notes it's intentional for UX, but the rest of the UX goes through Rich `console.print` (passed in from the CLI layer); this `print` is orphaned from both systems.

**Fix:**
```python
_log.info("Compiling JAX model (one-time, ~30s)...")
```

Or, since stage 4 receives `db_conn` but not `console`, add a `console` parameter or use the logger.

---

## Info

### IN-01: `training.py` iterates non-existent rounds for compound-agnostic stages

**File:** `packages/calibration/src/f1_calibration/training.py:54-57`

**Issue:** When `compound is None`, the iterator produces `(year, round)` for rounds 1..24 for every year in `years`. The 2022 season had 22 rounds, 2023 had 22 rounds. Rounds 23 and 24 do not exist for those years. Each such round × 8 drivers × 6 stints = up to 96 `load_stint` calls that immediately throw and are silently swallowed. No correctness impact (errors are caught), but it generates noise in DEBUG logs and imposes unnecessary latency during calibration runs.

**Fix:** Store per-year round counts or use `compound_map.COMPOUND_MAP` to bound the range:
```python
# Instead of hardcoded range(1, 25), derive from compound_map:
max_round = max((rnd for (yr, rnd) in COMPOUND_MAP if yr == y), default=24)
race_candidates.extend((y, r) for r in range(1, max_round + 1))
```

---

### IN-02: `_assemble_params` unpacks JSON dicts directly into dataclass constructors without field validation

**File:** `packages/calibration/src/f1_calibration/stage5_validation.py:61-66`

**Issue:**
```python
return PhysicsParams(
    aero=AeroParams(**stages[1]),
    friction=FrictionParams(**stages[2]),
    ...
)
```

If `params_json` in SQLite was written by an older schema version (or is manually edited), extra or missing fields will produce an unhelpful `TypeError: __init__() got an unexpected keyword argument` that gives no indication of which stage or compound is the source. Not a security concern, but a fragility that makes debugging schema migrations harder.

**Fix:** Wrap each unpack in a try/except that adds context:
```python
try:
    aero = AeroParams(**stages[1])
except TypeError as exc:
    raise RuntimeError(f"Stage 1 params for {compound} are incompatible with AeroParams: {exc}") from exc
```

---

### IN-03: `sbc_uniformity_test` is tested with `max_rank=500` but `run_sbc` produces ranks up to `draws*chains`

**File:** `packages/calibration/tests/test_sbc.py:11-13`

**Issue:** The fast unit tests generate ranks in `[0, 500]` to approximate the distribution, but this is detached from the actual normalizer used in `sbc_uniformity_test` (which normalizes by the observed max of those same ranks). The test does not assert that ranks passed from `run_sbc` use a consistent normalization. This means CR-01 (the normalization bug) cannot be caught by these tests alone.

**Fix:** After fixing CR-01, add a test that explicitly passes `n_posterior_draws` and verifies the KS test passes for known-uniform ranks at the boundary:
```python
def test_normalization_uses_supplied_n_posterior_draws():
    # All ranks at the maximum should still be uniform if there's only one possible value,
    # but using n_posterior_draws=500 with ranks uniform in [0,500] should pass.
    rng = np.random.default_rng(1)
    ranks = rng.integers(0, 501, size=(1000, 1))
    result = sbc_uniformity_test(ranks, param_names=["x"], n_posterior_draws=500)
    assert result["uniformity_ok"] is True
```

---

### IN-04: `test_cli.py` traceback-leak test only checks `result.stdout`, not `result.stderr`

**File:** `packages/calibration/tests/test_cli.py:63-68`

**Issue:**
```python
assert "Traceback" not in result.stdout
assert "File \"" not in result.stdout
```

Typer may route exception tracebacks to stderr in some configurations. The test currently only inspects stdout. A traceback appearing in stderr would satisfy both assertions while still violating T-3-04.

**Fix:**
```python
combined = result.stdout + (result.stderr or "")
assert "Traceback" not in combined
assert 'File "' not in combined
```

---

_Reviewed: 2026-04-23T11:38:15Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
