<!-- GSD:project-start source:PROJECT.md -->
## Project

**F1 Tire Degradation Analyzer**

A browser-based F1 race strategy tool that runs a physics-informed tire degradation model entirely from public FastF1 telemetry. Users pick a race, driver, and stint — the app fetches the telemetry, runs a seven-module physics model, and produces a lap-by-lap prediction of tire grip, temperature, and degradation, visualized in a data-dense dashboard inspired by professional timing graphics.

Designed for F1 fans, fantasy league players, and journalists who want to analyze race strategy at the level professional teams do — without needing proprietary team data or bespoke simulation software.

**Core Value:** A user can load any historical F1 stint and see a physics-based, quantitative prediction of how those tires degraded — lap by lap, tire by tire — derived entirely from public data.

### Constraints

- **Data:** Public FastF1 API only — no proprietary team telemetry, no Pirelli tire coefficients
- **Performance:** <2s end-to-end per stint simulation (frontend animates results live)
- **Stack:** Python/FastAPI + numpy/scipy + PyMC backend; React + TypeScript + D3 + Three.js frontend; FastAPI deployed to Vercel/Fly.io
- **Uncertainty:** All predictions must expose confidence intervals from the Bayesian posterior — point estimates alone are not acceptable
- **Modularity:** Each physics module must be a standalone class with unit tests, swappable without touching other modules
- **Deployment:** Desktop-first web app; no install; browser-native
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Backend
### Core Framework
| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| **Python** | 3.12 | Runtime | HIGH |
| **FastAPI** | 0.136.x | HTTP API, typed request/response, async | HIGH |
| **Uvicorn** | 0.32+ | ASGI server | HIGH |
| **Pydantic** | v2 (2.x) | Request/response schemas, validation | HIGH |
- FastAPI 0.130+ dropped Python 3.9 support (Feb 2026); 3.12 is the current sweet spot for scientific Python.
- SciPy 1.17, NumPy 2.x, PyMC 5.x, NumPyro all ship prebuilt wheels for 3.12 — 3.13 wheels are still incomplete in several niche scientific libs.
- **Do not use 3.13 yet**: JAX GPU wheels, some Numba-dependent bits of nutpie, and a few PyMC transitive deps are not consistently available.
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
- Use `scipy.integrate.solve_ivp` with `method='LSODA'` (automatic stiff/non-stiff switching) or `'Radau'` (implicit, for stiff thermal dynamics).
- **Do not use** `scipy.integrate.odeint` — legacy, SciPy explicitly recommends `solve_ivp` for new code.
- Thermal ODE is likely stiff (fast surface/bulk temperature gradients); `RK45` will be slow or unstable. Budget this during Phase 1.
- If per-stint simulation is slow (>2s budget blown), JIT the brush-model slip inversion inner loop. Don't add it preemptively — profile first.
### FastF1 Integration
| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| **fastf1** | 3.8.2 (latest March 2026) | F1 telemetry/timing data access | HIGH |
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
| Option | Verdict | Reasoning |
|--------|---------|-----------|
| **PyMC + NumPyro backend** (recommended) | Best fit | Familiar PyMC model specification (the calibration spec doc is presumably written in PyMC idioms). JAX-compiled NUTS gives ~2.9x ESS/s vs default PyMC on CPU. 15–20 params is trivially in the efficient range for NUTS. |
| **PyMC + nutpie backend** | Solid fallback | Rust-based, often faster on very small models. Numba compile is slower than JAX first-time (~seconds), but per-sample throughput can edge out NumPyro for tight posteriors. Use if NumPyro gives gradient trouble. |
| **Raw NumPyro** | Rejected | You'd rewrite the calibration spec doc. PyMC's model DSL is better for seven-module physics priors with interpretable names. |
| **Stan (via CmdStanPy)** | Rejected | Precompile dependency (C++ toolchain), slightly faster on very small models but loses the ~3x JAX advantage. Adds deployment complexity. |
| **BlackJAX** | Rejected for v1 | Lower-level, reasonable if you outgrow NumPyro but no reason to start there. |
| **Variational (ADVI)** | Keep in back pocket | PyMC's `pm.fit()` is available for mean-field ADVI if full NUTS posterior calibration exceeds patience during Phase 2. Trade: less accurate uncertainty tails. |
- (A) Rewrite hot paths in `jax.numpy` (straightforward if physics is mostly arithmetic + `solve_ivp`-equivalents via `diffrax`). Best performance.
- (B) Wrap NumPy model as a black-box log-likelihood via `pm.CustomDist` / `Potential` — works but loses JAX speedup; sampling falls back to default backend.
- (C) Use `numpyro` directly with a `pure_callback` to NumPy — works with some overhead.
### Data & Persistence
| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| **SQLite** | 3.40+ (stdlib) | Versioned parameter storage, per-stint simulation cache | HIGH |
| **SQLModel** or **SQLAlchemy 2.0** | latest | Typed DB access layer | HIGH |
| **Alembic** | 1.13+ | Schema migrations (param table schema will evolve) | HIGH |
### Task Execution Strategy
| Approach | Fit for `/simulate` (<2s budget) | Fit for offline calibration |
|----------|-----------------------------------|-----------------------------|
| Sync route in FastAPI threadpool | **Recommended for v1 `/simulate`** — simple, within budget, no new infra | Not suitable |
| FastAPI `BackgroundTasks` | Wrong tool — fire-and-forget, no result retrieval | Not suitable |
| **ARQ + Redis** | Overkill for v1 if simulation stays <2s; the right upgrade path if not | Good for calibration jobs |
| Celery | Rejected — too heavy; designed for large distributed workers | Works but heavyweight |
| Offline script + SQLite writeback | N/A | **Recommended for calibration** — brief explicitly says calibration is offline |
## Frontend
### Core Framework
| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| **React** | 19.x | UI framework | HIGH |
| **TypeScript** | 5.6+ | Type safety (strict mode) | HIGH |
| **Vite** | 6.x | Dev server + build | HIGH |
### Visualization
| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| **D3** | 7.9+ | Scales, shape generators, interpolators, color | HIGH |
| **Three.js** | r170+ | 3D/2D track map rendering (WebGL) | HIGH |
| **@react-three/fiber** | 9.x | React reconciler for Three.js scene graph | MEDIUM |
| **@react-three/drei** | 10.x | Common Three.js helpers (OrbitControls, Line2, etc.) | MEDIUM |
- Use `d3-scale`, `d3-shape`, `d3-array`, `d3-interpolate`, `d3-axis` to *compute* path data, domains, tick positions.
- Render SVG/Canvas elements from React JSX.
- This is the "D3 for math, React for DOM" pattern — standard in 2026.
- The brief says "2D track rendering with animated car position." A flat 2D track doesn't need Three.js — it can be an SVG path with a moving `<circle>`, driven by `requestAnimationFrame`.
- **Use Three.js only if** (a) you want 3D elevation from telemetry, (b) you want smooth GPU-accelerated animation of many concurrent points, or (c) you anticipate a 3D extension in v2.
- **Recommendation:** Start with SVG for track map; defer Three.js to v2 unless 3D is a brief-level requirement. Re-read the brief — "Three.js for 3D track map" is in the constraints, so keep it, but be ready to drop it if 3D turns out to be scope creep.
- **Recharts**: Too opinionated, can't do the multi-chart linked-hover Zone 4 layout cleanly.
- **Nivo**: Pretty defaults but heavy, slow on dense data, hard to customize.
- **Victory**: Declining maintenance momentum.
- **Chart.js**: Canvas-based, fine but no TypeScript-first story, hard to integrate linked-hover across charts.
- **Plotly.js**: Bundle size is enormous (~3 MB), interactive charts feel generic/boxy, not dashboard-grade.
- **visx (Airbnb)**: Reasonable if team finds D3 intimidating, but you're already committed to D3. Visx adds a layer you'll outgrow.
- **Observable Plot**: Great for exploratory notebooks, not for custom dashboards with linked interactions.
### State & Data
| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| **TanStack Query** | v5 | Server state cache (races, drivers, simulation results) | HIGH |
| **Zustand** | 5.x | Client UI state (selected lap, playing/paused, hover timestamp) | HIGH |
- Implement via a small custom hook syncing Zustand state ↔ `window.location.hash` on change. Don't add a router for this.
- If routing grows in v2, add TanStack Router (not React Router) — better TS inference.
### Styling
| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| **Tailwind CSS** | 4.x | Utility CSS for layout, spacing, theme tokens | HIGH |
| **CSS custom properties** | — | Dark theme tokens (deep navy, compound colors) | HIGH |
### Developer Tooling
| Tool | Purpose |
|------|---------|
| **Biome** 1.9+ OR **ESLint 9 + Prettier** | Lint + format (Biome is faster and single-binary; pick one) |
| **Vitest** 2.x | Unit tests for scale/formatter/state logic |
| **Playwright** 1.49+ | E2E for the critical user flow (pick stint → run → scrub) |
| **MSW** 2.x | Mock FastAPI responses during frontend dev |
## Deployment
### Recommended architecture
| Layer | Platform | Rationale | Confidence |
|-------|----------|-----------|------------|
| Frontend static assets | **Vercel** (or Cloudflare Pages) | Free tier, global edge CDN, zero-config Vite deploys | HIGH |
| FastAPI backend | **Fly.io** (shared-cpu-2x or performance-1x) | Docker-native, Performance CPU available, no serverless timeout, persistent filesystem for SQLite + FastF1 cache | HIGH |
| Database | SQLite on Fly.io volume (v1) → managed Postgres (Fly Postgres or Supabase) when multi-instance needed | Brief says "Postgres later" | HIGH |
### Why Vercel is wrong for the backend
- Free tier: 60 s function duration (with Fluid Compute).
- Pro tier: up to 14 min duration with Fluid Compute, 800 s max.
- 500 MB uncompressed bundle cap.
### Why Fly.io is right
- Docker container: install any scientific Python stack with no size cap.
- **Persistent volumes** (Fly Volumes): mount `/data` for SQLite + FastF1 cache directory.
- Performance CPU option: dedicated, non-burstable cores for the physics solve.
- Scale-to-zero supported (with first-request warmup cost ~500ms–2s on a 1x shared). For v1 traffic levels, 1 always-on shared-cpu-2x machine ($5–10/mo) is simpler.
- Global anycast: fine for a dashboard app, doesn't matter much here.
### Fly.io deployment shape
### Alternative: Railway
### Rejected: Render
### Rejected: AWS Lambda / Google Cloud Run (serverless)
### Frontend deployment note
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
## Open Questions
## Sources
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
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
