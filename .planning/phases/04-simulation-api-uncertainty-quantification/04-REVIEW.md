---
phase: 04-simulation-api-uncertainty-quantification
reviewed: 2026-04-24T00:00:00Z
depth: standard
files_reviewed: 22
files_reviewed_list:
  - packages/api/pyproject.toml
  - packages/api/src/f1_api/app.py
  - packages/api/src/f1_api/routers/calibration.py
  - packages/api/src/f1_api/routers/sessions.py
  - packages/api/src/f1_api/routers/simulate.py
  - packages/api/src/f1_api/schemas/calibration.py
  - packages/api/src/f1_api/schemas/sessions.py
  - packages/api/src/f1_api/schemas/simulate.py
  - packages/api/src/f1_api/services/calibration.py
  - packages/api/src/f1_api/services/posterior_store.py
  - packages/api/src/f1_api/services/sessions.py
  - packages/api/src/f1_api/services/simulate.py
  - packages/api/src/f1_api/cache/simulate_cache.py
  - packages/api/tests/conftest.py
  - packages/api/tests/fixtures/__init__.py
  - packages/api/tests/fixtures/calibration_fixture.py
  - packages/api/tests/fixtures/simulate_stubs.py
  - packages/api/tests/fixtures/zip_fixtures.py
  - packages/api/tests/test_calibration.py
  - packages/api/tests/test_phase4_integration.py
  - packages/api/tests/test_sessions.py
  - packages/api/tests/test_simulate.py
findings:
  critical: 2
  warning: 5
  info: 4
  total: 11
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-04-24T00:00:00Z
**Depth:** standard
**Files Reviewed:** 22
**Status:** issues_found

## Summary

Phase 4 delivers the `/simulate`, `/calibration/{compound}`, and `/sessions/upload` endpoints plus their service layers, schema definitions, cache infrastructure, and test suite. The overall quality is high: D-05 guards are coherent, the zip-extraction security hardening is thorough, and the two-layer cache design is sound.

Two critical issues were found: a thread-safety race in `SimulateCache.get()` that allows stale LRU promotion after a SQLite hit, and a D-05 module-level guard in `services/calibration.py` that fires at import time rather than after the module-level `__all__` assignment, silently breaking the module if any MCMC lib happens to be loaded (e.g., by a test that exercised calibration code). Five warnings cover a silent fallback in compound-letter derivation that can hide data bugs, an unvalidated `session_id` path that bypasses the schema-level pattern, unbounded file read in the sessions router, a closure-over-loop-variable bug in `_assemble_response`, and an ArviZ column-name assumption that will silently misassign HDI bounds if the ArviZ summary column names change. Four info items cover dead import, redundant re-export pattern, magic TTL constant, and a test that depends on wall-clock timing.

---

## Critical Issues

### CR-01: Thread-safety race in `SimulateCache.get()` — LRU promotion after SQLite hit

**File:** `packages/api/src/f1_api/cache/simulate_cache.py:103-119`

**Issue:** `get()` acquires the lock for the in-memory check, releases it, then does a SQLite read outside the lock, then re-acquires the lock to insert and promote the result. Between the lock release and re-acquisition another thread can evict or insert the same key, causing the eviction invariant (`max_entries`) to be briefly violated and the same SQLite fetch to execute multiple times concurrently. The double-write on line 117 is benign but the eviction race is not: under high concurrency two threads can each insert the same key and evict different victims, ending up with `max_entries + 1` entries in memory.

This is a FastAPI threadpool server; all sync routes run on threads from the same process. With K=100 forward-pass requests queued, the window is real.

**Fix:**
```python
def get(self, race_id, driver_code, stint_index, calibration_id, overrides_hash):
    key = make_cache_key(race_id, driver_code, stint_index, calibration_id, overrides_hash)

    # Fast path: hold lock for the full in-memory check + promote
    with self._lock:
        if key in self._memory:
            self._memory.move_to_end(key)
            return self._memory[key]

    # SQLite read outside lock (I/O should not hold the lock)
    conn = sqlite3.connect(str(self._db_path))
    try:
        cur = conn.execute(
            "SELECT payload_json FROM simulation_cache WHERE cache_key = :k",
            {"k": key},
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    payload: bytes = bytes(row[0])

    # Re-acquire lock to insert; use setdefault semantics to avoid double-insert
    with self._lock:
        if key not in self._memory:          # another thread may have inserted already
            self._memory[key] = payload
            self._memory.move_to_end(key)
            self._evict_locked()
    return payload
```

---

### CR-02: D-05 module-level guard in `services/calibration.py` fires at wrong position

**File:** `packages/api/src/f1_api/services/calibration.py:153-156`

**Issue:** The D-05 import guard is appended after `__all__` at the bottom of the file, below the `build_calibration_summary` function definition. Because `services/calibration.py` also imports `arviz` at line 9, and ArviZ transitively imports NumPy and sometimes SciPy which may (in certain test environments) have triggered lazy imports of PyMC internals, the guard can raise `ImportError` during the normal import of this module — crashing the worker rather than surfacing a clean error. More importantly, the guard is positioned after the function definitions but before nothing: any MCMC import that happens between module load and the guard reaching that line will not be caught by `services/simulate.py`'s equivalent guard at all, while this file's guard will raise unconditionally and crash the app.

The canonical pattern used in `services/simulate.py` (line 473-477) includes `# pragma: no cover — defence in depth`, signalling it is expected to be a rarely-triggered guard. `services/calibration.py` does not follow that same pattern and has no pragma, so it will fire incorrectly in test environments where prior tests have imported calibration-adjacent packages.

**Fix:** Mirror the pattern from `services/simulate.py` exactly, and add the pragma:
```python
# Runtime guard: this module must never pull in pymc/numpyro/pytensor.
import sys as _sys  # noqa: E402
_forbidden = [m for m in _sys.modules if m.split(".")[0] in {"pymc", "numpyro", "pytensor"}]
if _forbidden:  # pragma: no cover — defence in depth
    raise ImportError(
        f"D-05 violation in services/calibration.py: {_forbidden}"
    )
```

The absence of `# pragma: no cover` means the guard line shows as an uncovered branch in CI coverage, which can fail a coverage gate. Beyond the CI issue, the lack of `pragma` also signals the guard was not reviewed with the same care as the one in `simulate.py`.

---

## Warnings

### WR-01: Silent fallback to cross-year compound lookup can hide data correctness bugs

**File:** `packages/api/src/f1_api/services/simulate.py:172-183`

**Issue:** `_derive_compound_letter()` has a second-level fallback (lines 172-183) that scans all years/rounds in the compound mapping YAML when the exact `{year}-{round}` key is not found. This emits only a `log.warning` and silently returns a letter from a different year's compound allocation. Because Pirelli compound allocations vary year-to-year (e.g., C3 MEDIUM in 2022 is softer than C3 MEDIUM in 2024), a cross-year match can silently produce a wrong compound letter, corrupt the cache key, and serve incorrect simulation results without any error. The fallback should raise `ValueError` instead.

**Fix:**
```python
if not letter:
    raise ValueError(
        f"Cannot map compound {raw_compound!r} for race {year}-round{round_number}. "
        f"Add an entry to the compound mapping YAML."
    )
```
Remove lines 172-183 entirely, or gate the cross-year scan behind an explicit `allow_fallback=True` flag that tests can set.

---

### WR-02: `_merge_session_into_cache` validates `session_id` format but not after `SESSION_ROOT` resolution

**File:** `packages/api/src/f1_api/services/simulate.py:60-78`

**Issue:** The function validates `session_id` matches `^[0-9a-f]{32}$` (line 69) and checks `session_dir.resolve().is_relative_to(SESSION_ROOT.resolve())` (line 75). However, between the Pydantic-layer validation (schema) and this defence-in-depth check, the `SESSION_ROOT` module attribute may have been monkeypatched (in tests) to a `tmp_path` that resolves differently from the production path. This is correct in tests. The issue is that `SESSION_ROOT` is imported at module load time from `f1_api.services.sessions` and assigned to `sim_mod.SESSION_ROOT` (line 26). If `sessions.SESSION_ROOT` is monkeypatched after `simulate` is already imported, `sim_mod.SESSION_ROOT` and `sessions_svc.SESSION_ROOT` can diverge, and the path-containment check on line 75 uses `simulate`'s stale copy.

In production this is harmless (SESSION_ROOT is never changed). In tests, `test_phase4_integration.py` correctly patches both (lines 47-48), but `test_sessions.py:test_session_routes_simulate` only patches `f1_api.services.simulate.SESSION_ROOT` (line 112), not `sessions_svc.SESSION_ROOT`, which means the upload step uses the real SESSION_ROOT while the merge step uses tmp_path — the uploaded session_id would not be found by `session_dir.exists()` on line 72.

**Fix:** Import `SESSION_ROOT` lazily inside `_merge_session_into_cache` to always read the current value:
```python
def _merge_session_into_cache(session_id: str) -> None:
    from f1_api.services.sessions import SESSION_ROOT as _SESSION_ROOT
    ...
    session_dir = _SESSION_ROOT / session_id
```
This eliminates the stale-reference problem entirely without requiring callers to patch two modules.

---

### WR-03: Unbounded `file.file.read()` in sessions router before size check

**File:** `packages/api/src/f1_api/routers/sessions.py:38`

**Issue:** `zip_bytes = file.file.read()` reads the entire upload into memory before `extract_session_zip` checks `len(zip_bytes) > MAX_UPLOAD_BYTES`. A 1 GB upload will be fully buffered in the worker's heap before being rejected. The size guard in `extract_session_zip` (line 55 of `sessions.py`) is correct but comes too late. FastAPI does not enforce upload size limits by default.

This is not a crash (Python will raise `MemoryError` or the OS will OOM-kill before truly running out), but it is a DoS vector: an attacker can send many large concurrent uploads to exhaust server RAM.

**Fix:** Add a streaming read with an early abort, or configure a `Content-Length` guard at the router level:
```python
MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # imported from sessions service

zip_bytes = file.file.read(MAX_UPLOAD_BYTES + 1)
if len(zip_bytes) > MAX_UPLOAD_BYTES:
    raise HTTPException(
        status_code=413,
        detail=f"upload exceeds {MAX_UPLOAD_BYTES} byte limit",
    )
```
This keeps memory bounded to `MAX_UPLOAD_BYTES + 1` per request.

---

### WR-04: Closure-over-loop-variable bug in `_assemble_response` per-lap loop

**File:** `packages/api/src/f1_api/services/simulate.py:382-389`

**Issue:** `_scalar_ci` is defined as a nested function inside a `for lap_idx in range(n_laps)` loop (lines 382-389). It references `lap_draws` from the enclosing scope via closure. Because `lap_draws` is rebound on every iteration, the closure captures the variable by reference, not by value. If `_scalar_ci` were ever called lazily (e.g., if Python's list comprehension optimiser or a future refactor deferred its execution), it would use the final iteration's `lap_draws`. Currently the function is called eagerly inside the same loop body, so this is not a live bug — but it is a latent defect pattern that is easy to accidentally break.

**Fix:** Pass `lap_draws` as a default argument to make the binding explicit:
```python
def _scalar_ci(field_key: str, _draws=lap_draws) -> CIValue:
    vals = np.array([
        row[field_key] for row in _draws
        if isinstance(row.get(field_key), (int, float)) and _is_finite(row[field_key])
    ], dtype=np.float64)
    if len(vals) == 0:
        return CIValue(mean=0.0, lo_95=0.0, hi_95=0.0)
    return _aggregate_scalar(vals)
```

---

### WR-05: ArviZ `az.summary` column-name assumption — HDI bounds silently misassigned

**File:** `packages/api/src/f1_api/services/calibration.py:141-147`

**Issue:** `_stage4_var` accesses `df.loc[var, "hdi_2.5%"]` and `df.loc[var, "hdi_97.5%"]` (lines 144-145) relying on ArviZ's default column names for `hdi_prob=0.95`. The comment on lines 130-132 documents the expected column names. However, ArviZ changed its summary column naming convention between major versions (the `hdi_X%` format was introduced around ArviZ 0.12 and the exact rounding of the percentage string varies). If ArviZ produces `"hdi_2.50%"` instead of `"hdi_2.5%"` (a real variation seen in some builds), the `df.loc` access raises `KeyError` at runtime, crashing the `/calibration` endpoint.

**Fix:** Look up the column names defensively:
```python
def _stage4_var(df, var: str) -> Stage4VarSummary:
    # Resolve actual HDI column names (ArviZ may use "hdi_2.5%" or "hdi_2.50%")
    cols = df.columns.tolist()
    lo_col = next((c for c in cols if c.startswith("hdi_2.")), None)
    hi_col = next((c for c in cols if c.startswith("hdi_97.")), None)
    if lo_col is None or hi_col is None:
        raise ValueError(
            f"az.summary did not return expected HDI columns; got: {cols}"
        )
    return Stage4VarSummary(
        mean=float(df.loc[var, "mean"]),
        sd=float(df.loc[var, "sd"]),
        hdi_lo_95=float(df.loc[var, lo_col]),
        hdi_hi_95=float(df.loc[var, hi_col]),
        r_hat=float(df.loc[var, "r_hat"]),
        ess_bulk=float(df.loc[var, "ess_bulk"]),
    )
```

---

## Info

### IN-01: Dead import `SimulateRequest` in `services/simulate.py`

**File:** `packages/api/src/f1_api/services/simulate.py:33`

**Issue:** `SimulateRequest` is imported from `f1_api.schemas.simulate` with a `# noqa: F401` suppressor. This import is not used anywhere in the service module — the router unpacks the request fields before calling `run_simulation_with_uncertainty`. The noqa comment hides it from linters.

**Fix:** Remove `SimulateRequest` from the import line. If it is kept for re-export purposes, document that explicitly with a comment (e.g., `# re-exported for convenience`). As written it looks accidental.

---

### IN-02: Redundant `from packages.api.tests...` import pattern in `conftest.py`

**File:** `packages/api/tests/conftest.py:158-161` and `packages/api/tests/conftest.py:280`

**Issue:** `conftest.py` uses fully-qualified `packages.api.tests.fixtures.*` import paths (lines 158, 280) rather than the relative package path `f1_api.tests.fixtures.*` or a project-relative path. This makes the test suite sensitive to how `packages/` is placed on `sys.path` and will break if the working directory is not the workspace root. The pattern also mixes import styles (some tests use `from packages.api.tests.fixtures.zip_fixtures import ...`, others use `from f1_api.app import create_app`).

**Fix:** Use consistent relative imports within the test package. If `pytest` is run with `--import-mode=importlib` and `packages/api` on `sys.path`, the canonical form is:
```python
from tests.fixtures.calibration_fixture import build_fixture_posterior
from tests.fixtures.simulate_stubs import install_simulate_stubs
```

---

### IN-03: Magic TTL constant `SESSION_TTL_SECONDS` should be documented as a design decision

**File:** `packages/api/src/f1_api/services/sessions.py:26-31`

**Issue:** `SESSION_TTL_SECONDS = 3600` and `CLEANUP_INTERVAL_SECONDS = 300` are module-level constants with no explanation of why 1 hour was chosen or whether it is configurable via environment variable. The constraint is a design decision (D-07) but is hard-coded with no path to override in deployment. If Fly.io's ephemeral filesystem is mounted, leftover sessions after a restart accumulate indefinitely until a GC pass (the daemon is not started on process resume without the lifespan event).

**Fix:** Source TTL from an environment variable with a fallback:
```python
SESSION_TTL_SECONDS: int = int(os.environ.get("F1_SESSION_TTL_SECONDS", "3600"))
```

---

### IN-04: `test_simulate_cache_hit` uses wall-clock timing — fragile on slow CI

**File:** `packages/api/tests/test_simulate.py:310`

**Issue:** `assert second_ms < 50.0` is a hard wall-clock assertion. On a slow CI runner (shared GitHub Actions runner under load), the SQLite round-trip + JSON deserialization may routinely take 50-100 ms, causing spurious failures. The test is marked `@pytest.mark.integration` which partially mitigates this, but there is no skip condition for slow environments.

**Fix:** Relax the bound to a relative assertion (cache hit is significantly faster than cold path) or use a multiple:
```python
assert second_ms < first_ms * 0.5, (
    f"Cache hit ({second_ms:.1f} ms) was not significantly faster than cold path ({first_ms:.1f} ms)"
)
```
This avoids absolute timing while still asserting the cache is actually working.

---

_Reviewed: 2026-04-24T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
