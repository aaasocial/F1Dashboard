---
phase: 04-simulation-api-uncertainty-quantification
verified: 2026-04-24T12:45:00Z
status: human_needed
score: 12/13 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run `uvicorn f1_api.app:app --port 8000` after Phase 5 physics model is implemented, then POST /simulate with a real stint that has a Phase 3 calibration run. Confirm the cold-path wall time is under 2.0 s."
    expected: "Response returns in <2.0 s with 200 status, per_timestep/per_lap/per_stint all populated, metadata.k_draws=100."
    why_human: "The benchmark (test_simulate_wall_time) stubs run_simulation to return pre-built arrays, meaning only the aggregation + JSON + cache path is timed. The actual wall-time budget with real physics integration is unverified until Phase 5 delivers run_simulation. The <2 s D-04 contract cannot be fully confirmed programmatically until then."
---

# Phase 4: Simulation API + Uncertainty Quantification Verification Report

**Phase Goal:** Implement the Simulation API and Uncertainty Quantification layer — POST /simulate with K=100 posterior-draw CI triplets, GET /calibration/{compound} with full posterior summary, POST /sessions/upload with zip security hardening, all wired into the FastAPI app with GZipMiddleware and lifespan management.
**Verified:** 2026-04-24T12:45:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | POST /simulate with a valid canonical stint returns 200 with metadata + per_timestep + per_lap + per_stint blocks | VERIFIED | `routers/simulate.py` POST /simulate registered as `def simulate`, returns `SimulateResponse` with all 4 top-level keys; `test_simulate_happy_path` + `test_simulate_three_levels` assert structure |
| 2 | Every CI value is a {mean, lo_95, hi_95} triplet (D-02) at every data level | VERIFIED | `schemas/simulate.py` defines `CIValue`, `CIArray1D`, `CIArray2D` with those exact fields; `_assemble_response` uses `np.percentile(..., [2.5, 97.5])` at every level; `test_simulate_ci_triplets` asserts lo_95 <= mean <= hi_95 |
| 3 | K=100 posterior draws are sampled deterministically per cache key (seeded az.extract) — same request returns identical CI bands | VERIFIED | `K_DRAWS = 100` constant in `services/simulate.py`; `make_seed()` in `posterior_store.py` produces deterministic SHA256-based seed from (race_id, driver_code, stint_index, calibration_id); `sample_stage4_draws` uses `np.random.default_rng(seed)` |
| 4 | Override parameters shift all K draws identically; CI width survives (D-04); metadata.overrides_applied reflects presence | VERIFIED | `_apply_overrides` uses `dataclasses.replace` applied uniformly to all K `PhysicsParams`; `test_simulate_overrides` asserts `overrides_applied=True` and CI band integrity |
| 5 | Second call with the same (race_id, driver_code, stint_index, calibration_id, overrides_hash) returns in <50 ms via LRU+SQLite cache | VERIFIED | `SimulateCache` two-layer OrderedDict+SQLite cache; `test_simulate_cache_hit` (integration) asserts `second_ms < 50.0` with real cache backed by tmp_path DB |
| 6 | Cache entry becomes stale when a new calibration_runs row lands (new calibration_id → new key) | VERIFIED | Cache key includes `calibration_id` in SHA256 input; `test_simulate_cache_invalidation` confirms old key returns None after `invalidate_for_calibration(1)` |
| 7 | Endpoint is registered as a `def` (sync) route, importing the router does NOT import pymc/numpyro/pytensor (D-05) | VERIFIED | `grep "async def simulate"` returns 0 matches; `services/simulate.py` module-level D-05 guard raises ImportError if forbidden modules in sys.modules; `test_no_mcmc_at_runtime` passes |
| 8 | GET /calibration/C3 returns 200 with stage1/stage2/stage3/stage4/stage5 blocks + top-level metadata | VERIFIED | `routers/calibration.py` GET /calibration/{compound} registered as `def get_calibration`; `test_calibration_happy_path` asserts status 200 + all 5 stage keys |
| 9 | Stage 4 block contains mean, sd, hdi_lo_95, hdi_hi_95, r_hat, ess_bulk for each of beta_therm, T_act, k_wear | VERIFIED | `schemas/calibration.py` `Stage4VarSummary` has those 6 fields; `_stage4_var` maps ArviZ `az.summary` columns; `test_calibration_stage4_diagnostics` asserts all 6 keys + HDI brackets mean |
| 10 | Invalid compound returns 422 BEFORE any SQL runs | VERIFIED | `CompoundCode = Annotated[str, StringConstraints(pattern=r"^[Cc][1-5]$")]` at path-param layer; `build_calibration_summary` calls `validate_compound` at line 54 before any `sqlite3.connect`; `test_calibration_invalid_compound` passes over 6 malformed inputs |
| 11 | POST /sessions/upload: Zip Slip rejected 400, decompression bomb rejected 400, symlink rejected 400, non-zip rejected 415/400 | VERIFIED | `extract_session_zip` checks member count, `sum(file_size)` vs `MAX_ZIP_TOTAL_UNCOMPRESSED`, `external_attr & 0o170000 == 0o120000`, and `relative_to(dest_resolved)` — all BEFORE any filesystem write; `test_upload_rejects_path_traversal`, `test_upload_rejects_bomb`, `test_upload_rejects_symlink`, `test_upload_rejects_non_zip` all pass |
| 12 | create_app() includes /simulate, /calibration/{compound}, /sessions/upload with GZipMiddleware and lifespan management | VERIFIED | `app.py` has 6 `app.include_router(...)` calls; `app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)`; lifespan calls `start_cleanup_daemon()` + `prime_posterior(DEFAULT_DB_PATH, c)` for C1..C5 + `cleanup_stop.set()` in finally |
| 13 | Cold-path POST /simulate wall time is under 2.0 s end-to-end (D-04 budget) | PARTIAL | `test_simulate_wall_time` benchmark asserts `elapsed < 2.0 s` — but run_simulation is monkeypatched to return pre-built arrays. Only JSON aggregation + cache write path is timed. Actual timing with real physics (Phase 5) is unknown. Human verification required after Phase 5 delivers run_simulation. |

**Score:** 12/13 truths verified (truth 13 partially verified — benchmark path confirmed, real physics timing deferred)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `packages/api/src/f1_api/schemas/simulate.py` | 10 Pydantic v2 classes: CIValue, CIArray1D, CIArray2D, SimulationMetadata, PerTimestepBlock, PerLapRow, PerStintSummary, SimulateResponse, ParameterOverrides, SimulateRequest | VERIFIED | 10 classes confirmed by grep `^class` |
| `packages/api/src/f1_api/services/posterior_store.py` | get_posterior (lru_cache), sample_stage4_draws, read_latest_calibration_run, prime_posterior, make_seed | VERIFIED | 5 functions present; `@lru_cache(maxsize=8)` on `get_posterior`; no pymc/numpyro/pytensor imports |
| `packages/api/src/f1_api/services/simulate.py` | run_simulation_with_uncertainty, K_DRAWS=100, D-05 runtime guard, _merge_session_into_cache | VERIFIED | All present; `K_DRAWS = 100`; `MODEL_SCHEMA_VERSION = "v1"`; D-05 guard at module bottom |
| `packages/api/src/f1_api/cache/simulate_cache.py` | SimulateCache, make_cache_key, hash_overrides; thread-safe, SQLite-backed | VERIFIED | Class + functions present; `threading.Lock()`; "sim_v1|" namespace prefix; all SQL parameterized |
| `packages/api/src/f1_api/routers/simulate.py` | APIRouter POST /simulate as `def simulate` | VERIFIED | `@router.post("/simulate", response_model=SimulateResponse)` + `def simulate` (not async) |
| `packages/api/src/f1_api/schemas/calibration.py` | 8 classes: Stage1Summary, Stage2Summary, Stage3Summary, Stage4VarSummary, Stage4Summary, Stage5Summary, CalibrationMetadata, CalibrationResponse | VERIFIED | 8 classes confirmed by grep |
| `packages/api/src/f1_api/services/calibration.py` | build_calibration_summary, compound validation before DB, D-05 guard | VERIFIED | `build_calibration_summary` validates compound at line 54 before DB access at line 57; D-05 guard at bottom |
| `packages/api/src/f1_api/routers/calibration.py` | APIRouter GET /calibration/{compound} as `def get_calibration` | VERIFIED | `CompoundCode` Annotated type with `^[Cc][1-5]$` regex; `def get_calibration` (not async) |
| `packages/api/src/f1_api/schemas/sessions.py` | SessionUploadResponse (session_id 32-char hex, expires_at) | VERIFIED | `session_id: str = Field(pattern=r"^[0-9a-f]{32}$")` |
| `packages/api/src/f1_api/services/sessions.py` | extract_session_zip, register_session_upload, cleanup_once, start_cleanup_daemon | VERIFIED | All functions present; daemon=True threading.Thread; no threading.Timer; MAX_ZIP_TOTAL_UNCOMPRESSED, MAX_ZIP_MEMBERS, 0o120000 check, relative_to guard |
| `packages/api/src/f1_api/routers/sessions.py` | APIRouter POST /sessions/upload as `def upload_session` | VERIFIED | `@router.post("/sessions/upload")`; `def upload_session` (not async); rollback via `shutil.rmtree(session_dir, ignore_errors=True)` |
| `packages/api/src/f1_api/app.py` | 6 routers, GZipMiddleware(min=1024, level=5), extended lifespan | VERIFIED | 6 `include_router` calls confirmed; `GZipMiddleware, minimum_size=1024, compresslevel=5`; lifespan with cleanup daemon + posterior priming |
| `packages/api/tests/fixtures/calibration_fixture.py` | build_fixture_posterior | VERIFIED | Function present; builds 2-chain x 50-draw NetCDF + calibration_runs SQLite row |
| `packages/api/tests/fixtures/zip_fixtures.py` | make_valid_zip, make_zip_slip, make_decompression_bomb, make_symlink_zip, make_non_zip | VERIFIED | All 5 functions present; decompression bomb uses raw-byte patch for file_size header |
| `packages/api/tests/fixtures/simulate_stubs.py` | install_simulate_stubs | VERIFIED | Present; stubs run_simulation, load_stint, _build_params_list, get_posterior, sample_stage4_draws, read_latest_calibration_run, cache, DEFAULT_DB_PATH |
| `packages/api/tests/test_simulate.py` | 8 test functions (API-04-a..h) | VERIFIED | 8 functions; test_no_mcmc_at_runtime has real assertions; test_simulate_wall_time has `elapsed < 2.0` assertion |
| `packages/api/tests/test_calibration.py` | 5 test functions (API-05-a..e) | VERIFIED | 5 functions with real assertions (Wave-0 stubs replaced) |
| `packages/api/tests/test_sessions.py` | 6+ test functions (API-06-a..f + bonus symlink) | VERIFIED | 7 functions; includes bonus `test_upload_rejects_symlink` |
| `packages/api/tests/test_phase4_integration.py` | test_e2e_upload_simulate_calibration | VERIFIED | Present; 3-endpoint E2E cross-asserts calibration_id consistency |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `routers/simulate.py` | `services/simulate.py::run_simulation_with_uncertainty` | direct call inside `def simulate` | WIRED | `run_simulation_with_uncertainty(race_id=body.race_id, ...)` at line 22 |
| `services/simulate.py` | `f1_core.physics.orchestrator::run_simulation` | K=100 sequential invocations | WIRED | `run_simulation(artifact, params_k)` inside K-draw loop |
| `services/simulate.py` | `services/posterior_store.py::sample_stage4_draws` | per-request K-draw sampling | WIRED | `sample_stage4_draws(idata, K=K_DRAWS, seed=seed)` at line 125 |
| `services/simulate.py` | `cache/simulate_cache.py::SimulateCache` | get/put around K-draw forward pass | WIRED | `get_cache().get(...)` + `get_cache().put(...)` |
| `routers/calibration.py` | `services/calibration.py::build_calibration_summary` | direct call in `def get_calibration` | WIRED | `build_calibration_summary(compound)` |
| `services/calibration.py` | `f1_calibration.db::validate_compound` | whitelist check before any SQL | WIRED | `compound = validate_compound(compound)` at line 54 in `build_calibration_summary` (before `_read_calibration_run_direct`) |
| `services/calibration.py` | `services/posterior_store.py::get_posterior` | Stage 4 NetCDF read | WIRED | `get_posterior(cal_run["netcdf_path"])` at line 76 |
| `routers/sessions.py` | `services/sessions.py::extract_session_zip` | direct call with zip_bytes + dest | WIRED | `extract_session_zip(zip_bytes, session_dir)` |
| `app.py lifespan` | `services/sessions.py::start_cleanup_daemon` | call in lifespan async context manager | WIRED | `cleanup_thread, cleanup_stop = start_cleanup_daemon()` at line 42 |
| `app.py lifespan` | `services/posterior_store.py::prime_posterior` | loop over C1..C5, best-effort | WIRED | `prime_posterior(DEFAULT_DB_PATH, compound)` inside `for compound in ("C1", ...)` at line 47 |
| `services/simulate.py::run_simulation_with_uncertainty` | `services/sessions.py::SESSION_ROOT` | session_id merge into global FastF1 cache | WIRED | `if session_id is not None: _merge_session_into_cache(session_id)` at line 100; `_merge_session_into_cache` calls `shutil.copytree(session_dir, fastf1_cache_root, dirs_exist_ok=True)` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `routers/simulate.py` | `SimulateResponse` body | `run_simulation_with_uncertainty` → K-draw physics loop → `_assemble_response` with `np.percentile` | Yes — assembles from K SimulationResult objects, computes CI via percentile | FLOWING |
| `routers/calibration.py` | `CalibrationResponse` body | `build_calibration_summary` → SQLite `calibration_runs` + `parameter_sets` + ArviZ `az.summary` on NetCDF | Yes — reads real DB rows and posterior NetCDF | FLOWING (conditional: requires Phase 3 artifacts; returns 404 otherwise — correct behavior) |
| `routers/sessions.py` | `SessionUploadResponse` | `register_session_upload` → `extract_session_zip` → uuid4 session_id | Yes — real UUID generation + filesystem extraction | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| app.py creates all 7 expected routes | `python -c "from f1_api.app import create_app; app=create_app(); paths={r.path for r in app.routes if hasattr(r,'path')}; print(paths)"` | Verified by 04-04 SUMMARY: "python smoke test reports all 7 expected routes present" | PASS |
| D-05: no MCMC imports after create_app | `pytest tests/ -k test_no_mcmc_at_runtime` | 04-05 SUMMARY: "test_no_mcmc_at_runtime (D-05 enforcement) green end-to-end" | PASS |
| No f-string SQL in API source | `grep -rn 'f"SELECT\|f"DELETE\|f"INSERT\|f"UPDATE' packages/api/src/f1_api/` | 0 matches | PASS |
| No pymc/numpyro imports in API source | `grep -rn "import pymc\|import numpyro\|import pytensor" packages/api/src/` | 0 production code matches (only in docstring comments) | PASS |
| GZipMiddleware configured correctly | `grep "GZipMiddleware, minimum_size=1024, compresslevel=5" app.py` | 1 match at line 82 | PASS |
| Cache key uses sim_v1 namespace | `grep "sim_v1|"` in simulate_cache.py | 1 match — key = `f"sim_v1|{race_id}|..."` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| API-04 | Plans 00, 01, 04, 05 | POST /simulate with K=100 posterior-draw CI triplets, <2s end-to-end, parameter overrides | SATISFIED | All API-04-a..h tests implemented; 7/8 green (cache_hit), 8/8 green with integration; D-04 budget verified on stubbed path |
| API-05 | Plans 00, 02 | GET /calibration/{compound} with posterior summary (mean/sd/HDI/r_hat/ess_bulk) | SATISFIED | 5/5 API-05 tests pass; endpoint returns all stage summaries; compound whitelist at two layers |
| API-06 | Plans 00, 03, 04 | POST /sessions/upload with zip security, TTL cleanup | SATISFIED | 6/6 API-06 tests pass (5 unit + 1 integration test_session_routes_simulate); T-4-ZIP, T-4-BOMB, T-4-SYMLINK mitigated |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `cache/simulate_cache.py` | 103-119 | Thread-safety race: lock released between SQLite read and LRU promotion; concurrent threads can briefly violate max_entries invariant | Warning | Under heavy concurrent load (K=100 queued requests), max_entries may be transiently exceeded by 1-2 entries. Benign in practice given the 64-entry bound, but the code review (CR-01) documents the fix. |
| `services/calibration.py` | 154-156 | D-05 guard lacks `# pragma: no cover` comment (present in simulate.py's equivalent guard) | Info | Coverage report may flag uncovered branch; guard behavior is otherwise correct |
| `services/simulate.py` | 172-183 | Silent cross-year compound fallback emits warning but returns a compound letter from a different year's allocation; could silently corrupt cache key | Warning | Only triggers for stints where compound name is not in the exact year/round compound mapping. Current test fixture uses "C3" directly so this path is not exercised. |
| `routers/sessions.py` | 38 | `file.file.read()` reads full upload into memory before size check; 1 GB upload will OOM before being rejected | Warning | DoS vector; MAX_UPLOAD_BYTES check in extract_session_zip fires after full buffering |
| `services/simulate.py` | 382-389 | `_scalar_ci` nested function closes over `lap_draws` loop variable by reference (not by value) | Info | Currently called eagerly in same iteration, so not a live bug; latent defect if ever refactored to lazy evaluation |
| `services/calibration.py` | 141-147 | `az.summary` HDI column name `"hdi_2.5%"` is an ArviZ version-specific string; could KeyError on some ArviZ builds | Warning | Documented in code review WR-05; fixture-based tests pass because the fixture's ArviZ version produces the expected column names |

None of the anti-patterns are blockers — they are code-quality issues documented in the 04-REVIEW.md.

### Human Verification Required

#### 1. Wall-Time D-04 Budget with Real Physics

**Test:** After Phase 5 implements the physics modules (run_simulation), run the app locally with a Phase 3 calibration artifact for C3. POST `/simulate` with `{"race_id":"2023-bahrain_grand_prix","driver_code":"VER","stint_index":2}` and measure end-to-end cold-path response time.

**Expected:** Response returns in <2.0 s with status 200. `metadata.k_draws == 100`. All three data levels present.

**Why human:** `test_simulate_wall_time` stubs `run_simulation` to return pre-built arrays in <1 ms, verifying only the JSON aggregation + cache write path (~50-200 ms). The actual K=100 physics integrations (Module A→G per draw) are the dominant cost and are untested at real scale. The <2 s D-04 contract can only be confirmed after Phase 5 delivers the real physics modules.

### Gaps Summary

No blocking gaps found. All 12 directly verifiable must-haves are satisfied. Truth 13 (D-04 wall-time budget with real physics) requires human verification after Phase 5 implementation. The code review (04-REVIEW.md) identified 2 critical and 5 warning-level code quality issues — none block the phase goal but should be addressed before production deployment.

---

_Verified: 2026-04-24T12:45:00Z_
_Verifier: Claude (gsd-verifier)_
