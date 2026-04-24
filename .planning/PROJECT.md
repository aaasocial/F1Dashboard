# F1 Tire Degradation Analyzer

## What This Is

A browser-based F1 race strategy tool that runs a physics-informed tire degradation model entirely from public FastF1 telemetry. Users pick a race, driver, and stint — the app fetches the telemetry, runs a seven-module physics model, and produces a lap-by-lap prediction of tire grip, temperature, and degradation, visualized in a data-dense dashboard inspired by professional timing graphics.

Designed for F1 fans, fantasy league players, and journalists who want to analyze race strategy at the level professional teams do — without needing proprietary team data or bespoke simulation software.

## Core Value

A user can load any historical F1 stint and see a physics-based, quantitative prediction of how those tires degraded — lap by lap, tire by tire — derived entirely from public data.

## Requirements

### Validated

**Validated in Phase 1: Foundation, Data Pipeline & Module Contracts (2026-04-23)**
- [x] FastF1 integration with aggressive server-side caching (fetch-once, run-many per stint) — two-layer cache confirmed working, canonical fixture 22 laps / 8060 samples
- [x] `GET /races` — list available races (2022–present)
- [x] `GET /races/{race_id}/drivers` — list drivers who completed that race
- [x] `GET /stints/{race_id}/{driver_id}` — list driver's stints with metadata

### Validated

**Validated in Phase 2: Physics Model — Modules A–G (2026-04-23)**
- [x] Seven-module tire degradation model: kinematic front-end → vertical loads → force distribution → Hertzian contact + friction → brush model slip inversion → thermal ODE → cumulative energy + degradation
- [x] Strict A→B→C→D→E→F→G execution order enforced by orchestrator and AST-linter tests (PHYS-09)
- [x] Force-balance invariants: ΣF_z = M·g + F_aero (rtol=1e-10), ΣF_y = M·a_lat (rtol=1e-12)
- [x] μ identity: μ(T_opt, p̄₀) = μ₀ (rtol=1e-12), Θ capped at 1 on over-demand
- [x] `f1-simulate` CLI: per-lap Rich table output, exit codes 2/3 for data errors
- [x] 174 tests passing (modules A–G + orchestrator + CLI + architecture linter + benchmark)
- [x] Benchmark CI workflow committed to GitHub Actions (600ms threshold on ubuntu-latest)

### Active

**Backend — Physics Model**
- [ ] FastF1 integration with aggressive server-side caching (fetch-once, run-many per stint)
- [ ] Four-stage sequential Bayesian calibration pipeline (aero → friction → thermal → degradation)
- [ ] Calibrated model parameters stored in versioned SQLite database, tagged per simulation result
- [ ] Per-prediction confidence intervals from Bayesian parameter posterior (not point estimates only)
- [ ] Simulation completes in <2 seconds end-to-end per stint

**Backend — API**
- [ ] `GET /races` — list available races (2022–present)
- [ ] `GET /races/{race_id}/drivers` — list drivers who completed that race
- [ ] `GET /stints/{race_id}/{driver_id}` — list driver's stints with metadata
- [ ] `POST /simulate` — run model for a stint, return per-lap per-tire predictions with confidence intervals

**Frontend — Dashboard**
- [ ] Race + driver + stint picker (dropdowns, top bar)
- [ ] Track map (Zone 2): 2D track rendering with animated car position, sector boundaries, click-to-scrub
- [ ] Tire array (Zone 3): four tire widgets in 2×2 grid — circular temperature gauge, grip %, cumulative energy (MJ), slip angle
- [ ] Multi-chart main panel (Zone 4): stacked lap times / sliding power / tread temperature charts, shared x-axis, linked hover
- [ ] Transport bar (Zone 6): play/pause, step lap, speed control, scrub bar with pit stop markers
- [ ] Status/log (Zone 7): collapsible event log of model events per lap
- [ ] "Run model" triggers simulation with ~3s animated progress indicator
- [ ] Keyboard shortcuts: Space, ←/→, Shift+←/→, Home/End, 1/2/3/4, T, E, ?, Esc
- [ ] Desktop-first layout; responsive to tablet (view-only on mobile)
- [ ] Dark theme: deep navy background, off-white text, compound colors (red/yellow/white for SOFT/MEDIUM/HARD), warm-cool gradient for temperatures

**Frontend — Data Interactions**
- [ ] Linked charts: hovering any chart highlights the same timepoint across all charts and track map
- [ ] Tooltip on tire hover: temperature, grip %, cumulative energy
- [ ] Right-click chart → export PNG/SVG/CSV
- [ ] Right-click tire widget → copy metric to clipboard
- [ ] Scenario state encoded in URL hash (shareable, restorable on reload)
- [ ] Drag-and-drop `.ff1` cache file to load session without API fetch

**Educational**
- [ ] Jupyter notebook alongside backend showing each module in isolation with full physics derivation
- [ ] Comprehensive docstrings citing source papers for every equation (Pacejka, Castellano, Kobayashi, Sorniotti, Kenins, Greenwood-Williamson, Grosch, WLF)

### Out of Scope

- **Pit window optimizer** — v2; requires track position simulator on top of tire model
- **What-if laboratory (scenario sliders)** — v2; deferred to keep v1 focused on the core physics visualization
- **Compound comparison overlay** — v2; depends on what-if parameter overrides
- **Parameter sensitivity explorer (live sliders)** — v2; same dependency
- **Driver comparison side-by-side** — v2; UI complexity; wait until base dashboard is validated
- **Educational annotation overlay** — v2; toggleable layer over completed charts
- **Live race integration** — out of scope; FastF1 public feed latency makes real-time impractical
- **User accounts / saved scenarios** — out of scope for v1; URL hash sharing covers the core use case
- **`POST /calibrate` admin endpoint** — out of scope for v1; calibration runs offline
- **Wet tire model** — explicitly deferred in brief; extend thermal parameterization later
- **Mobile-first design** — view-only on mobile is acceptable; mobile-optimized UX is not v1

## Context

- **Physics specification:** `model_v1_complete.html` (seven-module architecture) and `model_calibration_strategy.html` (four-stage Bayesian calibration) — these are the authoritative algorithmic spec; any implementation question defers to them.
- **Data source:** FastF1 public telemetry (2022–present). Critical sensors (steering angle, wheel speeds, tire temperatures) are absent from the public feed — the model derives these from position, speed, and RPM via kinematics and physics priors.
- **No proprietary coefficients:** Pacejka tire coefficients are proprietary to Pirelli/teams. The model uses brush model inversion from observed forces instead — a key differentiator.
- **Calibration approach:** ~15–20 free parameters per compound, fitted via Bayesian inference (MCMC/variational) across multi-season data with held-out races for validation.
- **Existing code:** Fresh start — prior F1 Dashboard code is archived/not carried forward. Building from the brief's spec.
- **Competitive landscape:** FastF1, F1Tempo, tomastics, Viz show telemetry but don't predict. This is the first public physics-first predictive tool.

## Constraints

- **Data:** Public FastF1 API only — no proprietary team telemetry, no Pirelli tire coefficients
- **Performance:** <2s end-to-end per stint simulation (frontend animates results live)
- **Stack:** Python/FastAPI + numpy/scipy + PyMC backend; React + TypeScript + D3 + Three.js frontend; FastAPI deployed to Vercel/Fly.io
- **Uncertainty:** All predictions must expose confidence intervals from the Bayesian posterior — point estimates alone are not acceptable
- **Modularity:** Each physics module must be a standalone class with unit tests, swappable without touching other modules
- **Deployment:** Desktop-first web app; no install; browser-native

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| V1 = stint analyzer only | Ship the physics foundation and validate it before adding features on top | — Pending |
| Physics-first model (not ML) | Interpretable — users understand *why* degradation happens, not just see a prediction. No proprietary training data needed. | — Pending |
| Public data only via FastF1 | Team-grade sensors not available publicly; model derives missing signals from kinematics and physics priors | — Pending |
| Fresh start (ignore existing code) | Prior codebase doesn't align with brief's architecture; cleaner to build from spec | — Pending |
| Bayesian calibration (MCMC/variational) | Uncertainty quantification is a first-class requirement; frequentist approaches can't produce the required confidence intervals natively | — Pending |
| SQLite for parameter storage (initially) | Start simple; brief explicitly notes "Postgres later" once needs exceed SQLite | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-24 — Phase 3 complete (Bayesian Calibration Pipeline — 5-stage offline calibration, PyMC/NumPyro NUTS, 79 tests passing)*
