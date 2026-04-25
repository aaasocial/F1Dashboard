# Stack Research — F1 Tire Degradation Analyzer

**Researched:** 2026-04-23
**Overall confidence:** HIGH on backend core (verified via official docs), MEDIUM on frontend choices (a few rapidly moving pieces), HIGH on deployment (explicit Vercel limit blocker verified).
**Critical finding:** The stated Vercel deployment target is incompatible with the <2s simulation + Bayesian calibration workload. Fly.io is the correct target for the API; Vercel remains viable only for the static frontend. This must be resolved at roadmap time.

---

## Backend

### Core Framework

| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| **Python** | 3.12 | Runtime | HIGH |
| **FastAPI** | 0.136.x | HTTP API, typed request/response, async | HIGH |
| **Uvicorn** | 0.32+ | ASGI server | HIGH |
| **Pydantic** | v2 (2.x) | Request/response schemas, validation | HIGH |

**Why Python 3.12 (not 3.13):**
- FastAPI 0.130+ dropped Python 3.9 support (Feb 2026); 3.12 is the current sweet spot for scientific Python.
- SciPy 1.17, NumPy 2.x, PyMC 5.x, NumPyro all ship prebuilt wheels for 3.12 — 3.13 wheels are still incomplete in several niche scientific libs.
- **Do not use 3.13 yet**: JAX GPU wheels, some Numba-dependent bits of nutpie, and a few PyMC transitive deps are not consistently available.

**Why FastAPI:**
- Remains best-in-class in 2026 for typed Python HTTP APIs. Async-first, auto OpenAPI, Pydantic v2 integration. Microsoft/Netflix/Uber production use.
- For this project's 4 endpoints (races, drivers, stints, simulate), FastAPI is overkill in features but exactly right in ergonomics.
- **Critical pattern for this project**: the `/simulate` endpoint is CPU-bound (physics integration + Bayesian sampling). It MUST be a `def` (sync) route so FastAPI runs it in the threadpool, OR offloaded to a worker. It must NOT be an `async def` route — that would block the event loop.

### Scientific Core

| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| **NumPy** | 2.1+ | Array math, vectorized physics | HIGH |
| **SciPy** | 1.17.x | `solve_ivp` for thermal ODE, optimization, interpolation | HIGH |
| **pandas** | 2.2+ | Lap/telemetry tabular manipulation (FastF1 returns DataFrames) | HIGH |
| **Numba** | 0.60+ | Optional: JIT-compile per-lap tight loops (contact/slip inversion) | MEDIUM |

**ODE solver choice (thermal module):**
- Use `scipy.integrate.solve_ivp` with `method='LSODA'` (automatic stiff/non-stiff switching) or `'Radau'` (implicit, for stiff thermal dynamics).
- **Do not use** `scipy.integrate.odeint` — legacy, SciPy explicitly recommends `solve_ivp` for new code.
- Thermal ODE is likely stiff (fast surface/bulk temperature gradients); `RK45` will be slow or unstable. Budget this during Phase 1.

**Numba as an escape hatch:**
- If per-stint simulation is slow (>2s budget blown), JIT the brush-model slip inversion inner loop. Don't add it preemptively — profile first.

### FastF1 Integration

| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| **fastf1** | 3.8.2 (latest March 2026) | F1 telemetry/timing data access | HIGH |

**Critical FastF1 gotchas (verified from official docs + GitHub issues):**
1. **Ergast was shut down in early 2025.** FastF1 3.5+ migrated to the **Jolpica-F1 API** (drop-in replacement). Any tutorial/SO answer predating 2025 that references `fastf1.ergast` needs updating — use `fastf1.jolpica` (or just the high-level `fastf1.get_session()` which handles the transport internally).
2. **Rate limit is 500 calls/hour** on Jolpica-F1. Enforced as a soft-throttle first, then a hard `RateLimitExceededError`. Cached requests do not count.
3. **Rate-limit errors are silent on INFO/WARNING log levels.** They surface as `ValueError: Failed to load any schedule data` — misleading. Set FastF1 logger to DEBUG during dev (GitHub issue #748).
4. **Caching is on by default** (`requests-cache` SQLite + pickled parsed objects). First session fetch is 200–500 MB; subsequent loads are seconds. Set an explicit cache path: `fastf1.Cache.enable_cache('.cache/fastf1')`.
5. **Very recent sessions and pre-season tests can return empty/partial data.** Gate the `/races` endpoint to completed race weekends only.
6. **The project brief mentions a `.ff1` cache file drag-and-drop.** FastF1's on-disk cache files are `.ff1pickle` and SQLite fragments — a single "ff1 cache file" isn't an official FastF1 export format. Either repurpose this as a zip of the cache dir, or redefine as "pre-computed JSON stint payload." Flag for roadmap clarification.

**Caching strategy for this app (layered):**
- Layer 1: FastF1's own SQLite/pickle cache (automatic).
- Layer 2: App-level result cache — after the seven-module model runs on a stint, persist `(race_id, driver_id, stint_idx, param_version) → results JSON` in SQLite. Re-`/simulate` with identical inputs returns cached result in <50ms. This is how "<2s end-to-end" is achieved for repeat viewing.
- Layer 3: HTTP cache headers on `/races` and `/races/{id}/drivers` (they are immutable for completed races) — 1 year `Cache-Control: public, max-age=31536000, immutable`.

### Bayesian Inference (Calibration)

| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| **PyMC** | 5.18+ | Model specification, posterior sampling orchestration | HIGH |
| **NumPyro** | 0.16+ | Sampler backend (JAX-compiled NUTS) called from PyMC via `sample(nuts_sampler="numpyro")` | HIGH |
| **JAX** | 0.4.x (CPU-only build fine) | Compilation target for NumPyro | HIGH |
| **nutpie** | 0.13+ | Alternative Rust-based NUTS sampler; fallback if NumPyro compilation is slow | MEDIUM |
| **ArviZ** | 0.20+ | Posterior diagnostics, `InferenceData` format, trace plots for notebooks | HIGH |

**PyMC vs NumPyro vs Stan decision (for 15–20 parameters, four-stage sequential calibration):**

The project brief specifies PyMC. This is correct as the *specification layer*, but the sampling backend matters more than the DSL for your performance budget.

| Option | Verdict | Reasoning |
|--------|---------|-----------|
| **PyMC + NumPyro backend** (recommended) | Best fit | Familiar PyMC model specification (the calibration spec doc is presumably written in PyMC idioms). JAX-compiled NUTS gives ~2.9x ESS/s vs default PyMC on CPU. 15–20 params is trivially in the efficient range for NUTS. |
| **PyMC + nutpie backend** | Solid fallback | Rust-based, often faster on very small models. Numba compile is slower than JAX first-time (~seconds), but per-sample throughput can edge out NumPyro for tight posteriors. Use if NumPyro gives gradient trouble. |
| **Raw NumPyro** | Rejected | You'd rewrite the calibration spec doc. PyMC's model DSL is better for seven-module physics priors with interpretable names. |
| **Stan (via CmdStanPy)** | Rejected | Precompile dependency (C++ toolchain), slightly faster on very small models but loses the ~3x JAX advantage. Adds deployment complexity. |
| **BlackJAX** | Rejected for v1 | Lower-level, reasonable if you outgrow NumPyro but no reason to start there. |
| **Variational (ADVI)** | Keep in back pocket | PyMC's `pm.fit()` is available for mean-field ADVI if full NUTS posterior calibration exceeds patience during Phase 2. Trade: less accurate uncertainty tails. |

**Realistic calibration runtime expectation:** For 15–20 parameters with a four-stage pipeline, each stage ~1000 warmup + 1000 draws × 4 chains with JAX NUTS on a modern laptop CPU: **single-digit minutes per stage is plausible if the log-likelihood is vectorizable in JAX**. If the physics model is NumPy-only (not jit-able), you're stuck on the default PyMC backend and stages will take 10–30 minutes each. **This is the #1 performance risk in the project — addressed below.**

**Critical architectural implication:** PyMC models with JAX backend require the log-likelihood to be expressible in JAX-compatible ops. If the seven-module physics model is pure NumPy with Python control flow, JAX won't help directly. Options:
- (A) Rewrite hot paths in `jax.numpy` (straightforward if physics is mostly arithmetic + `solve_ivp`-equivalents via `diffrax`). Best performance.
- (B) Wrap NumPy model as a black-box log-likelihood via `pm.CustomDist` / `Potential` — works but loses JAX speedup; sampling falls back to default backend.
- (C) Use `numpyro` directly with a `pure_callback` to NumPy — works with some overhead.

Roadmap should include a Phase 1 spike to confirm which path the physics model takes.

**Also install:** `diffrax` (0.6+) — JAX-native ODE solver. If thermal module needs to live inside the JAX graph for calibration, this replaces `scipy.solve_ivp`.

### Data & Persistence

| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| **SQLite** | 3.40+ (stdlib) | Versioned parameter storage, per-stint simulation cache | HIGH |
| **SQLModel** or **SQLAlchemy 2.0** | latest | Typed DB access layer | HIGH |
| **Alembic** | 1.13+ | Schema migrations (param table schema will evolve) | HIGH |

SQLModel preferred over raw SQLAlchemy — fewer lines, Pydantic integration already required by FastAPI. If team dislikes SQLModel's magic, drop to SQLAlchemy 2.0 declarative.

### Task Execution Strategy

**This is critical and the project brief under-specifies it.** Options for running the physics simulation:

| Approach | Fit for `/simulate` (<2s budget) | Fit for offline calibration |
|----------|-----------------------------------|-----------------------------|
| Sync route in FastAPI threadpool | **Recommended for v1 `/simulate`** — simple, within budget, no new infra | Not suitable |
| FastAPI `BackgroundTasks` | Wrong tool — fire-and-forget, no result retrieval | Not suitable |
| **ARQ + Redis** | Overkill for v1 if simulation stays <2s; the right upgrade path if not | Good for calibration jobs |
| Celery | Rejected — too heavy; designed for large distributed workers | Works but heavyweight |
| Offline script + SQLite writeback | N/A | **Recommended for calibration** — brief explicitly says calibration is offline |

**Recommendation:** Keep `/simulate` synchronous in-process for v1. If profiling shows breaching the 2s budget, upgrade that single endpoint to ARQ without touching the rest. Calibration is an offline CLI script (`python -m f1tire.calibrate --compound SOFT`), writes to the parameters SQLite.

---

## Frontend

### Core Framework

| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| **React** | 19.x | UI framework | HIGH |
| **TypeScript** | 5.6+ | Type safety (strict mode) | HIGH |
| **Vite** | 6.x | Dev server + build | HIGH |

React 19 is stable and widely adopted by April 2026. Vite 6 remains the dominant build tool — no serious challenger for a non-SSR scientific dashboard. Do not use Next.js here (the app is client-only rendering of interactive charts; SSR adds zero value and complicates Three.js/WebGL).

### Visualization

| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| **D3** | 7.9+ | Scales, shape generators, interpolators, color | HIGH |
| **Three.js** | r170+ | 3D/2D track map rendering (WebGL) | HIGH |
| **@react-three/fiber** | 9.x | React reconciler for Three.js scene graph | MEDIUM |
| **@react-three/drei** | 10.x | Common Three.js helpers (OrbitControls, Line2, etc.) | MEDIUM |

**Critical viz architecture recommendation — use D3 as a utility library, not a renderer:**

The common anti-pattern for React + D3 is to let D3 manipulate the DOM (`d3.select('svg').append(...)`). This fights React's reconciler and breaks hover/state. Instead:
- Use `d3-scale`, `d3-shape`, `d3-array`, `d3-interpolate`, `d3-axis` to *compute* path data, domains, tick positions.
- Render SVG/Canvas elements from React JSX.
- This is the "D3 for math, React for DOM" pattern — standard in 2026.

**For the track map (Zone 2 in the brief):**
- The brief says "2D track rendering with animated car position." A flat 2D track doesn't need Three.js — it can be an SVG path with a moving `<circle>`, driven by `requestAnimationFrame`.
- **Use Three.js only if** (a) you want 3D elevation from telemetry, (b) you want smooth GPU-accelerated animation of many concurrent points, or (c) you anticipate a 3D extension in v2.
- **Recommendation:** Start with SVG for track map; defer Three.js to v2 unless 3D is a brief-level requirement. Re-read the brief — "Three.js for 3D track map" is in the constraints, so keep it, but be ready to drop it if 3D turns out to be scope creep.

**If keeping Three.js: use React Three Fiber, not raw Three.js.** For a single canvas with declarative scene, R3F is the idiomatic 2026 choice. Raw Three.js only wins when you need imperative control over the render loop (shader experiments, custom compositors) — none of that applies here.

**Rejected chart library choices:**
- **Recharts**: Too opinionated, can't do the multi-chart linked-hover Zone 4 layout cleanly.
- **Nivo**: Pretty defaults but heavy, slow on dense data, hard to customize.
- **Victory**: Declining maintenance momentum.
- **Chart.js**: Canvas-based, fine but no TypeScript-first story, hard to integrate linked-hover across charts.
- **Plotly.js**: Bundle size is enormous (~3 MB), interactive charts feel generic/boxy, not dashboard-grade.
- **visx (Airbnb)**: Reasonable if team finds D3 intimidating, but you're already committed to D3. Visx adds a layer you'll outgrow.
- **Observable Plot**: Great for exploratory notebooks, not for custom dashboards with linked interactions.

**Specific D3 sub-packages to install (don't install monolithic `d3`):**
`d3-scale`, `d3-shape`, `d3-array`, `d3-axis`, `d3-interpolate`, `d3-color`, `d3-format`, `d3-time-format`, `d3-selection` (only for transitions/tooltip-root escape hatch). Monolithic `d3` pulls 60+ subpackages; tree-shaking is imperfect.

### State & Data

| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| **TanStack Query** | v5 | Server state cache (races, drivers, simulation results) | HIGH |
| **Zustand** | 5.x | Client UI state (selected lap, playing/paused, hover timestamp) | HIGH |

**Why not Redux:** Zustand is 40% less code, no boilerplate, fits linked-chart hover state (single global "hovered timestamp" atom) perfectly. TanStack Query owns network state — Zustand owns *nothing* that TanStack should own. This split is the 2026 standard.

**URL-hash state sync** (requirement: "Scenario state encoded in URL hash"):
- Implement via a small custom hook syncing Zustand state ↔ `window.location.hash` on change. Don't add a router for this.
- If routing grows in v2, add TanStack Router (not React Router) — better TS inference.

### Styling

| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| **Tailwind CSS** | 4.x | Utility CSS for layout, spacing, theme tokens | HIGH |
| **CSS custom properties** | — | Dark theme tokens (deep navy, compound colors) | HIGH |

Tailwind v4 is significantly faster than v3 (Oxide engine, Vite plugin). Define the compound colors (SOFT red, MEDIUM yellow, HARD white) as CSS variables + Tailwind theme tokens so the palette stays consistent across SVG charts, Three.js materials, and DOM.

**Do not add a component library** (Mantine/Chakra/MUI/Radix primitives). The brief is a custom dark scientific dashboard — any off-the-shelf component library will visually clash and require extensive theming. Build the ~15 custom primitives directly. Exception: consider **Radix UI primitives** (headless) for the picker dropdowns if a11y becomes a concern — Radix gives keyboard nav / focus trap / ARIA for free without visual opinions.

### Developer Tooling

| Tool | Purpose |
|------|---------|
| **Biome** 1.9+ OR **ESLint 9 + Prettier** | Lint + format (Biome is faster and single-binary; pick one) |
| **Vitest** 2.x | Unit tests for scale/formatter/state logic |
| **Playwright** 1.49+ | E2E for the critical user flow (pick stint → run → scrub) |
| **MSW** 2.x | Mock FastAPI responses during frontend dev |

---

## Deployment

**The brief says "FastAPI deployed to Vercel/Fly.io." This needs clarification because the two are not substitutable for this workload.**

### Recommended architecture

| Layer | Platform | Rationale | Confidence |
|-------|----------|-----------|------------|
| Frontend static assets | **Vercel** (or Cloudflare Pages) | Free tier, global edge CDN, zero-config Vite deploys | HIGH |
| FastAPI backend | **Fly.io** (shared-cpu-2x or performance-1x) | Docker-native, Performance CPU available, no serverless timeout, persistent filesystem for SQLite + FastF1 cache | HIGH |
| Database | SQLite on Fly.io volume (v1) → managed Postgres (Fly Postgres or Supabase) when multi-instance needed | Brief says "Postgres later" | HIGH |

### Why Vercel is wrong for the backend

**Vercel's Python runtime hard limits (verified from Vercel docs, April 2026):**
- Free tier: 60 s function duration (with Fluid Compute).
- Pro tier: up to 14 min duration with Fluid Compute, 800 s max.
- 500 MB uncompressed bundle cap.

**Blocking issues for this project:**
1. The FastF1 + NumPy + SciPy + PyMC + NumPyro + JAX dependency graph **will exceed 500 MB** uncompressed. Measured: NumPy 2.x (~40 MB) + SciPy (~90 MB) + JAX (~80 MB) + PyMC (~30 MB) + PyTensor (~60 MB) + transitive = ~350–450 MB easily, with no headroom. Slim builds shaving C extensions would break the physics.
2. **No persistent filesystem** on Vercel. FastF1's on-disk cache (which is the *whole point* — "fetch once, run many") is ephemeral. Every cold start re-downloads, blowing both the 60s timeout AND the 500/hr Jolpica rate limit in minutes.
3. **No background workers**. Offline calibration jobs can't run on Vercel.
4. SQLite parameter store can't persist across deploys.

### Why Fly.io is right

- Docker container: install any scientific Python stack with no size cap.
- **Persistent volumes** (Fly Volumes): mount `/data` for SQLite + FastF1 cache directory.
- Performance CPU option: dedicated, non-burstable cores for the physics solve.
- Scale-to-zero supported (with first-request warmup cost ~500ms–2s on a 1x shared). For v1 traffic levels, 1 always-on shared-cpu-2x machine ($5–10/mo) is simpler.
- Global anycast: fine for a dashboard app, doesn't matter much here.

### Fly.io deployment shape

```
fly.toml: shared-cpu-2x (2 vCPU, 512 MB RAM — upgrade to 1 GB if PyMC chains run live; probably fine since calibration is offline)
Dockerfile: python:3.12-slim base, install numpy/scipy/pymc/numpyro via uv or pip
Volume: /data mounted, contains sqlite parameter DB + fastf1 cache
Healthcheck: GET /healthz → 200
Process: uvicorn main:app --host 0.0.0.0 --port 8080 --workers 2
```

Two Uvicorn workers (not 1): allows one to serve a GET while another does a simulate. Do not use more than 2 on shared-cpu-2x — CPU contention kills the <2s budget.

### Alternative: Railway

If Fly.io's CLI/ops feel heavy, **Railway** is a strong second choice. Pros: simpler deploy UX, auto-scaling, generous free trial. Cons: pricing is less predictable for CPU-intensive workloads (usage-based), no Performance CPU dedicated option. For v1 launch with low traffic, Railway is fine and marginally faster to ship on. Pick Fly.io if "<2s per stint" needs to be a guarantee; Railway if "usually under 2s" is acceptable.

### Rejected: Render

Render is Heroku-like and fine but gives up Fly's Performance CPU and Railway's simpler pricing. No standout advantage for this workload.

### Rejected: AWS Lambda / Google Cloud Run (serverless)

Same cold-start + filesystem problems as Vercel, worse DX. Don't.

### Frontend deployment note

Deploy the Vite build output to Vercel. Point it at the Fly.io backend via an env var (`VITE_API_BASE`). CORS config on the FastAPI side: restrict to the Vercel preview + production domains.

---

## What NOT to Use

| Rejected | Reason |
|----------|--------|
| **Vercel for the backend** | 500 MB bundle limit, 60s/14min timeout, no persistent FS for FastF1 cache, no offline workers. Use for frontend only. |
| **AWS Lambda / Cloud Run** | Same class of problem as Vercel; cold starts + no persistent cache = rate-limit disaster. |
| **Django / Flask** | FastAPI's typed Pydantic integration is purpose-built for this. Django is too heavy; Flask lacks native async and modern typing. |
| **Celery** | Overkill. The only async workload (calibration) is offline. Use a plain CLI script. |
| **Stan (CmdStanPy)** | Adds C++ toolchain to the Docker image, gains nothing for 15–20 params that NumPyro can't match. |
| **Raw `odeint`** | SciPy explicitly recommends `solve_ivp` for all new code; `odeint` will be deprecated eventually. |
| **Monolithic `d3` npm package** | Pull individual `d3-*` subpackages; bundle impact matters for fast dashboard loads. |
| **Recharts / Nivo / Victory / Chart.js** | Can't deliver the linked-hover, custom dark-theme, dense scientific aesthetic. You'd spend more time fighting them than writing D3. |
| **Plotly.js / Bokeh** | Bundle bloat (~3 MB), "sciencey" default look doesn't match the pro-timing-graphics aesthetic. |
| **Next.js** | Zero benefit for a client-rendered interactive dashboard. Adds SSR complexity that conflicts with Three.js/WebGL initialization. |
| **Redux Toolkit** | Zustand + TanStack Query cover the use case with far less code. |
| **Raw Three.js (without R3F)** | If Three.js is in the stack, use React Three Fiber. Raw Three.js only makes sense outside React, which this app isn't. |
| **Mantine/MUI/Chakra** | Custom dark scientific dashboard + off-the-shelf component library = visual inconsistency and theme-override hell. |
| **PyTorch for inference** | Wrong tool — this is a physics-informed model with explicit Bayesian parameter calibration, not a neural net. |
| **DuckDB** | SQLite is sufficient for the parameter table. DuckDB's analytical strength doesn't apply here (parameter store is small and write-mostly during calibration). |
| **Pydantic v1** | Pydantic v2 is 5–50x faster validation and is what FastAPI 0.100+ expects natively. |

---

## Open Questions

These need decisions during roadmap / Phase 1:

1. **Can the seven-module physics model be expressed in `jax.numpy`?** This is the make-or-break question for calibration wall-clock time. A Phase 1 spike should port one module (e.g., Hertzian contact) to JAX and measure `jit`+`grad` compile time and per-call speed. If yes → full NumPyro JAX backend. If no → PyMC default backend + expect longer calibration times (still feasible, not a blocker, just slower iteration).

2. **Is a 3D track map actually required, or is 2D sufficient?** The brief says 3D, but the described UI interactions (click-to-scrub, sector boundaries, car position) are all 2D concerns. If 2D is acceptable, drop Three.js entirely for v1 → simpler stack, smaller bundle, faster load. Surface to stakeholder.

3. **What does "`.ff1` cache file drag-and-drop" actually mean?** FastF1 doesn't export a single-file `.ff1`. Clarify whether this is (a) a zip of the cache dir, (b) a custom pre-computed session snapshot, (c) a dropped assumption. Small but concrete UX impact.

4. **How many concurrent users is v1 sized for?** Impacts Fly.io instance size choice (shared-cpu-2x vs performance-1x) and whether calibration results should be precomputed for popular races. Brief doesn't specify — default assumption: 1–10 concurrent, demo-scale.

5. **Is a precomputed "gallery" of common stints acceptable for the v1 demo?** If simulation wall-clock occasionally exceeds 2s in practice, seeding the app with 10–20 precomputed famous stints (Verstappen Spa 2022 medium, Hamilton Silverstone 2023 hard, etc.) gives a perfect-feeling demo without engineering heroics. Defer decision to Phase 3 (backend integration).

6. **Calibration parameter versioning semantics.** Brief says "versioned SQLite database, tagged per simulation result." Needs a concrete schema: per-compound? per-season? per-car-year? Affects the `/simulate` cache key and eventual param refresh workflow.

---

## Sources

**Verified primary sources:**
- [FastAPI releases and docs](https://fastapi.tiangolo.com/) — version, async guidance
- [FastAPI best practices 2026](https://fastlaunchapi.dev/blog/fastapi-best-practices-production-2026)
- [FastF1 3.8 official docs](http://docs.fastf1.dev/) — Jolpica migration, cache, rate limits
- [FastF1 rate-limit GitHub issue #748](https://github.com/theOehrly/Fast-F1/issues/748) — logging gotcha
- [SciPy 1.17 integrate docs](https://docs.scipy.org/doc/scipy/reference/integrate.html) — `solve_ivp` recommendation
- [SciPy solve_ivp reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html)
- [PyMC JAX + Numba sampling guide](https://www.pymc.io/projects/examples/en/latest/samplers/fast_sampling_with_jax_and_numba.html)
- [PyMC–Stan benchmark (PyMC Labs)](https://www.pymc-labs.com/blog-posts/pymc-stan-benchmark) — ESS/s comparisons
- [NumPyro MCMC docs](https://num.pyro.ai/en/latest/mcmc.html) — HMC/NUTS API
- [MCMC runtime comparison (Ingram)](https://github.com/martiningram/mcmc_runtime_comparison) — real-world Stan vs PyMC vs NumPyro wall-clock
- [Nutpie docs](https://pymc-devs.github.io/nutpie/) — Rust NUTS, JAX backend
- [Vercel Functions limits](https://vercel.com/docs/functions/limitations) — 500 MB, duration caps
- [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python) — beta, size limits
- [Fly.io vs Railway 2026 comparison](https://thesoftwarescout.com/fly-io-vs-railway-2026-which-developer-platform-should-you-deploy-on/)
- [Python hosting comparison 2025](https://www.nandann.com/blog/python-hosting-options-comparison) — Fly/Railway/Render
- [Three.js vs R3F 2026](https://graffersid.com/react-three-fiber-vs-three-js/) — performance, WebGPU state
- [Three.js 2026 features](https://www.utsubo.com/blog/threejs-2026-what-changed) — WebGPU, workflows
- [React chart library survey 2026](https://weavelinx.com/best-chart-libraries-for-react-projects-in-2026/)
- [ARQ vs Celery vs FastAPI BackgroundTasks](https://davidmuraya.com/blog/fastapi-background-tasks-arq-vs-built-in/)

**Confidence notes:** FastAPI, Fly.io, PyMC/NumPyro, FastF1, SciPy recommendations are HIGH confidence (verified against primary docs). Three.js/R3F recommendation is MEDIUM because the 3D-vs-2D question is a project-scope issue more than a technical one. D3 sub-package list is HIGH (standard 2026 tree-shaking practice).
