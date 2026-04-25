---
phase: 04-simulation-api-uncertainty-quantification
plan: "03"
subsystem: api
tags: [sessions, upload, zip-security, ttl, fastapi, pydantic, multipart]

requires:
  - phase: 04
    plan: "00"
    provides: Wave-0 test stubs for API-06 (test_sessions.py) + zip_fixtures.py security builders

provides:
  - POST /sessions/upload endpoint (API-06) with full Zip Slip / bomb / symlink / size security
  - SessionUploadResponse Pydantic v2 schema (session_id 32-char hex, expires_at ISO-8601 UTC)
  - extract_session_zip: per-member path containment + decompression bomb cap + symlink rejection
  - register_session_upload: uuid4().hex + SESSION_ROOT/{id} mkdir
  - cleanup_once(now_seconds): pure-function TTL cleanup returning removed count
  - start_cleanup_daemon: daemon=True threading.Thread, 300s interval (NOT threading.Timer)
  - compute_expires_at: ISO-8601 UTC expiry helper
  - 6/6 API-06 tests green (5 non-integration + 1 deferred skip for Plan 05)

affects:
  - 04-04-PLAN (app wiring / lifespan — sessions router already included in create_app)
  - 04-05-PLAN (test_session_routes_simulate deferred here, wired there)

tech-stack:
  added:
    - python-multipart>=0.0.9 (f1-api runtime dep — required by FastAPI UploadFile/File form parsing)
  patterns:
    - Zip security: check-before-extract — validate member count, uncompressed size sum, symlink bits,
      path traversal ALL from ZipInfo metadata before touching the filesystem
    - Pure-function cleanup: cleanup_once(now_seconds) takes explicit time arg — testable without
      monkeypatching time.time
    - Rollback pattern: register dir first, extract, shutil.rmtree on ValueError before re-raise
    - Monkeypatch SESSION_ROOT in tests: each test patches the module-level SESSION_ROOT attr so
      extraction writes to tmp_path, not WORKSPACE_ROOT

key-files:
  created:
    - packages/api/src/f1_api/schemas/sessions.py
    - packages/api/src/f1_api/services/sessions.py
    - packages/api/src/f1_api/routers/sessions.py
  modified:
    - packages/api/src/f1_api/app.py (added sessions_router import + include_router)
    - packages/api/tests/test_sessions.py (replaced all Wave-0 skips with real assertions)
    - packages/api/pyproject.toml (added python-multipart>=0.0.9)
    - Desktop/CC/F1 Dashboard/uv.lock (updated for python-multipart 0.0.26)

key-decisions:
  - "python-multipart added as runtime dep (not just test extra): FastAPI raises RuntimeError at
    app creation time if UploadFile endpoint is registered without it — it is required at import time"
  - "sessions router wired into create_app() in this plan (not Plan 04) because the router is
    self-contained and the test suite needs it active immediately"
  - "cleanup_once takes now_seconds as explicit float arg: pure function, no monkeypatching needed
    for TTL tests; daemon loop passes time.time() at call site"
  - "Session dir rollback via shutil.rmtree(session_dir, ignore_errors=True) before re-raise: ensures
    no partial extraction directory leaks on security rejection"

patterns-established:
  - "zip-check-before-extract: all security violations detected from ZipInfo metadata (before any
    filesystem write) — count cap, size sum, symlink bits, path traversal all in one pre-pass"
  - "test isolation via monkeypatch.setattr(sessions_svc, 'SESSION_ROOT', tmp_path / 'sessions'):
    each test gets a fresh isolated session dir, no WORKSPACE_ROOT pollution"

requirements-completed: [API-06]

duration: ~15min
completed: "2026-04-24"
---

# Phase 4 Plan 03: POST /sessions/upload with Full Zip Security Summary

**POST /sessions/upload (API-06): Zip Slip + decompression bomb + symlink + size-cap security, 1-hour TTL daemon, 6/6 API-06 tests green**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-24T01:00:00Z
- **Completed:** 2026-04-24T01:15:00Z
- **Tasks:** 2
- **Files created/modified:** 7

## Accomplishments

- Implemented `extract_session_zip` with all three HIGH-severity T-4 mitigations: T-4-ZIP (Zip Slip
  via `is_relative_to` guard), T-4-BOMB (ZipInfo uncompressed size sum cap 500 MB + member count cap
  10,000 before any extraction), T-4-SYMLINK (`external_attr >> 16 & 0o170000 == 0o120000` check)
- Built TTL session lifecycle: `register_session_upload()` → `extract_session_zip()` → rollback on
  failure via `shutil.rmtree`; `cleanup_once(now_seconds)` pure-function for testability;
  `start_cleanup_daemon()` uses `daemon=True` threading.Thread + threading.Event (not threading.Timer)
- 6/6 API-06 tests green: happy path (200 + UUID4 session_id + dir exists), path traversal (400 +
  "escape"), non-zip (415), TTL cleanup (cleanup_once removes old dir, returns 1), bomb (400 +
  "expands"), symlink (400 + "symlink"); `test_session_routes_simulate` deferred to Plan 05

## Security Budget

| Threat | Mitigation | Verified by |
|--------|-----------|-------------|
| T-4-ZIP (Zip Slip) | `(dest / member).resolve().relative_to(dest_resolved)` per-member check | `test_upload_rejects_path_traversal` |
| T-4-BOMB (decompression bomb) | `sum(info.file_size for info in infolist()) > 500 MB` — header-only, before extraction | `test_upload_rejects_bomb` |
| T-4-SYMLINK | `(info.external_attr >> 16) & 0o170000 == 0o120000` → reject | `test_upload_rejects_symlink` |
| T-4-NON-ZIP | Content-type guard (415) + `BadZipFile` catch (400) | `test_upload_rejects_non_zip` |
| T-4-UPLOAD-DOS | `MAX_UPLOAD_BYTES = 100 MB` compressed size cap in `extract_session_zip` | inline check |
| T-4-TTL-LEAK | `cleanup_once` daemon removes sessions older than 1 hour | `test_session_ttl_cleanup` |

## Configuration Constants

| Constant | Value |
|----------|-------|
| `MAX_ZIP_TOTAL_UNCOMPRESSED` | 500 MB (500 * 1024 * 1024) |
| `MAX_ZIP_MEMBERS` | 10,000 |
| `MAX_UPLOAD_BYTES` | 100 MB (100 * 1024 * 1024) |
| `SESSION_TTL_SECONDS` | 3600 (1 hour) |
| `CLEANUP_INTERVAL_SECONDS` | 300 (5 min) |
| `_CHUNK_BYTES` | 65536 (64 KB) |

## Task Commits

1. **Task 1: Session schemas + secure zip extractor + cleanup daemon** — `d6ac92e` (feat)
2. **Task 2: FastAPI router + test-body fills for API-06** — `832e378` (feat)

## Files Created/Modified

- `packages/api/src/f1_api/schemas/sessions.py` — `SessionUploadResponse` (session_id, expires_at)
- `packages/api/src/f1_api/services/sessions.py` — full session service: extract, register, cleanup, daemon
- `packages/api/src/f1_api/routers/sessions.py` — `POST /sessions/upload` router (def, not async)
- `packages/api/src/f1_api/app.py` — wired sessions_router into `create_app()`
- `packages/api/tests/test_sessions.py` — 6 real assertions replacing Wave-0 skips
- `packages/api/pyproject.toml` — added python-multipart>=0.0.9 runtime dep
- `Desktop/CC/F1 Dashboard/uv.lock` — updated lockfile

## Decisions Made

- `python-multipart` added as a runtime dependency (not test-only): FastAPI raises a `RuntimeError` at
  app creation time when registering a `File(...)` endpoint without it. It is effectively required at
  import time, not just at request time.
- Sessions router included in `create_app()` in Plan 03 (not deferred to Plan 04): the router is
  fully self-contained and test isolation via monkeypatching SESSION_ROOT is sufficient.
- `cleanup_once(now_seconds: float)` takes the timestamp as an explicit argument so tests can call it
  with a controlled value without monkeypatching `time.time`. The daemon loop supplies `time.time()`
  at each call.
- `start_cleanup_daemon` uses `threading.Thread(daemon=True)` + `threading.Event.wait(interval)`, not
  `threading.Timer`. The Event permits a clean shutdown signal; timer-based approaches accumulate
  drift and don't allow early cancellation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added python-multipart runtime dependency**
- **Found during:** Task 2 (router integration + test run)
- **Issue:** FastAPI raises `RuntimeError: Form data requires "python-multipart" to be installed` at
  app startup when any `UploadFile`/`File(...)` route is registered — even before the first request.
  The package was not in `pyproject.toml`.
- **Fix:** Added `python-multipart>=0.0.9` to `[project.dependencies]` in
  `packages/api/pyproject.toml`; ran `uv sync --all-extras --all-packages` to install 0.0.26.
- **Files modified:** `packages/api/pyproject.toml`, `uv.lock`
- **Verification:** Tests pass after install (6/6 green).
- **Committed in:** `832e378` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 — blocking missing dependency)
**Impact on plan:** Fix essential to register the UploadFile endpoint. No scope creep.

## Test Results

```
packages/api/tests/test_sessions.py::test_upload_happy_path           PASSED
packages/api/tests/test_sessions.py::test_upload_rejects_path_traversal PASSED
packages/api/tests/test_sessions.py::test_upload_rejects_non_zip      PASSED
packages/api/tests/test_sessions.py::test_session_ttl_cleanup         PASSED
packages/api/tests/test_sessions.py::test_upload_rejects_bomb         PASSED
packages/api/tests/test_sessions.py::test_upload_rejects_symlink      PASSED
6 passed, 1 deselected (test_session_routes_simulate @integration — deferred Plan 05)
```

## Issues Encountered

None beyond the python-multipart blocking issue documented as deviation above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `POST /sessions/upload` fully wired into `create_app()` — Plan 04 can proceed with lifespan wiring
- `cleanup_once` and `start_cleanup_daemon` ready to be called from lifespan context manager in Plan 04
- `test_session_routes_simulate` deferred to Plan 05 — requires `/simulate` to accept `session_id` in
  request body and route data loading through the uploaded session cache (Pitfall 7 in RESEARCH.md)
- All three HIGH-severity T-4 threats fully mitigated and independently tested

## Known Stubs

| File | Test | Wired by |
|------|------|----------|
| test_sessions.py | test_session_routes_simulate | Plan 05 (needs /simulate + session_id routing) |

This stub is intentional design — Plan 03 scope explicitly excludes session_id wiring into /simulate.

## Threat Flags

No new security-relevant surface beyond what the plan's threat model covers. All T-4-* threats are
mitigated by extract_session_zip checks that fire before any filesystem write.

---
*Phase: 04-simulation-api-uncertainty-quantification*
*Completed: 2026-04-24*
