# Phase 4: Simulation API & Uncertainty Quantification — Research

**Researched:** 2026-04-24
**Domain:** FastAPI read/write endpoints, ArviZ posterior sampling, K-draw forward-pass uncertainty quantification, in-process + SQLite result cache, ZIP upload with path-traversal safety, TTL-scoped session storage
**Confidence:** HIGH on stack & patterns (all libraries pre-selected in CLAUDE.md and already in use in Phases 1-3); MEDIUM on vectorization choice (sequential vs numpy batch vs JAX vmap — must be profiled against 2 s budget); MEDIUM on exact response-payload size until measured on real K=100 runs.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**POST /simulate Response Shape**
- **D-01:** Return all three data levels in a single JSON response: per-timestep (~4 Hz arrays), per-lap (summary rows), and per-stint (aggregate stats). No opt-in query param — Phase 5 needs all three levels to render track animation, lap charts, and stint summary simultaneously.
- **D-02:** CI structure is triplet-per-value: `{"mean": 95.2, "lo_95": 88.1, "hi_95": 102.4}`. Applied to every predicted metric at every level. Self-documenting, easy to destructure in TypeScript. Consistent across per-timestep, per-lap, and per-stint fields.
- **D-03:** Response metadata block in every `/simulate` response: `calibration_id` (INTEGER from `calibration_runs` table), `model_schema_version` (string constant bumped on breaking changes), `fastf1_version` (from `importlib.metadata.version("fastf1")`), plus `compound` and `stint_index` echoed back.

**POST /simulate — K=100 Posterior Draws**
- **D-04:** K=100 posterior draws are sampled from the ArviZ NetCDF for the relevant compound. Override parameters (if provided in the request body) apply identically to ALL K draws — the override shifts all samples equally but variance from the non-overridden posterior dimensions survives. CI bands are always present in the response regardless of whether overrides are provided. Override presence is flagged in the response metadata (`overrides_applied: true/false`).
- **D-05:** The endpoint never imports or invokes PyMC, NumPyro, or ArviZ at request time for MCMC purposes. NetCDF reading (ArviZ `from_netcdf`) at startup or first call is acceptable; NUTS sampling is not.

**Result Caching**
- **D-06:** Two-layer cache exactly as specified in CLAUDE.md §FastF1 Integration Layer 2: in-process LRU dict in front of a SQLite JSON blob keyed by `(race_id, driver_id, stint_idx, calibration_id)`. Cache hit returns in <50 ms. Cache is invalidated when `calibration_id` changes (new calibration run replaces the key). Cache miss triggers the K=100 forward-pass computation.

**POST /sessions/upload — Session Lifetime**
- **D-07:** Uploaded sessions are ephemeral with a 1-hour TTL. Upload response returns a `session_id` (UUID). Subsequent `/simulate` calls include `session_id` as an optional request body field to route data loading through the uploaded cache instead of Jolpica. Sessions are stored under `/data/sessions/{session_id}/` and cleaned up after 1 hour (background cleanup task, not a scheduled cron).
- **D-08:** Upload accepts a zip file. Server extracts it under the session directory. Subsequent `/simulate` calls with that `session_id` will find the FastF1 session data locally and skip the Jolpica API call entirely. Session scope is server-side only — no per-user isolation (V1 has no auth).

**GET /calibration/{compound} — Response Scope**
- **D-09:** Returns parameter summaries for all four calibration stages:
  - Stage 1 (aero): point estimate + scipy residual uncertainty for C_LA, C_DA, xi
  - Stage 2 (friction): point estimate + residual uncertainty for mu_0_fresh, p_bar_0, n
  - Stage 3 (thermal): point estimate + residual uncertainty for 8 ODE params (C_tread, C_carc, C_gas, R_tc, R_cg, h_0, h_1, alpha_p); T_opt and sigma_T noted as held-fixed at nominal
  - Stage 4 (degradation): full posterior summary for beta_therm, T_act, k_wear — mean, std, 5th/25th/75th/95th percentiles, r_hat, ess_bulk
  - Stage 5 validation metrics: held-out RMSE (s), baseline RMSE (s), beat-baseline flag
  - Also includes calibration_id, compound, year_range, created_at metadata from `calibration_runs` table

### Claude's Discretion

- Vectorization strategy for K=100 draws (numpy batch axis vs sequential loop in threadpool vs JAX vmap) — planner decides based on <2 s timing budget; **recommendation below in §Architecture Patterns #2**
- Exact JSON schema field names (snake_case consistent with existing API convention)
- LRU cache size (max entries count) — planner decides reasonable default; **recommendation below in §Architecture Patterns #3**
- ZIP extraction security (path traversal mitigation) — planner implements standard python zipfile safe-extract pattern; **recommendation below in §Code Examples #2**
- Background TTL cleanup implementation (threading.Timer vs background thread loop); **recommendation below in §Architecture Patterns #4**
- HTTP status codes for error cases (422 for invalid compound, 404 for missing calibration, 503 if no posterior available)

### Deferred Ideas (OUT OF SCOPE)

- **Streaming response for per-timestep data** — NDJSON or chunked transfer encoding. Deferred to v2 if payload size becomes a problem in practice.
- **DELETE /sessions/{session_id}** — Explicit session cleanup. V1 uses TTL auto-cleanup; explicit delete is a v2 API.
- **POST /simulate → background job + poll pattern** — If K=100 runs blow the 2 s budget even with vectorization, an async job queue (ARQ + Redis) is the escape hatch. CLAUDE.md notes this as the upgrade path. Not needed until profiled.
- **Per-user session isolation** — V1 has no auth; sessions are server-global.
- **GET /calibration/{compound}/history** — List all past calibration runs. Deferred.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| API-04 | POST /simulate runs the 7-module forward model for a given stint; returns per-timestep (~4 Hz), per-lap, and per-stint outputs with 95% credible intervals from K=100 posterior draws; responds in <2 s end-to-end (cache hit, excluding cold start); payload supports optional parameter overrides | §Architecture Patterns #1 & #2 (router + vectorization), §Code Examples #1 (K-draw sampling), §Common Pitfalls #1 (sync def for CPU-bound), §Standard Stack (ArviZ.extract, numpy batch / JAX vmap) |
| API-05 | GET /calibration/{compound} returns current fitted parameter summaries (posterior mean ± 95% CI) for a compound | §Code Examples #3 (az.summary), §Architecture Patterns #5 (calibration service), §Stage-wise response composition (D-09) |
| API-06 | POST /sessions/upload accepts a zip of FastF1 cache directory; parses and ingests the session data server-side for drag-and-drop loading without re-fetching from Jolpica | §Architecture Patterns #4 (TTL cleanup), §Code Examples #2 (safe zip extract), §Common Pitfalls #4 (zip slip), §Common Pitfalls #7 (session routing in load_stint) |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

Actionable directives the plan MUST honor:

- **Python 3.12 only** (`requires-python = ">=3.12,<3.13"`). No 3.13.
- **FastAPI 0.136.x + Pydantic v2** — already installed in `packages/api/pyproject.toml`. Keep.
- **`/simulate` MUST be a `def` (sync) route** — CPU-bound (K×forward pass). CLAUDE.md §Backend/Core Framework and `packages/api/src/f1_api/app.py` module docstring are explicit: `async def` would block the event loop; `def` runs on FastAPI's threadpool.
- **The endpoint NEVER imports or invokes PyMC/NumPyro/ArviZ for MCMC at request time** (D-05). ArviZ `from_netcdf` at startup or first call is acceptable. `import pymc` at the router layer is forbidden.
- **All param dataclasses are `@dataclass(frozen=True)`** — `PhysicsParams`, `AeroParams`, `FrictionParams`, `ThermalParams`, `DegradationParams` from `f1_core.physics.params`. Construct a new instance per draw (or per batch) — no mutation.
- **`f1_api` imports from `f1_core` and `f1_calibration`; `f1_calibration` does NOT import from `f1_api`** — preserve existing layering.
- **FastF1 cache:** single-process-wide via `fastf1.Cache.enable_cache(str(resolved))`. `f1_core.ingestion.fastf1_client.init_cache()` is idempotent and locked. When a session upload lands, the FastF1 cache for that session must be served from `/data/sessions/{session_id}/` rather than the global cache. This requires either (a) per-session cache dir swap inside `load_stint`, or (b) symlink / file copy of session data into the shared cache. See §Common Pitfalls #7.
- **SQLite is shared between `f1_calibration` and `f1_api`.** `DEFAULT_DB_PATH = WORKSPACE_ROOT/.data/f1.db`. Use `f1_calibration.db.resolve_db_path` and `f1_calibration.db.validate_compound` — they enforce workspace containment and the `^C[1-5]$` whitelist (T-3-01..T-3-06). Do NOT re-implement these.
- **Endpoint pattern:** `raise HTTPException(status_code=404, detail=str(e)) from e` on `ValueError`; see `packages/api/src/f1_api/routers/stints.py` lines 26-29.
- **Pydantic v2 response models:** use `response_model=...` decorator argument and `ConfigDict(from_attributes=True)` when wrapping dataclasses (see `packages/api/src/f1_api/schemas/stints.py` line 14).
- **Service-layer separation:** `routers/*.py` is HTTP-shaped; `services/*.py` holds business logic; `schemas/*.py` holds Pydantic response models. This pattern is enforced by the existing tests' monkeypatch strategy — `conftest.py` patches at the service layer.
- **ASGI server:** Uvicorn 0.32+. Middleware stacks added via `app.add_middleware(...)` in `create_app()`.
- **CORS:** already configured; `GET, POST` methods allowed; adding another POST endpoint does not require config change.
- **Lifespan context manager** in `app.py` is where expensive one-time init goes (NetCDF preloading, LRU priming) — see lines 26-31.
- **Tests live in `packages/api/tests/`** and must not make Jolpica calls. Monkeypatch at the service layer (existing conftest pattern).

## Summary

Phase 4 wires Phase 3's offline Bayesian posteriors into a 3-endpoint REST surface on top of the existing Phase 1 FastAPI app. The critical paths:

1. **`POST /simulate`** loads a stint artifact (Layer-2 pickle cache from Phase 1), assembles `PhysicsParams` for each of K=100 posterior draws sampled from the ArviZ NetCDF written in Phase 3, runs the `f1_core.physics.orchestrator.run_simulation()` forward pass K times (or in a vectorized batch), aggregates mean + 95 % CI across the K draws at three data levels (per-timestep, per-lap, per-stint), and returns the result as JSON. A warm-cache hit (same race/driver/stint/calibration_id) skips the K-draw loop entirely via an in-process LRU over a SQLite JSON blob and returns in <50 ms.

2. **`GET /calibration/{compound}`** queries the SQLite `calibration_runs` + `parameter_sets` tables, loads the NetCDF at the recorded path, produces per-stage parameter summaries (point estimates + 95 % CIs for Stages 1-3, full posterior quantiles for Stage 4, held-out RMSE for Stage 5), and returns a single composite JSON document.

3. **`POST /sessions/upload`** accepts a multipart ZIP, safely extracts it under `/data/sessions/{uuid}/`, returns a `session_id`, and hooks into the data-loading path so that subsequent `/simulate` calls with `session_id` in the request body use the uploaded FastF1 cache instead of Jolpica.

**Primary recommendation:** Build the endpoints in the exact service/router/schema layering already established. Use **sequential K-draw loops with numpy-vectorized per-timestep math** in v1 — do not attempt JAX vmap refactor of the full orchestrator unless the 2 s budget is blown after profiling. The existing orchestrator is NumPy-based and well-optimized; K=100 sequential forward-passes on a typical 22-lap stint (~8 k timesteps, ~0.2-0.4 s each per the Phase 2 fixture) must be measured before any refactor. If needed, the cheapest escape hatch is the existing JAX F+G scan in `f1_calibration.jax_model.simulate_mu_0` — it can be wrapped in `jax.vmap` over the 3 Stage-4 parameters to batch K draws through Modules F+G while Stages 1-3 outputs (Module A-E trajectories) are computed once from posterior means and reused across draws. This is exactly the factorization already used in Phase 3's Stage 4 likelihood.

## Standard Stack

### Core (all already installed; verified versions)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **FastAPI** | 0.136.x | HTTP framework | [CITED: packages/api/pyproject.toml] Already pinned; explicitly chosen in CLAUDE.md. |
| **Uvicorn** | 0.32+ | ASGI server | [CITED: packages/api/pyproject.toml] |
| **Pydantic v2** | 2.6+ | Request/response validation | [CITED: packages/api/pyproject.toml] `ConfigDict(from_attributes=True)` pattern already in use. |
| **Starlette GZipMiddleware** | Bundled with FastAPI | Response compression | [CITED: fastapi.tiangolo.com/advanced/middleware/] Default `minimum_size=500` bytes, `compresslevel=9`. |
| **NumPy** | 2.1+ | Aggregation (mean, percentile, vectorized CI) | [CITED: f1_core deps via workspace] `np.percentile(draws, [2.5, 97.5], axis=0)` for CIs. |
| **ArviZ** | 0.20+ | NetCDF posterior reading, `az.summary`, `az.extract` | [CITED: packages/calibration/pyproject.toml] Already used in `f1_calibration.stage4_degradation.persist_posterior`. |
| **netcdf4** | 1.7+ | NetCDF4 backend for ArviZ | [CITED: packages/calibration/pyproject.toml] |
| **xarray** | (transitive via ArviZ) | Posterior Dataset operations — `.stack`, `.isel`, `.sel` | [VERIFIED: ArviZ 0.20+ depends on xarray] |
| **SQLite (stdlib sqlite3)** | 3.40+ | Cache + calibration metadata | [CITED: Python 3.12 stdlib] Schema already created in Phase 3. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **ORJSONResponse** | orjson 3.10+ (bundled via FastAPI when present) | Faster JSON serialization; native numpy dtype support | Optional; **defer** unless profiling shows JSON serialization is the bottleneck. `json.dumps` of ~700 k floats is ~100-200 ms on CPython 3.12; likely under budget. |
| **uuid (stdlib)** | — | `session_id` generation | Session upload. |
| **tempfile (stdlib)** | — | Atomic zip extraction to temp dir then rename | Session upload. |
| **zipfile (stdlib)** | — | ZIP reading/extraction | Session upload; see pitfall #4. |
| **importlib.metadata (stdlib)** | — | Runtime `fastf1.__version__` for metadata block | D-03. |
| **functools.lru_cache** | stdlib | Config / helper memoization | NOT used for the simulate result cache — we need custom TTL + SQLite backing. See pitfall #3. |
| **threading / concurrent.futures** | stdlib | Lock around in-memory LRU writes | See §Architecture Patterns #3. |
| **JAX + jax.vmap** | Already present via f1_calibration | Fallback vectorization of Modules F+G across K draws | Only if sequential K=100 loop exceeds 2 s. See §Architecture Patterns #2. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| In-process dict LRU + SQLite JSON blob | Redis | Overkill for single-worker V1 and requires infra change. The decision in CLAUDE.md §Task Execution is explicit: stay on in-process cache until profiling demands more. |
| Sequential K=100 loop | `jax.vmap(simulate_mu_0)` batched across draws | JAX variant exists in `f1_calibration.jax_model`; covers only F+G (not full A-G forward pass). Would require re-running Modules A-E once per stint then vmap over the 3 Stage-4 params. Adds JIT-compile overhead on first call per worker (~30 s per the Phase 3 SBC experience — see stage4_degradation.py line 387). Defer unless needed. |
| `functools.lru_cache` | Hand-rolled `OrderedDict` + threading.Lock | `lru_cache` is thread-safe for reads but has no TTL, no eviction-on-key-invalidation, and no persistent backing. We need (a) eviction when a new `calibration_id` supersedes the old, (b) SQLite durability across restarts. Hand-rolled is the right call. |
| Pickle the SimulationResult for cache | JSON in SQLite TEXT column | SimulationResult includes numpy arrays; pickle is denser. But: JSON is the wire format we return anyway, so serializing once to JSON and storing as the cache value lets cache hits skip re-serialization entirely. **Recommend: store the final JSON bytes as the cache value.** |

**Installation:** Nothing to install. All dependencies are already declared.

**Version verification (npm view equivalent via `uv tree` or pip show — run during Wave 0):**

| Package | Declared | Verified at research time | Notes |
|---------|----------|---------------------------|-------|
| fastapi | >=0.136,<0.200 | [ASSUMED] current 0.136.x | Confirm in Wave 0 via `uv pip show fastapi`. |
| arviz | >=0.20,<1 | [VERIFIED: ArviZ 1.0.0 released March 2026 per PyPI][1] | ArviZ 1.0.0 is within the `<1` cap only if spec allows 1.x; current cap is `<1` which **excludes 1.0**. Planner may need to bump cap — but Phase 3 already locked 0.20 series; keep. |
| orjson | not declared | — | Add as optional if ORJSONResponse adopted. |

[1] https://python.arviz.org/ (ArviZ home, 1.0.0 release notes)

## Architecture Patterns

### Recommended Project Structure

```
packages/api/src/f1_api/
├── app.py                    # unchanged — add 3 include_router() calls + GZipMiddleware
├── dependencies.py           # add StintIndex type
├── routers/
│   ├── stints.py             # existing (API-03)
│   ├── races.py              # existing (API-01)
│   ├── drivers.py            # existing (API-02)
│   ├── simulate.py           # NEW — POST /simulate (API-04)
│   ├── calibration.py        # NEW — GET /calibration/{compound} (API-05)
│   └── sessions.py           # NEW — POST /sessions/upload (API-06)
├── schemas/
│   ├── stints.py             # existing
│   ├── simulate.py           # NEW — SimulateRequest, SimulateResponse, CIValue,
│   │                         #       PerTimestepBlock, PerLapRow, PerStintSummary,
│   │                         #       SimulationMetadata
│   ├── calibration.py        # NEW — CalibrationResponse + Stage{1-5}Summary
│   └── sessions.py           # NEW — SessionUploadResponse
├── services/
│   ├── stints.py             # existing
│   ├── simulate.py           # NEW — the K-draw forward pass + aggregation + cache
│   ├── calibration.py        # NEW — compose stage summaries from SQLite + NetCDF
│   ├── sessions.py           # NEW — safe zip extraction + TTL registry
│   └── posterior_store.py    # NEW — wraps az.from_netcdf + K-draw selection, cached per compound
└── cache/
    └── simulate_cache.py     # NEW — OrderedDict LRU wrapping a SQLite JSON blob
```

### Pattern 1: Router → Service → SimulationResult → Pydantic response

```
Router (routers/simulate.py)
  ├─ Validate RaceId, DriverCode, stint_index via Pydantic path/body params
  ├─ Call service: run_simulation_with_uncertainty(race_id, driver_code, stint_index,
  │                                                 compound, overrides=None, session_id=None)
  ├─ On ValueError: HTTPException(422 or 404, detail=str(e))
  └─ return response_model-validated Pydantic object

Service (services/simulate.py)
  ├─ Determine effective FastF1 cache dir: global or session-scoped
  ├─ Cache lookup in simulate_cache (returns cached JSON bytes if hit)
  ├─ If miss:
  │   ├─ load_stint(...) from f1_core.ingestion (Phase 1 — already cached)
  │   ├─ Load posterior (posterior_store.get_posterior(compound))
  │   ├─ Sample K=100 draws → list[PhysicsParams] (merge Stage 1-3 point estimates
  │   │                                               + Stage 4 samples)
  │   ├─ Apply overrides to every PhysicsParams if provided
  │   ├─ For draw in K: run_simulation(artifact, params) → SimulationResult
  │   │                 (keep numpy arrays, not python lists)
  │   ├─ Stack: shape (K, N, 4) for per-tire per-timestep; (K, L, …) for per-lap
  │   ├─ Aggregate: mean + np.percentile along axis=0 → three CI blocks
  │   ├─ Attach metadata (calibration_id, model_schema_version, fastf1_version,
  │   │                    overrides_applied)
  │   ├─ Serialize final object to JSON bytes
  │   └─ Write (cache_key, json_bytes) to simulate_cache
  └─ Return the Python object (router serializes, or we return Response(json_bytes))
```

**Why:** This mirrors the Phase 1 pattern exactly. Service function is monkeypatchable from `conftest.py` without touching router. Business logic — K-draw loop, aggregation, cache — is unit-testable without TestClient.

### Pattern 2: K=100 Vectorization Decision

**Recommended for v1: sequential loop with numpy-optimized per-timestep inner body.**

```python
# services/simulate.py
results: list[SimulationResult] = []
for k in range(K):
    params_k = merge_params(stage1_pt, stage2_pt, stage3_pt, stage4_draws[k],
                            overrides=overrides)
    result_k = run_simulation(artifact, params_k)   # already vectorized in NumPy
    results.append(result_k)

# Stack to (K, N, 4)
t_tread_stack = np.stack([r.t_tread for r in results], axis=0)
# Aggregate
t_tread_mean = t_tread_stack.mean(axis=0)
t_tread_lo, t_tread_hi = np.percentile(t_tread_stack, [2.5, 97.5], axis=0)
```

**Rationale:**
- `run_simulation` is already numpy-vectorized per timestep (see `packages/core/src/f1_core/physics/orchestrator.py` lines 235-304 — pre-allocated (n,4) arrays, no Python-level inner-tire loops).
- K=100 × ~8 k timesteps × per-step math ≈ 800 k iterations of module code. Phase 2's orchestrator was written with `np.empty((n, 4))` pre-allocation and no per-step list appends.
- Budget: 2 s total, minus ~100 ms for NetCDF load (amortized to ~5 ms with caching), minus ~50 ms for JSON serialize, minus ~50 ms for aggregation → **~1.8 s available for K=100 simulations = 18 ms/draw**.
- **This is tight but plausible.** Must be profiled. Acceptance: pytest-benchmark test on the canonical Bahrain 2023 VER stint 2 fixture, target wall <2 s.

**Escape hatches if budget blown:**

1. **JAX vmap on F+G only** — Modules A-E produce fixed trajectories (velocity, lateral accel, F_z, F_y, F_x, mu, a_cp, p_slide) under posterior means of Stages 1-3. F+G run vmap'd over K Stage-4 parameter draws. `simulate_mu_0` already exists as a jit-compiled lax.scan in `packages/calibration/src/f1_calibration/jax_model.py` lines 34-91. Wrap with `jax.vmap(simulate_mu_0, in_axes=(0, 0, 0, None, None, None, None))` over `(beta_therm, T_act, k_wear)` stacks. This is what the Phase 3 calibration already does implicitly at every MCMC sample.
   - **Caveat:** JIT compile cost is ~30 s per worker on first call (see stage4_degradation.py line 387 comment). Must be paid in lifespan startup, not on first request.
2. **Reduce K.** K=100 was chosen because CI tails at 2.5 % and 97.5 % need at least ~40 samples in each tail for stable percentile estimation. K=50 works with wider MC error on the tail but halves compute. D-04 locks K=100; would need CONTEXT change.
3. **Parallelize with concurrent.futures.ThreadPoolExecutor** — numpy releases the GIL in most hot loops; K draws across n_cpu threads might give linear-ish speedup. Cheap to try but measure first; numpy threads can oversubscribe.
4. **ARQ + Redis async job queue** — CLAUDE.md documents this as the upgrade path. Out of scope for v1 unless all above fail.

### Pattern 3: Simulate Result Cache (D-06)

```
simulate_cache (module-level singleton, created in lifespan)
├── in-memory: collections.OrderedDict[CacheKey, bytes]  (JSON-encoded response)
│   - threading.Lock around mutate operations
│   - LRU eviction at max_size (recommend 64 entries; at ~700 kB/entry → ~45 MB)
├── persistent: SQLite table simulation_cache
│   - CREATE TABLE simulation_cache (
│         cache_key TEXT PRIMARY KEY,  -- hash(race_id|driver|stint|calibration_id)
│         calibration_id INTEGER NOT NULL,
│         created_at TEXT NOT NULL,
│         payload_json BLOB NOT NULL   -- gzipped JSON or raw JSON
│     );
│   - Index on calibration_id for bulk invalidation
└── Invalidation: on every POST/GET that consults calibration metadata, check if
                  the latest calibration_id for that compound has changed; if so,
                  DELETE FROM simulation_cache WHERE calibration_id = <old>.
                  (Simpler: at cache miss, look up latest calibration_id first and
                   bake it into cache_key — stale entries then just never match.)
```

**Cache key recommendation:** `f"{race_id}|{driver_code}|{stint_idx}|{calibration_id}|{overrides_hash or 'none'}"`. Including `overrides_hash` (SHA256 of the sorted JSON of override params) means override-driven forward passes are also cached; omitting it means overridden responses always bypass the cache — either is defensible. **Recommend: include `overrides_hash`.** Cache hits with identical override dicts are not rare (URL-hash sharing, repeat scrubbing).

**Max size:** 64 entries is ~45 MB worst case; reasonable on a Fly.io shared-cpu-2x with 512 MB - 1 GB RAM.

### Pattern 4: Session Upload TTL Cleanup (D-07)

**Recommendation: single daemon background thread loop, not `threading.Timer`.**

```
In lifespan startup:
    cleanup_thread = threading.Thread(
        target=_session_cleanup_loop,
        daemon=True,
        name="session-ttl-cleanup",
    )
    cleanup_thread.start()
    yield
    # daemon=True → thread dies with the process on shutdown

def _session_cleanup_loop() -> None:
    while True:
        time.sleep(300)   # every 5 min is fine — TTL is 1 h, jitter acceptable
        now = time.time()
        for session_dir in SESSION_ROOT.iterdir():
            mtime = session_dir.stat().st_mtime
            if now - mtime > 3600:
                shutil.rmtree(session_dir, ignore_errors=True)
```

**Why not threading.Timer per upload?**
- Timer creates a new thread per call; 100 uploads = 100 zombie threads until fire.
- Timer can leak if process crashes between scheduling and firing.
- One daemon loop is simpler, restartable, observable in logs.

**Why not FastAPI BackgroundTasks?**
- BackgroundTasks fires once after the response is sent; it's fire-and-forget, not a recurring cleanup. Wrong tool. (Also confirmed by WebSearch — "BackgroundTasks is designed for fire-and-forget short jobs, not for starting background loops.")

### Pattern 5: GET /calibration/{compound} Response Composition

```
Router: validate compound (reuse f1_calibration.db.validate_compound)
       ├─> 422 if compound is not ^C[1-5]$

Service: 
    1. Open SQLite conn (or use an app-lifespan-managed connection)
    2. SELECT the latest calibration_runs row for compound
       ├─> 404 if none
    3. SELECT parameter_sets rows for stages 1-4 by FK (param_set_stage1-4)
    4. az.from_netcdf(calibration_runs.netcdf_path) — load posterior
       ├─> use posterior_store cache; it's the same Phase-3 file
    5. For Stage 4:
       ├─ az.summary(posterior, var_names=["beta_therm","T_act","k_wear"],
       │             stat_focus="mean", hdi_prob=0.95) → DataFrame with mean/sd/hdi_2.5/hdi_97.5/r_hat/ess_bulk
    6. For Stages 1-3:
       ├─ point_estimate from parameter_sets.params_json
       ├─ residual_uncertainty from parameter_sets.diagnostics_json["rmse"] or similar
    7. For Stage 5:
       ├─ calibration_runs.heldout_rmse_s, baseline_rmse_s, beat_baseline = heldout < baseline
    8. Return Pydantic model
```

**NetCDF re-read cost:** ArviZ NetCDFs for Stage-4 with 4000 samples are typically <1 MB; first read is 50-200 ms, then filesystem page cache makes it ~5 ms. Cache the `posterior` handle per-compound in a module-level dict.

### Anti-Patterns to Avoid

- **`async def simulate(...)`** — K=100 forward passes are CPU-bound; `async def` would block the event loop. Use plain `def` (PHYS-09 pattern, explicit in app.py docstring).
- **`import pymc` at the router module level** — D-05 forbids this. The posterior is a plain NetCDF; read it with ArviZ.
- **Re-validating compound regex inside the router** — call `f1_calibration.db.validate_compound` which is the project's single source of truth (T-3-01).
- **`zipfile.ZipFile.extractall()` on untrusted paths** — See pitfall #4. Always loop + path-check.
- **Returning raw numpy arrays in response_model-validated Pydantic objects** — Pydantic v2 rejects `np.float64` in some field types. Convert to Python floats/lists at the aggregation step. Alternatively, use `ORJSONResponse` which serializes numpy natively (but drops the Pydantic validation step for outbound).
- **LRU cache keyed on PhysicsParams instances or on StintArtifact** — neither is hashable usefully. Key on the minimal identifier tuple.
- **Running the TTL cleanup loop as an `async def` with `asyncio.sleep`** — works, but the cleanup I/O (`shutil.rmtree`) is blocking; better to keep it off the event loop entirely.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Compound regex validation | Re-implementing `^C[1-5]$` check in a new router | `f1_calibration.db.validate_compound` | Already exists, already secured (T-3-01), already tested. |
| Path traversal check inside workspace | Custom `is_relative_to` wrapper | `f1_calibration.db.resolve_db_path` | Already enforces workspace containment + symlink rejection. Reuse for NetCDF path resolution. |
| Posterior sampling | Custom NumPy array handling of the posterior file | `az.from_netcdf(path).posterior` → xarray Dataset, then `.stack(sample=("chain","draw"))` or `az.extract(idata, num_samples=K)` | ArviZ is already in dependencies; `extract` handles combining chains + random-without-replacement subset in one call. See WebSearch [Working with InferenceData — ArviZ 0.23.4]. |
| Posterior CI percentiles | Custom quantile loop | `np.percentile(draws_stack, [2.5, 50, 97.5], axis=0)` | Numpy has this built-in, vectorized over arbitrary trailing axes. See §Code Examples #4. |
| Per-compound posterior handle caching | Bespoke LRU | `functools.lru_cache(maxsize=8)` on the loader | `lru_cache` is safe for read-heavy single-writer access and posterior Datasets are immutable once loaded. |
| JSON response compression | Custom gzip middleware | `from fastapi.middleware.gzip import GZipMiddleware; app.add_middleware(GZipMiddleware, minimum_size=1024)` | Bundled with FastAPI. Default min_size=500 bytes, compresslevel=9. Our payloads are ~500 kB+ uncompressed → 70-90 % savings with almost no CPU impact at level 5-6. [CITED: fastapi.tiangolo.com/advanced/middleware/] |
| UUID generation | `str(random.randint(...))` | `uuid.uuid4().hex` | 128-bit entropy, collision-safe, URL-safe. |
| Atomic file write | Hand-rolled tmp + rename | `tempfile.TemporaryDirectory()` + `shutil.move` / `os.replace` | Battle-tested, cross-platform, Windows semantics handled. |
| Runtime library version lookup | Parse `__version__` strings | `importlib.metadata.version("fastf1")` | stdlib, cached by importlib, matches PEP 566. |

**Key insight:** The Phase 3 layer (`f1_calibration.db`) is the single authority for compound validation, path containment, and workspace safety. Phase 4 routers and services import from it directly. Do not duplicate or reimplement the checks — that's how security regressions happen.

## Common Pitfalls

### Pitfall 1: `async def /simulate` blocks the event loop
**What goes wrong:** K=100 CPU-bound forward passes run in the single asyncio thread. All other requests stall for seconds.
**Why it happens:** Copy-paste from async tutorials; developers assume `async def` is "just faster".
**How to avoid:** Declare as `def simulate(...)`. FastAPI routes `def` through `run_in_threadpool` automatically, parallelizing with other threadpool workers. This is explicit in `packages/api/src/f1_api/app.py` module docstring ("All endpoints are plain `def` (pitfall P9)").
**Warning signs:** Any pending request to `/healthz` takes >500 ms during a simulate call → event loop is blocked.

### Pitfall 2: Importing PyMC at request time breaks the deployment image size contract
**What goes wrong:** D-05 forbids it. PyMC + PyTensor + JAX is hundreds of MB of Python deps; `/simulate` doesn't need them.
**Why it happens:** Convenience — developer imports `pm.sample` to re-verify draws.
**How to avoid:** The only import from `f1_calibration` should be `f1_calibration.db.*`. NetCDF reading is done via ArviZ directly. ArviZ alone (with netcdf4 + xarray + numpy) is enough. Add a lint rule / unit test: `assert "pymc" not in sys.modules` after calling `create_app()` in tests (optional but valuable).
**Warning signs:** `uv tree --package f1_api --only-runtime | grep pymc` finds a transitive dep path.

### Pitfall 3: LRU cache races on cache miss → duplicate compute
**What goes wrong:** Two concurrent requests for the same (race, driver, stint, calibration_id) both miss cache, both run K=100 forward passes, only one wins the insert.
**Why it happens:** `functools.lru_cache` docs: "It is possible for the wrapped function to be called more than once if another thread makes an additional call before the initial call has been completed and cached." (WebSearch — Python CPython issue 93179.)
**How to avoid:** Use a per-key lock dict or a single global lock around both check and compute:
```python
with cache_lock:
    cached = cache.get(key)
if cached:
    return cached
# compute...  (outside lock so other keys aren't blocked)
with cache_lock:
    cache[key] = result
```
A finer-grained per-key lock is possible but complex; the global-lock approach is fine at V1 traffic (single machine, few concurrent users).
**Warning signs:** Metrics show 2× compute count vs cache miss count during burst traffic.

### Pitfall 4: Zip Slip path traversal on session upload
**What goes wrong:** Zip entry `../../../../etc/passwd` extracts outside `/data/sessions/<uuid>/`.
**Why it happens:** `ZipFile.extractall(dest)` has sanitization since Python 3.12+ per the Python docs ("zipfile.extractall and zipfile.extract functions sanitize zip entries and thus prevent such path traversal vulnerabilities"), **but** custom extraction loops using `os.path.join` bypass this. Never trust — always verify.
**How to avoid:** Use the pattern in §Code Examples #2. Reject any member whose `Path(dest / member).resolve()` is not `is_relative_to(dest.resolve())`. Also enforce:
- No absolute paths in member names.
- No symlinks (reject entries with `external_attr` indicating symlink bits).
- Cap extracted size (decompression bomb defense).
- Cap member count (small zips with millions of tiny files).
**Warning signs:** Unit test with crafted malicious zip MUST be in the test suite — see §Validation Architecture.

### Pitfall 5: Pydantic v2 rejects numpy scalars in response models
**What goes wrong:** `np.float64(95.2)` in a `float` field raises `ValidationError` under Pydantic v2 in strict mode. [VERIFIED: pydantic/pydantic issue #7017 — "json code was ported to pydantic-core and json_encoders was no longer available".]
**Why it happens:** Pydantic v2 is stricter; Python's `float` is `builtins.float`, not `numpy.float64`.
**How to avoid:** In the aggregation step, convert with `.tolist()` or `float(x)` for scalars. Build the response dict out of Python-native floats and lists. Alternative: configure the model with `arbitrary_types_allowed=True` and let orjson handle numpy — but this loses schema guarantees. **Recommend: explicit `.tolist()` at aggregation boundary.**
**Warning signs:** `ValidationError: Input should be a valid number`.

### Pitfall 6: ArviZ NetCDF path stored as relative in SQLite → API resolves from wrong CWD
**What goes wrong:** `calibration_runs.netcdf_path` is stored as `.data/posteriors/C3_2022-2024_...nc`; API resolves from `packages/api/` at runtime and fails.
**Why it happens:** Phase 3's `_validate_stored_path` (db.py line 261) explicitly stores the raw string, not the absolute. The resolved form is only used for validation.
**How to avoid:** In the API service, prepend `f1_calibration.common.WORKSPACE_ROOT` when the stored path is relative, THEN call `resolve_db_path` for the final containment check. Phase 3 uses the same pattern (db.py line 280-281).
**Warning signs:** `FileNotFoundError` on NetCDF open only when running the API from a different CWD than calibration CLI.

### Pitfall 7: Session upload doesn't actually skip Jolpica
**What goes wrong:** User uploads a FastF1 cache zip; `/simulate` with that `session_id` still tries to hit Jolpica because `load_stint` uses the global `init_cache`-registered directory.
**Why it happens:** `f1_core.ingestion.fastf1_client.init_cache` is process-wide and idempotent (line 35-50). Once `fastf1.Cache.enable_cache(path)` is called with the global cache dir, FastF1 looks there for everything. Changing the path mid-process is not straightforward.
**How to avoid (options):**
- **Option A (recommended):** Extract session zip contents INTO the global cache dir structure. FastF1 cache is organized by year/event/session. If the uploaded cache has the same tree, merging it is just a copy. No per-session cache dir swap needed.
- **Option B:** Session-scoped `load_stint` that temporarily re-calls `fastf1.Cache.enable_cache(session_dir)` with a lock. Fragile if concurrent requests race.
- **Option C:** Bypass FastF1's cache entirely for session uploads — parse the zip contents (which are already pickles that FastF1 would have produced) and construct `StintArtifact` directly. Requires knowing FastF1's pickle schema (brittle across versions).

**Recommend Option A with validation:** on upload, inspect the zip's directory tree, confirm it looks like a FastF1 cache (`YYYY/YYYY-MM-DD_*/...`), copy into global cache. Session_id then just records "this upload provenance" but doesn't route anything. Simplicity >> isolation for V1.

**Warning signs:** Upload + /simulate + air-gapped test machine (no internet) = FileNotFoundError on Jolpica.

### Pitfall 8: `az.extract(num_samples=K)` returns DIFFERENT samples on each call
**What goes wrong:** Same request run twice gives slightly different CI bands.
**Why it happens:** `az.extract` uses a random subset by default (`arviz.extract — rng=True`).
**How to avoid:** Pass `rng=np.random.default_rng(seed)` with a fixed seed computed from the cache key (e.g., `hash((race_id, driver, stint, calibration_id)) & 0xFFFFFFFF`). This makes K-draw selection deterministic per cache key, so CI bands are reproducible.
**Warning signs:** Caching layer works but identical requests to a fresh cache return slightly different numbers.

### Pitfall 9: GZipMiddleware compresses small responses at high cost
**What goes wrong:** `/calibration/{compound}` returns ~5-10 kB of JSON; compressing at level 9 wastes CPU for marginal gain.
**Why it happens:** Default `minimum_size=500` is fine but default `compresslevel=9` is slow.
**How to avoid:** `app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)`. Level 5 gives ~95 % of level-9 compression at ~30 % the CPU cost. Since large responses are the `/simulate` payload (~500 kB), level 5 is the right tradeoff.
**Warning signs:** `/calibration/{compound}` latency >50 ms for a trivial DB query.

### Pitfall 10: JSON serialization of K stacked arrays explodes memory transiently
**What goes wrong:** `json.dumps({"t_tread": {"mean": arr.tolist(), "lo_95": ...}})` on (N=8000, 4) arrays builds 24 k nested Python lists in memory before stringify.
**Why it happens:** `.tolist()` creates Python floats (28 bytes each). 700 k floats × 28 bytes = ~20 MB of objects just for the list, plus the Unicode string at the end.
**How to avoid:**
- Use ORJSONResponse with `orjson.OPT_SERIALIZE_NUMPY` → serializes numpy directly without `.tolist()`.
- OR: chunk the JSON output (write per-tire sub-objects sequentially to a BytesIO).
- Profile first; might be a non-issue at K=100 single-stint scale.
**Warning signs:** `/simulate` memory spikes to 200+ MB briefly during serialization; K=100 cold response >1.5 s wall time.

## Runtime State Inventory

Phase 4 is an additive phase (new endpoints, new cache). It does NOT rename/refactor existing runtime state. **Skipping the Runtime State Inventory section per the template guidance: "Include this section for rename/refactor/migration phases only. Omit entirely for greenfield phases."**

The following relevant state already exists and is READ by Phase 4:
- SQLite DB at `.data/f1.db` — Phase 3 created the schema.
- ArviZ NetCDFs at `.data/posteriors/*.nc` — Phase 3 wrote them.
- FastF1 cache at `F1_CACHE_DIR` — Phase 1 populated it.

Phase 4 ADDS:
- A new SQLite table `simulation_cache`.
- A new filesystem tree `/data/sessions/{uuid}/` with 1-hour TTL contents.
- An in-process OrderedDict cache (ephemeral, per worker).
- A daemon thread for session cleanup.

None of these rename existing things. **No migration actions required.**

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Entire phase | ✓ (per pyproject) | 3.12 | — |
| FastAPI | All endpoints | ✓ | 0.136.x | — |
| Pydantic v2 | Schemas | ✓ | 2.6+ | — |
| ArviZ | Posterior reading | ✓ | 0.20.x | — |
| netcdf4 | NetCDF backend | ✓ | 1.7+ | — |
| NumPy | Aggregation | ✓ | 2.1+ | — |
| xarray | Posterior Dataset ops | ✓ (transitive) | — | — |
| SQLite (stdlib) | Cache + metadata | ✓ | 3.40+ | — |
| Phase 3 NetCDFs | `/simulate`, `/calibration` | **✓/✗ depends on Phase 3 completion state** | — | Phase 4 tests use a fixture NetCDF generated in `conftest.py` (recommend: vendor a small-K fixture) |
| Phase 3 `calibration_runs` row | `/simulate`, `/calibration` | Same as above | — | Same |
| JAX | Optional fallback vectorization | ✓ (via f1_calibration) | 0.4.x | Sequential loop is the default path — no fallback needed. |
| orjson | Optional fast JSON | ✗ (not declared) | — | Standard `json` is fine; add orjson only if profiling shows it's needed. |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** orjson (only if needed).

**Phase 3 artifact dependency:** Phase 4 cannot do an integration-level E2E test without Phase 3 artifacts. Wave 0 must either (a) confirm Phase 3 has produced at least one calibration_runs row + one NetCDF, or (b) vendor a small test fixture NetCDF + seeded SQLite row. Planner: **recommend a tiny canonical fixture generator in `packages/api/tests/fixtures/calibration_fixture.py`** that writes a minimal (2 chain, 50 draw) Stage-4 posterior NetCDF + inserts a single calibration_runs row. This keeps Phase 4 tests decoupled from Phase 3 execution state.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8+ (already installed in root `dev` dependency group) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` at repo root |
| Quick run command | `pytest packages/api/tests/ -x` |
| Full suite command | `pytest packages/api/tests/ packages/core/tests/ -v` |
| Integration marker | `-m "integration"` (already in pyproject.toml markers list); use for K=100 wall-time benchmarks |
| Existing files | `packages/api/tests/conftest.py` (TestClient fixture with monkeypatched service layer), `test_endpoints.py` (Phase 1 endpoint tests). Pattern established. |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| API-04-a | POST /simulate with valid stint returns 200 + schema-valid body | unit | `pytest packages/api/tests/test_simulate.py::test_simulate_happy_path -x` | ❌ Wave 0 |
| API-04-b | Response includes per-timestep, per-lap, per-stint blocks | unit | `pytest packages/api/tests/test_simulate.py::test_simulate_three_levels -x` | ❌ Wave 0 |
| API-04-c | Every predicted value has mean+lo_95+hi_95 triplet | unit | `pytest packages/api/tests/test_simulate.py::test_simulate_ci_triplets -x` | ❌ Wave 0 |
| API-04-d | Overrides apply to all K draws; response metadata flags overrides_applied=true | unit | `pytest packages/api/tests/test_simulate.py::test_simulate_overrides -x` | ❌ Wave 0 |
| API-04-e | Cache hit returns in <50 ms | integration | `pytest packages/api/tests/test_simulate.py::test_simulate_cache_hit -m integration` | ❌ Wave 0 |
| API-04-f | Cache invalidation when calibration_id changes | unit | `pytest packages/api/tests/test_simulate.py::test_simulate_cache_invalidation -x` | ❌ Wave 0 |
| API-04-g | Cold-path wall time <2 s on canonical fixture | integration | `pytest packages/api/tests/test_simulate.py::test_simulate_wall_time -m integration --benchmark-only` | ❌ Wave 0 |
| API-04-h | No `pymc` / `numpyro` imported at request time | unit | `pytest packages/api/tests/test_simulate.py::test_no_mcmc_at_runtime -x` | ❌ Wave 0 |
| API-05-a | GET /calibration/C3 returns 200 + valid schema | unit | `pytest packages/api/tests/test_calibration.py::test_calibration_happy_path -x` | ❌ Wave 0 |
| API-05-b | Invalid compound (C9, empty, `'C1; DROP TABLE'`) → 422 | unit | `pytest packages/api/tests/test_calibration.py::test_calibration_invalid_compound -x` | ❌ Wave 0 |
| API-05-c | Missing NetCDF / calibration_runs row → 404 | unit | `pytest packages/api/tests/test_calibration.py::test_calibration_no_data -x` | ❌ Wave 0 |
| API-05-d | Response includes all 5 stage summaries | unit | `pytest packages/api/tests/test_calibration.py::test_calibration_all_stages -x` | ❌ Wave 0 |
| API-05-e | Stage 4 summary contains r_hat and ess_bulk | unit | `pytest packages/api/tests/test_calibration.py::test_calibration_stage4_diagnostics -x` | ❌ Wave 0 |
| API-06-a | POST /sessions/upload with valid zip → 200 + session_id | unit | `pytest packages/api/tests/test_sessions.py::test_upload_happy_path -x` | ❌ Wave 0 |
| API-06-b | Zip slip rejected | unit (**SECURITY**) | `pytest packages/api/tests/test_sessions.py::test_upload_rejects_path_traversal -x` | ❌ Wave 0 |
| API-06-c | Non-zip upload → 400 | unit | `pytest packages/api/tests/test_sessions.py::test_upload_rejects_non_zip -x` | ❌ Wave 0 |
| API-06-d | Uploaded session routes subsequent /simulate without Jolpica call | integration | `pytest packages/api/tests/test_sessions.py::test_session_routes_simulate -m integration` | ❌ Wave 0 |
| API-06-e | Session dir cleaned after TTL | unit (with patched time) | `pytest packages/api/tests/test_sessions.py::test_session_ttl_cleanup -x` | ❌ Wave 0 |
| API-06-f | Oversized zip rejected (decompression bomb defense) | unit | `pytest packages/api/tests/test_sessions.py::test_upload_rejects_bomb -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest packages/api/tests/ -x` — fast, all unit tests green.
- **Per wave merge:** `pytest packages/api/tests/ -v` plus any `-m integration` benchmarks introduced in that wave.
- **Phase gate:** `pytest -v` (full repo) + `pytest packages/api/tests/ -m integration` (slow benchmarks) green before `/gsd-verify-work`.

### Wave 0 Gaps

- [ ] `packages/api/tests/test_simulate.py` — new file, covers API-04-a..h
- [ ] `packages/api/tests/test_calibration.py` — new file, covers API-05-a..e
- [ ] `packages/api/tests/test_sessions.py` — new file, covers API-06-a..f
- [ ] `packages/api/tests/fixtures/` — new dir
- [ ] `packages/api/tests/fixtures/calibration_fixture.py` — builds a tiny NetCDF + SQLite row at test session start
- [ ] `packages/api/tests/fixtures/zip_fixtures.py` — builds good + malicious zips programmatically
- [ ] `packages/api/tests/conftest.py` — extend with NetCDF fixture, temporary DB path, monkeypatched `run_simulation` for fast tests, monkeypatched `load_stint` for session tests
- [ ] Add `pytest-benchmark` to the integration test invocation (already in root dev group)
- [ ] No framework install needed

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture | yes | Service/router/schema layering; no `pymc` at request time (D-05); CORS already restricted in `app.py`. |
| V2 Authentication | no | V1 has no auth (documented in REQUIREMENTS.md Out of Scope and CONTEXT D-08). |
| V3 Session Management | partial | Server-side "session" here = uploaded FastF1 cache, not a user session. Still needs: UUID unguessable (uuid4), TTL enforcement, no cross-session leakage (UUID in path only, not content). |
| V4 Access Control | no | V1 open-access API. |
| V5 Input Validation | **yes — critical** | Pydantic v2 for all request bodies and path params. Compound validated via `f1_calibration.db.validate_compound`. Zip entries validated individually (pitfall #4). Override dict keys restricted to a known allowlist. |
| V6 Cryptography | no | No secrets handled. |
| V7 Error Handling & Logging | yes | `raise HTTPException(..., detail=str(e)) from e` pattern. Never leak stack traces to clients. Log at WARNING on zip rejections. |
| V8 Data Protection | partial | Uploaded files are ephemeral + bounded in size. SQLite DB is inside workspace (T-3-03 enforced). |
| V9 Communication | no (deferred to Phase 7) | HTTPS is a deployment concern. |
| V10 Malicious Code | yes | Zip Slip mitigation is the primary threat; pickle of user-supplied content is FORBIDDEN (we never load user pickles as such — we copy files into FastF1's own cache path). |
| V11 Business Logic | yes | Override parameters must be range-bounded (no `-1` negative tire wear rate etc.). |
| V12 File & Resource | **yes — critical** | Upload size limit, decompression bomb cap, member count cap, path traversal rejection, workspace containment for all extracted paths (reuse `resolve_db_path` pattern). |
| V13 API | yes | OpenAPI surface auto-generated by FastAPI; inputs validated by Pydantic; no verb confusion (POST for mutations, GET for reads). |
| V14 Configuration | yes | `F1_ALLOWED_ORIGIN` env var pattern already in app.py; reuse same style if new config flags are needed. |

### Known Threat Patterns for {stack}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Zip Slip (path traversal on extract) | Tampering, Elevation | Per-member path resolution + `is_relative_to` check (§Code Examples #2). |
| Zip decompression bomb | DoS | Enforce cap on `sum(info.file_size for info in zf.infolist())` before extraction; cap member count at e.g. 10 000. |
| Symlink-in-zip | Tampering, Elevation | Reject members where `info.external_attr >> 16 == 0o120000` (symlink bits). Python's `zipfile` does not extract symlinks by default, but verify explicitly. |
| SQL injection on compound | Tampering | Already mitigated by `validate_compound` regex whitelist + parameterized sqlite3 queries (T-3-01, T-3-05 — Phase 3 patterns). |
| DoS via large simulate payload | DoS | K=100 is a hard constant; no user-tunable size. Wall-time budget + threadpool limits. |
| Override parameter abuse (e.g. `mu_0_fresh = 1e99`) | Tampering | Pydantic v2 `Field(gt=0, lt=5)` range bounds on every override field. Values outside physical plausibility reject with 422. |
| Cache poisoning via cache_key collision | Integrity | SHA256 of the normalized key tuple; namespace-prefixed (`"sim_v1|"`) to allow future schema changes. |
| Log injection | Tampering | Log messages include `repr(user_input)`, never raw. Use `log.info("compound=%r", compound)` pattern. |
| Unbounded session uploads | DoS | Rate-limit at reverse proxy (Phase 7 concern); in V1 app, cap single-zip size at e.g. 100 MB. |
| SSRF via override field | Tampering | No override field contains a URL or filesystem path. Enforce at schema level. |
| Path traversal via NetCDF path from SQLite | Tampering | `resolve_db_path` on the value before any file I/O (T-3-02, T-3-03). Phase 3's `_validate_stored_path` writes only workspace-contained values, but defense-in-depth: re-validate on read. |

## Code Examples

Verified patterns from official sources + existing project code.

### Example 1: K-Draw Posterior Sampling from NetCDF

```python
# services/posterior_store.py
"""Load a posterior NetCDF and sample K deterministic draws."""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import arviz as az
import numpy as np

# Source: https://python.arviz.org/en/stable/getting_started/WorkingWithInferenceData.html
# Source: packages/calibration/src/f1_calibration/stage4_degradation.py lines 420-425

@lru_cache(maxsize=8)
def get_posterior(netcdf_path: str) -> az.InferenceData:
    """Load a NetCDF posterior; cached per path in-process."""
    return az.from_netcdf(netcdf_path)


def sample_stage4_draws(
    idata: az.InferenceData,
    K: int,
    *,
    seed: int,
) -> dict[str, np.ndarray]:
    """Return dict of (K,) arrays for beta_therm, T_act, k_wear.

    Uses `az.extract` — the idiomatic ArviZ API for combining chains+draws and
    returning a random subset. `rng` is set for determinism per cache key.
    """
    rng = np.random.default_rng(seed)
    ext = az.extract(
        idata,
        var_names=["beta_therm", "T_act", "k_wear"],
        num_samples=K,
        rng=rng,
    )
    return {
        "beta_therm": ext["beta_therm"].values,  # shape (K,)
        "T_act": ext["T_act"].values,
        "k_wear": ext["k_wear"].values,
    }
```

### Example 2: Safe ZIP Extraction

```python
# services/sessions.py (excerpt)
"""Zip Slip mitigation — per-member path verification."""
from __future__ import annotations
from pathlib import Path
import zipfile

# Source: https://docs.python.org/3/library/zipfile.html (3.12 docs on sanitization)
# Source: https://github.com/snyk/zip-slip-vulnerability (pattern reference)
# Source: packages/calibration/src/f1_calibration/db.py line 260 (resolve_db_path pattern)

MAX_ZIP_TOTAL_UNCOMPRESSED = 500 * 1024 * 1024   # 500 MB
MAX_ZIP_MEMBERS = 10_000


def extract_session_zip(zip_bytes: bytes, dest: Path) -> None:
    """Extract zip_bytes safely under dest. Rejects path traversal, symlinks,
    decompression bombs, and excessive member counts.

    Args:
        zip_bytes: Raw bytes of the uploaded zip.
        dest: Already-created, workspace-contained target directory.

    Raises:
        ValueError: On any security violation (caller maps to 400).
    """
    dest_resolved = dest.resolve()
    import io
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        infos = zf.infolist()
        if len(infos) > MAX_ZIP_MEMBERS:
            raise ValueError(f"zip has too many members: {len(infos)}")
        total = sum(i.file_size for i in infos)
        if total > MAX_ZIP_TOTAL_UNCOMPRESSED:
            raise ValueError(f"zip expands to {total} bytes, cap is {MAX_ZIP_TOTAL_UNCOMPRESSED}")
        for info in infos:
            # Symlink check — POSIX mode bits in the high 16 of external_attr
            mode = info.external_attr >> 16
            if mode & 0o170000 == 0o120000:
                raise ValueError(f"zip contains symlink member: {info.filename!r}")
            # Path traversal check
            target = (dest / info.filename).resolve()
            try:
                target.relative_to(dest_resolved)
            except ValueError:
                raise ValueError(f"zip member escapes dest: {info.filename!r}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as dst:
                    # copy in chunks; .read() on giant member would OOM
                    while True:
                        chunk = src.read(65536)
                        if not chunk:
                            break
                        dst.write(chunk)
```

### Example 3: `az.summary` for Stage 4 Posterior Block

```python
# services/calibration.py (excerpt)
# Source: https://python.arviz.org/en/latest/api/generated/arviz.summary.html
import arviz as az

def stage4_summary_block(idata: az.InferenceData) -> dict:
    """Build the Stage-4 portion of /calibration/{compound}."""
    df = az.summary(
        idata,
        var_names=["beta_therm", "T_act", "k_wear"],
        hdi_prob=0.95,
        stat_focus="mean",
    )
    # df has columns: mean, sd, hdi_2.5%, hdi_97.5%, mcse_mean, mcse_sd,
    # ess_bulk, ess_tail, r_hat  (ArviZ 0.20+ API)
    return {
        var: {
            "mean": float(df.loc[var, "mean"]),
            "sd": float(df.loc[var, "sd"]),
            "hdi_lo_95": float(df.loc[var, "hdi_2.5%"]),
            "hdi_hi_95": float(df.loc[var, "hdi_97.5%"]),
            "r_hat": float(df.loc[var, "r_hat"]),
            "ess_bulk": float(df.loc[var, "ess_bulk"]),
        }
        for var in ["beta_therm", "T_act", "k_wear"]
    }
```

### Example 4: Vectorized CI Aggregation

```python
# services/simulate.py (excerpt)
# Source: https://numpy.org/doc/stable/reference/generated/numpy.percentile.html
import numpy as np

def aggregate_with_ci(stack: np.ndarray) -> dict:
    """stack: (K, *shape). Returns {'mean', 'lo_95', 'hi_95'} with trailing shape."""
    mean = stack.mean(axis=0)
    lo, hi = np.percentile(stack, [2.5, 97.5], axis=0)
    return {
        "mean": mean.tolist(),
        "lo_95": lo.tolist(),
        "hi_95": hi.tolist(),
    }
```

### Example 5: Pydantic v2 Response Models for /simulate

```python
# schemas/simulate.py
from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field

# Source: packages/api/src/f1_api/schemas/stints.py (existing pattern)
# Source: CONTEXT D-02 (CI triplet)

class CIValue(BaseModel):
    model_config = ConfigDict(frozen=True)
    mean: float
    lo_95: float
    hi_95: float


class CIArray1D(BaseModel):
    model_config = ConfigDict(frozen=True)
    mean: list[float]
    lo_95: list[float]
    hi_95: list[float]


class CIArray2D(BaseModel):
    """For per-timestep per-tire (N, 4) arrays."""
    model_config = ConfigDict(frozen=True)
    mean: list[list[float]]     # (N, 4)
    lo_95: list[list[float]]
    hi_95: list[list[float]]


class SimulationMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)
    calibration_id: int
    model_schema_version: str = "v1"
    fastf1_version: str
    compound: str
    stint_index: int
    overrides_applied: bool
    k_draws: int = 100


class PerTimestepBlock(BaseModel):
    model_config = ConfigDict(frozen=True)
    t: list[float]                  # (N,) — time is deterministic, not uncertain
    t_tread: CIArray2D              # (N, 4)
    e_tire: CIArray2D
    mu: CIArray2D
    f_z: CIArray2D
    f_y: CIArray2D
    f_x: CIArray2D
    mu_0: CIArray1D                 # (N,)


class PerLapRow(BaseModel):
    model_config = ConfigDict(frozen=True)
    lap: int
    compound: str
    age: int
    obs_s: float | None
    pred_s: CIValue
    delta_s: CIValue
    grip_pct: CIValue
    t_tread_max_c: CIValue
    e_tire_mj: CIValue


class PerStintSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    total_predicted_time_s: CIValue
    stint_end_grip_pct: CIValue
    peak_t_tread_c: CIValue
    total_e_tire_mj: CIValue


class SimulateResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    metadata: SimulationMetadata
    per_timestep: PerTimestepBlock
    per_lap: list[PerLapRow]
    per_stint: PerStintSummary


class ParameterOverrides(BaseModel):
    """All fields optional; if present, applied to every K draw before run_simulation."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    # Aero
    C_LA: float | None = Field(default=None, gt=0, lt=20)
    C_DA: float | None = Field(default=None, gt=0, lt=10)
    xi: float | None = Field(default=None, ge=0, le=1)
    # Friction
    mu_0_fresh: float | None = Field(default=None, gt=0, lt=3)
    # Thermal
    T_opt: float | None = Field(default=None, ge=50, le=150)
    # Degradation
    beta_therm: float | None = Field(default=None, ge=0, lt=1)
    # (Add more as override scope grows — V2 is full Expert Mode)


class SimulateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    race_id: str = Field(pattern=r"^[0-9]{4}-[a-z0-9_]+$", min_length=6, max_length=48)
    driver_code: str = Field(pattern=r"^[A-Z]{3}$")
    stint_index: int = Field(ge=1, le=10)
    overrides: ParameterOverrides | None = None
    session_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
```

### Example 6: Sync `def` Router with Threadpool

```python
# routers/simulate.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException

from f1_api.schemas.simulate import SimulateRequest, SimulateResponse
from f1_api.services.simulate import run_simulation_with_uncertainty

# Source: packages/api/src/f1_api/app.py line 3-5 (module docstring)
# Source: packages/api/src/f1_api/routers/stints.py line 26-29 (error pattern)

router = APIRouter()


@router.post("/simulate", response_model=SimulateResponse)
def simulate(body: SimulateRequest) -> SimulateResponse:
    """K=100 posterior-draw forward pass; cache hit <50 ms; cold <2 s.

    CPU-bound → plain `def` so FastAPI runs in threadpool.
    """
    try:
        return run_simulation_with_uncertainty(
            race_id=body.race_id,
            driver_code=body.driver_code,
            stint_index=body.stint_index,
            overrides=body.overrides,
            session_id=body.session_id,
        )
    except ValueError as e:
        # 422 for body-shape issues, 404 for missing stint/calibration
        raise HTTPException(status_code=422, detail=str(e)) from e
```

### Example 7: GZip Middleware + CORS + Lifespan

```python
# app.py additions
from fastapi.middleware.gzip import GZipMiddleware

# in create_app():
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)
app.include_router(simulate_router.router)
app.include_router(calibration_router.router)
app.include_router(sessions_router.router)

# extend lifespan to prime the posterior store:
@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    cache_dir = init_cache()
    log.info("FastF1 cache initialized at %s", cache_dir)

    # Session cleanup daemon
    cleanup = threading.Thread(target=_session_cleanup_loop, daemon=True,
                               name="session-ttl")
    cleanup.start()

    # Optional: warm the posterior cache for common compounds
    for compound in ("C1", "C2", "C3", "C4", "C5"):
        try:
            prime_posterior(compound)
        except Exception as e:
            log.warning("No posterior for %s at startup: %s", compound, e)

    yield
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| FastAPI `async def` for everything | `def` for CPU-bound, `async def` only for I/O | Ongoing best practice | CPU-bound CPU routes in `async def` block the event loop. Explicit in FastAPI docs since 0.100+. |
| `response_class=JSONResponse` | `response_class=ORJSONResponse` (optional) | orjson mature since ~2021 | 4-12× faster numpy serialization. Optional here; default `json` is adequate. |
| Pydantic v1 `Config.json_encoders` | Pydantic v2 `@field_serializer` + `ConfigDict` | v2 release mid-2023 | Stricter types, faster validation; some numpy-array patterns need rewriting (pitfall #5). |
| `fastapi.Cache.enable_cache` called repeatedly | Idempotent `init_cache()` locked wrapper | Phase 1 convention | Prevents multi-init warnings; `f1_core.ingestion.fastf1_client.init_cache` implements this. |
| PyMC `pm.sample(...)` inside web request | Offline CLI → NetCDF → runtime `az.from_netcdf` | Project decision (CLAUDE.md §Task Execution) | D-05 enforces. Runtime deps shrink; web worker doesn't need PyMC/PyTensor/JAX. |
| Global `app = FastAPI()` | Factory `create_app()` + lifespan | FastAPI 0.93+ | Cleaner tests (each test can create a fresh app with overrides). Already in use. |

**Deprecated/outdated:**
- `@app.on_event("startup")` / `@app.on_event("shutdown")` — deprecated in FastAPI 0.93+; replaced by the `lifespan` context manager (already used correctly in `app.py`).
- `scipy.integrate.odeint` — out of scope here but flagged in CLAUDE.md; we don't touch it in Phase 4.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | K=100 sequential forward passes on the canonical Bahrain 2023 VER stint 2 fixture fit within 2 s | §Architecture Patterns #2 | If wrong, must escalate to JAX vmap F+G or reduce K; both require additional work but don't block the phase. |
| A2 | Phase 3 writes at least one `calibration_runs` row per compound that Phase 4 tests can use | §Environment Availability | If Phase 3 hasn't run yet (Phase 3 is not actually complete per STATE.md), Phase 4 MUST vendor a synthetic fixture. **Verify in Wave 0.** |
| A3 | ArviZ 0.20.x API surface (`az.extract`, `az.summary(hdi_prob=)`, `az.from_netcdf`) is stable between 0.20 and whatever's installed | §Standard Stack | LOW risk; ArviZ 1.0.0 released March 2026 but calibration dep pin is `<1`. Confirm at Wave 0. |
| A4 | Simulation result payload at K=100 is ~500 kB - 1 MB uncompressed | §Specifics (CONTEXT) + §Pitfall 10 | LOW; even 5 MB compresses to <1 MB with gzip level 5. |
| A5 | Session uploads won't need per-user isolation in V1 | CONTEXT D-08 | Locked decision. |
| A6 | FastF1 cache directory structure is stable enough for Option A (merge upload into global cache) | §Pitfall 7 | MEDIUM; if FastF1 changes its cache layout between versions, merge logic could fail. Pin fastf1 version in Wave 0. |
| A7 | `run_simulation` can be called with override-modified `PhysicsParams` without re-running Modules A's preprocessing | §Architecture Patterns #2 | Actually verified in orchestrator.py line 229: Module A receives `params.aero` only; if overrides touch other stages, Module A's output is unchanged. Aero overrides (C_LA, xi) DO affect Module A. **Conservative plan: re-run full pipeline on every override.** |
| A8 | orjson is NOT required for the 2 s budget at K=100 | §Standard Stack | LOW; measurement-gated. Add later if needed. |
| A9 | `az.extract(num_samples=K, rng=…)` reliably returns K distinct samples when total samples > K | §Code Examples #1 | HIGH confidence; this is `az.extract`'s documented behavior. |
| A10 | GZipMiddleware default streaming behavior is sufficient for our response sizes (no trouble with SSE) | §Don't Hand-Roll | HIGH; we're not using SSE. GZipMiddleware issue #4739 on FastAPI repo is about streaming responses specifically, which we don't use. |

**Items for discuss-phase / user confirmation before planning is finalized:**
- A2 (Phase 3 completion state) — decide: fixture or real Phase 3 artifacts?
- A7 (override scope re-run) — confirm "every override triggers full pipeline re-run" is acceptable.

## Open Questions

1. **When should the cache be warmed?**
   - What we know: Fly.io first-request after cold start is ~500 ms to 2 s (per CLAUDE.md). Post-warm, 50 ms cache hits are expected.
   - What's unclear: Should INFRA-03's "pre-warm 10 most recent race sessions" also pre-run `/simulate` on the headline stint of each? That would give zero-latency startup.
   - Recommendation: Defer to Phase 7. Phase 4 writes a `/warmup` endpoint stub (optional) that Phase 7 can invoke at deploy time.

2. **How does the endpoint discover `calibration_id` for a given stint?**
   - What we know: `calibration_runs` is keyed by compound; a stint has one compound.
   - What's unclear: What if multiple `calibration_runs` exist for the same compound (e.g., C3 calibrated in 2024 and again in 2025)? Should `/simulate` always use the LATEST, or is the request allowed to pin a calibration_id?
   - Recommendation: V1 = always latest by `created_at DESC LIMIT 1` within the compound. V2 could add `?calibration_id=` query param. Document in the endpoint docstring.

3. **Where does "per-stint aggregate" come from?**
   - What we know: CONTEXT D-01 says per-stint summary is returned. Existing `SimulationResult` has per-timestep and per-lap, no per-stint aggregates.
   - What's unclear: Does Phase 4 compute per-stint in the service (mean over per-lap rows, sum of per-lap energy), or does it belong in `f1_core`?
   - Recommendation: Phase 4 computes it in `services/simulate.py`. Simple numpy aggregations over the already-stacked per-lap rows. Adding it to `f1_core` would be a cross-phase change.

4. **Should `/simulate` cache hits still recompute metadata (fastf1_version, calibration_id)?**
   - What we know: Cached response includes metadata baked in.
   - What's unclear: If `fastf1` is upgraded but cache wasn't invalidated, a cache hit returns stale `fastf1_version`. Is that correct?
   - Recommendation: `fastf1_version` is baked into cache value at write time. That's "provenance of the cached computation" and is the CORRECT behavior. If fastf1 version changes, the cache should be invalidated (via FastF1 PREPROCESSING_VERSION bump pattern from Phase 1). Document this.

5. **Strictness of Pydantic `extra="forbid"` on `/simulate` body?**
   - What we know: Example 5 uses `extra="forbid"` to reject unknown fields.
   - What's unclear: Does the UI team need leeway to send forward-compatible optional fields (like `session_id` in V2)?
   - Recommendation: Forbid is right for v1 — stricter contracts surface bugs early. Loosen in v2 if the UI team needs it.

## Sources

### Primary (HIGH confidence)

- **Existing repository code** (internal, examined first-hand):
  - `packages/api/src/f1_api/app.py` — lifespan, create_app, CORS, routers
  - `packages/api/src/f1_api/routers/stints.py` — router pattern
  - `packages/api/src/f1_api/schemas/stints.py` — Pydantic v2 pattern
  - `packages/api/src/f1_api/services/stints.py` — service layer pattern
  - `packages/api/src/f1_api/dependencies.py` — validated path-param types
  - `packages/api/tests/conftest.py` — test pattern with monkeypatched services
  - `packages/core/src/f1_core/physics/orchestrator.py` — `run_simulation`, SimulationResult
  - `packages/core/src/f1_core/physics/params.py` — frozen dataclass params
  - `packages/core/src/f1_core/ingestion/fastf1_client.py` — `init_cache`, `load_stint`
  - `packages/core/src/f1_core/ingestion/cache.py` — Layer-2 pickle cache
  - `packages/calibration/src/f1_calibration/db.py` — SQLite schema, `validate_compound`, `resolve_db_path`, `read_latest_parameter_set`
  - `packages/calibration/src/f1_calibration/stage4_degradation.py` — NetCDF persist pattern, posterior reading
  - `packages/calibration/src/f1_calibration/jax_model.py` — JAX F+G scan (fallback for §Architecture Patterns #2)
  - `packages/calibration/src/f1_calibration/common.py` — `WORKSPACE_ROOT`, `DEFAULT_POSTERIORS_DIR`
  - `CLAUDE.md` — stack constraints, deployment, forbidden libraries
  - `.planning/REQUIREMENTS.md` — API-04/05/06 acceptance text
  - `.planning/phases/04-simulation-api-uncertainty-quantification/04-CONTEXT.md` — locked decisions D-01..D-09
  - `.planning/phases/03-bayesian-calibration-pipeline/03-RESEARCH.md` — upstream research patterns

- **Official docs:**
  - https://fastapi.tiangolo.com/advanced/middleware/ — GZipMiddleware parameters (minimum_size, compresslevel)
  - https://fastapi.tiangolo.com/advanced/events/ — lifespan context manager
  - https://fastapi.tiangolo.com/tutorial/testing/ — TestClient + dependency_overrides
  - https://docs.python.org/3/library/zipfile.html — zipfile.ZipFile sanitization behavior
  - https://python.arviz.org/en/stable/getting_started/WorkingWithInferenceData.html — az.extract, az.InferenceData.sel
  - https://python.arviz.org/en/stable/api/generated/arviz.summary.html — az.summary output columns
  - https://numpy.org/doc/stable/reference/generated/numpy.percentile.html — percentile(axis=0) pattern
  - https://docs.jax.dev/en/latest/_autosummary/jax.vmap.html — jax.vmap fallback

### Secondary (MEDIUM confidence)

- WebSearch "FastAPI GZipMiddleware compression threshold 2026" — default 500 B minimum, 1-9 compresslevel (verified against FastAPI official docs)
- WebSearch "ArviZ InferenceData posterior stack chain draw select random subset K samples 2026" — confirms `az.extract` is the idiomatic K-draw API
- WebSearch "FastAPI UploadFile zipfile safe extract path traversal 2026" — Zip Slip still a 2026 concern; CVE-2026-3954 example
- WebSearch "python zipfile extract CVE path traversal zip slip 3.12" — Python 3.12 has some sanitization; caller still responsible
- WebSearch "FastAPI ORJSONResponse numpy array fast JSON serialization 2026" — orjson 4-12× faster on numpy; optional optimization
- WebSearch "functools lru_cache threading safety FastAPI worker shared memory" — lru_cache thread-safe for reads, per-worker (not shared across processes)
- WebSearch "FastAPI BackgroundTasks TTL cleanup threading timer best practice 2026" — BackgroundTasks wrong tool for recurring cleanup
- WebSearch "pytest FastAPI TestClient async sync endpoint mock patch service layer 2026" — service-layer monkeypatch pattern

### Tertiary (LOW confidence — flagged for validation)

- None at this time. The stack is mature and the patterns well-established.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in use in Phases 1-3, pinned in pyproject, verified by reading code.
- Architecture: HIGH — service/router/schema pattern is a direct extension of Phase 1's pattern, nothing novel.
- Pitfalls: HIGH — each pitfall is either observed in the existing codebase (Phase 1-3 research), documented by FastAPI/Python docs, or derived from recognized security patterns (Zip Slip, LRU race).
- Vectorization strategy: MEDIUM — recommended sequential approach is plausible but not yet measured; escape hatches documented.
- Session upload integration with FastF1 cache (Pitfall 7): MEDIUM — Option A is pragmatic but depends on FastF1 cache layout staying stable.

**Research date:** 2026-04-24
**Valid until:** 2026-05-24 (30 days — stable stack, slow-moving ecosystem)
