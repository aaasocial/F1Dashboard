# Research Summary — F1 Tire Degradation Analyzer

> **Note:** Physics model sections are authoritative from `model_spec.md` and the two HTML spec files, which override general research findings where they conflict.

---

## Stack Recommendation

**1. Backend: Python 3.12 + FastAPI 0.136 + Uvicorn**
Sync routes (`def`, not `async def`) for CPU-bound simulation — wraps in threadpool via `asyncio.to_thread`. Python 3.13 not yet supported by JAX wheels; stay on 3.12.

**2. Numerical core: NumPy 2.1 + SciPy 1.17**
Per model_spec: forward Euler at 4 Hz (Δt = 0.25s) is **stable** for the thermal ODE — thermal time constants all exceed 5 seconds, so the system is not stiff. Use RK4 only for higher accuracy, not as a necessity. `scipy.integrate.solve_ivp` with Radau/BDF is **not needed** and would add overhead with no benefit at this timestep. SciPy smoothing splines for track curvature, Savitzky-Golay for speed differentiation.

**3. Bayesian inference: PyMC 5.18 + NumPyro 0.16 (Stage 4 only)**
Per model_spec and calibration strategy: Bayesian MCMC/variational is used **only for Stage 4** (degradation parameters). Stages 1–3 use `scipy.optimize.least_squares` with trust-region-reflective. This is cheaper and more appropriate for the earlier stages where observational constraints are direct.

**4. Simulation performance: ~100ms per stint (per model_spec)**
The model_spec explicitly states "~100 ms per stint" — the <2s budget is achievable with straightforward NumPy. No Numba or JAX required for the forward simulation. Vectorize over the posterior draw axis for uncertainty quantification.

**5. Deployment: Fly.io (backend) + Vercel (frontend static)**
Vercel categorically unsuitable for Python scientific backend: 500 MB bundle cap exceeded by FastAPI + NumPy + SciPy + PyMC stack; no persistent filesystem for FastF1 cache; ephemeral storage burns the 500 calls/hour Jolpica API rate limit on every cold start. Fly.io with persistent volume is the correct choice.

**6. Frontend: React 19 + TypeScript 5.6 + Vite 6 + visx + Zustand 5 + TanStack Query v5 + React Three Fiber**
React owns DOM; D3/visx owns scales and math only. No `d3.select(ref).append()` anywhere. Three.js via `@react-three/fiber` for track map, code-split with `React.lazy`. Zustand for 60 Hz hover state; TanStack Query for server state.

---

## Physics Model (Authoritative — from model_spec.md and HTML files)

### Seven-module pipeline, executed in strict sequence per telemetry timestep (4 Hz):

| Module | Input | Output | Source |
|--------|-------|--------|--------|
| **A — Kinematics** | V, X, Y, RPM, gear | a_lat, a_long, κ, ψ, V_sx | Frenet-Serret; Gim 1988 |
| **B — Vertical loads** | a_lat, a_long, V | F_z,i per tire | Castellano 2021 Eqs 1–9 |
| **C — Force distribution** | F_z,i | F_y,i, F_x,i per tire | Castellano 2021 Eqs 10–27 |
| **D — Hertzian + friction** | F_z,i, T_tread (prev), μ₀(t) | a_cp,i, p̄_i, μ_i | GW 1966; Grosch 1963 |
| **E — Slip + sliding power** | F_y,i, F_x,i, μ_i, F_z,i | Θ_i, α_i, V_sy,i, P_slide,i | Pacejka 2012 Ch 3; Kobayashi 2019 |
| **F — Thermal ODE** | P_total,i, T_tread (prev) | T_tread,i, T_carc,i, T_gas,i | Sorniotti 2009; Kenins 2019 |
| **G — Energy + degradation** | P_total,i, T_tread,i | E_tire,i, μ₀(t), d_tread | Todd 2025; Castellano 2021 |

**No iteration within a timestep.** Friction at time t uses temperature from t − Δt. Causally correct, no inner loop needed.

**Core equations (for implementation reference):**
- μ_i(T, p̄) = μ₀(t) · (p̄₀/p̄_i)^(1−n) · exp(−(T−T_opt)²/2σ_T²) — model core
- Θ_i = 1 − (1 − |F_y,i|/μ_i F_z,i)^(1/3) — brush model inversion
- dμ₀/dt = −β_therm · μ₀ · exp((T_tread − T_ref)/T_act) — thermal aging
- Δt_lap ≈ (t_ref/2) · (μ₀^fresh − μ₀(t))/μ₀^fresh — lap time penalty

### Parameter taxonomy (~18 learned per compound):
- **FIXED:** M_dry=798kg, WB=3.6m, R₀=0.330m, C_rr=0.012, ρ from weather
- **SEMI:** M_fuel(t), WD, H_CG, K_rad, ΔT_blanket, BB, gear ratios (inferable from RPM vs V)
- **LEARNED per car/track:** C_LA, C_DA, ξ (aero); K_rf/(K_rf+K_rr) (roll stiffness)
- **LEARNED per compound:** μ₀^fresh, p̄₀, n, T_opt, σ_T, c_py, C_tread, C_carc, C_gas, R_tc, R_cg, h₀, h₁, α_p, β_therm, T_act, k_wear

**Effective calibration dimension: ~6 per compound** (μ₀^fresh, n, T_opt, σ_T, β_therm, C_tread/R_tc ratio). Well-posed with 20+ races × ~50 degrading laps per compound.

---

## Five-Stage Calibration Pipeline (Authoritative)

| Stage | Parameters | Method | Observables |
|-------|-----------|--------|-------------|
| **1 — Aero** | C_LA, C_DA, ξ | scipy.optimize (not Bayesian) | Max lateral g at aero-limited corners; terminal straight speed |
| **2 — Friction** | μ₀^fresh, p̄₀, n | scipy.optimize | Peak lateral g laps 2–5 per stint; ln(μ) vs ln(p̄) plot |
| **3 — Thermal** | T_opt, σ_T, C_tread, C_carc, R_tc, R_cg, h₀, h₁, α_p | constrained optimization | Out-lap warm-up rate; performance vs track temperature |
| **4 — Degradation** | β_therm, T_act, k_wear | **Bayesian MCMC or variational** | Lap-time evolution mid-to-late stint |
| **5 — Validation** | — | Cross-validation | 20% held-out races; RMSE vs observed; pit window accuracy |

---

## Table Stakes Features (V1 Must-Haves)

| Feature | Why non-negotiable |
|---------|-------------------|
| Race → driver → stint cascade picker | Every F1 analysis tool opens on selection UI |
| Loading skeletons per zone | Skeletons reduce perceived wait; prevent layout shift across 6+ zones |
| Simulation progress with phase labels ("2/7 Vertical loads...") | Transparent computation at 2-3s; difference between "working" and "broken" |
| Error states with retry | FastF1 calls fail; silent failure is top bounce driver |
| Lap-by-lap multi-line chart, shared X-axis | Canonical F1 analyst chart |
| Linked hover across all charts + track map + tire array | Zone 4 requirement; expected by users of F1Tempo/TracingInsights |
| Confidence interval bands on all predictions | Bayesian CIs are the core value prop — omitting removes the differentiator |
| Four-tire 2×2 widget array (temp, grip %, energy MJ, slip angle) | Zone 3 spec |
| Transport bar (play/pause, step, scrub, speed, pit markers) | Zone 6 spec |
| FIA compound colors (SOFT=red, MEDIUM=yellow, HARD=white) | Deviation confuses F1 fans immediately |
| Keyboard shortcuts (Space, arrows, 1/2/3/4, ?, Esc, etc.) | Professional tool expectation |
| Right-click → export PNG/SVG/CSV | Universal trio |
| URL hash state encoding | Shareable deep links; replaces user accounts in V1 |
| Data provenance footer (FastF1 version + model version + calibration tag) | Journalists must cite and reproduce |
| Dark theme (deep navy, off-white, compound accent colors) | Per spec |
| Empty-state hero with curated example stints | Blank dashboard causes bounce |

---

## Architecture Decisions

**1. Contract-first, stubs everywhere**
Define all 7 inter-module typed dataclasses (KinematicState, WheelLoads, ContactPatch, ThermalState, DegradationState, etc.) before writing any physics code. This unblocks frontend and calibration development simultaneously.

**2. Calibration is offline CLI; /simulate never runs MCMC**
`POST /simulate` loads pre-computed posterior samples from NetCDF (ArviZ InferenceData), runs the forward model K times in vectorized numpy broadcast. Calibration is a CLI script. The online/offline boundary is the single most important architectural decision.

**3. Forward Euler at 4 Hz is correct (not stiff ODE solvers)**
Per model_spec: forward Euler is stable at Δt = 0.25s because all thermal time constants > 5s. Do not use `solve_ivp` with Radau/BDF — unnecessary overhead. Upgrade to RK4 only if higher accuracy is needed.

**4. Two-layer cache on persistent Fly.io volume**
FastF1 native disk cache (Layer 1) + app-level gzip-pickled stint artifacts keyed on `(race_id, driver_id, stint_index, preprocessing_version)` (Layer 2). No Redis. Stint data is cold-read and immutable.

**5. React owns DOM; D3/visx owns math only**
This pattern must be documented and enforced before the first chart component. Mixed pattern requires full rewrite of all charts to fix. Linked hover propagates via Zustand `hover.t`, not D3 selections.

---

## Critical Pitfalls to Avoid

**1. Running MCMC inside /simulate**
`POST /simulate` must be a sub-second forward model evaluation against pre-fitted parameters — never a calibration run. Violating this makes <2s impossible.

**2. Vercel backend deployment**
Size limit alone (500 MB bundle) kills this. Decide Fly.io in Phase 0 — deciding after building forces a full platform migration.

**3. FastF1 data quality issues (known)**
- throttle=104 sentinel values (corrupt data, not actual WOT)
- Compound mislabeling: 2025 Belgian GP intermediates labeled MEDIUM in public feed
- RUS 2025 Bahrain: transponder fault → gaps in position data
- FastF1 moved to Jolpica-F1 API (Ergast shutdown early 2025), 500 calls/hour rate limit; rate errors reported at INFO log level (not ERROR — easy to miss)
- Build `data_integrity.py` as the first backend component; refuse simulation below quality threshold

**4. Bayesian non-identifiability in Stage 4**
15-20 correlated parameters can produce banana-shaped joint posteriors even when marginals look converged. Mitigation: sequential calibration stages (spec-prescribed); simulation-based calibration (SBC) with synthetic data before real telemetry; monitor ArviZ r_hat > 1.01 or ESS < 400.

**5. F1/FOM copyright risk**
FastF1 data ToS: personal, non-commercial use. Must display clear "unofficial fan tool" footer; no FOM/FIA/Pirelli trademarked assets; historical data only; never expose FastF1 cache as download. Decide legal posture before public deployment.

---

## Recommended Build Order

**Phase 1: Data Pipeline + Contracts**
FastF1 integration → data_integrity.py → all 7 module dataclass contracts with stubs → FastAPI with 4 core endpoints returning stub data. Unblocks all parallel work.

**Phase 2: Core Physics (Modules A–G)**
Implement one module at a time, each with unit tests verifying physical invariants (per model_spec test suite). Forward Euler integration. Benchmark: target ~100ms per stint, well within <2s budget.

**Phase 3: Calibration Pipeline**
Five-stage offline CLI. Prior predictive checks before MCMC. Bayesian only for Stage 4. ArviZ InferenceData → NetCDF. Validation against held-out circuits.

**Phase 4: Frontend Core**
AppShell + Zustand + TanStack Query + URL hash. TopBar pickers. MultiChartPanel (visx, shared X-axis, linked hover, CI bands). Tire array. Transport bar + keyboard shortcuts. React Three Fiber track map (code-split).

**Phase 5: Polish + Data Interactions**
Export (PNG/SVG/CSV), clipboard copy, drag-and-drop .ff1, URL hash with lz-string, skeleton screens, error states, provenance footer, onboarding tour, Physics Glossary.

**Phase 6: Deployment**
Fly.io hardening, persistent volume, CORS, cache pre-warm, Vercel frontend, performance regression tests, per-circuit RMSE dashboard.

---

## Key Open Questions

1. **API: Does `/what_if` merge into `/simulate` via overrides, or stay as a separate endpoint?** model_spec lists both `POST /simulate` and `POST /what_if`. The brief's `/simulate` payload already has an `overrides` field — recommend merging into one endpoint with optional overrides for V1.
2. **Can the forward model be vectorized over the draw axis in pure NumPy for CI generation?** model_spec says ~100ms per stint — with K=100 draws this is ~10s. Need to validate vectorization actually reduces this to <2s.
3. **What does `.ff1` drag-and-drop mean precisely?** FastF1 has no single-file export. Recommend: accept a zip of the FastF1 cache directory via `POST /sessions/upload`.
4. **3D track map vs 2D SVG?** All described interactions are 2D concerns. Three.js adds ~200 kB gzipped. Surface the question; brief specifies "2D track rendering" (Zone 2 description). React Three Fiber for the car position overlay may be overkill.
5. **Driver aggressiveness modeling?** Calibration doc flags this as ~20 additional parameters. V1 recommendation: fit a single "driver aggressiveness multiplier" per driver rather than per-driver parameter sets.
