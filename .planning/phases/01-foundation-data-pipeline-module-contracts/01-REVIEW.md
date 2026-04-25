---
phase: 01-foundation-data-pipeline-module-contracts
reviewed: 2026-04-23T00:00:00Z
depth: standard
files_reviewed: 34
files_reviewed_list:
  - packages/api/src/f1_api/app.py
  - packages/api/src/f1_api/dependencies.py
  - packages/api/src/f1_api/routers/drivers.py
  - packages/api/src/f1_api/routers/races.py
  - packages/api/src/f1_api/routers/stints.py
  - packages/api/src/f1_api/schemas/drivers.py
  - packages/api/src/f1_api/schemas/races.py
  - packages/api/src/f1_api/schemas/stints.py
  - packages/api/src/f1_api/services/stints.py
  - packages/api/tests/conftest.py
  - packages/api/tests/test_endpoints.py
  - packages/core/src/f1_core/contracts.py
  - packages/core/src/f1_core/curvature.py
  - packages/core/src/f1_core/data/compound_mapping.yaml
  - packages/core/src/f1_core/data/known_issues.yaml
  - packages/core/src/f1_core/data_integrity.py
  - packages/core/src/f1_core/filters.py
  - packages/core/src/f1_core/gear_inference.py
  - packages/core/src/f1_core/ingestion/__init__.py
  - packages/core/src/f1_core/ingestion/cache.py
  - packages/core/src/f1_core/ingestion/config.py
  - packages/core/src/f1_core/ingestion/fastf1_client.py
  - packages/core/src/f1_core/stint_annotation.py
  - packages/core/tests/conftest.py
  - packages/core/tests/test_cache.py
  - packages/core/tests/test_contracts.py
  - packages/core/tests/test_curvature.py
  - packages/core/tests/test_data_integrity.py
  - packages/core/tests/test_gear_inference.py
  - packages/core/tests/test_ingestion.py
  - packages/core/tests/test_stint_annotation.py
  - scripts/build_canonical_fixture.py
  - scripts/build_corrupted_fixture.py
  - scripts/fetch.py
findings:
  critical: 1
  warning: 5
  info: 4
  total: 10
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-04-23T00:00:00Z
**Depth:** standard
**Files Reviewed:** 34
**Status:** issues_found

## Summary

Phase 1 delivers the FastF1 ingestion pipeline, data-integrity scoring, stint annotation, curvature computation, gear-ratio inference, module contracts, and the three FastAPI endpoints (API-01/02/03). The overall code quality is high: security controls (input validation, atomic writes, safe YAML loading, CORS allowlist) are correctly layered; physics contracts are clean dataclasses with no Pydantic bleed; the two-layer cache design is sound.

One critical issue was found: `load_or_fetch` in `cache.py` deserializes a pickle from disk without verifying that the file's embedded key matches the requested key. A stale or hand-crafted cache entry could return data belonging to a different driver or stint without any error. Five warnings cover logic gaps (bare-except swallowing driver-load errors, missing error handling for `list_races`, unguarded race conditions in the cache initializer, a `_atomic_write` that does not `fsync` before `os.replace`, and a curvature-map edge case when all laps are degenerate). Four info items round out the report.

---

## Critical Issues

### CR-01: Pickle cache returned without key integrity check

**File:** `packages/core/src/f1_core/ingestion/cache.py:71-78`
**Issue:** `load_or_fetch` opens an existing `.pkl.gz` file and accepts it as valid if it deserializes to a `StintArtifact` instance. It never asserts that `artifact.key == key`. If a file is renamed, written by an older code path, or an OS-level rename collision occurs, a caller requesting `(VER, stint 2)` could silently receive data for `(HAM, stint 1)`. The comment "stale file from older preprocessing_version" only handles the case where the type check fails — it does not catch same-type mismatches.

**Fix:**
```python
if p.exists():
    with gzip.open(p, "rb") as f:
        artifact = pickle.load(f)
    if not isinstance(artifact, StintArtifact) or artifact.key != key:
        # Key mismatch or wrong type — treat as cache miss and overwrite.
        artifact = fetcher(key)
        _atomic_write(artifact, p)
    return artifact
```

---

## Warnings

### WR-01: Bare `except` swallows all errors in `list_drivers_for_race`

**File:** `packages/api/src/f1_api/services/stints.py:91-93`
**Issue:** The `try/except Exception` block around `session.get_driver(drv)` silently treats every failure — including `KeyboardInterrupt` via `BaseException` subclasses if they somehow tunnel through — as an empty dict. More practically, a `TypeError` or `AttributeError` in the `get_driver` call produces a driver record with an empty `full_name` and `team`, which is exposed directly in the API response. Network errors, missing data, or FastF1 API changes will degrade silently with no log entry.

**Fix:** Log the exception and only catch the specific exceptions FastF1 raises for missing driver info:
```python
try:
    info = session.get_driver(drv)
except (KeyError, ValueError):
    log.warning("get_driver(%s) failed: %s", drv, e, exc_info=True)
    info = {}
```
If the full exception type is unknown, keep `Exception` but add a `log.warning` call.

### WR-02: `list_races` silently swallows all schedule-load errors

**File:** `packages/api/src/f1_api/services/stints.py:60-62`
**Issue:** `except Exception: continue` in the year loop discards every error from `load_schedule` — including I/O errors, FastF1 API timeouts, and programming errors — and returns a partial or empty list with no indication of failure. A caller querying `start_year=2022, end_year=2024` could receive only 2022 races because 2023 errored, with no 500 response or log entry.

**Fix:** At minimum, log the exception at WARNING level so operators can diagnose silent data gaps:
```python
try:
    sched = load_schedule(year)
except Exception as e:
    log.warning("Failed to load schedule for year %d: %s", year, e, exc_info=True)
    continue
```

### WR-03: `init_cache` has a TOCTOU gap — `_cache_initialized` is checked outside the lock read

**File:** `packages/core/src/f1_core/ingestion/fastf1_client.py:34-44`
**Issue:** The current implementation reads and sets `_cache_initialized` inside `_cache_lock`, which is correct. However, `fastf1.Cache.enable_cache` is not reentrant; if a second thread calls `init_cache()` with a *different* `cache_dir` argument while the first call is inside `enable_cache`, the lock prevents the double-call correctly. The real issue is that `cache_dir or get_cache_dir()` is evaluated **before** the lock is acquired on line 38, meaning two threads could resolve to different directories and the second will silently skip its `enable_cache` call. If the first thread passed `None` but the second thread passes an explicit `Path`, the explicit path is ignored.

**Fix:** Resolve the directory inside the lock:
```python
def init_cache(cache_dir: Path | None = None) -> Path:
    global _cache_initialized
    with _cache_lock:
        resolved = cache_dir or get_cache_dir()
        if not _cache_initialized:
            logging.getLogger("fastf1").setLevel(logging.WARNING)
            fastf1.Cache.enable_cache(str(resolved))
            _cache_initialized = True
        return resolved
```
This is already the implementation — but the return value on a cache-hit does not return the previously-resolved path; it returns whatever `cache_dir or get_cache_dir()` resolved to on this call. This means two callers with different directories get back different paths even though only one was actually registered with FastF1. Store the resolved path as a module-level variable and return it on subsequent calls:
```python
_cache_initialized = False
_cache_dir: Path | None = None

def init_cache(cache_dir: Path | None = None) -> Path:
    global _cache_initialized, _cache_dir
    with _cache_lock:
        if not _cache_initialized:
            resolved = cache_dir or get_cache_dir()
            logging.getLogger("fastf1").setLevel(logging.WARNING)
            fastf1.Cache.enable_cache(str(resolved))
            _cache_initialized = True
            _cache_dir = resolved
        return _cache_dir  # type: ignore[return-value]
```

### WR-04: `_atomic_write` does not `fsync` the gzip file before `os.replace`

**File:** `packages/core/src/f1_core/ingestion/cache.py:84-90`
**Issue:** The code opens a gzip file, writes the pickle, and calls `os.replace`. The gzip file's underlying file descriptor is flushed and closed when the `with` block exits (before `os.replace`), but `fsync` is never called. On Linux the `gzip.open` context manager closes the underlying file, but if the process is killed between close and `os.replace`, or if the OS writes the directory entry before the data blocks (crash consistency), the final path can point to a valid-length but corrupt file on ext4/XFS without `fsync`. The comment says "prevents partial reads (T-01-07)" but that claim requires an `fsync`.

**Fix:**
```python
def _atomic_write(artifact: StintArtifact, final_path: Path) -> None:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = final_path.with_suffix(final_path.suffix + ".tmp")
    with gzip.open(tmp, "wb") as gz:
        pickle.dump(artifact, gz, protocol=pickle.HIGHEST_PROTOCOL)
        gz.flush()
        # fsync the underlying file before rename
        os.fsync(gz.fileobj.fileno())  # type: ignore[attr-defined]
    os.replace(tmp, final_path)
```
Note: `gzip.GzipFile.fileobj` is the underlying raw file; this pattern works in CPython. Alternatively open the raw file first and wrap it with `gzip.GzipFile`.

### WR-05: `compute_curvature_map` raises a misleading error when all laps are short

**File:** `packages/core/src/f1_core/curvature.py:56-68`
**Issue:** When `laps_xy` is non-empty but every lap has fewer than 4 points, the inner `continue` loop produces `per_lap = []`, and then line 68 raises `ValueError("no lap had enough samples to compute curvature")`. This is functionally correct but the raised message is easy to confuse with the earlier empty-list check. More importantly, if exactly one lap has >= 4 points but after the monotonicity filter (`mask`) it ends up with fewer than 4 points, `CubicSpline` will raise an undescriptive scipy error rather than the clean `ValueError`. The monotonicity filter on lines 30-32 can reduce the point count significantly for noisy telemetry with many repeated arc-length values, yet no guard exists.

**Fix:** Add a post-filter length check before constructing the splines:
```python
s = s[mask]; x = x[mask]; y = y[mask]
if len(s) < 4:
    continue  # skip this lap rather than crashing in CubicSpline
cs_x = CubicSpline(s, x)
```

---

## Info

### IN-01: `list[str]` as a `default_factory` argument is a type annotation, not a factory

**File:** `packages/core/src/f1_core/contracts.py:237`
**Issue:** `field(default_factory=list[str])` passes the generic alias `list[str]` (a `types.GenericAlias` object) as the factory. In CPython 3.12, calling `list[str]()` actually works because `list[str]` is callable and returns an empty `list`. This is a CPython implementation detail, not guaranteed by the language spec, and it is needlessly confusing to readers. The conventional idiom is `field(default_factory=list)`.

**Fix:**
```python
issues: list[str] = field(default_factory=list)
```

### IN-02: `stints.py` service imports `fastf1` inside function bodies

**File:** `packages/api/src/f1_api/services/stints.py:82,108`
**Issue:** `import fastf1` is deferred to inside `list_drivers_for_race` and `list_stints_for_driver`. This avoids a top-level import but means the import is re-evaluated on every request (though Python caches it in `sys.modules`). More importantly, it hides the dependency from static analysis tools and makes the module's requirements non-obvious. The `build_canonical_fixture.py` and `fetch.py` scripts use top-level imports for the same package family.

**Fix:** Move `import fastf1` to the module's top-level imports alongside the other `f1_core` imports.

### IN-03: `compound_mapping.yaml` key format inconsistency with service layer lookup

**File:** `packages/core/src/f1_core/data/compound_mapping.yaml:6` and `packages/api/src/f1_api/services/stints.py:138`
**Issue:** The compound mapping file uses zero-padded two-digit round numbers (e.g. `"2023-01"`). The service layer constructs the lookup key as `f"{year}-{round_number:02d}"` (line 138 of `stints.py`), which matches. However, the `_compound_letter` function in `stint_annotation.py` uses the same format (`f"{year}-{round_number:02d}"`, line 76). These are consistent, but the YAML keys are quoted strings (e.g. `"2023-01"`) while the Python format string produces an unquoted equivalent. YAML loads quoted strings as plain strings, so this is fine — but the inconsistency in quoting style (some YAML keys quoted, some unquoted in YAML spec) could cause confusion if a new entry is added without quotes and a YAML parser treats it differently (e.g. `2023-1` could be interpreted as the integer subtraction `2022` in some parsers). Recommend documenting the required quoting convention in the YAML file header.

**Fix:** Add a comment at the top of `compound_mapping.yaml`:
```yaml
# IMPORTANT: All keys MUST be quoted strings (e.g. "2023-01"), NOT bare YAML scalars.
# A bare "2023-01" is a valid YAML string, but "2023-1" without zero-padding
# would also be valid and silently mis-key the entry.
```

### IN-04: `test_contracts_module_does_not_import_pydantic` test is order-dependent

**File:** `packages/core/tests/test_contracts.py:81-93`
**Issue:** The test deletes all `pydantic*` keys from `sys.modules`, then reloads `f1_core.contracts` and asserts pydantic is still absent. If any prior test in the same process imported `f1_core.contracts` together with code that transitively imports pydantic (e.g., if a future module is added to `f1_core` that imports pydantic and is imported at test-collection time), the test could give a false negative because `importlib.reload` only re-executes the module body — it does not re-execute transitive imports that are already cached under different `sys.modules` keys. The test could be made more robust with an isolated subprocess.

**Fix:** This is a test reliability observation only. For now, document the limitation with a comment. For stronger isolation, consider:
```python
import subprocess, sys
result = subprocess.run(
    [sys.executable, "-c",
     "import f1_core.contracts; import sys; assert 'pydantic' not in sys.modules"],
    capture_output=True,
)
assert result.returncode == 0, result.stderr.decode()
```

---

_Reviewed: 2026-04-23T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
