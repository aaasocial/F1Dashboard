# Roadmap: F1 Tire Degradation Analyzer

**Created:** 2026-04-23
**Granularity:** standard
**Parallelization:** enabled

---

## Overview

Seven phases deliver the v1 stint analyzer: a browser-based physics-informed tire degradation model over public FastF1 telemetry, with Bayesian confidence intervals and a six-zone data-dense dashboard.

- **Total phases:** 7
- **v1 requirements:** 49
- **Coverage:** 49/49 (100%)

**Phase order is driven by architectural dependencies, not feature priority:**
1. Data integrity + typed module contracts land first — they unblock physics, calibration, and frontend in parallel.
2. Physics model is implemented against its own contracts with unit tests (no frontend coupling).
3. Calibration runs offline (CLI) — once posteriors are persisted to NetCDF, `/simulate` becomes a fast forward pass.
4. The API layer then wires real physics + posteriors into the four core endpoints.
5. Frontend is built against the real API (or its stub during parallel work), delivering all six dashboard zones.
6. Interactions, exports, and URL-hash state land once the visualization substrate is stable.
7. Deployment hardens the Fly.io + Vercel split and pre-warms the cache.

---

## Phases

- [x] **Phase 1: Foundation, Data Pipeline & Module Contracts** — FastF1 ingestion, data integrity, curvature + gear inference, typed dataclass contracts, API stub endpoints
- [x] **Phase 2: Physics Model (Modules A–G)** — Seven-module forward simulation, strict A→B→C→D→E→F→G sequence, unit-tested physical invariants, ~100 ms/stint benchmark
- [x] **Phase 3: Bayesian Calibration Pipeline** — Five-stage offline CLI (aero → friction → thermal → degradation → validation), PyMC+NumPyro for Stage 4, ArviZ NetCDF + SQLite versioning, baseline linear model sanity check
- [x] **Phase 4: Simulation API & Uncertainty Quantification** — POST /simulate wires physics + posteriors, K=100 vectorized CI draws, <2 s end-to-end, session upload endpoint, calibration summary endpoint
- [x] **Phase 5: Dashboard Shell & Visualization** — React+TypeScript+visx shell, six-zone layout, cascade pickers, multi-chart panel with CI bands, tire array, track map, status log, linked hover
- [x] **Phase 6: Playback, Interactions & Sharing** — Transport bar + scrub, keyboard shortcuts, right-click export (PNG/SVG/CSV), clipboard copy, URL hash state, drag-and-drop session upload, provenance footer
- [ ] **Phase 7: Deployment & Operations** — Fly.io backend with persistent volume, Vercel frontend, CORS hardening, healthz, cache pre-warm with 10 recent sessions

---

## Phase Details

### Phase 1: Foundation, Data Pipeline & Module Contracts
**Goal:** A developer can fetch, validate, and annotate any 2022–present FastF1 stint, and all seven physics-module interfaces are typed and importable — enabling physics, calibration, and frontend work to proceed in parallel.
**Depends on:** Nothing (first phase)
**Requirements:** DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, PHYS-08 (contract/protocol portion), PHYS-09 (state-object portion), API-01, API-02, API-03
**Success Criteria** (what must be TRUE):
  1. Running the CLI `fetch <race_id> <driver_id>` retrieves a stint's telemetry via FastF1/Jolpica, writes to the two-layer disk cache, and a second invocation returns cached bytes without network I/O.
  2. `data_integrity.py` detects throttle=104 sentinels, NaN lap times, mislabeled compounds, and missing positions on a corrupted fixture stint, emits a quality score, and marks the stint as warn-but-simulate or exclude-from-calibration appropriately.
  3. Per-circuit curvature map κ(s) and per-team gear-ratio inference (8 ratios + final drive) are computed from reference laps and cached; a unit test confirms curvature stability across two seasons of the same circuit.
  4. Each lap of every fetched stint is annotated with (compound→C1–C5, tire age, fuel estimate, weather, in/out-lap flag, SC/VSC flag) and excluded laps are correctly omitted from the degrading-lap view.
  5. The seven typed dataclass contracts (KinematicState, WheelLoads, ContactPatch, SlipState, ThermalState, DegradationState, SimulationState) are importable from a single module, each implementing the `PhysicsModule` protocol, and a placeholder module passes a contract-compliance test.
  6. FastAPI serves `GET /races`, `GET /races/{race_id}/drivers`, `GET /stints/{race_id}/{driver_id}` against real cached data with correct response schemas.
**Plans:** 5 plans
- [x] 01-01-PLAN.md — uv workspace scaffold (3 packages, ruff, .gitignore, Python 3.12)
- [x] 01-02-PLAN.md — seven @dataclass contracts + PhysicsModule Protocol + QualityReport (PHYS-08, PHYS-09)
- [x] 01-03-PLAN.md — FastF1 ingestion + two-layer cache + canonical fixture + fetch CLI (DATA-01, DATA-02)
- [x] 01-04-PLAN.md — data integrity + stint annotation + curvature + gear inference (DATA-03, DATA-04, DATA-05, DATA-06)
- [x] 01-05-PLAN.md — FastAPI endpoints /races, /races/{id}/drivers, /stints/{race_id}/{driver_id} (API-01, API-02, API-03)

### Phase 2: Physics Model (Modules A–G)
**Goal:** A user running the simulation CLI against a real stint sees physically-valid per-lap, per-tire predictions (grip, temperatures, cumulative energy, degradation) computed by all seven modules in strict sequence, with every physical invariant verified by unit tests.
**Depends on:** Phase 1
**Requirements:** PHYS-01, PHYS-02, PHYS-03, PHYS-04, PHYS-05, PHYS-06, PHYS-07, PHYS-08 (invariant tests), PHYS-09 (execution sequence)
**Success Criteria** (what must be TRUE):
  1. Running `simulate --stint <id>` with nominal parameters produces a lap-by-lap result where ΣF_z equals total weight plus aerodynamic downforce within tolerance, ΣF_y equals M·a_lat within tolerance, and μ(T_opt, p̄₀) returns μ₀ exactly.
  2. A single forward simulation of a full-length stint (≈30 laps, ~4 Hz) completes in under 200 ms on a developer laptop, measured by a benchmark test committed to CI.
  3. Module E correctly clips Θᵢ=1 and emits an event in the status log when force demand exceeds available grip on at least one synthetic over-demand test case.
  4. Thermal ODE forward-Euler integration at Δt=0.25 s is numerically stable across a 60-lap synthetic stint (no temperature divergence, steady-state matches analytical prediction).
  5. All seven modules execute in the strict A→B→C→D→E→F→G order per timestep with state carried in an explicit `SimulationState` object — a linter/test rejects any inner-timestep iteration or mutation of prior-module outputs.
  6. Cumulative tire energy is monotonically non-decreasing, tread thickness is monotonically non-increasing, and the Arrhenius thermal-aging update produces a μ₀(t) trajectory that declines under sustained elevated T_tread.
**Plans:** 7 plans
- [x] 02-01-PLAN.md — infrastructure: deps (typer/pytest-benchmark/hypothesis), params dataclasses, defaults, frozen contracts, test stubs
- [x] 02-02-PLAN.md — Module A (kinematics preprocessor: Savgol a_long, a_lat = V²κ, ψ, V_sx) — PHYS-01
- [x] 02-03-PLAN.md — Modules B + C (vertical loads with ΣF_z closure + force distribution with ΣF_y = M·a_lat) — PHYS-02, PHYS-03
- [x] 02-04-PLAN.md — Modules D + E (Hertzian friction + brush-model slip inversion + event log cap) — PHYS-04, PHYS-05
- [x] 02-05-PLAN.md — Modules F + G (three-node thermal ODE + Arrhenius aging + wear) — PHYS-06, PHYS-07
- [x] 02-06-PLAN.md — Orchestrator (strict A→G sequence) + f1-simulate Typer CLI — PHYS-08, PHYS-09
- [x] 02-07-PLAN.md — AST architecture tests + pytest-benchmark + CI workflow + human-verify checkpoint

### Phase 3: Bayesian Calibration Pipeline
**Goal:** A calibration engineer can run `f1-calibrate run-all --compound C3` end-to-end and obtain versioned posterior parameter sets (NetCDF) with passing convergence diagnostics (r̂ < 1.01, ESS > 400) and lower held-out RMSE than a linear baseline — completing the offline path that makes `/simulate` a pure forward pass.
**Depends on:** Phase 2
**Requirements:** CALIB-01, CALIB-02, CALIB-03, CALIB-04, CALIB-05, CALIB-06, CALIB-07, CALIB-08
**Success Criteria** (what must be TRUE):
  1. Running the CLI `calibrate stage1 --year 2024` fits C_LA, C_DA, ξ within ±10 % / ±15 % of expected values on a validation fixture; Stage 2 fits μ₀^fresh within ±5 % and n within ±0.05; Stage 3 fits T_opt within ±10 °C and σ_T within ±5 °C.
  2. Stage 4 MCMC (PyMC 5.x + NumPyro JAX backend) achieves r̂ < 1.01 and ESS > 400 for all sampled parameters on a 20-race training slice; prior predictive checks and simulation-based calibration (SBC) on synthetic data pass before real-data fitting runs.
  3. A baseline linear degradation model (lap-time vs tire age per compound per stint) is fitted as a sanity check, and the physics model achieves a meaningfully lower per-lap time RMSE on the 20 % held-out set.
  4. Stage 5 cross-validation reports per-lap time RMSE < 0.3 s on calibrated compounds, with a per-circuit breakdown emitted as a CSV artifact.
  5. Fitted posteriors are persisted as ArviZ InferenceData NetCDF files; a row in the `calibration_runs` SQLite table records (compound, season, timestamp, held-out RMSE, git SHA, parameter_set_id); every simulation result produced afterwards carries a calibration_id tag traceable back to that row.
**Plans:** 8 plans
- [x] 03-01-PLAN.md — Wave 0 scaffold: pyproject deps, SQLite schema + is_latest trigger, compound_map, training iterator, priors, conftest (CALIB-07)
- [x] 03-02-PLAN.md — Stage 1 aero fit (scipy.optimize.least_squares) + Stage 2 friction fit (log-log regression) — CALIB-01, CALIB-02
- [x] 03-03-PLAN.md — Linear baseline (sklearn LinearRegression) + SBC harness with Pitfall 7 joint-sampling — CALIB-06, CALIB-08
- [x] 03-04-PLAN.md — Stage 3 thermal calibration (forward-integrated module_f, Pitfall 2 bounds) — CALIB-03
- [x] 03-05-PLAN.md — JAX rewrite of Modules F + G (jax.lax.scan, x64 enforced, parity test vs NumPy to 1e-6) — CALIB-04
- [x] 03-06-PLAN.md — Stage 4 PyMC + NumPyro MCMC + pytensor JAX Op bridge + SBC gate + NetCDF persistence — CALIB-04, CALIB-06, CALIB-07
- [x] 03-07-PLAN.md — Stage 5 cross-validation + per-circuit CSV + baseline RMSE comparison (MAD outlier filter) — CALIB-05, CALIB-08
- [x] 03-08-PLAN.md — Typer CLI (f1-calibrate stage1..5 + run-all) + resumable orchestrator + calibration_runs writeback — CALIB-01..08

### Phase 4: Simulation API & Uncertainty Quantification
**Goal:** A client can POST a race/driver/stint to `/simulate`, receive lap-level, timestep-level, and stint-level outputs with 95 % credible-interval bands from K=100 posterior draws, in under 2 seconds on a cache hit — with session upload and calibration summary endpoints available.
**Depends on:** Phase 3
**Requirements:** API-04, API-05, API-06
**Success Criteria** (what must be TRUE):
  1. `POST /simulate` with a valid stint reference returns per-timestep (~4 Hz), per-lap, and per-stint predictions with 95 % CI bands computed from K=100 vectorized posterior draws, and end-to-end wall time is under 2 s on a warm cache (excluding cold start), measured by an integration benchmark.
  2. The `/simulate` payload accepts optional parameter overrides that modify the forward pass without triggering MCMC; the endpoint never imports or invokes PyMC at runtime.
  3. `GET /calibration/{compound}` returns posterior means and 95 % CIs for all learned parameters of the requested compound, sourced from the latest NetCDF posterior tagged in SQLite.
  4. `POST /sessions/upload` accepts a zip of a FastF1 cache directory, extracts it into the persistent volume under the caller's session scope, and subsequent `/simulate` calls against that session succeed without any Jolpica API call.
  5. Every `/simulate` response includes the calibration_id, model schema version, and FastF1 library version in its payload metadata.
**Plans:** 6 plans
- [x] 04-00-PLAN.md — Wave 0 scaffold: test stubs + calibration/zip fixtures + pyproject deps (API-04/05/06)
- [x] 04-01-PLAN.md — POST /simulate: schemas + posterior store + K=100 forward pass + two-layer cache + router (API-04, D-01..D-06)
- [x] 04-02-PLAN.md — GET /calibration/{compound}: schemas + service + router (API-05, D-09)
- [x] 04-03-PLAN.md — POST /sessions/upload: secure zip extractor + TTL cleanup daemon + router (API-06, D-07, D-08)
- [x] 04-04-PLAN.md — App wiring: include_router chain + GZipMiddleware + lifespan extensions + session_id -> FastF1 cache merge (API-04/05/06)
- [x] 04-05-PLAN.md — Integration: wall-time benchmark + E2E test + human-verify checkpoint (API-04/05/06)

### Phase 5: Dashboard Shell & Visualization
**Goal:** A user visiting the deployed frontend can pick a race, driver, and stint, click "Run model," and see all six dashboard zones populate with the returned simulation — CI bands on predicted traces, linked hover across every zone, and correct FIA compound colors throughout.
**Depends on:** Phase 4 (or the Phase 1 API stubs for parallel development)
**Requirements:** DASH-01, DASH-02, DASH-03, DASH-04, VIZ-01, VIZ-02, VIZ-03, VIZ-04, VIZ-05, VIZ-06, VIZ-07
**Success Criteria** (what must be TRUE):
  1. The top bar (Zone 1, 56 px) hosts race/driver/stint cascade dropdowns that drive a URL-hash-encoded selection; choosing a race populates drivers, and choosing a driver populates stints, with loading skeletons in each zone during fetches.
  2. At ≥1280 px desktop width all six zones (top bar, track map, tire array, multi-chart panel, transport bar, status log) render without overflow; at ≥768 px tablet width the layout adapts to view-only; mobile URLs render content even though interactions are disabled.
  3. Clicking "Run model" issues `/simulate` and shows a phased progress indicator cycling through "Module 1/7 — Kinematics…" through "Module 7/7 — Degradation…"; FastF1 errors surface a retry affordance; flagged-quality stints display a warning badge while still rendering results.
  4. The multi-chart main panel (Zone 4) stacks lap times (bars + predicted overlay), sliding power per tire (4 traces), and tread temperature per tire (4 traces) on a shared x-axis with mouse-wheel zoom, drag-to-pan, and shaded 95 % CI bands visually distinct from observed data.
  5. The tire array (Zone 3) shows four widgets in a 2×2 grid (FL/FR/RL/RR) each displaying circular temperature gauge, numeric temperature, grip %, cumulative energy (MJ), and slip angle — all updating in sync with chart hover.
  6. Hovering any chart, tire widget, or track SVG highlights the same lap/timepoint in every other zone simultaneously with tooltips showing exact values and units; the status log (Zone 7) lists per-lap model events and can be collapsed.
  7. FIA compound colors (SOFT=red, MEDIUM=yellow, HARD=white), Okabe-Ito palette for categorical data, viridis for temperatures, deep navy background (#0a0e1a), off-white text, and JetBrains Mono / Inter typography are applied site-wide.
**Plans:** 9 plans
- [x] 05-01-PLAN.md — Vite scaffold, Tailwind 4 CSS tokens, self-hosted fonts, Wave 0 test infra (DASH-04, VIZ-06)
- [x] 05-02-PLAN.md — TypeScript types, D3 color/format utils, Zustand stores, TanStack Query hooks (DASH-01, VIZ-05, VIZ-06)
- [x] 05-03-PLAN.md — TopStrip: cascade pickers, mode toggle, scrubber, lap counter, shared PanelHeader/Skeleton (DASH-01, DASH-04)
- [x] 05-04-PLAN.md — CarPanel: SF-24 chassis SVG, CarWheel ×4 with viridis/wear/grip/CI halo, footer readouts (VIZ-02, VIZ-05, VIZ-06)
- [x] 05-05-PLAN.md — MapPanel: FastF1 X/Y track utilities, SVG circuit with 3-sector coloring, car dot, turn labels (VIZ-01)
- [x] 05-06-PLAN.md — LapPanel: pace trace, status log, big lap time, deltas, sector cards, stint projection (VIZ-03, VIZ-07)
- [x] 05-07-PLAN.md — PhysicsPanel: 4 metric tabs × 4 cornerwise CI band charts, hover crosshair (VIZ-03, VIZ-04, VIZ-05, VIZ-06)
- [x] 05-08-PLAN.md — POST /simulate/stream SSE backend endpoint: 7 module_complete events + simulation_complete (DASH-03)
- [x] 05-09-PLAN.md — App shell wiring: cockpit grid, SSE consumer hook, MSW dev activation, ErrorBoundary, human-verify (DASH-02, DASH-03, VIZ-05)

### Phase 6: Playback, Interactions & Sharing
**Goal:** A user can play back a stint lap-by-lap, scrub or step with keyboard, export any chart, copy tire metrics, drop in a FastF1 cache zip, and share a URL that restores the exact scenario on reload — all with a provenance footer that makes the result citable.
**Depends on:** Phase 5
**Requirements:** PLAY-01, PLAY-02, INT-01, INT-02, INT-03, INT-04, INT-05, INT-06
**Success Criteria** (what must be TRUE):
  1. The transport bar (Zone 6, 48 px) provides play/pause, step ±1 lap, jump to first/last, speed control (0.5×/1×/2×/4×), a scrub bar colored by sector and pit-stop segments, and a "current / total laps" readout; dragging the scrub bar updates all zones in real time.
  2. Playback animates car position on the track SVG, advances the chart playhead, and updates the tire array in sync at the selected speed without visible stutter on a mid-range laptop.
  3. Keyboard shortcuts work globally: Space (play/pause), ←/→ (step lap), Shift+←/→ (step sector), Home/End (first/last lap), 1/2/3/4 (focus FL/FR/RL/RR), T (toggle track map), E (toggle event log), S (save/share URL), ? (shortcuts overlay), Esc (close modal/panel).
  4. Right-click on any chart opens a context menu exporting PNG, SVG, or CSV of that chart's data; right-click on any tire widget copies a formatted "temperature / grip % / energy / slip angle" string to the clipboard.
  5. The full scenario (race, driver, stint, current lap, any parameter overrides) is encoded in the URL hash; pasting that URL into a fresh browser restores the exact view.
  6. Dragging a zip of a FastF1 cache directory onto the app fires `POST /sessions/upload`, and on success the app loads that session and runs `/simulate` against it without any further FastF1 fetch.
  7. The data provenance footer shows FastF1 library version, model schema version, calibration ID, calibration date, and the "Unofficial fan tool — not affiliated with F1, FIA, or Pirelli" disclaimer on every page.
**Plans:** 6 plans
- [x] 06-01-PLAN.md — Wave 0 test infra: Playwright + E2E spec stubs + export.ts/useDragUpload scaffolds + Toast + MSW upload handler (PLAY-01, PLAY-02, INT-01..INT-06)
- [x] 06-02-PLAN.md — Store extensions + TopStrip step/jump/0.5× + ⓘ button + error/RETRY banner + Scrubber sector colors + pit markers (PLAY-01, PLAY-02, SC-3 carry-in)
- [x] 06-03-PLAN.md — Global keyboard shortcuts + ShortcutsModal + MapFullscreenOverlay + StatusLog Zustand collapse + Toast mount (INT-01)
- [x] 06-04-PLAN.md — Chart context menu (PNG/SVG/CSV export) + tire clipboard copy (INT-02, INT-03)
- [x] 06-05-PLAN.md — URL hash extension with lap + drag-and-drop FastF1 zip upload with progress + auto-simulate (INT-04, INT-05)
- [x] 06-06-PLAN.md — PhysicsPanel wheel zoom + drag pan + RESET + ProvenanceModal + Playwright E2E test completion (INT-06, PLAY-02, SC-4 carry-in)

### Phase 7: Deployment & Operations
**Goal:** The application is live on its production URLs with persistent FastF1 + posterior storage, CORS locked down, a liveness probe passing, and the ten most recent race sessions pre-warmed so a first-time visitor's `/simulate` call lands on a cache hit.
**Depends on:** Phase 6
**Requirements:** INFRA-01, INFRA-02, INFRA-03
**Success Criteria** (what must be TRUE):
  1. The backend is deployed to Fly.io with a mounted persistent volume at `/data` (holding both the FastF1 cache and NetCDF posteriors), a minimum of 2 Uvicorn workers, `auto_stop_machines=false`, and `GET /healthz` returning 200 under external probing.
  2. The frontend is deployed to Vercel as a static React/Vite bundle; backend CORS allows only the production Vercel domain and `localhost` for development; a cross-origin request from any other origin is rejected.
  3. At deploy time, a `prewarm` job fetches the 10 most recent race sessions into the FastF1 cache; a post-deploy smoke test confirms `/simulate` against one of those stints completes within the <2 s budget on first user request.
**Plans:** TBD

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation, Data Pipeline & Module Contracts | 5/5 | Complete | 2026-04-23 |
| 2. Physics Model (Modules A–G) | 7/7 | Complete | 2026-04-23 |
| 3. Bayesian Calibration Pipeline | 8/8 | Complete | 2026-04-23 |
| 4. Simulation API & Uncertainty Quantification | 6/6 | Complete | 2026-04-24 |
| 5. Dashboard Shell & Visualization | 9/9 | Complete | 2026-04-24 |
| 6. Playback, Interactions & Sharing | 0/6 | Not started | — |
| 7. Deployment & Operations | 0/? | Not started | — |

---

## Coverage Summary

- **v1 requirements:** 49
- **Mapped:** 49 (100 %)
- **Orphans:** 0
- **Duplicates:** 0

Requirement-to-phase mapping is maintained in `.planning/REQUIREMENTS.md` under Traceability.

---
*Roadmap created: 2026-04-23*
