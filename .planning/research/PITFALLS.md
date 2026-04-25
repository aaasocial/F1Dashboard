# Pitfalls Research — F1 Tire Degradation Analyzer

**Domain:** Physics-informed simulation + scientific web app over public F1 telemetry
**Researched:** 2026-04-23
**Overall confidence:** MEDIUM-HIGH (FastF1 + scientific computing pitfalls well documented; Bayesian physics-model identifiability is a known-hard problem with established literature; F1 legal ambiguity is documented but not litigated for this class of tool)

---

## Critical Pitfalls

*Severity: Critical — project-ending if missed. These either kill the product's credibility, break the <2s SLA, or create legal/deployment landmines.*

### C1. Bayesian calibration is non-identifiable with 15–20 correlated parameters

**What goes wrong:** The seven-module model has parameters that cannot be distinguished from data — e.g. thermal-conductivity and convective-cooling coefficients trade off to produce identical lap-level temperature curves; friction scaling and brush stiffness are confounded when you only observe lap times and GPS. MCMC produces a posterior that looks converged on marginals but has banana-shaped joint distributions. Predictions with "confidence intervals" end up with either (a) absurd uncertainty because the sampler is exploring an unidentifiable ridge, or (b) falsely tight CIs because the prior is doing the work.

**Warning signs (detect early):**
- Pair plots show strong linear/curvilinear correlations between posterior parameters (|ρ| > 0.9)
- Posterior means sit on the prior mean when data is informative — prior is dominating
- Posterior mean is far from prior mean with wide CI — likelihood is flat, prior saturates
- ArviZ `r_hat > 1.01` or ESS < 400 per chain even after long warm-up
- Divergences in NUTS even after `target_accept=0.95`
- Removing a parameter doesn't change posterior predictive — that parameter is unidentifiable

**Prevention:**
- **Do a local sensitivity analysis BEFORE calibration:** for each parameter, perturb ±20%, measure effect on observables. If effect is zero or mirrors another parameter, fix it from physics or marginalize it out.
- **Use the sequential four-stage calibration from the brief religiously** — don't collapse it into one joint fit. Stage ordering (aero → friction → thermal → degradation) is specifically the remedy from the identifiability literature ([Kennedy-O'Hagan work](https://pmc.ncbi.nlm.nih.gov/articles/PMC6156799/)).
- **Reparametrize funnels:** non-centered parameterization for hierarchical scales (driver effects, compound effects).
- **Tight physics priors, explicit and documented:** every parameter needs a prior with a cited reference, not uniform. `pm.Normal("tread_conductivity", 0.2, 0.05)` with a comment citing Grosch.
- **Simulation-based calibration (SBC):** before running on real data, generate fake data from known parameters, verify posterior recovers them. If it doesn't, the model is broken before you touch real data.

**Phase:** Backend Phase — Bayesian calibration phase. Cannot be deferred. If identifiability fails, the entire "confidence intervals from posterior" promise collapses.

---

### C2. <2s simulation budget blown by MCMC or Python loops

**What goes wrong:** The <2s target is per-simulation (user clicks Run). Naive implementation hits this three ways:
1. Accidentally re-running MCMC inside `/simulate` instead of loading pre-fitted posteriors from SQLite — full MCMC is minutes-to-hours for 15–20 params.
2. Per-timestep Python loops through 90 laps × thousands of time steps × 4 tires instead of vectorized numpy — 100× slowdown is typical ([vectorization speedups](https://medium.com/data-science/vectorization-must-know-technique-to-speed-up-operations-100x-faster-50b6e89ddd45)).
3. Using `scipy.integrate.odeint` with an explicit RK45 solver on a stiff thermal ODE (tread-carcass has multi-second time constant, surface has sub-second) — solver takes tiny steps for stability, blowing the budget.

**Warning signs:**
- End-to-end simulate request > 500ms in dev on a single stint
- cProfile shows >20% of time in pure-Python `for` loops
- Wall-clock time scales linearly with stint length (should be near-sublinear if vectorized properly)
- `solve_ivp` with RK45 reports "making unusually many iterations" or stalls — classic stiff signal ([SciPy solve_ivp docs](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html))
- Memory spikes during simulation — you're materializing per-timestep arrays you don't need

**Prevention:**
- **Architectural firewall:** `/simulate` NEVER runs MCMC. It loads pre-computed posterior samples from SQLite (or a single MAP estimate + covariance for fastest path) and does forward simulation only. Calibration is an offline batch job.
- **Sample from posterior, don't re-run it:** for confidence intervals, draw N=50–200 parameter samples from the saved posterior, run the forward model once per sample (vectorizable across samples), take quantiles of predicted observables.
- **Stiff solver from day one:** `solve_ivp` with `method='BDF'` or `'Radau'` for the thermal ODE. Supply an analytical Jacobian if possible — otherwise sparse finite differences. Benchmark vs RK45 to confirm stiffness is the issue.
- **Vectorize across laps and tires:** batch one stint into a `(n_laps, 4_tires, n_timesteps)` tensor; numpy the whole forward pass. Use Numba `@jit` on the ODE RHS if pure numpy isn't enough ([Numba + odeint speedup](https://gist.github.com/moble/3aa44230256b66956587)).
- **Budget explicitly:** draft a time-budget table now (FastF1 fetch: 0ms cached / 0.5s miss; kinematic prep: 100ms; thermal ODE: 500ms; brush inversion: 300ms; degradation accumulation: 100ms; response serialization: 100ms). If any module exceeds its budget, it's flagged for optimization.
- **Set `nuts_sampler="nutpie"` or `"numpyro"`** for offline calibration — 2–5× faster than vanilla PyMC NUTS for this problem size ([PyMC sampler backends](https://www.pymc.io/projects/docs/en/stable/api/samplers.html)).

**Phase:** Backend Phase — must be designed in from Day 1. Retrofitting vectorization and pre-computed posteriors is a rewrite.

---

### C3. FastF1 data quality landmines invalidate a whole stint silently

**What goes wrong:** FastF1 documents that it "partially mixes data from multiple endpoints to correct for errors" but doesn't guarantee integrity. Known specific failures:
- **Throttle = 104 / sentinel values:** FastF1 emits throttle=104 as a "no data" flag during stationary moments ([data quality thread](https://x.com/drivenbydata_/status/1504134996319166480)). Feeding this to a physics model produces garbage forces.
- **Missing lap times on RUS at 2025 Bahrain (and similar transponder issues):** fixed in later versions by imputing from sector times, but older versions return NaN lap times silently.
- **Tire compound mislabeled:** 2025 Belgian GP intermediate stints labeled as MEDIUM ([FastF1 issue #779](https://github.com/theOehrly/Fast-F1/issues/779)). If your model applies dry-compound priors to a wet stint, predictions are meaningless.
- **Missing laps-to-grid:** if live timing recording didn't start pre-session, FastF1 thinks cars weren't on track until first pit stop.
- **Mexico FP1 POU case:** 4 laps with NaN LapTime broke `pick_fastest()`.
- **Inlap / outlap confounders:** an outlap includes cold tire warmup and pit-release acceleration; an inlap includes deliberate slow-down. Neither is representative of "normal" tire behavior but both are in the stint.

**Warning signs:**
- NaN / sentinel values in telemetry (throttle==104, speed==0 mid-lap, brake==True for entire lap)
- `pick_quicklaps()` returns empty set for a driver who clearly raced
- Sudden discontinuity in tire compound within a stint (stint number same, compound changes)
- PitInTime/PitOutTime populated on a lap that's also treated as a "normal" stint lap
- Elevation profiles don't align across comparison laps — the F1technical thread warns this indicates telemetry integrity problems
- Data for post-2022 race has holes that mirror the live-feed outage at that real event

**Prevention:**
- **Defensive ingestion layer:** separate module `data_integrity.py` that runs on every fetched stint and returns a quality report (missing lap fractions, sentinel value counts, compound continuity checks, pit-lap flags). Simulate refuses to run if quality score is below a threshold, OR runs with an explicit "degraded data" watermark in the output.
- **Explicit inlap/outlap handling:** filter them from the calibration dataset; in user predictions, display them differently (greyed-out data points with tooltip "pit lap — physics model not applied").
- **Pin FastF1 version; monitor upstream:** `fastf1==3.6.x` or later (which fixed the Bahrain transponder issue); subscribe to FastF1 GitHub releases for data-quality fixes affecting races you've calibrated on.
- **Known-bad races list:** maintain a manually curated denylist (`data/known_issues.yaml`) of specific sessions with confirmed data problems (2025 Belgian wet stints, any session with confirmed FastF1 issues). The `/races` endpoint can still show them with a warning badge rather than hiding them.
- **Round-trip test:** for each calibration race, load it fresh and verify row counts match a pinned snapshot. If FastF1 changes upstream, you notice.

**Phase:** Backend Phase — data ingestion and integrity checks are the first thing built. Calibration and simulation both depend on clean data.

---

### C4. F1 / FOM copyright creates takedown risk for a public tool

**What goes wrong:** Formula 1's legal notices explicitly state that timing data and derived telemetry are copyrighted and database-protected, and that their content is for "personal, non-commercial use only" ([F1 Legal Notices](https://www.formula1.com/en/information/legal-notices.7egvZU48hzrypubGBNcQKt)). FastF1 itself is explicit that it is "unofficial and not associated with the Formula 1 companies." FOM actively enforces takedowns on derivative works that republish live/historical timing. A public website that caches and redistributes per-lap telemetry could receive a takedown notice, and F1's terms prohibit automated access that could "damage, disable, or overburden" their services — which live-timing scraping arguably does. Bare facts (lap times) are not copyrightable in the US but compilation/database rights apply in the EU/UK.

**Warning signs:**
- Product presented as commercial (paywall, ads, sponsored features) without a license from FOM
- Product frames itself as "official" or uses F1/FIA/Pirelli trademarks in the branding
- Product exposes raw FastF1 caches for download, essentially redistributing FOM's feed
- High traffic from the app triggers livetiming rate-limit pushback
- Feature requests creep toward live/real-time data rather than historical-only

**Prevention:**
- **V1 is non-commercial only.** Add an unmistakable footer: "Unofficial fan tool. Not affiliated with Formula 1, FIA, or any F1 team. Data via FastF1." Matches FastF1's own approach.
- **No trademarked assets.** Don't use the F1 logo, team logos, Pirelli compound graphics. Use generic geometric shapes and letters (S/M/H) with color coding. Not "Red Bull Racing" — just the driver's car number and an anonymized team name if needed.
- **Historical data only.** The brief already scopes live integration OOS — keep it that way. Real-time is what FOM most aggressively defends.
- **Server-side caching is a one-way door, not a redistribution point.** Don't expose the FastF1 cache as a download; keep it an internal implementation detail. The `.ff1` drag-drop feature in the brief should load a user's own local cache, not fetch/serve FOM-owned data on their behalf.
- **Include an explicit takedown contact** in the footer so FOM (if they notice) escalates to email rather than a lawyer.
- **Before any monetization conversation:** consult a lawyer or transition to a public, officially-sanctioned data source (F1 Strategy API if/when one exists).

**Phase:** Project-level — decide in Phase 0. Affects branding, deployment, and every later commercialization decision.

---

## High-Risk Pitfalls

*Severity: High — major rework if missed.*

### H1. Three.js + React memory leaks from geometry/material churn

**What goes wrong:** Track map animation in Zone 2 continuously re-renders as user scrubs. Naive React + Three.js pattern creates new geometries and materials inside `useEffect` without disposing the old ones. WebGL entities are NOT garbage-collected automatically — they live in GPU memory until `.dispose()` is called on each geometry, material, texture, and render target ([Three.js docs on disposal](https://discourse.threejs.org/t/dispose-things-correctly-in-three-js/6534)). After 10 minutes of scrubbing the user's tab is consuming 2 GB of GPU memory and Chrome tab crashes.

**Warning signs:**
- Chrome DevTools Memory tab shows steadily growing GPU memory
- Three.js `renderer.info.memory` reports growing geometry/texture count after any user interaction
- Tab crashes with "Aw, Snap!" after 5–10 minutes
- `scene.clear()` is called but memory doesn't drop
- WebGLRenderer recreated on every route change/component remount

**Prevention:**
- **Single renderer, single scene per app lifetime.** Create renderer in a ref, not in state. Never recreate on re-render. Dispose only on full unmount (top-level App cleanup).
- **Dispose protocol in every useEffect:** cleanup function calls `.dispose()` on geometry, material, and texture; removes from scene; calls `renderer.renderLists.dispose()` after scene changes.
- **Prefer react-three-fiber over hand-rolled Three.js in React:** it handles disposal via reconciler automatically. The brief says "D3 + Three.js" but react-three-fiber is the mature default for this combo in 2026.
- **Reuse geometries for static track shapes.** Create the track geometry once; only mutate uniform positions / colors for animation.
- **Memory leak test in CI:** a headless test that mounts/unmounts the dashboard 100 times and asserts GPU memory returns to baseline.

**Phase:** Frontend Phase — before Three.js is introduced into the Zone 2 track map.

---

### H2. D3 vs React DOM ownership war

**What goes wrong:** The classic mistake: put D3 selections inside a React component, and both try to own the DOM. Either D3 mutates nodes React thinks it owns (React removes them on next render, D3 rebinds them to phantoms, chaos), or you disable React's reconciliation for that subtree and lose React benefits. Either way, linked charts (hover highlighting across 4 charts + track map) become a nightmare of stale refs and ghost tooltips.

**Warning signs:**
- Hovering chart A highlights chart B, then reloads and highlights are gone
- Chart tooltips duplicate or become stuck
- "Maximum update depth exceeded" or "can't perform a React state update on an unmounted component" warnings in console during chart interactions
- DOM inspector shows SVG elements React doesn't know about
- Resizing breaks the chart until a refresh

**Prevention:**
- **Pick one pattern and enforce project-wide:** either "React renders JSX, D3 does math/scales only" (recommended by most 2025 guides) or the faux-DOM approach. Don't mix.
- **Recommended split for this project:** React owns SVG structure (axes, grid, lines as JSX using D3-computed paths). D3 owns scales, line generators, zoom behavior, brush, tooltip positioning. No `d3.select(ref).append(...)` anywhere.
- **Linked-chart highlighting via shared state (Context or Zustand), not via D3 selections.** Each chart reads `hoveredLap` from context and re-renders its highlight band via React.
- **Canvas for high-density charts:** 1000+ points per chart × 4 charts = 4000+ SVG nodes, near the ~1000-node pain threshold for smooth SVG. Use canvas for the dense line charts, SVG for axes/overlays/interactive elements. Consider d3fc or visx for hybrid patterns.

**Phase:** Frontend Phase — decide the pattern before building the first chart. Switching later requires rewriting every chart component.

---

### H3. Serverless cold starts + PyMC/numpy deployment size exceeds Vercel limits

**What goes wrong:** Vercel serverless functions cap at ~250 MB unzipped (500 MB for some plans); numpy + scipy + PyMC + pandas + FastF1 + FastAPI easily exceeds this, especially with PyMC's PyTensor backend ([Vercel size limits](https://github.com/vercel/community/discussions/4354)). Even if you squeeze it under, cold starts are 8–20s because Python has to import the whole scientific stack before it can serve a request. The user clicks Run, FastAPI cold-starts, FastF1 cache miss triggers a 3s fetch, model runs in 1.5s, first response arrives at 15s. The <2s SLA is a joke.

**Warning signs:**
- Deploy fails with "function exceeded maximum size" on Vercel
- First request after idle takes >5s even on a cached stint
- P99 latency 10× the P50 — cold starts are driving the tail
- `time python -c "import pymc"` > 3s locally (cold-start proxy)

**Prevention:**
- **Deploy to Fly.io as long-lived container, not Vercel serverless.** Fly's default shared-cpu-1x / 1GB RAM holds the scientific stack warm. The brief says "Vercel/Fly.io" — Fly.io is the right answer for this workload. Vercel is fine for the React frontend only.
- **Separate frontend and backend deployments.** Frontend to Vercel/Netlify (free, CDN, fast). Backend Python to Fly.io as a persistent container.
- **Bake the FastF1 cache into the backend container image** for the calibration races and the top ~20 most-requested races. Cold cache fetch on a popular race is 3s of FOM-facing latency the user shouldn't pay.
- **If serverless is non-negotiable:** strip PyMC from the runtime entirely. Calibration happens offline; the serving container only needs `numpy`, `scipy`, `fastapi`, `fastf1`. Posterior samples ship as a pickled array in the image. That drops deployment size to ~100 MB.
- **Warm-up ping / min-instances-1.** Fly.io `auto_stop_machines=false` or similar to avoid scale-to-zero.

**Phase:** Deployment phase — but the decision between serverless and container affects the backend architecture (stateful SQLite? filesystem cache?) and must be made early.

---

### H4. FastF1 cache on ephemeral serverless filesystem = redundant fetching + rate-limit risk

**What goes wrong:** FastF1 caches parsed session data on disk. On serverless (Vercel Functions, AWS Lambda), the filesystem is ephemeral — every cold start loses the cache. The app re-fetches from livetiming.formula1.com on every cold start, turning a cached 0.1s load into a 3–5s round-trip. At scale this (a) blows the <2s SLA, (b) gets the IP rate-limited by FOM, (c) actually triggers the "automated use that overburdens services" legal clause from F1's terms.

**Warning signs:**
- FastF1 logs show "Fetching data from API" on every request rather than cache hits
- Response times bimodal: fast (cached) or slow (fresh)
- Requests to livetiming.formula1.com show up in monitoring
- Intermittent 429 responses or timeouts from FastF1's internal API calls

**Prevention:**
- **Persistent volume on Fly.io** for the FastF1 cache — `fly volumes create fastf1_cache --size 5`, mount at `/data/fastf1_cache`, set `FASTF1_CACHE=/data/fastf1_cache`.
- **Pre-warm the cache at container build or first boot** with the calibration races + top-20 historical races. Ship a `warmup.py` script that runs on container start.
- **Consider cloud object storage (S3/R2) + custom cache backend** if you outgrow a single volume. The FastF1 maintainer's Discussion #787 acknowledges this is an open area.
- **Circuit-break on FastF1 failures:** if livetiming returns an error, serve the last-known-good cached data and flag the response as stale rather than hammering the API.

**Phase:** Backend Phase — cache strategy is coupled to deployment choice (H3).

---

### H5. Prior sensitivity — too tight = model can't learn; too loose = MCMC doesn't converge

**What goes wrong:** The brief's physics-first framing leans on priors from academic papers (Pacejka, Kobayashi, Grosch, WLF) to substitute for missing team data. Two failure modes:
1. **Too tight:** priors narrow around literature values that don't match current (2022+) F1 tire compounds. Posterior is stuck at the prior mean, model fits badly, users don't trust predictions.
2. **Too loose:** uniform or very-wide priors on all 15–20 parameters. MCMC explores vast unlikely regions, chains don't mix, r-hat > 1.1, samplings takes hours.

**Warning signs:**
- Posterior mean ≈ prior mean AND posterior std ≈ prior std (data didn't update the belief — prior too tight)
- Posterior wanders off to physically unrealistic values (negative friction coefficients, tread conductivity 10× literature — prior too loose or unconstrained)
- Sampler divergences concentrate in one region of parameter space (prior is pulling into a physics-impossible zone)
- Posterior predictive check: predicted lap times cluster in the middle of the observed range, never at extremes (classic over-regularized symptom)

**Prevention:**
- **Document every prior with a citation and a justification:**
  ```python
  # Pacejka (2012), Table 4.3 for contemporary F1 compounds
  # Std=0.05 allows ~2σ to span the range reported across 2022-2025 seasons
  mu_friction = pm.Normal("mu_friction", mu=1.4, sigma=0.05)
  ```
- **Run a prior predictive check FIRST.** Before calibration: draw 1000 samples from the prior, forward-simulate, plot predicted lap times against realistic F1 lap time ranges (~80–120s depending on circuit). If prior-predictive extremes are 60s or 200s, your priors are way too loose.
- **Hierarchical pooling across drivers, compounds, circuits** rather than tight per-combination priors. Let the model share information.
- **Sensitivity analysis on the posterior:** double each prior's std, rerun; if posterior shifts significantly, the prior is doing too much work. If it doesn't shift, prior is fine.

**Phase:** Backend Phase — Bayesian calibration. Needs a dedicated "prior specification" sub-task separate from the sampling code.

---

### H6. Overfitting to one circuit — model looks great on Silverstone, embarrassing on Singapore

**What goes wrong:** Temperate European tracks dominate academic tire literature and F1 data abundance. The team calibrates and validates on Silverstone/Monza/Spa, hits great RMSE, ships. Then a user loads Singapore (high temp, low-speed street circuit) or Las Vegas (cold, abrasive) and predicted temperatures are off by 40°C, grip is off by 30%. Users lose trust instantly because the product is demonstrably wrong on one of the most-watched races.

**Warning signs:**
- Calibration dataset is all-European or all-one-season
- Posterior predictive checks pass on training circuits but no held-out test on climate-extreme circuits
- Ambient temperature parameter has narrow posterior (model hasn't seen cold/hot extremes to learn from)
- The first user report of "this looks wrong" comes from Singapore/Vegas/Baku

**Prevention:**
- **Stratified held-out test set:** the brief specifies "multi-season data with held-out races for validation" — make the hold-outs deliberately spanning climate extremes (Silverstone AND Singapore AND Vegas AND Monaco AND Spa-wet AND Baku).
- **Circuit-level hierarchical parameters:** track-specific offsets to temperature and friction rather than a single global set. Let the model say "I know less about Vegas than Silverstone" and widen CIs accordingly on sparse circuits.
- **Publish a validation dashboard:** inside the app or in docs, show RMSE per circuit. Users self-calibrate their trust. "This model is ±5% on Silverstone, ±15% on Vegas" is more honest than a single headline number.
- **Add a "confidence" badge per prediction:** wider posterior CI on under-represented circuit conditions — surface the uncertainty the Bayesian model already knows.

**Phase:** Calibration phase — validation strategy must be designed before the first calibration run, not after.

---

## Medium-Risk Pitfalls

*Severity: Medium — annoying but recoverable.*

### M1. URL hash state encoding exceeds browser limits for complex scenarios

**What goes wrong:** Scenario state (race + driver + stint + time cursor + selected tire + chart zoom states + panel visibility) encoded as JSON in `#state=...` can easily exceed 2000 characters once v2 features (what-if sliders with 15 parameter overrides) land. Browsers accept up to 8000 chars but some services (Slack, Twitter, email clients) truncate at 2000 when rendering link previews. Shared links silently drop state.

**Warning signs:**
- Copy-pasted URL reloads with partial state
- Hash > 1500 chars after normal usage
- Shared-link-to-social previews show truncated URLs

**Prevention:**
- **Minimize keys + use short names:** `#r=2024_spa&d=ver&s=2&t=34` not `#raceId=...&driverId=...`.
- **Compress:** `lz-string` for URL-safe compression of any JSON state larger than 200 chars.
- **Server-backed short-URL for v2:** when what-if sliders arrive, POST scenario, get back `/s/abc123`, share that. Keep hash state for back-button navigation only.
- **Cap and warn:** if encoded state > 1800 chars, show a "state too complex to share via URL, copy share link" affordance.

**Phase:** Frontend Phase — design URL encoding scheme early so you don't paint yourself into a corner.

---

### M2. Pit-stop markers, SC periods, red-flag interruptions confuse the model

**What goes wrong:** A stint is not a continuous running period. Safety car periods, VSC periods, red flags, and in/out laps all break the assumption that tires continuously accumulate energy/temperature. A red flag where cars go into the garage and sit for 20 minutes produces a tire-cooling event the model won't capture unless told about it. Predictions after the red flag look wrong.

**Warning signs:**
- Race control messages in the stint period are ignored
- Predicted temperature continues rising smoothly through a 20-min red flag
- User reports "model predictions diverge after the SC period"

**Prevention:**
- **Parse FastF1 race control messages** and annotate the stint with SC/VSC/red-flag intervals.
- **Model these as reset events:** thermal state cools (known cooling law during stationary or low-speed), cumulative-energy clock pauses.
- **Display event markers on charts** (shaded bands in Zone 4) so users can see the model is accounting for them.
- **Validate on races with known SCs** (e.g. Baku is a safe bet) as a calibration test.

**Phase:** Backend Phase — after basic thermal ODE works but before validation.

---

### M3. Module interface drift breaks the "swappable modules" promise

**What goes wrong:** The brief explicitly requires each of the 7 physics modules to be swappable without touching others. In practice developers pass `kwargs` around, mutate shared dicts, or reach into other modules' internals for convenience. A year later, swapping the brush model for an alternative requires changing 4 other modules.

**Warning signs:**
- A physics module imports from another physics module (other than the public interface)
- Unit tests of one module require fixtures from another
- Changing the output type of one module triggers changes in modules not directly downstream

**Prevention:**
- **Define typed data contracts** between modules from Day 1 — Pydantic models or dataclasses. `KinematicState`, `ContactPatch`, `ThermalState`, etc. Each module takes and returns these, never raw dicts.
- **Unit test each module in isolation** with synthetic inputs. If a module's test needs another module to run, the contract is leaky.
- **The Jupyter notebook in the brief** is the contract documentation — each notebook cell instantiates one module in isolation with known inputs and shows known outputs. If the notebook breaks, the contract was broken.

**Phase:** Backend Phase — from Day 1 when module skeletons are laid out.

---

### M4. Calibration parameter versioning without DB schema support → silent drift

**What goes wrong:** The brief calls for parameters stored in "versioned SQLite database, tagged per simulation result." Naive implementation: one table, `UPDATE` on recalibration. Now you can't reproduce a simulation from 3 weeks ago because the parameters changed. Worse: old cached predictions in the UI claim confidence intervals from the *new* posterior.

**Warning signs:**
- No `calibration_id` or `version` column joining parameters to simulation results
- Rerunning the same input produces different outputs (recalibration happened silently)
- No audit trail: "which parameter set produced this prediction?"

**Prevention:**
- **Schema from Day 1:** `calibrations` (id, date, git_sha, fastf1_version, training_race_ids) × `calibration_parameters` (calibration_id, parameter_name, posterior_samples_blob) × `simulations` (id, calibration_id, request_hash, result_blob).
- **Every prediction response includes `calibration_id` and model `git_sha`.** Surfaced in the UI footer as a small version string.
- **Never delete old calibrations.** `UPDATE` is forbidden; you only `INSERT` new calibration runs. Clients can request a specific calibration version.
- **Include a "model changelog"** in the docs: "Calibration v3 (2026-05-01) — added hierarchical driver effects; Silverstone RMSE improved from 0.8s to 0.5s."

**Phase:** Backend Phase — SQLite schema. Easy to get right at the start, painful to retrofit.

---

### M5. Scope creep from "just add the what-if slider"

**What goes wrong:** The brief correctly defers the what-if laboratory, compound comparison, and parameter-sensitivity sliders to v2. Once the v1 dashboard exists, every demo/test-user asks "can I try a softer compound?" The team caves on "just one slider," which requires the forward model to accept parameter overrides, which requires the API to accept them, which requires the UI to handle them, which requires validation of parameter ranges, which requires...you get the point. v1 ship date slips two months.

**Warning signs:**
- PRs that add "optional override" params to internal functions "for later"
- Frontend code that looks like it's wired up to sliders that don't exist yet
- Backlog growth exceeds burn-down for two consecutive sprints
- Design mockups start showing slider UI "as an option"

**Prevention:**
- **Hold the v1 scope line.** The brief already drew it. Print it. Pin it. The "Out of Scope" section is not advisory.
- **Lock the `/simulate` API contract:** inputs are `race_id`, `driver_id`, `stint_number`. No override params. Adding them is a v2 API version (`/v2/simulate`), a deliberate decision, not an incremental slippage.
- **Ship v1 first, then survey users** on which v2 feature to build. Often the guessed top priority is wrong once users have the tool.
- **Document the slippery slope explicitly** in team docs: "What-if sliders require parameter override path, override path requires validation layer, validation requires physics-constraint enforcement. Total estimate: 3 weeks. Not in v1."

**Phase:** Project-level — ongoing throughout v1.

---

### M6. Frontend animates predictions before they arrive — race condition on slow fetches

**What goes wrong:** Brief says "Run model triggers simulation with ~3s animated progress indicator." If simulation actually completes in 800ms (under-budget, good!), the UI shows 3s of progress for 800ms of work — feels broken. If it takes 4s (over-budget, bad!), the progress bar hits 100% at 3s and stalls — feels broken differently. If user clicks Run twice fast, two requests race and the wrong one wins.

**Warning signs:**
- Progress bar visibly out of sync with actual completion
- Rapid clicking causes UI to show stale results
- No request cancellation — aborted simulations still consume server CPU
- Animation duration hardcoded rather than data-driven

**Prevention:**
- **Indeterminate "working" animation** rather than a fake progress bar. Shader/spinner that communicates "active" without claiming a percent.
- **Streaming or phased response:** backend returns in stages (`{ phase: "loaded_telemetry" }` → `{ phase: "ran_kinematics" }` → `{ phase: "complete", data: ... }`) via SSE or WebSocket. UI shows actual progress.
- **Debounce + cancel.** AbortController on fetch; every new click cancels in-flight. Ignore out-of-order responses via request IDs.
- **Minimum animation duration** (e.g. 400ms) to prevent sub-perception-threshold flash when simulation completes in 200ms.

**Phase:** Frontend Phase — API contract decision affects backend design.

---

### M7. PyMC / PyTensor version churn breaks calibration reproducibility

**What goes wrong:** PyMC 5.x has been actively released with breaking changes to API. A calibration done with `pymc==5.10` may not load with `pymc==5.15`. Calibration posterior samples cached in SQLite as pickled arrays are even more fragile — pickled PyMC objects do NOT survive version changes.

**Warning signs:**
- Loading old calibration fails after a `pip install -U`
- `pickle.load` raises on old data
- CI and local dev produce different posteriors from same data

**Prevention:**
- **Pin exact versions in production** — `pymc==5.X.Y` with a `.lock` file (poetry, uv, or pip-tools).
- **Serialize posteriors as numpy arrays or parquet,** not pickled PyMC traces. The only thing you need at inference time is `posterior_samples: np.ndarray of shape (n_samples, n_params)`.
- **Store a `requirements.txt` / `pyproject.toml` hash with each calibration** in the DB (M4's calibration table). Reproducibility requires matching library versions.

**Phase:** Backend Phase — calibration infrastructure.

---

## Open Questions

*Anything that needs decision during planning.*

1. **MCMC vs Variational Inference for the 15–20 param problem** — MCMC is more accurate but slower (hours); ADVI is faster but doesn't capture posterior geometry for multimodal / non-Gaussian posteriors. **Proposal:** MCMC offline for calibration (slow-path is acceptable), ADVI only if MCMC fails to converge on a specific compound. Decide after first full-run of Stage 3 (thermal calibration) — that's the first stage with enough parameters to stress the sampler.

2. **Numba / Cython / pure-numpy for the forward simulation** — the <2s budget might be reachable with pure numpy; if not, Numba `@jit` or a Cython module is the next step. **Proposal:** build pure-numpy first, benchmark, only add Numba if the profiler actually demands it. Avoid premature optimization.

3. **Deployment target: Fly.io container vs Vercel serverless vs Railway** — H3/H4 strongly argue for Fly.io or Railway (persistent container + volume). The brief says "Vercel/Fly.io" — is this a hard requirement or the original author's first guess? **Proposal:** ship to Fly.io; revisit only if pain forces it.

4. **Posterior sampling count for confidence intervals** — 50 samples is fast but noisy CIs; 500 samples is smooth but 10× compute. **Proposal:** default 100, make configurable per request, surface "CI smoothness" tradeoff in admin docs.

5. **What counts as a "valid stint" for calibration?** — minimum lap count, allowed SC laps, wet/dry mixing rules. **Proposal:** define these rules in a `stint_filter.py` module before running any calibration; document in the Jupyter notebook.

6. **Handling of driver-specific effects** — two drivers on same compound at same circuit drive differently (braking patterns, throttle application). Hierarchical driver parameters or pool? **Proposal:** hierarchical pooling with a small per-driver offset on friction utilization; keeps parameter count manageable while allowing driver differences.

7. **Mobile experience scope** — brief says "view-only on mobile is acceptable." What does that mean in practice? Read-only rendering of a desktop-shared URL, or a mobile layout? **Proposal:** read-only desktop-layout rendering with horizontal scroll; no mobile-specific UI work in v1.

---

## Phase Mapping Summary

| Phase | Pitfalls to address here |
|-------|--------------------------|
| **Phase 0 — Scoping / Legal** | C4 (copyright), M5 (scope creep guardrails), Open Q3 (deployment target) |
| **Phase 1 — Data Ingestion & Integrity** | C3 (data quality), H4 (cache strategy), M2 (event-aware stint parsing) |
| **Phase 2 — Physics Modules (Forward)** | C2 (performance budget, stiff ODE choice, vectorization), M3 (module contracts) |
| **Phase 3 — Bayesian Calibration** | C1 (identifiability), H5 (prior specification), H6 (circuit stratification), M4 (versioning), M7 (reproducibility), Open Q1 (MCMC vs VI) |
| **Phase 4 — API** | M4 (calibration_id in response), M6 (progress UX contract) |
| **Phase 5 — Frontend** | H1 (Three.js disposal), H2 (D3 pattern choice), M1 (URL encoding), M6 (animation state machine) |
| **Phase 6 — Deployment** | H3 (Fly.io over serverless), H4 (persistent cache volume), C4 (non-commercial framing in UI) |
| **Cross-cutting** | M5 (scope discipline), H6 (per-circuit validation dashboard), C2 (performance regression tests) |

---

## Sources

### FastF1 / F1 data
- [FastF1 GitHub](https://github.com/theOehrly/Fast-F1) — known issues tracker
- [FastF1 Issue #779 — Wrong tyre compound data (2025 Belgian GP)](https://github.com/theOehrly/Fast-F1/issues/779)
- [FastF1 Discussion #787 — cache handling](https://github.com/theOehrly/Fast-F1/discussions/787)
- [FastF1 Issue #472 — pick_fastest inconsistency](https://github.com/theOehrly/Fast-F1/issues/472)
- [FastF1 Docs 3.8.2 — Introduction & disclaimers](http://docs.fastf1.dev/)
- [Driven By Data — telemetry data quality disclaimer](https://x.com/drivenbydata_/status/1504134996319166480)
- [Formula 1 Legal Notices](https://www.formula1.com/en/information/legal-notices.7egvZU48hzrypubGBNcQKt)
- [Formula 1 Guidelines](https://www.formula1.com/en/information/guidelines.4EOKE9RRqevL4niTK9kWyt)
- [Atlas F1 Copyright & Terms (community reference)](https://atlasf1.autosport.com/copyright.html)

### Physics / ODE / Numerics
- [SciPy solve_ivp — stiff solver guidance](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html)
- [Efficient simulation for stiff equation systems](https://tlk-energy.de/blog-en/efficient-simulation-for-stiff-equation-systems)
- [Introduction to Stiff ODEs with Python](https://edwinchenyj.github.io/scientific%20computing/stiff-python/)
- [Numba + scipy.integrate.odeint speedup gist](https://gist.github.com/moble/3aa44230256b66956587)
- [Vectorization speedups — 100x examples](https://medium.com/data-science/vectorization-must-know-technique-to-speed-up-operations-100x-faster-50b6e89ddd45)

### Bayesian calibration
- [Diagnosing Biased Inference with Divergences — PyMC](https://www.pymc.io/projects/examples/en/latest/diagnostics_and_criticism/Diagnosing_biased_Inference_with_Divergences.html)
- [Variational inference convergence — PyMC Discourse](https://discourse.pymc.io/t/variational-inference-diagnosing-convergence/15140)
- [Variational API Quickstart — PyMC](https://www.pymc.io/projects/examples/en/latest/variational_inference/variational_api_quickstart.html)
- [PyMC Samplers API — nuts_sampler options](https://www.pymc.io/projects/docs/en/stable/api/samplers.html)
- [Nonidentifiability in model calibration — PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC6156799/)
- [Bayesian Model Calibration with Integrated Discrepancy — arXiv](https://arxiv.org/html/2603.11960)
- [Pacejka parameter identification — Polimi](https://garatti.faculty.polimi.it/Publications/Conference%20Proceedings/2009_garatti_bittanti.pdf)

### Frontend / Performance
- [React + D3.js performance & DX — Medium](https://medium.com/@tibotiber/react-d3-js-balancing-performance-developer-experience-4da35f912484)
- [Working with React and D3 together — gist](https://gist.github.com/alexcjohnson/a4b714eee8afd2123ee00cb5b3278a5f)
- [Rendering 1M datapoints with D3 and WebGL — Scott Logic](https://blog.scottlogic.com/2020/05/01/rendering-one-million-points-with-d3.html)
- [Performant large-scale charts with React + D3 — Wellally](https://www.wellally.tech/blog/performant-react-d3-health-charts)
- [Three.js forum — disposal best practices](https://discourse.threejs.org/t/dispose-things-correctly-in-three-js/6534)
- [Three.js forum — when to dispose](https://discourse.threejs.org/t/when-to-dispose-how-to-completely-clean-up-a-three-js-scene/1549)
- [Roger Chi — Preventing memory leaks in Three.js](https://roger-chi.vercel.app/blog/tips-on-preventing-memory-leak-in-threejs-scene)

### Deployment
- [Vercel serverless function size limits — community discussion](https://github.com/vercel/community/discussions/4354)
- [Deploy FastAPI on Fly.io](https://fly.io/docs/python/frameworks/fastapi/)
- [FastAPI low-memory microservices](https://medium.com/@bhagyarana80/optimizing-fastapi-for-low-memory-footprint-on-microservices-6bf756f5fe8f)
- [Understanding Lambda cold starts — AWS blog](https://aws.amazon.com/blogs/compute/understanding-and-remediating-cold-starts-an-aws-lambda-perspective/)

### URL state / Frontend misc
- [URL length limits reference](https://urleditor.online/docs/parameters/max-length)
- [state-in-url limits](https://github.com/asmyshlyaev177/state-in-url/blob/master/Limits.md)
- [State management in React via URL hashes — Peter Kellner](https://peterkellner.net/2023-09-16-state-management-in-react-applications-through-url-hashes/)

### Reproducibility / Versioning
- [Versioning, Provenance, and Reproducibility in Production ML](https://ckaestne.medium.com/versioning-provenance-and-reproducibility-in-production-machine-learning-355c48665005)
- [MLflow data versioning best practices](https://lakefs.io/blog/mlflow-data-versioning/)
