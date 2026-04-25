---
phase: 04-simulation-api-uncertainty-quantification
plan: "00"
subsystem: testing
tags: [pytest, arviz, netcdf4, fixtures, wave-0, test-scaffold, nyquist]

requires:
  - phase: 03-bayesian-calibration-pipeline
    provides: calibration_runs SQLite schema and write_calibration_run/write_parameter_set writers used by calibration_fixture

provides:
  - 19 discoverable test stubs (API-04-a..h, API-05-a..e, API-06-a..f) — red until Plans 01-03
  - fixtures/calibration_fixture.py: build_fixture_posterior() creates 2-chain x 50-draw Stage-4 NetCDF + SQLite row
  - fixtures/zip_fixtures.py: make_valid_zip/make_zip_slip/make_decompression_bomb/make_symlink_zip/make_non_zip
  - conftest.py extended with fixture_calibration, fake_stint_artifact, monkeypatched_run_simulation, malicious_zip
  - D-05 baseline enforcement: test_no_mcmc_at_runtime is green and will catch any MCMC import regression
  - arviz + netcdf4 in f1-api runtime deps (required by /simulate and /calibration services)

affects:
  - 04-01-PLAN (consumes test stubs test_simulate.py, fixture_calibration, monkeypatched_run_simulation)
  - 04-02-PLAN (consumes test stubs test_calibration.py, fixture_calibration)
  - 04-03-PLAN (consumes test stubs test_sessions.py, malicious_zip fixture, zip_fixtures)

tech-stack:
  added:
    - arviz>=0.20,<1 (f1-api runtime dep — posterior loading by /simulate and /calibration)
    - netcdf4>=1.7 (f1-api runtime dep — NetCDF file I/O for posterior)
    - pytest-benchmark>=4 (f1-api test extra)
  patterns:
    - skip-on-ImportError: test stubs guard on router import before asserting, enabling wave-gated red→green progression
    - session-scoped calibration fixture: expensive posterior build runs once per test session
    - in-memory zip builders: all security zip fixtures produce bytes without filesystem I/O
    - raw-bytes patching: decompression bomb patches the ZIP central-directory header directly to set fraudulent file_size

key-files:
  created:
    - packages/api/tests/fixtures/__init__.py
    - packages/api/tests/fixtures/calibration_fixture.py
    - packages/api/tests/fixtures/zip_fixtures.py
    - packages/api/tests/test_simulate.py
    - packages/api/tests/test_calibration.py
    - packages/api/tests/test_sessions.py
  modified:
    - packages/api/pyproject.toml (added arviz, netcdf4, pytest-benchmark deps)
    - packages/api/tests/conftest.py (extended with 4 Phase-4 fixtures)

key-decisions:
  - "arviz and netcdf4 added as f1-api runtime deps (not just test extras) because /simulate and /calibration services read posteriors at request time"
  - "Decompression bomb size is injected by raw-byte patching the ZIP central directory (writestr overwrites file_size so ZipInfo.file_size=N cannot be set before write)"
  - "NetCDF written under WORKSPACE_ROOT/.data/posteriors/ (not tmp_path) to satisfy db._validate_stored_path workspace-root containment check"
  - "test_no_mcmc_at_runtime has real assertions (not a skip stub) — green from day 0, enforces D-05 permanently"

patterns-established:
  - "skip-on-ImportError pattern: try: import router; except ImportError: pytest.skip() — enables wave-gated red→green"
  - "calibration fixture uses uuid4 filename to avoid collision with real calibration NetCDF files"
  - "zip security fixtures are pure bytes factories (no filesystem I/O) — clean, fast, composable"

requirements-completed: [API-04, API-05, API-06]

duration: 18min
completed: "2026-04-24"
---

# Phase 4 Plan 00: Wave 0 Test Scaffold Summary

**19 pytest stubs (API-04/05/06) + calibration and zip fixture helpers + D-05 baseline test wired and green**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-04-24T00:15:00Z
- **Completed:** 2026-04-24T00:33:40Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Added `arviz>=0.20,<1` and `netcdf4>=1.7` to f1-api runtime dependencies (required by /simulate and /calibration services that load posterior NetCDFs at request time; no pymc/numpyro — D-05 compliant)
- Created `packages/api/tests/fixtures/` with `calibration_fixture.py` (deterministic 2-chain x 50-draw Stage-4 posterior + SQLite calibration_runs row) and `zip_fixtures.py` (5 in-memory zip builders including a decompression bomb with patched central-directory header)
- Created 19 test stubs matching exact VALIDATION.md function names; `test_no_mcmc_at_runtime` passes today and will catch any future MCMC import regression (D-05 enforcement)

## Task Commits

1. **Task 1: Add arviz + netcdf4 + pytest-benchmark to f1-api dependencies** — `c9760e8` (chore)
2. **Task 2: Build calibration_fixture + zip_fixtures + extended conftest** — `247f01f` (feat)
3. **Task 3: Write red-test stubs for API-04, API-05, API-06** — `ed1fc1c` (test)

## Files Created/Modified

- `packages/api/pyproject.toml` — added arviz/netcdf4 runtime deps + test optional-dependencies group
- `packages/api/tests/fixtures/__init__.py` — empty package marker
- `packages/api/tests/fixtures/calibration_fixture.py` — `build_fixture_posterior(tmp_path, compound, chains, draws, seed)` → `(netcdf_path, calibration_id, db_path)`
- `packages/api/tests/fixtures/zip_fixtures.py` — five in-memory zip builders for security and happy-path tests
- `packages/api/tests/conftest.py` — extended with `fixture_calibration` (session-scoped), `fake_stint_artifact`, `monkeypatched_run_simulation`, `malicious_zip` (parametrised)
- `packages/api/tests/test_simulate.py` — 8 stubs (API-04-a..h); `test_no_mcmc_at_runtime` has real assertions
- `packages/api/tests/test_calibration.py` — 5 stubs (API-05-a..e)
- `packages/api/tests/test_sessions.py` — 6 stubs (API-06-a..f); `test_upload_rejects_non_zip` has partial real assertion

## Decisions Made

- `arviz` and `netcdf4` placed in f1-api runtime deps (not just test extras) because the `/simulate` and `/calibration` services read `.nc` files at request time — they are not test-only tools.
- Decompression bomb size patched via raw byte manipulation of the ZIP central-directory header. `writestr()` overwrites `ZipInfo.file_size` with the actual data length after compression, so pre-setting it has no effect. The raw patch ensures `infolist()[0].file_size == 600_000_000` as read by the upload validator.
- NetCDF written under `WORKSPACE_ROOT/.data/posteriors/fixture_<uuid>.nc` (not `tmp_path`) because `f1_calibration.db._validate_stored_path` resolves relative paths against `WORKSPACE_ROOT` and rejects anything outside it. Session teardown cleans up both the NetCDF and stage5 CSV.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed decompression-bomb file_size declaration**
- **Found during:** Task 2 (zip_fixtures.py implementation)
- **Issue:** `zipfile.ZipFile.writestr()` overwrites `ZipInfo.file_size` with the actual data length after compression, so `info.file_size = 600_000_000` before `writestr()` has no effect. Verified: `infolist()[0].file_size` returned `1024` instead of `600_000_000`.
- **Fix:** Write the zip normally with a small payload, then use `struct.pack_into("<I", raw, idx+24, FAKE_SIZE)` to patch the uncompressed-size field in both the local file header and central directory record of the raw bytes.
- **Files modified:** `packages/api/tests/fixtures/zip_fixtures.py`
- **Verification:** `zipfile.ZipFile(io.BytesIO(make_decompression_bomb())).infolist()[0].file_size == 600_000_000`
- **Committed in:** `247f01f` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in zip fixture construction)
**Impact on plan:** Fix essential for the decompression-bomb security test to work. No scope creep.

## Issues Encountered

None beyond the zip bug documented above.

## User Setup Required

None — no external service configuration required. `uv sync --all-extras --all-packages` installs all test dependencies.

## Next Phase Readiness

- 19 test stubs ready for Plans 01, 02, 03 to turn green wave-by-wave
- `fixture_calibration` session fixture provides a reusable posterior without running real MCMC
- `malicious_zip` parametrised fixture ready for Plan 03 security tests
- D-05 baseline test guards against accidental MCMC imports from day 0
- Remaining: Plans 01-05 implement the actual /simulate, /calibration, /sessions routers

## Known Stubs

The following test bodies are intentional skip-stubs (not data stubs) — they will be wired with real assertions by Plans 01-03:

| File | Test | Wired by |
|------|------|----------|
| test_simulate.py | test_simulate_happy_path..test_simulate_cache_invalidation | Plan 01 |
| test_simulate.py | test_simulate_wall_time, test_simulate_cache_hit | Plan 01 (integration) |
| test_calibration.py | test_calibration_happy_path..test_calibration_stage4_diagnostics | Plan 02 |
| test_sessions.py | test_upload_happy_path..test_upload_rejects_bomb | Plan 03 |

These stubs are intentional Wave 0 scaffolding — they do not prevent this plan's goal (test infrastructure creation) from being achieved.

---
*Phase: 04-simulation-api-uncertainty-quantification*
*Completed: 2026-04-24*
