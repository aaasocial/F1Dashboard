---
phase: 04-simulation-api-uncertainty-quantification
plan: 05
subsystem: testing
tags: [integration, benchmark, human-verify, pytest, fastapi, simulate, calibration, sessions]

# Dependency graph
requires:
  - phase: 04-01
    provides: POST /simulate endpoint + K=100 posterior-draw service
  - phase: 04-02
    provides: GET /calibration/{compound} endpoint + calibration service
  - phase: 04-03
    provides: POST /sessions/upload endpoint + zip extractor + cleanup daemon
  - phase: 04-04
    provides: app wiring (GZipMiddleware, lifespan, session_id merge into simulate)

provides:
  - Wall-time benchmark verifying D-04 <2s cold-path budget (K=100 stubbed physics, real aggregation + JSON + cache)
  - E2E integration test spanning all three Phase 4 endpoints with cross-asserted calibration_id
  - install_simulate_stubs helper in fixtures/simulate_stubs.py for reuse across test modules
  - Full Phase 4 regression: 40 passed, 0 failed (unit) + 4 integration tests green
  - Human-verify checkpoint confirming correct runtime behaviour and security handling
  - Bug fix: missing calibration_runs table returns 404 instead of 500

affects:
  - 05-physics-model (relies on simulate service API shape and <2s budget being confirmed)
  - any future calibration work (posterior_store.py graceful 404 pattern established)

# Tech tracking
tech-stack:
  added:
    - packages/api/tests/fixtures/simulate_stubs.py (new fixture module)
    - packages/api/tests/test_phase4_integration.py (new test file)
  patterns:
    - install_simulate_stubs helper: centralised monkeypatching of all simulate-layer dependencies for integration tests
    - time.perf_counter() manual wall-time assertion (not pytest-benchmark statistical harness) to avoid flaky re-runs
    - Cross-endpoint calibration_id consistency assertion pattern for /simulate <-> /calibration

key-files:
  created:
    - packages/api/tests/fixtures/simulate_stubs.py
    - packages/api/tests/test_phase4_integration.py
  modified:
    - packages/api/tests/test_simulate.py (replaced skip with real benchmark)
    - packages/api/tests/conftest.py (re-export install_simulate_stubs)
    - packages/api/src/f1_api/services/posterior_store.py (graceful 404 on missing table)

key-decisions:
  - "Used time.perf_counter() manually rather than pytest-benchmark's statistical harness to avoid non-deterministic re-runs that could mask real budget violations"
  - "Centralised all simulate-layer monkeypatching in fixtures/simulate_stubs.py::install_simulate_stubs rather than duplicating stubs across test modules"
  - "Human verify: POST /simulate returning 404 (no Phase 3 artifacts) was accepted as correct — error message accuracy is the gate, not a 200 response"

patterns-established:
  - "Benchmark pattern: stub the physics kernel, keep real aggregation + serialisation + cache to verify JSON path timing budget"
  - "E2E pattern: seed DB via fixture -> upload session -> simulate -> read calibration -> cross-assert shared calibration_id"
  - "Graceful degradation: sqlite3.OperationalError on missing table returns None (404) not 500"

requirements-completed: [API-04, API-05, API-06]

# Metrics
duration: 115min
completed: 2026-04-24
---

# Phase 04-05: Wave 3 Verification Summary

**40/40 unit tests + 4 integration tests green; D-04 <2s wall-time budget verified; human-verify checkpoint passed with one bug fix applied during verification**

## Performance

- **Duration:** ~115 min
- **Started:** 2026-04-24T10:20Z (approx)
- **Completed:** 2026-04-24T12:30Z (approx)
- **Tasks:** 3 (Task 1: benchmark + E2E tests; Task 2: full suite regression; Task 3: human-verify checkpoint)
- **Files modified:** 5

## Accomplishments

- Replaced the Wave-0 `pytest.skip` placeholder in `test_simulate_wall_time` with a real benchmark: K=100 cold-path calls through real aggregation, JSON serialisation, and SQLite cache write, asserting `elapsed < 2.0 s` (D-04 budget).
- Delivered `test_e2e_upload_simulate_calibration` in a new `test_phase4_integration.py`: a single integration test spanning POST /sessions/upload -> POST /simulate -> GET /calibration/C3, cross-asserting that both endpoints return the same `calibration_id`.
- Achieved full Phase 4 suite pass: 40 unit tests + 4 integration tests, 0 failures, 0 skips — `test_no_mcmc_at_runtime` (D-05 enforcement) green end-to-end.
- Human-verify checkpoint confirmed: health check 200, OpenAPI surface 7 routes, session upload 200 + UUID, Zip Slip rejected 400, POST /simulate 404 with correct message (no Phase 3 artifacts — expected), GZip compression confirmed on /races.
- Bug fix applied during verification: `posterior_store.py` was raising a 500 on missing `calibration_runs` table; patched to catch `sqlite3.OperationalError` and return `None` (surfaced as 404).

## Task Commits

1. **Task 1: Wall-time benchmark + E2E integration test** - `f1dfec3` (feat)
2. **Task 2: Full Phase 4 test suite regression run** - `7b7132d` (test)
3. **Task 3: Human-verify checkpoint (bug fix applied by orchestrator)** - `d249920` (fix)

## Files Created/Modified

- `packages/api/tests/fixtures/simulate_stubs.py` - New: centralised `install_simulate_stubs` helper monkeypatching all simulate-layer dependencies (run_simulation, load_stint, _build_params_list, get_posterior, sample_stage4_draws, read_latest_calibration_run, DEFAULT_DB_PATH, cache)
- `packages/api/tests/test_phase4_integration.py` - New: `test_e2e_upload_simulate_calibration` — 3-endpoint E2E integration test
- `packages/api/tests/test_simulate.py` - Modified: replaced `pytest.skip` in `test_simulate_wall_time` with real time.perf_counter() benchmark asserting `< 2.0 s`
- `packages/api/tests/conftest.py` - Modified: re-export `install_simulate_stubs` from fixtures package
- `packages/api/src/f1_api/services/posterior_store.py` - Modified: added `except sqlite3.OperationalError: return None` in `read_latest_calibration_run` to prevent 500 on missing table

## Decisions Made

- Manual `time.perf_counter()` was used rather than the `pytest-benchmark` statistical harness to keep the wall-time assertion deterministic: `pytest-benchmark` auto-reruns tests to estimate timing statistics and would obscure a real budget overrun. Since all physics is stubbed and only JSON/cache paths run, the assertion has ample headroom.
- `install_simulate_stubs` was extracted to `fixtures/simulate_stubs.py` rather than added directly to `conftest.py` to keep the fixture module focused and make the helper importable independently.

## Deviations from Plan

### Auto-fixed Issues

**1. [Bug — 500 on missing calibration_runs table] posterior_store.py raised OperationalError on first-run DB**
- **Found during:** Task 3 (human-verify step 6 — POST /simulate)
- **Issue:** When no Phase 3 calibration has ever been run, the `calibration_runs` table does not exist. `read_latest_calibration_run` propagated the `sqlite3.OperationalError` as an unhandled exception, producing a 500 instead of a 404.
- **Fix:** Added `except sqlite3.OperationalError: return None` so the service layer returns `None` and the router surfaces a clean 404 with the message "no calibration for compound=...".
- **Files modified:** `packages/api/src/f1_api/services/posterior_store.py`
- **Verification:** Human-verify step 6 confirmed 404 with correct error message after fix.
- **Committed in:** `d249920` (fix — separate commit by orchestrator during verification)

---

**Total deviations:** 1 auto-fixed (1 unhandled exception → graceful 404)
**Impact on plan:** Bug fix was necessary for correctness. No scope creep. All 44 tests still green after fix.

## Issues Encountered

The only issue was the `sqlite3.OperationalError` bug in `posterior_store.py` (see above). It was caught during the human-verify checkpoint, fixed immediately, and confirmed correct before approval.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All three Phase 4 endpoints (POST /simulate, GET /calibration/{compound}, POST /sessions/upload) are implemented, tested, and human-verified.
- The <2s wall-time budget for `/simulate` is verified against the real aggregation + JSON + cache path (physics stubbed — actual physics integration will be profiled in Phase 5).
- D-05 (no MCMC at request time) is enforced and tested end-to-end.
- Phase 5 (physics model implementation) can begin: the API contract is stable, schemas are locked, and the test fixture infrastructure (install_simulate_stubs) is ready for reuse.
- Potential concern: actual physics integration (Phase 5 `run_simulation`) may push wall time above 2s; the benchmark currently stubs physics. Profile `run_simulation` early in Phase 5 and apply Numba JIT to the brush-model slip inversion loop if needed.

---
*Phase: 04-simulation-api-uncertainty-quantification*
*Completed: 2026-04-24*
