---
phase: 01-foundation-data-pipeline-module-contracts
plan: 05
subsystem: api/http-boundary
tags: [fastapi, pydantic-v2, cors, path-validation, testclient, phase-1-completion]
requires:
  - f1_core.contracts.QualityReport
  - f1_core.contracts.QualityVerdict
  - f1_core.ingestion.init_cache
  - f1_core.ingestion.load_schedule
  - f1_core.ingestion.load_stint
  - f1_core.ingestion.parse_race_id
  - f1_core.data_integrity.analyze
  - f1_core.stint_annotation.load_compound_mapping
provides:
  - f1_api.app (FastAPI create_app + module-level app)
  - f1_api.dependencies.RaceId (Annotated[str, StringConstraints])
  - f1_api.dependencies.DriverCode (Annotated[str, StringConstraints])
  - f1_api.schemas.races.RaceSummaryResponse (Pydantic v2)
  - f1_api.schemas.drivers.DriverSummaryResponse (Pydantic v2)
  - f1_api.schemas.stints.StintSummaryResponse (Pydantic v2)
  - f1_api.services.stints.list_races / list_drivers_for_race / list_stints_for_driver
  - f1_api.services.stints.RaceSummary / DriverSummary / StintSummary (plain dataclasses)
  - GET /races (API-01)
  - GET /races/{race_id}/drivers (API-02)
  - GET /stints/{race_id}/{driver_id} (API-03)
  - GET /healthz
affects:
  - Phase 4 (will add POST /simulate following the same def-in-threadpool pattern)
  - Phase 5 (frontend can develop against a real typed API contract)
  - Phase 7 (CORS origin comes from F1_ALLOWED_ORIGIN env var)
tech-stack:
  added:
    - fastapi 0.136.0 (HTTP framework)
    - pydantic 2.13.3 (response model validation)
    - starlette CORSMiddleware (explicit-origin CORS)
    - pytest-importlib mode (avoid duplicate tests.conftest plugin name)
  patterns:
    - Plain `def` handlers (pitfall P9) so blocking FastF1 calls run in threadpool
    - `@asynccontextmanager` lifespan for one-shot init_cache() (research A8)
    - `ConfigDict(from_attributes=True)` + `Model.model_validate(dataclass)` at API boundary (D-04)
    - `Annotated[str, StringConstraints(pattern=...)]` for path-param regex (T-01-10)
    - Explicit `allow_origins=` list (T-01-11, never wildcard)
    - `Cache-Control: public, max-age=31536000, immutable` for completed-race endpoints
    - Monkeypatched service layer in TestClient tests — zero network calls
key-files:
  created:
    - packages/api/src/f1_api/app.py
    - packages/api/src/f1_api/dependencies.py
    - packages/api/src/f1_api/schemas/__init__.py
    - packages/api/src/f1_api/schemas/races.py
    - packages/api/src/f1_api/schemas/drivers.py
    - packages/api/src/f1_api/schemas/stints.py
    - packages/api/src/f1_api/routers/__init__.py
    - packages/api/src/f1_api/routers/races.py
    - packages/api/src/f1_api/routers/drivers.py
    - packages/api/src/f1_api/routers/stints.py
    - packages/api/src/f1_api/services/__init__.py
    - packages/api/src/f1_api/services/stints.py
    - packages/api/tests/conftest.py
    - packages/api/tests/test_endpoints.py
  modified:
    - pyproject.toml (added --import-mode=importlib to pytest addopts)
  deleted:
    - packages/api/tests/__init__.py (avoid duplicate tests.conftest collision)
    - packages/core/tests/__init__.py (same reason)
decisions:
  - API surface closed out with only API-01/02/03 for Phase 1; POST /simulate deferred to Phase 4
  - Service layer sits between routers and f1_core so TestClient tests monkeypatch a single
    public function per endpoint instead of mocking FastF1 at import time
  - RaceId/DriverCode regex duplicated from f1_core.ingestion.config into f1_api.dependencies
    so the regex is visible in OpenAPI docs (T-01-10 single source of truth is the regex
    pattern string, not the module that owns it)
  - All endpoints are plain def (never async def) — FastAPI threadpool handles blocking
    FastF1 calls correctly; pitfall P9 enforced by grep-checked acceptance criterion
  - CORS origins from F1_ALLOWED_ORIGIN env var (production) plus localhost:5173 (Vite dev);
    allow_origins is never `["*"]`
  - Pickled 2022_schedule.pkl.gz fixture NOT created: we chose the simpler monkeypatch path
    (mock list_races directly) over committing a snapshot of the FastF1 schedule DataFrame
metrics:
  tasks_completed: 2
  duration_seconds: 580
  files_created: 14
  files_modified: 1
  files_deleted: 2
  lines_added: 701
  lines_removed: 98
  test_count_phase1: 84
  test_count_api: 23
  completed_date: 2026-04-23
---

# Phase 1 Plan 05: FastAPI Endpoints (API-01/02/03) Summary

Three read-only FastAPI endpoints (plus /healthz) wired over the Plan 02–04 core pipeline,
with regex-validated path params, explicit-origin CORS, one-shot FastF1 cache init via
lifespan, and 23 TestClient integration tests that hit zero external services.

## What Shipped

**FastAPI app** (`packages/api/src/f1_api/app.py`):
- `create_app()` factory + module-level `app = create_app()`
- `@asynccontextmanager lifespan` calls `init_cache()` once per process (research A8)
- `CORSMiddleware` with `allow_origins=_allowed_origins()` (no wildcards)
- Routers mounted: races, drivers, stints
- `/healthz` endpoint returning `{"status": "ok"}`
- `debug=False` (T-01-13)

**Endpoints (all plain `def`, never `async def`):**

| Route                                  | Method | Response                         | Req ID | Cache-Control                              |
|----------------------------------------|--------|----------------------------------|--------|---------------------------------------------|
| `/races`                               | GET    | `list[RaceSummaryResponse]`      | API-01 | `public, max-age=31536000, immutable`      |
| `/races/{race_id}/drivers`             | GET    | `list[DriverSummaryResponse]`    | API-02 | `public, max-age=31536000, immutable`      |
| `/stints/{race_id}/{driver_id}`        | GET    | `list[StintSummaryResponse]`     | API-03 | (none — depends on param_version in Ph 4)  |
| `/healthz`                             | GET    | `{"status": "ok"}`               | —      | (none)                                      |

**Response schemas (Pydantic v2, `ConfigDict(from_attributes=True)`):**
- `RaceSummaryResponse`: `year: int, round: int, name: str, country: str, date: date | None`
- `DriverSummaryResponse`: `driver_code: str, full_name: str, team: str, stint_count: int`
- `StintSummaryResponse`: `stint_index, compound, compound_letter, lap_count, start_lap, end_lap, pit_in_lap?, pit_out_lap?, tire_age_at_start, quality_score (0..1), quality_verdict ('ok'|'warn'|'exclude'|'refuse')`

**Path-param validation (T-01-10 mitigation):**
- `RaceId = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}-[a-z0-9_]+$", min_length=6, max_length=48)]`
- `DriverCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$", min_length=3, max_length=3)]`
- Pydantic rejects non-matching requests with HTTP 422 before the handler body runs.

**CORS configuration (T-01-11 mitigation):**
- Dev: `http://localhost:5173` always in allowed list.
- Prod: `F1_ALLOWED_ORIGIN` env var (single origin) appended if set.
- `allow_credentials=True`, `allow_methods=["GET", "POST"]`, `allow_headers=["*"]`.
- Evil origins (`https://evil.example.com`) are NOT echoed back in `Access-Control-Allow-Origin`.

## Monkeypatch Strategy (for Phase 4)

`packages/api/tests/conftest.py` exposes a `client` fixture that:
1. Creates three fake service responses (races, drivers, stints) as plain `RaceSummary`/`DriverSummary`/`StintSummary` dataclasses.
2. `monkeypatch.setattr` on each router module where the service function is imported (`f1_api.routers.races.list_races`, etc.) — patching at the import site, not the source, because FastAPI closes over the name at import time.
3. Wraps the resulting app in a `TestClient` context manager.

Phase 4 (`POST /simulate`) should follow the same pattern: split the simulation orchestrator into `f1_api.services.simulate.run_simulation(request) -> SimulationResponse`, and monkeypatch that single function in tests. This keeps tests network-free and fast.

## Test Suite

**Total Phase 1 tests:** 84 (61 core + 23 api)

API tests (`packages/api/tests/test_endpoints.py`, 23 tests):
- `test_healthz` — sanity
- `test_get_races` — shape + year >= 2022 + Cache-Control header
- `test_get_races_start_year_rejects_below_2022` — T-01-12 year bounds
- `test_get_drivers_for_bahrain_2023` — canonical VER/PER/HAM list
- `test_get_drivers_unknown_race_404` — ValueError → 404
- `test_get_stints_for_ver_bahrain_2023` — asserts stint 2 is MEDIUM/C2/23 laps/ok
- `test_path_traversal_rejected_on_drivers[6 params]` — T-01-10 regex
- `test_path_traversal_rejected_on_stints_race_id[4 params]` — T-01-10 regex
- `test_driver_code_regex_rejects_invalid[5 params]` — T-01-10 regex
- `test_cors_allows_localhost` — echo `http://localhost:5173`
- `test_cors_rejects_evil_origin` — do NOT echo `https://evil.example.com`

Run from repo root:
```
uv run pytest
```

## Phase 1 Roadmap Success-Criterion Coverage

| Criterion | Plan | Automated test |
|-----------|------|----------------|
| 1. `scripts/fetch.py` round-trips through two-layer cache | 03 | `test_ingestion.py::test_load_stint_*` |
| 2. `analyze()` downgrades verdict on corrupted fixture | 04 | `test_data_integrity.py::test_corrupted_*` |
| 3. Curvature + gear deterministic | 04 | `test_curvature.py`, `test_gear_inference.py` |
| 4. `annotate_stint()` emits compound→C1-C5 etc | 04 | `test_stint_annotation.py::test_annotate_*` |
| 5. Seven dataclass contracts + Protocol | 02 | `test_contracts.py::test_*` |
| 6. GET /races, /drivers, /stints respond correctly | 05 | `test_endpoints.py::test_get_*` |

All six have at least one passing automated test. Phase 1 is done.

## Deviations from Plan

### Rule 3 - Blocking: Fix pytest duplicate-plugin error

- **Found during:** Task 2 — first run of `uv run pytest` at repo root
- **Issue:** `ValueError: Plugin already registered under a different name` — both `packages/api/tests/conftest.py` and `packages/core/tests/conftest.py` loaded as `tests.conftest` because both directories contain `__init__.py` and pytest's default prepend import mode uses relative package paths. When run together, the second conftest registration crashed pluggy.
- **Fix:**
  1. Deleted `packages/api/tests/__init__.py` and `packages/core/tests/__init__.py` (the plan's files_modified list confirmed the api __init__.py was supposed to stay empty, but it is not needed for discovery).
  2. Added `--import-mode=importlib` to pyproject `addopts` so pytest uses file-path-unique module names instead of package-relative names.
- **Files modified:** `pyproject.toml`, removed two `__init__.py`.
- **Commit:** 7f03eb9.

### Rule 3 - Blocking: Repo-wide lint to pass plan verification

- **Found during:** Task 2 verify step (`uv run ruff check .`)
- **Issue:** Plan-02/03/04 tests and scripts had pre-existing ruff `I001`, `F401`, `RUF100`, `RUF007` violations, and 32 files were not formatted to `ruff format`. Plan 01-05 `<verify>` explicitly requires `uv run ruff check . && uv run ruff format --check .` to exit 0.
- **Fix:** Applied `uv run ruff check . --fix` and `uv run ruff format .` repo-wide. Hand-fixed one non-auto-fixable RUF007 in `test_gear_inference.py` (replaced `zip(xs, xs[1:])` with `itertools.pairwise(xs)`).
- **Scope note:** This was technically out-of-scope code cleanup of prior plans' output, but applying it here was the minimum viable path to satisfy the plan's own verification criteria. All changes are formatting + import-ordering + pairwise substitution — zero behavior change. Core + API tests continue to pass.
- **Files modified:** 19 files across `packages/core/src`, `packages/core/tests`, `scripts/`.
- **Commit:** 7f03eb9.

### Skipped: 2022_schedule.pkl.gz fixture

- The plan's frontmatter `files_modified` listed `packages/api/tests/fixtures/2022_schedule.pkl.gz`, and the pitfall section said "mock `fastf1.get_event_schedule` via `monkeypatch`, or commit a pickled 2022 schedule DataFrame."
- We chose the first option (monkeypatch `list_races` directly at the router import site). The pickled schedule is unnecessary — our monkeypatch never reaches `fastf1.get_event_schedule`, so the fixture would be unused bytes in the repo.
- **Impact:** None. The test still exercises `/races` with realistic response shapes (year 2022 included) and the regex path validation remains enforced.

## Authentication Gates

None — all endpoints are public read-only.

## Open Follow-ups (not blocking Phase 1)

- Pydantic 2.13 emits a harmless `UnsupportedFieldAttributeWarning` for `Annotated[str, StringConstraints]` path params ("The 'alias' attribute with value 'race_id' was provided..."). This is a known interplay between FastAPI's path-param aliasing and Pydantic 2.13's stricter `Field()` validation. The tests pass and path-param validation still fires (regex is honored). Revisit when upgrading to Pydantic 2.14+ or FastAPI 0.140+.
- The `list_drivers_for_race` service currently calls `fastf1.get_session` directly rather than going through the Layer-2 cache. For Phase 4, consider caching the driver roster per race_id inside Layer-2 to avoid repeated 30s+ session loads.

## Self-Check: PASSED

**Files created:**
- FOUND: Desktop/CC/F1 Dashboard/packages/api/src/f1_api/app.py
- FOUND: Desktop/CC/F1 Dashboard/packages/api/src/f1_api/dependencies.py
- FOUND: Desktop/CC/F1 Dashboard/packages/api/src/f1_api/schemas/races.py
- FOUND: Desktop/CC/F1 Dashboard/packages/api/src/f1_api/schemas/drivers.py
- FOUND: Desktop/CC/F1 Dashboard/packages/api/src/f1_api/schemas/stints.py
- FOUND: Desktop/CC/F1 Dashboard/packages/api/src/f1_api/routers/races.py
- FOUND: Desktop/CC/F1 Dashboard/packages/api/src/f1_api/routers/drivers.py
- FOUND: Desktop/CC/F1 Dashboard/packages/api/src/f1_api/routers/stints.py
- FOUND: Desktop/CC/F1 Dashboard/packages/api/src/f1_api/services/stints.py
- FOUND: Desktop/CC/F1 Dashboard/packages/api/tests/conftest.py
- FOUND: Desktop/CC/F1 Dashboard/packages/api/tests/test_endpoints.py

**Commits:**
- FOUND: 1ac92cd (feat(01-05): FastAPI app with API-01/02/03 routers, schemas, services)
- FOUND: 7f03eb9 (feat(01-05): TestClient integration tests for API-01/02/03 + repo-wide lint)
