---
phase: 01-foundation-data-pipeline-module-contracts
plan: 03
subsystem: data-ingestion
tags: [fastf1, python, pandas, gzip-pickle, cache, argparse, pytest]

# Dependency graph
requires:
  - phase: 01
    plan: 01
    provides: uv workspace layout, f1-core package skeleton, ruff config
provides:
  - f1_core.ingestion module (config, cache, fastf1_client, __init__)
  - StintKey + StintArtifact dataclasses (contract for Layer-2 cache)
  - load_or_fetch two-layer cache with atomic os.replace writes
  - validate_race_id / validate_driver_code / parse_race_id (T-01-04 mitigation)
  - get_cache_dir (F1_CACHE_DIR env override, default .data/fastf1_cache)
  - init_cache (idempotent FastF1 Cache.enable_cache + logger silencing)
  - load_stint / load_schedule public API
  - scripts/fetch.py CLI with pre-validation
  - scripts/build_canonical_fixture.py one-shot fixture builder
  - packages/core/tests/fixtures/bahrain_2023_ver_stint2.pkl.gz (D-06 canonical fixture)
affects:
  - 01-04 (data-integrity, annotation, curvature — consumes StintArtifact)
  - 01-05 (FastAPI GET endpoints — uses load_stint, load_schedule, validators)
  - 02 (physics model — reads fixture for benchmarks)
  - 03 (calibration — loads multiple stint artifacts)

# Tech tracking
tech-stack:
  added: [fastf1==3.8.2 usage, gzip+pickle Layer-2 cache, pytest parametrize]
  patterns:
    - "Two-layer cache with version-keyed filenames (fastf1 version + preprocessing version)"
    - "Atomic disk writes via .tmp + os.replace to prevent partial-read corruption"
    - "CLI argv validation at boundary BEFORE any filesystem/network access (T-01-04)"
    - "Idempotent module init via lock + flag (init_cache called once per process)"
    - "Mock-fetcher testing pattern — all cache tests run offline without FastF1"

key-files:
  created:
    - packages/core/src/f1_core/ingestion/__init__.py
    - packages/core/src/f1_core/ingestion/config.py
    - packages/core/src/f1_core/ingestion/cache.py
    - packages/core/src/f1_core/ingestion/fastf1_client.py
    - packages/core/tests/test_cache.py
    - packages/core/tests/test_ingestion.py
    - packages/core/tests/fixtures/.gitkeep
    - packages/core/tests/fixtures/bahrain_2023_ver_stint2.pkl.gz
    - scripts/__init__.py
    - scripts/build_canonical_fixture.py
    - scripts/fetch.py
  modified: []

key-decisions:
  - "CACHE_DIR default .data/fastf1_cache (local dev, gitignored); F1_CACHE_DIR env overrides"
  - "Layer-2 cache filename includes BOTH fastf1.__version__ and preprocessing_version=v1"
  - "Atomic write (.tmp + os.replace) used so concurrent readers never see partial pickle"
  - "Cache-miss defensive fallback: if unpickled object is not StintArtifact, treat as cache miss and refetch"
  - "scripts/ uses sys.path.insert to avoid requiring package install for one-off runs"

patterns-established:
  - "Dataclass contract for cache artifacts (StintArtifact is what every stint looks like)"
  - "Fetcher callable injection — load_or_fetch accepts Callable[[StintKey], StintArtifact] so tests use mocks and production uses FastF1"
  - "Validators return the validated value (validate_race_id(x) -> x) so they can be composed in guard clauses"

requirements-completed: [DATA-01, DATA-02]

# Metrics
duration: 8m 20s
completed: 2026-04-23
---

# Phase 01 Plan 03: FastF1 Ingestion + Two-Layer Cache Summary

**FastF1 wrapper with versioned gzip-pickle Layer-2 cache, path-traversal-safe CLI, and committed Bahrain 2023 VER stint 2 canonical fixture (22 laps, 8060 telemetry samples, 20.9 MB).**

## Performance

- **Duration:** ~8m 20s
- **Started:** 2026-04-23T01:10:26Z
- **Completed:** 2026-04-23T01:18:46Z
- **Tasks:** 3
- **Files created:** 11
- **Files modified:** 0

## Accomplishments

- **DATA-01 satisfied:** `load_stint(year, event, driver_code, stint_index)` fetches a typed `StintArtifact` from FastF1 via Jolpica; lookup goes through the versioned disk cache on subsequent calls.
- **DATA-02 satisfied:** Two-layer cache operational — Layer 1 is FastF1's built-in SQLite/pickle (via `fastf1.Cache.enable_cache`); Layer 2 is our gzip-pickle artifact keyed by `(year, round, driver_code, stint_index, fastf1_version, preprocessing_version)`. A second call to `load_or_fetch` with identical keys issues zero HTTP traffic (verified by `test_second_call_hits_cache`).
- **T-01-04 mitigated:** `scripts/fetch.py` rejects `../etc/passwd`-style race_ids and lowercase driver codes with exit 2 BEFORE any filesystem/network access. 7 parametrized path-traversal rejection cases pass.
- **T-01-07 mitigated:** Layer-2 writes go to `.tmp` first then `os.replace` into final path, so a partial pickle is never visible to a concurrent reader (verified by `test_atomic_write_never_leaves_partial`).
- **P5 mitigated:** `logging.getLogger("fastf1").setLevel(logging.WARNING)` called inside `init_cache`, silencing Jolpica rate-limit INFO spam.
- **P6 mitigated:** `grep pickle.dump packages/core/src/f1_core/ingestion/` shows a single match — `pickle.dump(artifact, ...)`. No `Session` object ever pickled.
- **A8 satisfied:** `init_cache` uses a `threading.Lock` + module-level flag so `fastf1.Cache.enable_cache` is called at most once per process.
- **D-06 canonical fixture committed** to git at `packages/core/tests/fixtures/bahrain_2023_ver_stint2.pkl.gz` (20.9 MB compressed). Unblocks Plans 04, 05 and Phase 2 benchmarks — they can run entirely offline.

## Task Commits

1. **Task 1: Ingestion module (config, cache, fastf1_client, __init__)** — `20376f1` (feat)
2. **Task 2: Cache + validator unit tests (mock fetcher, no network)** — `082779e` (test)
3. **Task 3: Build canonical fixture + fetch CLI; commit fixture** — `3ff80c6` (feat)

All three commits carry the `01-03` scope. Tests pass 29/29 after Task 3.

## Files Created

**Source (packages/core/src/f1_core/ingestion/):**
- `__init__.py` — re-exports the public surface (StintKey, StintArtifact, load_or_fetch, init_cache, load_stint, load_schedule, validators, get_cache_dir, PREPROCESSING_VERSION)
- `config.py` — `RACE_ID_PATTERN`, `DRIVER_CODE_PATTERN`, `validate_race_id`, `validate_driver_code`, `parse_race_id`, `get_cache_dir`
- `cache.py` — `PREPROCESSING_VERSION`, `StintKey`, `StintArtifact`, `load_or_fetch`, `_atomic_write`
- `fastf1_client.py` — `init_cache`, `_extract_artifact`, `load_stint`, `load_schedule`

**Tests (packages/core/tests/):**
- `test_cache.py` — 4 cache-layer tests (hit/miss, key versioning, write path, atomic write)
- `test_ingestion.py` — 25 parametrized validator + fixture-smoke tests
- `fixtures/.gitkeep` — ensures fixture directory tracked
- `fixtures/bahrain_2023_ver_stint2.pkl.gz` — 20.9 MB canonical fixture (22 laps, 8060 samples)

**Scripts (scripts/):**
- `__init__.py` — marker file
- `build_canonical_fixture.py` — one-shot D-06 fixture builder
- `fetch.py` — argparse-based CLI with pre-validation

## Fixture Build Results (Task 3)

| Attribute | Value |
|-----------|-------|
| Race | 2023 Bahrain Grand Prix (round 1) |
| Driver | VER |
| Stint index | 2 |
| Compound (ground truth) | **SOFT** (see Deviations — plan said MEDIUM) |
| Lap numbers | 15.0–36.0 (22 laps) |
| TyreLife range | 1.0 → 22.0 |
| Car telemetry samples | 8060 |
| Compressed pickle size | 21438 KB (~20.9 MB) |
| fastf1 version baked into filename | 3.8.2 |
| preprocessing_version | v1 |
| Cache filename | `2023_01_VER_stint2__ff1-3.8.2__prep-v1.pkl.gz` |
| Cold-cache fetch wall-clock | ~25s (single FastF1 session load) |
| Warm-cache `scripts/fetch.py` wall-clock | 1.36s (includes Python + FastF1 import; cache read itself is sub-100ms) |

## Decisions Made

- **Default cache path `.data/fastf1_cache`** (Claude's discretion, per CONTEXT.md). `.data/` is already in `.gitignore`. Production will set `F1_CACHE_DIR=/data/fastf1_cache` on Fly.io.
- **`F401` ignored in `__init__.py`** via existing `ruff.toml` per-file-ignore — re-exports don't need explicit `__all__` usage. We still provide `__all__` for IDE completeness.
- **`scripts/__init__.py` as plain marker** rather than making scripts a proper package; sys.path manipulation kept inside each script for ergonomics (single `uv run python scripts/xyz.py` invocation).
- **Defensive cache-miss reload** when unpickled object isn't a `StintArtifact` — handles stale pickles from older `PREPROCESSING_VERSION` values even when filename-level versioning somehow missed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused `noqa: E402` directives in scripts**
- **Found during:** Task 3 (ruff check on scripts/)
- **Issue:** The plan's script snippets included `# noqa: E402` on `from f1_core.ingestion import ...` lines after `sys.path.insert(...)`. Ruff rule `RUF100` flagged both as "unused noqa" because `E402` is not in the project's active selection (`E` includes `E402` by default, but our `ruff.toml` shows just `select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]` and the imports appear top-level so no `E402` fires anyway).
- **Fix:** Removed the `# noqa: E402` directives from both `scripts/fetch.py` and `scripts/build_canonical_fixture.py`.
- **Files modified:** `scripts/fetch.py`, `scripts/build_canonical_fixture.py`
- **Verification:** `uv run ruff check scripts/` → `All checks passed!`
- **Committed in:** `3ff80c6` (Task 3 commit)

**2. [Rule 1 - Bug] Fixed ruff `UP037` and `RUF022` errors in ingestion module**
- **Found during:** Task 1 (ruff check)
- **Issue:** (a) `session: "fastf1.core.Session"` used string-quoted annotation but pyupgrade (`UP037`) wants the naked annotation once `from __future__ import annotations` is present; (b) `__all__` order in `ingestion/__init__.py` wasn't isort-sorted (`RUF022`).
- **Fix:** Added `import fastf1.core`, dropped quotes around the annotation. Re-sorted `__all__` alphabetically (with dataclasses first per project convention observed in existing files).
- **Files modified:** `packages/core/src/f1_core/ingestion/fastf1_client.py`, `packages/core/src/f1_core/ingestion/__init__.py`
- **Verification:** `uv run ruff check packages/core/src/f1_core/ingestion/` → `All checks passed!`
- **Committed in:** `20376f1` (Task 1 commit)

**3. [Rule 1 - Documentation correction] Fixture compound is SOFT, not MEDIUM**
- **Found during:** Task 3 (fixture integrity verification)
- **Issue:** Plan doc and `.planning/.../01-CONTEXT.md` D-06 describe the Bahrain 2023 VER stint 2 fixture as "MEDIUM compound, laps 16–38". Running `scripts/build_canonical_fixture.py` against actual FastF1 ground truth yields `Compound=SOFT`, `LapNumber=15–36`, `TyreLife=1–22` (22 laps total, not ~23). The stint selector is correct (stint_index=2); only the compound label in the documentation was wrong.
- **Fix:** Not a code fix — the FastF1 data is authoritative. Plan's acceptance criteria tolerate 15–30 laps, which 22 satisfies. The fixture is committed as-is. Discrepancy noted here so Plans 04/05/02 treat SOFT as the canonical compound for the benchmark.
- **Files modified:** None (code correct; only documentation was off).
- **Verification:** `uv run pytest packages/core/tests/test_ingestion.py::test_fetch_canonical_fixture_smoke` — passes.
- **Committed in:** `3ff80c6` (Task 3 commit message explicitly notes this)

**4. [Rule 2 - Missing critical] Plan's `load_stint` logic was unreachable for the `_fetcher` closure's `key` variable**
- **Found during:** Task 1 (implementing `load_stint` from the plan snippet)
- **Issue:** The plan's inner `_fetcher` closure rebuilt a new `key` variable using `fastf1.get_event_schedule` inside the closure, but the outer function also independently built the same key before calling `load_or_fetch(key, root, _fetcher)`. The closure's reassignment never reached `load_or_fetch`. The plan noted "Simpler: look up the round via event schedule, cache by the canonical key" and then did exactly that with the outer schedule lookup — but left the now-redundant (and broken) closure logic in.
- **Fix:** Simplified `_fetcher` to take the already-built `key`, call `fastf1.get_session(...)`, `session.load(...)`, and `_extract_artifact(session, k)` — no more round re-derivation inside the closure. Outer key construction happens once via the schedule lookup.
- **Files modified:** `packages/core/src/f1_core/ingestion/fastf1_client.py`
- **Verification:** `scripts/build_canonical_fixture.py` ran successfully producing the right key `StintKey(2023, 1, 'VER', 2)`; `test_fetch_canonical_fixture` passes with the matching key.
- **Committed in:** `20376f1` (Task 1 commit)

---

**Total deviations:** 4 auto-fixed (2 ruff lint bugs, 1 doc correction, 1 implementation bug in plan snippet).
**Impact on plan:** All fixes necessary to get green tests / green lint. No scope creep; no architectural change.

## Issues Encountered

- **UV virtualenv warning** on every `uv run` invocation: `VIRTUAL_ENV=...\python\cpython-3.13-windows-x86_64-none does not match the project environment path .venv`. This is a host-side env-var that uv correctly ignores because the project pins Python 3.12. Non-blocking; all commands succeeded. No code change needed.
- **`scripts/fetch.py` event slug translation** — the plan sketched `event = event_slug.replace("_", " ")` (e.g. `saudi_arabia` → `saudi arabia`) relying on FastF1's fuzzy matching. This was not exercised end-to-end by a test because the canonical fixture builder passes `event="Bahrain"` directly. Real CLI invocations with multi-word slugs will be validated in Plan 05 (FastAPI endpoints) which shares the same translation.

## Known Stubs

None. All functions ship with real implementations backed by tests; the only `.empty` fallbacks in `_extract_artifact` are defensive guards for optional session fields (weather, track_status, race_control_messages) that FastF1 itself may return as None.

## Threat Flags

None — all files touched are within the planned threat model (CLI argv → filesystem, Jolpica HTTP → pickle artifact). No new network endpoints, auth paths, or unexpected file access introduced.

## Self-Check: PASSED

Verified on disk:
- `packages/core/src/f1_core/ingestion/__init__.py` FOUND
- `packages/core/src/f1_core/ingestion/config.py` FOUND
- `packages/core/src/f1_core/ingestion/cache.py` FOUND
- `packages/core/src/f1_core/ingestion/fastf1_client.py` FOUND
- `packages/core/tests/test_cache.py` FOUND
- `packages/core/tests/test_ingestion.py` FOUND
- `packages/core/tests/fixtures/.gitkeep` FOUND
- `packages/core/tests/fixtures/bahrain_2023_ver_stint2.pkl.gz` FOUND (21,438 KB)
- `scripts/__init__.py` FOUND
- `scripts/build_canonical_fixture.py` FOUND
- `scripts/fetch.py` FOUND

Verified in git log:
- `20376f1` (Task 1) FOUND
- `082779e` (Task 2) FOUND
- `3ff80c6` (Task 3) FOUND

Verified behaviorally:
- `uv run pytest packages/core/tests -x` — 29 passed, 0 failed, 0 skipped
- `uv run ruff check packages/core/src/f1_core/ingestion/ scripts/` — All checks passed
- `uv run python scripts/fetch.py "../etc/passwd" VER --stint 2` — exit 2, "Invalid race_id"
- `uv run python scripts/fetch.py "2023-bahrain" "ver" --stint 2` — exit 2, "Invalid driver_code 'ver'"
- `uv run python scripts/fetch.py "2023-bahrain" "VER" --stint 2` (warm cache) — 1.36s total, emits "OK: Bahrain Grand Prix VER stint 2: 22 laps, 8060 telemetry samples"

## Next Plan Readiness

- **Plan 04 (data integrity, annotation, curvature, gear inference)** unblocked: can read `StintArtifact` from the committed fixture, filter by `laps` column, and derive curvature/gear without Jolpica access.
- **Plan 05 (FastAPI GET endpoints)** unblocked: can call `load_stint`, `load_schedule`, `validate_race_id`, `validate_driver_code` directly. The HTTP-path-param validation regex is already the same one the CLI enforces.
- **Phase 2 benchmark** has its canonical stint: 22 laps of VER / Bahrain 2023 stint 2 (SOFT).

No blockers.

---
*Phase: 01-foundation-data-pipeline-module-contracts*
*Plan: 03*
*Completed: 2026-04-23*
