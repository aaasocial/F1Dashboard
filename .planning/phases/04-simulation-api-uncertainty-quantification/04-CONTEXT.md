# Phase 4: Simulation API & Uncertainty Quantification - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 4 wires the Phase 3 Bayesian posteriors into a REST API. A client POSTs a race/driver/stint reference to `/simulate` and receives per-timestep (~4 Hz), per-lap, and per-stint predictions with 95% credible-interval bands derived from K=100 posterior draws sampled from the ArviZ NetCDF files produced in Phase 3. Two additional endpoints round out the surface: `GET /calibration/{compound}` for parameter summaries and `POST /sessions/upload` for offline FastF1 cache loading.

Phase 4 does NOT include: any frontend code, the Bayesian calibration pipeline (Phase 3), or deployment infrastructure (Phase 7). The `/simulate` endpoint is a pure forward pass against pre-fitted posteriors — PyMC is never imported or invoked at API runtime.

Deliverable: three new FastAPI endpoints added to the existing `packages/api/` package, with a simulation result cache that makes repeat calls return in <50 ms.

</domain>

<decisions>
## Implementation Decisions

### POST /simulate Response Shape
- **D-01:** Return all three data levels in a single JSON response: per-timestep (~4 Hz arrays), per-lap (summary rows), and per-stint (aggregate stats). No opt-in query param — Phase 5 needs all three levels to render track animation, lap charts, and stint summary simultaneously.

- **D-02:** CI structure is triplet-per-value: `{"mean": 95.2, "lo_95": 88.1, "hi_95": 102.4}`. Applied to every predicted metric at every level. Self-documenting, easy to destructure in TypeScript. Consistent across per-timestep, per-lap, and per-stint fields.

- **D-03:** Response metadata block in every `/simulate` response: `calibration_id` (INTEGER from `calibration_runs` table), `model_schema_version` (string constant bumped on breaking changes), `fastf1_version` (from `importlib.metadata.version("fastf1")`), plus `compound` and `stint_index` echoed back.

### POST /simulate — K=100 Posterior Draws
- **D-04:** K=100 posterior draws are sampled from the ArviZ NetCDF for the relevant compound. Override parameters (if provided in the request body) apply identically to ALL K draws — the override shifts all samples equally but variance from the non-overridden posterior dimensions survives. CI bands are always present in the response regardless of whether overrides are provided. Override presence is flagged in the response metadata (`overrides_applied: true/false`).

- **D-05:** The endpoint never imports or invokes PyMC, NumPyro, or ArviZ at request time for MCMC purposes. NetCDF reading (ArviZ `from_netcdf`) at startup or first call is acceptable; NUTS sampling is not.

### Result Caching
- **D-06:** Two-layer cache exactly as specified in CLAUDE.md §FastF1 Integration Layer 2: in-process LRU dict in front of a SQLite JSON blob keyed by `(race_id, driver_id, stint_idx, calibration_id)`. Cache hit returns in <50 ms. Cache is invalidated when `calibration_id` changes (new calibration run replaces the key). Cache miss triggers the K=100 forward-pass computation.

### POST /sessions/upload — Session Lifetime
- **D-07:** Uploaded sessions are ephemeral with a 1-hour TTL. Upload response returns a `session_id` (UUID). Subsequent `/simulate` calls include `session_id` as an optional request body field to route data loading through the uploaded cache instead of Jolpica. Sessions are stored under `/data/sessions/{session_id}/` and cleaned up after 1 hour (background cleanup task, not a scheduled cron).

- **D-08:** Upload accepts a zip file. Server extracts it under the session directory. Subsequent `/simulate` calls with that `session_id` will find the FastF1 session data locally and skip the Jolpica API call entirely. Session scope is server-side only — no per-user isolation (V1 has no auth).

### GET /calibration/{compound} — Response Scope
- **D-09:** Returns parameter summaries for all four calibration stages:
  - Stage 1 (aero): point estimate + scipy residual uncertainty for C_LA, C_DA, xi
  - Stage 2 (friction): point estimate + residual uncertainty for mu_0_fresh, p_bar_0, n
  - Stage 3 (thermal): point estimate + residual uncertainty for 8 ODE params (C_tread, C_carc, C_gas, R_tc, R_cg, h_0, h_1, alpha_p); T_opt and sigma_T noted as held-fixed at nominal
  - Stage 4 (degradation): full posterior summary for beta_therm, T_act, k_wear — mean, std, 5th/25th/75th/95th percentiles, r_hat, ess_bulk
  - Stage 5 validation metrics: held-out RMSE (s), baseline RMSE (s), beat-baseline flag
  - Also includes calibration_id, compound, year_range, created_at metadata from `calibration_runs` table

### Claude's Discretion
- Vectorization strategy for K=100 draws (numpy batch axis vs sequential loop in threadpool vs JAX vmap) — planner decides based on <2s timing budget
- Exact JSON schema field names (snake_case consistent with existing API convention)
- LRU cache size (max entries count) — planner decides reasonable default
- ZIP extraction security (path traversal mitigation) — planner implements standard python zipfile safe-extract pattern
- Background TTL cleanup implementation (threading.Timer vs background thread loop)
- HTTP status codes for error cases (422 for invalid compound, 404 for missing calibration, 503 if no posterior available)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 4 Requirements
- `.planning/REQUIREMENTS.md` §REST API — API-04, API-05, API-06. These are the acceptance tests for Phase 4.
- `.planning/ROADMAP.md` §Phase 4 — Five success criteria. Use as the acceptance checklist.

### Physics Specification
- `model_v1_complete.html` — Complete seven-module physics specification. SimulationResult fields map to this document's output variables.
- `model_calibration_strategy.html` — Part IV (Stage 4 posterior structure), Part VII (challenges). Understand what the NetCDF posterior contains before designing the draw sampling logic.

### Existing API Package (extend, don't rewrite)
- `packages/api/src/f1_api/app.py` — FastAPI app factory, lifespan, CORS, existing routers. New routers are added here.
- `packages/api/src/f1_api/routers/stints.py` — Pattern for new routers: `def` endpoint, HTTPException on ValueError.
- `packages/api/src/f1_api/schemas/stints.py` — Pydantic v2 schema pattern (`ConfigDict(from_attributes=True)`).
- `packages/api/src/f1_api/services/stints.py` — Service layer pattern (business logic separated from router).

### Forward Pass (the simulation engine)
- `packages/core/src/f1_core/physics/orchestrator.py` — `run_simulation(artifact, params) -> SimulationResult`. This is called K=100 times (or vectorized). Read SimulationResult fields carefully — these become the /simulate response fields.
- `packages/core/src/f1_core/physics/params.py` — PhysicsParams, AeroParams, FrictionParams, ThermalParams, DegradationParams. K draws become K PhysicsParams instances.
- `packages/core/src/f1_core/ingestion/fastf1_client.py` — `load_stint()` — how the API loads the StintArtifact that run_simulation() needs.

### Calibration Store (posteriors and parameter sets)
- `packages/calibration/src/f1_calibration/db.py` — `read_latest_parameter_set()`, `validate_compound()`, `DEFAULT_DB_PATH`. The /simulate and /calibration endpoints query this DB. Security patterns here must be replicated in the new API routes.
- `packages/calibration/src/f1_calibration/jax_model.py` — JAX forward model for F+G. May be reused for vectorized K=100 inference if vmap approach is chosen.
- `packages/calibration/src/f1_calibration/stage4_degradation.py` — PyMC model structure (shows what variables the NetCDF posterior contains: beta_therm, T_act, k_wear).

### Project Context
- `CLAUDE.md` §Bayesian Inference — ArviZ InferenceData format, NetCDF path conventions.
- `CLAUDE.md` §FastF1 Integration — Two-layer cache, <2s budget rationale, `/simulate` sync def requirement.
- `.planning/PROJECT.md` §Key Decisions — "Calibration is offline CLI; /simulate is a forward pass against pre-fitted posteriors."

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `f1_api.routers`, `f1_api.schemas`, `f1_api.services` — directory pattern. New endpoints follow the same split: `routers/simulate.py`, `schemas/simulate.py`, `services/simulate.py`.
- `f1_calibration.db.validate_compound()` — whitelist regex for compound param. Import and call this in the new `/calibration/{compound}` router (don't re-implement).
- `f1_calibration.db.read_latest_parameter_set()` — how to load Stage 1–4 params from SQLite. Wrapper in the simulate service assembles PhysicsParams from the four stage results.
- `f1_calibration.db.DEFAULT_DB_PATH` — canonical DB path (`WORKSPACE_ROOT/.data/f1.db`). Both calibration and API packages use this.
- `f1_core.physics.orchestrator.run_simulation()` — core forward pass. The simulate service calls this K times (or in a vectorized batch).
- `f1_core.ingestion.fastf1_client.load_stint()` — returns `StintArtifact` needed by `run_simulation()`. Session upload adds a code path that patches the FastF1 cache dir before this is called.

### Established Patterns
- `def` (sync) endpoints — `app.py` comment explicitly calls this out; CPU-bound simulate must be `def` so FastAPI runs it in threadpool.
- `raise HTTPException(status_code=404, detail=str(e)) from e` — error pattern from stints router.
- `response_model=...` on route decorator — Pydantic v2 validates outbound responses.
- Separate `lifespan` context manager in `app.py` — expensive one-time init (like loading ArviZ NetCDF or priming the LRU cache) goes here.

### Integration Points
- `app.py` `create_app()` — include new routers: `simulate_router`, `calibration_router`, `sessions_router`.
- SQLite DB at `DEFAULT_DB_PATH` — shared between `f1_calibration` and `f1_api`. No migration needed for Phase 4 (the schema was created in Phase 3).
- ArviZ NetCDF at `.data/posteriors/{compound}_{season}_{timestamp}.nc` — `read_latest_parameter_set()` returns the `netcdf_path` field from `calibration_runs`; the simulate service reads it with `az.from_netcdf(path)`.

</code_context>

<specifics>
## Specific Ideas

- **K=100 draw sampling:** `az.from_netcdf(path).posterior` is an xarray Dataset. Stack chains and draws with `.stack(sample=("chain", "draw"))`, then use `rng.choice(n_samples, size=K, replace=False)` to pick K indices. Build a `PhysicsParams` per draw by merging Stage 1–3 point estimates with Stage 4 sampled values.

- **Response size concern:** Per-timestep arrays for a 22-lap stint at 4 Hz = ~8,000 rows. With 7 fields × 4 tires × 3 numbers each (mean, lo_95, hi_95) = ~672,000 numbers per response. Consider `Content-Encoding: gzip` (FastAPI/Uvicorn default ASGI middleware handles this automatically with `GZipMiddleware`).

- **Session upload path traversal guard:** Use Python's built-in `zipfile.ZipFile.namelist()` check — reject any member whose resolved path is outside the session directory. Pattern: `if not resolved.is_relative_to(session_dir): raise`.

- **Calibration_id in /simulate response:** Pull the `calibration_id` from the `calibration_runs` row returned by `read_latest_parameter_set()` (or a companion `read_latest_calibration_run()` query). This is how the frontend knows which calibration vintage produced the prediction.

</specifics>

<deferred>
## Deferred Ideas

- **Streaming response for per-timestep data** — NDJSON or chunked transfer encoding to avoid buffering the full response. Deferred to v2 if payload size becomes a problem in practice.
- **DELETE /sessions/{session_id}** — Explicit session cleanup. V1 uses TTL auto-cleanup; explicit delete is a v2 API.
- **POST /simulate → background job + poll pattern** — If K=100 runs blow the 2s budget even with vectorization, an async job queue (ARQ + Redis) is the escape hatch. CLAUDE.md notes this as the upgrade path. Not needed until profiled.
- **Per-user session isolation** — V1 has no auth; sessions are server-global. Multi-user isolation requires accounts (out of scope for v1).
- **GET /calibration/{compound}/history** — List all past calibration runs, not just latest. Deferred until version management is needed.

</deferred>

---

*Phase: 04-simulation-api-uncertainty-quantification*
*Context gathered: 2026-04-24*
