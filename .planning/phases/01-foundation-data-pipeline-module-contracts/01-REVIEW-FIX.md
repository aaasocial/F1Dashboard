---
phase: 01-foundation-data-pipeline-module-contracts
fixed_at: 2026-04-23T00:00:00Z
review_path: .planning/phases/01-foundation-data-pipeline-module-contracts/01-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 01: Code Review Fix Report

**Fixed at:** 2026-04-23T00:00:00Z
**Source review:** .planning/phases/01-foundation-data-pipeline-module-contracts/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (1 Critical, 5 Warning)
- Fixed: 6
- Skipped: 0

## Fixed Issues

### CR-01: Pickle cache returned without key integrity check

**Files modified:** `packages/core/src/f1_core/ingestion/cache.py`
**Commit:** 0ef9212
**Applied fix:** Extended the isinstance check in `load_or_fetch` to also assert `artifact.key == key`. A cache miss is now triggered on either a type mismatch or a key mismatch, preventing silent cross-driver or cross-stint data returns from renamed or colliding cache files.

### WR-01: Bare `except` swallows all errors in `list_drivers_for_race`

**Files modified:** `packages/api/src/f1_api/services/stints.py`
**Commit:** cf9748b
**Applied fix:** Added `import logging` and a module-level `log = logging.getLogger(__name__)`. Changed `except Exception:` to `except Exception as e:` and added `log.warning("get_driver(%s) failed: %s", drv, e, exc_info=True)` before falling back to `info = {}`. Failures are now visible in operator logs rather than silently producing empty driver records.

### WR-02: `list_races` silently swallows all schedule-load errors

**Files modified:** `packages/api/src/f1_api/services/stints.py`
**Commit:** d022a90
**Applied fix:** Changed `except Exception: continue` in `list_races` to `except Exception as e: log.warning("Failed to load schedule for year %d: %s", year, e, exc_info=True); continue`. Partial schedule gaps are now surfaced in logs so operators can diagnose silent data gaps.

### WR-03: `init_cache` has a TOCTOU gap — `_cache_initialized` is checked outside the lock read

**Files modified:** `packages/core/src/f1_core/ingestion/fastf1_client.py`
**Commit:** 9b38512
**Applied fix:** Added a module-level `_cache_dir: Path | None = None` variable. Moved `resolved = cache_dir or get_cache_dir()` inside the `if not _cache_initialized:` branch so directory resolution only occurs on the first call. On subsequent calls the stored `_cache_dir` is returned directly, ensuring all callers receive the same path regardless of which `cache_dir` argument they passed.

### WR-04: `_atomic_write` does not `fsync` the gzip file before `os.replace`

**Files modified:** `packages/core/src/f1_core/ingestion/cache.py`
**Commit:** 04b0b5a
**Applied fix:** Replaced `gzip.open(tmp, "wb")` with an explicit `open(tmp, "wb") as raw` wrapping a `gzip.GzipFile(fileobj=raw, mode="wb")`. After the gzip context manager closes (flushing compressed data), `raw.flush()` and `os.fsync(raw.fileno())` are called on the underlying file descriptor before `os.replace`. This ensures data blocks are on disk before the directory entry is updated, satisfying the crash-consistency guarantee claimed by the T-01-07 comment.

### WR-05: `compute_curvature_map` raises a misleading error when all laps are short

**Files modified:** `packages/core/src/f1_core/curvature.py`
**Commit:** 1d29f4d
**Applied fix:** Added a post-monotonicity-filter length guard in `curvature_from_xy`: if `len(s) < 4` after the deduplication mask, a descriptive `ValueError` is raised immediately rather than letting `CubicSpline` crash with an opaque scipy error. In `compute_curvature_map`, the `curvature_from_xy` call is wrapped in `try/except ValueError: continue` so laps that pass the initial 4-point check but shrink below 4 after filtering are silently skipped, matching the existing handling for laps that start below 4 points.

---

_Fixed: 2026-04-23T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
