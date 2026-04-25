---
phase: 04
plan: "04"
subsystem: api
tags: [app-wiring, middleware, lifespan, session-integration, gzip, cleanup-daemon]

requires:
  - phase: 04
    plan: "01"
    provides: simulate service + posterior_store + routers/simulate.py
  - phase: 04
    plan: "02"
    provides: calibration router (routers/calibration.py)
  - phase: 04
    plan: "03"
    provides: sessions service + routers/sessions.py + start_cleanup_daemon

provides:
  - create_app() wiring 6 routers (races, drivers, stints, sessions, simulate, calibration)
  - GZipMiddleware(minimum_size=1024, compresslevel=5) on all responses
  - Extended lifespan: start_cleanup_daemon() + prime_posterior for C1..C5 (best-effort)
  - _merge_session_into_cache: Pitfall 7 Option A — copies session dir into global FastF1 cache
  - run_simulation_with_uncertainty: session_id-aware (merges before load_stint)
  - test_session_routes_simulate: green under @pytest.mark.integration (API-06-d)

affects:
  - 04-05-PLAN (wall-time benchmark + integration E2E use the fully wired app)

tech-stack:
  added:
    - fastapi.middleware.gzip.GZipMiddleware (built-in FastAPI; no new dep)
  patterns:
    - GZip config: minimum_size=1024, compresslevel=5 (Pitfall 9 — never use compresslevel=9)
    - Lifespan: try/yield/finally with cleanup_stop.set() for graceful daemon shutdown
    - prime_posterior wrapped in try/except Exception so missing DB at startup only logs warning
    - Pitfall 7 Option A: shutil.copytree(session_dir, fastf1_cache_root, dirs_exist_ok=True)
    - Defence-in-depth: _SESSION_ID_RE regex + is_relative_to SESSION_ROOT guard in simulate.py

key-files:
  modified:
    - packages/api/src/f1_api/app.py (GZipMiddleware + extended lifespan + import additions)
    - packages/api/src/f1_api/services/simulate.py (_merge_session_into_cache + session_id wiring)
    - packages/api/tests/test_sessions.py (test_session_routes_simulate: skip replaced with real assertions)

key-decisions:
  - "GZipMiddleware added with compresslevel=5 (not 9): compresslevel=9 causes >10x CPU penalty
    on large simulation responses; 5 achieves ~70% of the compression ratio at <2x CPU cost"
  - "prime_posterior for C1..C5 wrapped in try/except: missing calibration DB at cold startup
    must not crash the server — logs a warning and continues (T-4-LIFESPAN-CRASH mitigation)"
  - "Lifespan uses try/yield/finally + cleanup_stop.set(): ensures daemon receives stop signal
    on any exit path (normal shutdown, unhandled exception, SIGTERM)"
  - "_merge_session_into_cache placed in simulate.py (not sessions.py): keeps the Pitfall 7
    Option A merge logic close to the load_stint call site; sessions.py stays focused on
    upload/TTL lifecycle; the SESSION_ROOT import is the only coupling"

router-order:
  - races_router (GET /races, GET /races/{race_id}/drivers)
  - drivers_router (GET /races/{race_id}/drivers)
  - stints_router (GET /stints/{race_id}/{driver_id})
  - sessions_router (POST /sessions/upload)
  - simulate_router (POST /simulate)
  - calibration_router (GET /calibration/{compound})

gzip-config:
  minimum_size: 1024
  compresslevel: 5

lifespan-posterior-priming:
  compounds: [C1, C2, C3, C4, C5]
  on_failure: log WARNING, continue startup

cleanup-daemon:
  thread_name: session-ttl-cleanup
  stop_signal: cleanup_stop.set() in lifespan finally block

requirements-completed: [API-04, API-05, API-06]

metrics:
  duration: ~8 min
  completed: "2026-04-24"
  tasks: 2
  files_modified: 3
  tests_passing: 41
  tests_skipped: 2
---

# Phase 4 Plan 04: App Wiring — GZipMiddleware + Lifespan + session_id Routing

**Wave-2 wiring complete: 6 routers + GZipMiddleware + cleanup daemon + posterior priming + session_id merge path — 41 unit tests green, test_session_routes_simulate (API-06-d) green**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-24T01:20:00Z
- **Completed:** 2026-04-24T01:28:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Extended `create_app()` in `app.py`: added `GZipMiddleware(minimum_size=1024, compresslevel=5)`
  after CORS middleware; all 6 routers now present in router chain
- Extended `lifespan` context manager: calls `start_cleanup_daemon()` (captures thread + stop_event),
  loops over C1..C5 calling `prime_posterior(DEFAULT_DB_PATH, c)` in try/except, and sets
  `cleanup_stop.set()` in the `finally` block for graceful shutdown
- Implemented `_merge_session_into_cache(session_id)` in `services/simulate.py`: regex validation
  (`_SESSION_ID_RE = r"^[0-9a-f]{32}$"`), existence check, `is_relative_to(SESSION_ROOT)` guard,
  then `shutil.copytree(session_dir, fastf1_cache_root, dirs_exist_ok=True)` (Pitfall 7 Option A)
- Wired `session_id` into `run_simulation_with_uncertainty`: calls `_merge_session_into_cache`
  before `load_stint` when `session_id is not None`
- Replaced `pytest.skip` stub in `test_session_routes_simulate` with real assertions: uploads valid
  zip, patches SESSION_ROOT + init_cache, calls `_merge_session_into_cache`, asserts merge populated
  global FastF1 cache dir

## Task Commits

1. **Task 1 (TDD RED): Failing test** — `3873720` (test)
2. **Task 1 (app.py): GZipMiddleware + extended lifespan** — `1a7b81d` (feat)
3. **Task 2 (TDD GREEN): _merge_session_into_cache + session_id wiring** — `e3913de` (feat)

## GZip Configuration

| Parameter | Value | Reason |
|-----------|-------|--------|
| `minimum_size` | 1024 bytes | Skip compression for tiny error responses; benefit threshold |
| `compresslevel` | 5 | Pitfall 9: level=9 is 10x slower with <5% extra ratio gain |

## Lifespan Startup Sequence

1. `init_cache()` — initialises FastF1 disk cache
2. `start_cleanup_daemon()` — spawns `session-ttl-cleanup` daemon thread
3. Loop C1..C5: `prime_posterior(DEFAULT_DB_PATH, c)` — warms get_posterior LRU cache
4. `yield` — app serves requests
5. `finally: cleanup_stop.set()` — signals daemon to stop

## Session Merge Path (Pitfall 7 Option A)

```
POST /simulate {session_id: "abc...32chars"}
  → _merge_session_into_cache("abc...")
      → validate regex ^[0-9a-f]{32}$
      → check SESSION_ROOT/abc... exists
      → resolve path, assert is_relative_to(SESSION_ROOT)
      → shutil.copytree(SESSION_ROOT/abc..., GLOBAL_FASTF1_CACHE, dirs_exist_ok=True)
  → load_stint(year, event, driver, stint)  ← finds data locally, skips Jolpica
```

## Test Results

| Test file | Count | Status |
|-----------|-------|--------|
| test_endpoints.py | 23 | PASSED |
| test_sessions.py (non-integration) | 6 | PASSED |
| test_sessions.py::test_session_routes_simulate | 1 | PASSED (integration) |
| test_simulate.py (non-integration) | 7 | PASSED |
| test_calibration.py (non-integration) | 3 | PASSED |
| test_no_mcmc_at_runtime | 1 | PASSED |
| test_simulate_wall_time | 1 | SKIPPED (Plan 05) |
| test_simulate_cache_hit | 1 | SKIPPED (integration) |

**Total: 41 passed, 2 skipped (both integration deferred to Plan 05)**

## Deviations from Plan

None — plan executed exactly as written.

The test stub in Plan 03 (which deferred `test_session_routes_simulate` to "Plan 05") was
intentionally resolved in Plan 04 as directed by the plan. The test body follows the approach
specified in the plan's `<action>` section (direct `_merge_session_into_cache` call rather than
full POST /simulate end-to-end, which requires posterior + params stubbing already done in Plan 01).

## Known Stubs

| File | Test | Wired by |
|------|------|----------|
| test_simulate.py | test_simulate_wall_time | Plan 05 (integration benchmark) |
| test_simulate.py | test_simulate_cache_hit | Plan 05 (integration) |

## Threat Surface Scan

No new security-relevant surface beyond the plan's threat model:
- T-4-SESSION-ESCAPE: fully mitigated in `_merge_session_into_cache` (regex + is_relative_to)
- T-4-LIFESPAN-CRASH: fully mitigated (prime_posterior in try/except, daemon uses daemon=True)
- T-4-MERGE-COLLISION: accepted per threat register (session IS authoritative cache for TTL duration)
- T-4-PYMC: 0 pymc/numpyro/pytensor imports in packages/api/src/ (verified by grep)

## Self-Check: PASSED

Files modified exist:
- packages/api/src/f1_api/app.py — FOUND
- packages/api/src/f1_api/services/simulate.py — FOUND
- packages/api/tests/test_sessions.py — FOUND

Commits exist:
- 1a7b81d — FOUND (Task 1 feat)
- 3873720 — FOUND (Task 2 RED)
- e3913de — FOUND (Task 2 GREEN)

---
*Phase: 04-simulation-api-uncertainty-quantification*
*Completed: 2026-04-24*
