# Requirements: F1 Tire Degradation Analyzer

**Defined:** 2026-04-23
**Core Value:** A user can load any historical F1 stint and see a physics-based, quantitative prediction of how those tires degraded — lap by lap, tire by tire — derived entirely from public data.

---

## v1 Requirements

### Data Pipeline

- [ ] **DATA-01**: System fetches FastF1 telemetry (V, X, Y, RPM, gear, throttle, brake, T_track, T_air at ~4 Hz) for any race/driver/stint from 2022–present via Jolpica-F1 API
- [ ] **DATA-02**: System maintains a two-layer disk cache (FastF1 native + app-level pickle keyed by race/driver/stint/preprocessing_version) on persistent storage; a given stint fetches once and runs many times without re-fetching
- [ ] **DATA-03**: System computes a per-circuit reference curvature map κ(s) from the fastest 20% of laps, cached per circuit per season
- [ ] **DATA-04**: System infers per-team gear ratios (8 ratios + final drive) automatically from steady-speed telemetry segments (throttle=100%, gear constant)
- [ ] **DATA-05**: System detects and flags data quality issues (throttle=104 sentinel values, NaN lap times, mislabeled compounds, missing position data) with a per-stint quality score; UI shows a warning badge when issues are present but simulation still runs; flagged stints are excluded from the calibration dataset
- [ ] **DATA-06**: System annotates each lap with metadata (compound mapped to C1–C5, tire age, fuel estimate, weather conditions) and excludes in/out-laps and SC/VSC-affected laps from degradation analysis

### Physics Model

- [ ] **PHYS-01**: Module A (Kinematics) derives lateral acceleration (a_lat = V²·κ), longitudinal acceleration (a_long = dV/dt via Savitzky-Golay filter, window 7–11, order 2–3), heading angle ψ, and rear longitudinal slip velocity V_sx from FastF1 position and RPM data
- [ ] **PHYS-02**: Module B (Vertical loads) computes per-tire F_z using static loads, longitudinal load transfer, simplified elastic lateral load transfer (front/rear split by roll stiffness ratio K_rf/(K_rf+K_rr), no roll angle sensor required), and aerodynamic downforce (F_aero = ½ρ·C_LA·V²) split by aero balance ξ; F_z clipped to minimum 50 N
- [ ] **PHYS-03**: Module C (Force distribution) distributes total lateral and longitudinal forces proportionally to vertical load share per Castellano et al. (2021) Eqs 10–27; brake bias BB applied to front/rear split during braking; power applied to rear axle only (RWD)
- [ ] **PHYS-04**: Module D (Hertzian contact + friction) computes contact patch half-length (a_cp,i = √(2R₀F_z,i/K_rad)), mean contact pressure (p̄_i = F_z,i/4·a_cp,i·b_tread), and complete friction coefficient μ_i(T,p̄) = μ₀(t)·(p̄₀/p̄_i)^(1−n)·exp(−(T_tread,i−T_opt)²/2σ_T²); uses previous timestep's T_tread and current μ₀(t)
- [ ] **PHYS-05**: Module E (Slip inversion + sliding power) inverts the brush model to recover Θ_i = 1−(1−|F_y,i|/μ_i·F_z,i)^(1/3), slip angle α_i = sgn(F_y,i)·arctan(3μ_iF_z,i/c_py·a_cp,i² · Θ_i), lateral slip velocity V_sy,i = V·sin(α_i), and sliding power P_slide,i = |F_y,i|·|V_sy,i|+|F_x,i|·|V_sx,i|; clips Θ_i=1 and logs events when force demand exceeds grip
- [ ] **PHYS-06**: Module F (Thermal ODE) integrates a three-node lumped model (tread/carcass/gas nodes) per tire using forward Euler at 4 Hz (Δt=0.25s, stable given time constants >5s); heat source α_p·P_total,i enters tread; convection h_air(V)=h₀+h₁√V; initial conditions T_tread=T_carc=T_gas=T_track+ΔT_blanket
- [ ] **PHYS-07**: Module G (Energy + degradation) integrates cumulative tire energy E_tire,i, updates reference friction via Arrhenius thermal aging (dμ₀/dt = −β_therm·μ₀·exp((T_tread−T_ref)/T_act)), tracks tread thickness via mechanical wear (dd_tread/dt = −k_wear·P_slide,i), and computes lap-time penalty Δt_lap ≈ (t_ref/2)·(μ₀^fresh−μ₀(t))/μ₀^fresh
- [ ] **PHYS-08**: Each module (A–G) is a standalone Python class implementing a typed PhysicsModule protocol with unit tests verifying physical invariants: Module B force balance closure (ΣF_z = total weight + downforce), Module C lateral force closure (ΣF_y,i = M·a_lat), Module D identity (μ(T_opt,p̄₀) = μ₀), Module E identity (|F_y|=μ·F_z → Θ=1), Module F steady state (dT/dt=0), Module G monotonicity (E_tire non-decreasing)
- [ ] **PHYS-09**: Modules execute in strict sequence A→B→C→D→E→F→G at each telemetry timestep; simulation state (temperatures, cumulative energy, μ₀) carried in an explicit state object; no globals, no inner-timestep iteration

### Calibration Pipeline (Offline CLI)

- [ ] **CALIB-01**: Stage 1 (Aero calibration) — CLI command fits C_LA, C_DA, ξ from max lateral g at known fast corners and terminal straight speeds using scipy.optimize.least_squares; expected accuracy ±10% C_LA, ±15% C_DA
- [ ] **CALIB-02**: Stage 2 (Friction baseline) — fits μ₀^fresh, p̄₀, n from peak lateral g in laps 2–5 per stint via ln(μ_eff) vs ln(p̄) regression across corners and speeds; expected accuracy ±5% μ₀^fresh, ±0.05 n
- [ ] **CALIB-03**: Stage 3 (Thermal parameters) — fits T_opt, σ_T, C_tread, C_carc, C_gas, R_tc, R_cg, h₀, h₁, α_p from out-lap warm-up rate and performance variation across track temperatures using constrained optimization; expected accuracy ±10°C T_opt, ±5°C σ_T
- [ ] **CALIB-04**: Stage 4 (Degradation) — fits β_therm, T_act, k_wear from stint lap-time evolution using Bayesian MCMC (PyMC 5.x + NumPyro JAX backend); monitors r_hat < 1.01 and ESS > 400; expected accuracy ±30% on degradation rates
- [ ] **CALIB-05**: Stage 5 (Cross-validation) — evaluates calibrated model against 20% held-out races; computes per-lap time prediction RMSE (target <0.3s on calibrated compounds), stint-end grip error, and per-circuit breakdown
- [ ] **CALIB-06**: Simulation-based calibration (SBC) and prior predictive checks run on synthetic data before Stage 4 uses real telemetry
- [ ] **CALIB-07**: Calibrated posterior parameters stored as ArviZ InferenceData NetCDF files; metadata (compound, season, calibration timestamp, held-out RMSE, git SHA) stored in versioned SQLite database (parameter_sets and calibration_runs tables); every simulation result tagged with model version + calibration ID
- [ ] **CALIB-08**: Baseline linear degradation model (lap time vs tire age per stint per compound) fitted as a sanity check; physics model must achieve meaningfully lower RMSE on validation set

### REST API

- [ ] **API-01**: GET /races returns list of (year, round, name) for 2022–present, served from cache
- [ ] **API-02**: GET /races/{race_id}/drivers returns drivers who completed that race with stint summary
- [ ] **API-03**: GET /stints/{race_id}/{driver_id} returns stint list with compound, lap count, pit info, tire age, and data quality score
- [ ] **API-04**: POST /simulate runs the 7-module forward model for a given stint; returns per-timestep (~4 Hz), per-lap, and per-stint outputs with 95% credible intervals from K=100 posterior draws; responds in <2s end-to-end (cache hit, excluding cold start); payload supports optional parameter overrides
- [ ] **API-05**: GET /calibration/{compound} returns current fitted parameter summaries (posterior mean ± 95% CI) for a compound
- [ ] **API-06**: POST /sessions/upload accepts a zip of FastF1 cache directory; parses and ingests the session data server-side for drag-and-drop loading without re-fetching from Jolpica

### Dashboard Shell

- [ ] **DASH-01**: Top bar (Zone 1, 56px): race/driver/stint cascade pickers (dropdowns); selection state encoded in URL hash; settings icon (right)
- [ ] **DASH-02**: Six-zone layout (track map, tire array, multi-chart panel, control panel, transport bar, status log) renders correctly at desktop width (≥1280px); adapts to tablet (≥768px, view-only mode); mobile users landing via shared URL see content without interaction capability
- [ ] **DASH-03**: "Run model" button triggers simulation with phased progress indicator ("Module 2/7 — Vertical loads…"); error state with retry action surfaces FastF1 API failures; data quality warning badge displays on stints with flagged issues
- [ ] **DASH-04**: Dark theme by default — deep navy background (#0a0e1a or similar), off-white text, JetBrains Mono or IBM Plex Mono (13–14px) for data, Inter (14–16px) for UI chrome

### Visualization

- [ ] **VIZ-01**: Track map (Zone 2): 2D SVG rendering of circuit with animated car position as pulsing dot; ghost trace for current lap; sector boundaries marked; click any track point to jump playhead to that lap/sector position
- [ ] **VIZ-02**: Tire array (Zone 3): four tire widgets in 2×2 grid (FL top-left, FR top-right, RL bottom-left, RR bottom-right); each shows circular temperature gauge (color-mapped warm-cool gradient), numeric temperature (large center), grip %, cumulative energy (MJ), slip angle (°)
- [ ] **VIZ-03**: Multi-chart main panel (Zone 4): three stacked charts sharing x-axis — (1) lap times as bars with predicted overlay, (2) sliding power per tire (4 colored traces), (3) tread temperature per tire (4 colored traces); mouse-wheel zoom and drag-to-pan on shared x-axis
- [ ] **VIZ-04**: Confidence interval bands (shaded 95% CI) rendered on all predicted output traces, clearly distinguishing predicted from observed historical data
- [ ] **VIZ-05**: Linked hover across all zones — hovering any chart, tire widget, or track SVG highlights the same lap/timepoint on all other zones simultaneously; tooltip shows exact values with units (°C, MJ, %, deg)
- [ ] **VIZ-06**: FIA compound colors throughout (SOFT=red, MEDIUM=yellow, HARD=white); non-compound categorical data uses Okabe-Ito palette; temperature gradients use viridis sequential scale (colorblind-safe)
- [ ] **VIZ-07**: Status/log panel (Zone 7): collapsible per-lap model event log ("Lap 8: tire reaching operating window", "Lap 14: front-left approaching thermal limit", "Lap 16: thermal degradation threshold exceeded")

### Playback

- [ ] **PLAY-01**: Transport bar (Zone 6, 48px): play/pause, step forward/back one lap, jump to first/last lap, speed control (0.5×/1×/2×/4×), scrub bar with colored sector and pit stop segments, current lap / total laps readout
- [ ] **PLAY-02**: Playback animates car position on track SVG, updates tire array state, and advances chart playhead in sync at selected speed; scrub bar drag updates all zones in real-time

### Keyboard and Data Interactions

- [ ] **INT-01**: Keyboard shortcuts: Space (play/pause), ←/→ (step lap), Shift+←/→ (step sector), Home/End (first/last lap), 1/2/3/4 (focus FL/FR/RL/RR tire), T (toggle track map), E (toggle event log), S (save/share URL), ? (keyboard shortcuts help overlay), Esc (close any modal or panel)
- [ ] **INT-02**: Right-click any chart → context menu to export as PNG, SVG, or CSV
- [ ] **INT-03**: Right-click any tire widget → "Copy metric" puts current values (temperature, grip %, energy, slip angle) in clipboard as formatted text
- [ ] **INT-04**: Complete scenario state (race, driver, stint, current lap, any parameter overrides) encoded in URL hash; reloading the URL restores exact scenario
- [ ] **INT-05**: Drag-and-drop of a zip file containing FastF1 cache directory onto the app triggers POST /sessions/upload; success loads that session without API fetch
- [ ] **INT-06**: Data provenance footer shows FastF1 library version, model schema version, calibration ID, calibration date, and "Unofficial fan tool — not affiliated with F1, FIA, or Pirelli" disclaimer

### Infrastructure

- [ ] **INFRA-01**: Backend deployed to Fly.io with persistent volume (/data) for FastF1 cache and NetCDF posteriors; minimum 2 Uvicorn workers; auto_stop_machines=false; /healthz liveness endpoint
- [ ] **INFRA-02**: Frontend deployed to Vercel as static React/Vite bundle; CORS on backend restricted to Vercel domain and localhost
- [ ] **INFRA-03**: FastF1 cache pre-warmed with the 10 most recent race sessions at deploy time

---

## v2 Requirements

### What-If Laboratory
- Scenario sliders: compound override, track temperature, fuel load, aero balance, downforce level, roll stiffness split
- Predictions update in real-time as sliders change
- "Reset to actual" button restores historical values

### Pit Window Optimizer
- Given mid-race state (lap N, compound, tire age), predict optimal pit lap for each remaining compound option
- Race position probability estimates (e.g., "Pit now for HARD → P3 with 72% probability")

### Compound Comparison
- Overlay predicted stint evolution for all available compounds on the same chart
- "What if the driver had started on SOFT instead of MEDIUM?"

### Parameter Sensitivity Explorer
- Live sliders for key physics parameters (μ₀, T_opt, C_LA, aero balance, roll stiffness)
- Predictions update in real-time as parameters change

### Driver Comparison
- Overlay two drivers' same-stint tire state side-by-side
- Highlight which driver ran higher temperatures through key corners

### Educational Annotation Overlay
- Toggleable layer that annotates charts with plain-language physics explanations per lap

### Jupyter Notebook
- Per-module educational notebook showing each physics module in isolation with toy inputs and physics derivations

### Expert Mode
- GET /calibration/{compound} parameters become editable in the UI
- Users can override fitted parameters and re-run simulation

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| Proprietary Pacejka coefficients | Not publicly available; brush model inversion is the public-data alternative |
| Team-grade sensor data (steering angle, wheel speeds, tire IR temp) | Not in FastF1 public feed; model derives these from kinematics and physics priors |
| Live race integration | FastF1 public feed latency makes real-time impractical; historical only |
| User accounts / authentication | URL hash sharing covers V1 sharing needs; accounts add complexity without core value |
| POST /calibrate admin endpoint | Calibration runs offline as a CLI script; no web-triggered calibration in V1 |
| Wet tire physics model | Explicitly deferred in brief; requires different thermal parameterization |
| Mobile-first design | View-only on mobile is acceptable for V1; mobile-optimized UX is not the priority |
| F1 Manager / game integration | Entertainment product, not physics-grounded analysis |
| LLM-generated explanations | Adds latency, cost, and hallucination risk; educational log covers the use case |
| PDF export | Browser print-to-PDF covers this; dedicated PDF adds complexity for little gain |
| Annotations / saved notes | Adds database complexity; not core to V1 value |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | Pending |
| DATA-02 | Phase 1 | Pending |
| DATA-03 | Phase 1 | Pending |
| DATA-04 | Phase 1 | Pending |
| DATA-05 | Phase 1 | Pending |
| DATA-06 | Phase 1 | Pending |
| PHYS-01 | Phase 2 | Pending |
| PHYS-02 | Phase 2 | Pending |
| PHYS-03 | Phase 2 | Pending |
| PHYS-04 | Phase 2 | Pending |
| PHYS-05 | Phase 2 | Pending |
| PHYS-06 | Phase 2 | Pending |
| PHYS-07 | Phase 2 | Pending |
| PHYS-08 | Phase 1 + Phase 2 | Pending |
| PHYS-09 | Phase 1 + Phase 2 | Pending |
| CALIB-01 | Phase 3 | Pending |
| CALIB-02 | Phase 3 | Pending |
| CALIB-03 | Phase 3 | Pending |
| CALIB-04 | Phase 3 | Pending |
| CALIB-05 | Phase 3 | Pending |
| CALIB-06 | Phase 3 | Pending |
| CALIB-07 | Phase 3 | Pending |
| CALIB-08 | Phase 3 | Pending |
| API-01 | Phase 1 | Pending |
| API-02 | Phase 1 | Pending |
| API-03 | Phase 1 | Pending |
| API-04 | Phase 4 | Pending |
| API-05 | Phase 4 | Pending |
| API-06 | Phase 4 | Pending |
| DASH-01 | Phase 5 | Pending |
| DASH-02 | Phase 5 | Pending |
| DASH-03 | Phase 5 | Pending |
| DASH-04 | Phase 5 | Pending |
| VIZ-01 | Phase 5 | Pending |
| VIZ-02 | Phase 5 | Pending |
| VIZ-03 | Phase 5 | Pending |
| VIZ-04 | Phase 5 | Pending |
| VIZ-05 | Phase 5 | Pending |
| VIZ-06 | Phase 5 | Pending |
| VIZ-07 | Phase 5 | Pending |
| PLAY-01 | Phase 6 | Pending |
| PLAY-02 | Phase 6 | Pending |
| INT-01 | Phase 6 | Pending |
| INT-02 | Phase 6 | Pending |
| INT-03 | Phase 6 | Pending |
| INT-04 | Phase 6 | Pending |
| INT-05 | Phase 6 | Pending |
| INT-06 | Phase 6 | Pending |
| INFRA-01 | Phase 7 | Pending |
| INFRA-02 | Phase 7 | Pending |
| INFRA-03 | Phase 7 | Pending |

**Note on PHYS-08 and PHYS-09:** These are cross-cutting structural requirements.
- PHYS-08's **protocol/contract** lands in Phase 1 (dataclass contracts); its **per-module invariant tests** land in Phase 2 as each module is implemented.
- PHYS-09's **state-object scaffold** lands in Phase 1; its **strict-sequence execution** is enforced in Phase 2 when modules run end-to-end.

**Coverage:**
- v1 requirements: 49 total
- Mapped to phases: 49 (100 %)
- Unmapped: 0

---
*Requirements defined: 2026-04-23*
*Last updated: 2026-04-23 after roadmap creation*
