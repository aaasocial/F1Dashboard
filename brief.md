# brief.md

## The one-liner

A browser-based F1 race strategy tool that predicts tire degradation using only publicly available telemetry, built on a physics-informed model no team has published.

---

## What it is

**Web app.** Runs in the browser. No install. Desktop-first (graph-heavy, multi-panel layouts), responsive down to tablet. Mobile is view-only — not designed for driving calibration runs from a phone.

**Lets F1 fans, analytics enthusiasts, fantasy league players, and journalists run the same kind of tire degradation analysis that professional race strategy teams do — without needing access to team telemetry, proprietary tire models, or bespoke simulation software.**

---

## The problem

- Tire degradation is the single most important factor in F1 race strategy, yet no public tool lets fans actually model it quantitatively.
- The industry standard even inside F1 teams is "simple linear models, manually calculated" (Todd et al., Mercedes 2025) — there is no publicly available sophisticated alternative.
- Existing F1 data tools (FastF1, F1Tempo, tomastics, Viz) show telemetry and stats but don't predict anything — they're visualization tools, not inference tools.
- Anyone trying to build their own model hits three walls immediately: (1) Pacejka tire coefficients are proprietary to Pirelli and the teams, (2) critical sensors like steering angle, wheel speeds, and tire temperatures are not in the public feed, (3) the physics involves contact mechanics, viscoelasticity, and thermal ODEs that most fans don't have the background to implement from scratch.
- Fantasy league players, journalists covering strategy calls, and fans arguing about optimal pit windows have no way to test their intuitions against a real physics model — they rely on gut feeling or outcome-based hindsight.
- Existing race strategy commentary ("they should have pitted on lap 18!") is post-hoc and qualitative. There is no tool that can answer "given the state of the race at lap 14, what was the predicted optimal window?" with a defensible quantitative answer.

---

## The solution

A web app that runs a full physics-informed tire degradation model entirely from FastF1 public data. Users pick a race, a driver, and a stint — the app pulls the telemetry, runs the model, and produces a lap-by-lap prediction of tire grip, temperature, and degradation. Users can then experiment: what if the driver had pitted 3 laps earlier? What if track temperature had been 5°C higher? What if the compound had been the SOFT instead of the MEDIUM?

**What it achieves:**
- Turns raw public telemetry into actionable strategic insight
- Lets users visualize tire state during a stint — not just lap times, but underlying grip, temperature, and accumulated energy per tire
- Reproduces the kind of "what-if" analysis that teams do with proprietary simulators, but with public data and open physics

**What it does for users:**
- Makes strategy debates concrete and falsifiable — you can test your intuition against a physics model rather than arguing opinions
- Makes tire behavior visible — you see which tire was working hardest, how hot it got, and when it started losing grip
- Lets users understand the physics by playing with parameters (higher downforce → more load transfer → faster degradation of outside front, visible in real time)

**What it looks like:**
- Clean, data-dense dashboard inspired by Bloomberg Terminal, Datadog, and professional timing graphics
- Track map at top left with the car's position animated during lap playback
- Per-tire thermal gauges showing current tread temperature within the operating window
- Main chart area showing lap-time evolution, sliding power, and cumulative tire energy as time series
- Control panel on the right for compound selection, setup tweaks, and scenario overrides

**How users interact:**
- Pick a race from a dropdown (season + event)
- Pick a driver and stint — the app auto-loads telemetry
- Hit "Run model" and watch the stint replay with all derived quantities animated
- Drag sliders to experiment: change downforce level, shift aero balance, change compound, adjust track temperature. Watch predicted degradation update.

---

## Key features

**1. Stint analyzer**
- Load any race + driver + stint from 2022-present
- See per-tire sliding power and cumulative tire energy for that stint
- Example: load Hamilton's stint 2 at 2024 Silverstone — see that his front-left tire absorbed ~2.3 MJ over 14 laps, with peak temperature reaching 118°C at the Copse exit (above the optimal 100°C window, explaining the visible tail-off in lap 12-14 lap times).

**2. Pit window optimizer**
- Given current race state, predict optimal lap to pit for each remaining compound option
- Uses the thermal degradation model + a simple track position simulator
- Example: user loads a live mid-race state (lap 22 of 50, on MEDIUM tire age 18). App predicts: "Pit now for HARD → finish P3 with 72% probability. Pit lap 26 for HARD → finish P4 with 58%. Stay out and pit lap 30 → finish P6 with 31%."

**3. What-if laboratory**
- Rerun any historical stint with modified parameters
- Example: "Verstappen's 2023 Monaco stint with 5% more rear downforce" — see how the shifted aero balance redistributes tire stress and whether the rear tires would have held up better.

**4. Compound comparison**
- Run the same stint hypothetically on all three available compounds
- Example: "What if Norris had started on SOFT instead of MEDIUM at Austin 2024?" — model predicts higher peak grip but steeper degradation curve, with crossover point at lap 16.

**5. Parameter sensitivity explorer**
- Live sliders for key physics parameters ($\mu_0$, $T_{opt}$, $C_L A$, aero balance, roll stiffness)
- See predictions update in real-time as parameters change
- Useful for learning the physics by playing with it — why does shifting aero balance forward make the front tires degrade faster?

**6. Driver comparison**
- Overlay two drivers' same-stint tire state side-by-side
- Example: compare Leclerc's vs Sainz's tire temperatures through the same stint at Silverstone to see which driver was easier on tires.

**7. Educational overlay**
- Toggleable explanation layer that annotates the charts with the physics happening
- "Lap 8 to 10: tire entering operating window, grip still building — expect best lap around lap 12"
- "Lap 15: cumulative tire energy exceeded thermal threshold, $\mu_0$ starting to decay — expect ~0.3s/lap degradation from here"

---

## How it works under the hood

**[NOTE: this section is the algorithmic spec — see full implementation in model_v1_complete.html and model_calibration_strategy.html]**

The backend runs a seven-module physics-informed tire degradation model:

1. **Kinematic front-end:** Derives lateral acceleration, path curvature, and longitudinal slip velocity from FastF1 XY position, speed, and RPM data.
2. **Vertical load computation:** Applies weight transfer (longitudinal + lateral) and aerodynamic downforce to compute per-tire vertical load at each timestep.
3. **Force distribution:** Uses Castellano et al.'s (2021) proportional-to-load split to distribute total lateral and longitudinal forces across the four tires.
4. **Hertzian contact mechanics + friction:** Computes contact patch half-length and mean pressure via Hertzian theory, then derives a load-sensitive, temperature-dependent friction coefficient $\mu(\bar{p}, T)$ from Greenwood-Williamson contact theory and Grosch's rubber friction model.
5. **Brush model inversion:** Inverts the Pacejka/Guiggiani brush tire model to recover slip angles from observed forces — no proprietary Pacejka coefficients required.
6. **Thermal ODE:** A three-node (tread / carcass / gas) lumped thermal model following Sorniotti (2009) and Kenins et al. (2019), with the friction-generated sliding power as the heat source and speed-dependent convective cooling.
7. **Cumulative energy and degradation:** Integrates total power to get tire energy. Thermal aging and mechanical wear cause a slow decay in the reference friction $\mu_0(t)$, which manifests as predicted lap-time loss.

The model is calibrated in stages: aero first (from max lateral g at known corners), then friction baseline (from fresh-tire peak performance vs. speed), then thermal parameters (from out-lap warm-up dynamics), and finally degradation rates (from stint-end lap-time trends). ~15-20 truly free parameters per compound, fitted via Bayesian inference (MCMC/variational) across a multi-season dataset with held-out races for validation.

**Implementation stack:** Python backend (FastAPI + numpy/scipy + PyMC), served via a Vercel/Fly.io endpoint. React + TypeScript frontend with D3 for custom visualizations and Three.js for the 3D track map. FastF1 data is cached server-side to avoid repeated downloads.

**This section is designed to evolve — as the model improves (better thermal parameterization, wet tire extension, compound-specific calibrations), the backend is updated but the frontend API surface stays stable.**

---

## What makes it different

**Competitors and what they do:**

- **FastF1 / F1Tempo / tomastics / Viz (community F1 analytics tools):** Visualize raw telemetry, lap times, sector splits. No prediction, no physics model.
- **F1Insight / RaceFans analytics columns:** Post-race qualitative analysis of strategy. Not quantitative, not interactive, not real-time.
- **Autosport Strategy reports:** Human-written strategy retrospectives. Good for context but not a tool.
- **F1 Manager (game):** Arcade-style strategy game with simplified tire model. Not physics-grounded, designed for entertainment.
- **Proprietary team software (Mercedes' tyre energy model, Ferrari's simulation tools, etc.):** Not publicly available. Also generally proprietary, ML-based rather than physics-first, and requires team-grade sensor data.

**Specific major differences:**

- **Predictive, not descriptive.** Existing public tools show what happened. This tool predicts what would happen under hypothetical conditions — the kind of counterfactual reasoning that strategy requires.
- **Physics-first, not ML-first.** Unlike Mercedes' LSTM/TFT approach, this model is grounded in first-principles physics (Hertzian contact, viscoelasticity, brush model). This makes it interpretable — users can understand *why* a tire degrades, not just see a prediction.
- **Public data only.** Castellano's published framework requires team-grade sensors. This adapts it to work from FastF1's much sparser public data by deriving accelerations from position, inferring slip angles from observed forces, and using physics-based priors where sensors are missing.
- **Interactive, not batch.** The sliders let users play with parameters live. This is both a learning tool and a strategy sandbox.
- **Educational.** The annotated mode teaches users the physics as they use the tool — turning tire degradation from a mysterious "the tires fell off a cliff" hand-waving into a transparent thermomechanical process.

---

## Target user

**Primary persona: Alex, 28, software engineer and F1 fan**

- Watches every race. Active on r/formula1 and Twitter.
- Plays F1 fantasy leagues; spends Saturday nights optimizing picks.
- Has a CS degree, can read a paper if motivated but isn't an academic.
- Gets frustrated when broadcasters say "the tires fell off a cliff" without explaining what that actually means.
- Wants to understand strategy calls at the level teams operate at.
- Currently uses FastF1 and free online tools to dig into data; would pay $5-15/month for a tool that does deeper analysis.

**Secondary personas:**

- **Journalists** covering strategy calls who want a quick defensible source for "why did this pit window open up?" questions.
- **Fantasy league serious players** who want an edge in picking drivers based on tire-stress-vs-compound expectations.
- **Academic/student researchers** (motorsports engineering students, mechanical engineering undergrads) who want a working reference implementation of tire physics they can dissect and extend.
- **Sim racers** running Assetto Corsa / iRacing F1 mods who want to understand what's realistic tire behavior for their custom setups.

---

## The experience

**Chronological walkthrough of typical first session:**

1. User arrives at landing page. Sees a hero visual — animated track map with a car running a lap, tire temps pulsing on the sidebar. Copy: "See what F1 teams see. Public data, real physics."
2. Clicks "Try it."
3. Lands in the main app. A tutorial overlay highlights: Race picker (top left), driver picker, stint picker.
4. Picks a recent race (default: most recent GP).
5. Picks a driver (default: the race winner).
6. Picks a stint (default: stint 1).
7. Clicks "Run model." A ~3-second progress bar animates while the backend fetches telemetry and runs the simulation.
8. Dashboard populates: track map with the car at lap 1 position, four tire thermal gauges at the sides, lap-time evolution chart below, sliding power heat map below that.
9. User hits play. The lap animates, tires heat up, power spikes in corners, lap times scroll as they tick by.
10. User pauses on lap 14. Hovers over the front-left tire gauge. Tooltip: "Front-left tire: 112°C (8°C above optimal). Grip at 91% of fresh-tire peak. Cumulative energy: 1.8 MJ."
11. User opens the "What-if" panel on the right. Drags the "Aero balance" slider 3% toward the rear. Predictions update in place — rear tires now slightly hotter, fronts slightly cooler, predicted lap times shift by ±0.05s each.
12. User discovers the "Compound comparison" button. Clicks. A second translucent trace appears on the lap-time chart showing the predicted evolution if the driver had been on SOFT instead of MEDIUM.
13. User bookmarks the session and shares a link with their fantasy-league group chat.

---

## The interface

Visual description — could be replaced with Figma frames later.

**Overall aesthetic:** Dark theme by default (F1 broadcast feel). Monospace font for data (`JetBrains Mono` or `IBM Plex Mono`, 13-14px). Sans-serif for UI chrome (`Inter`, 14-16px). Thin, precise lines. Information-dense but hierarchical. Color palette: deep navy background, off-white text, accent colors for compounds (red/yellow/white for SOFT/MEDIUM/HARD per FIA conventions), and a warm-cool gradient for tire temperatures.

**Layout zones:**

**Zone 1 — Top bar (full width, 56px tall):** App name on the left. Race + driver + stint picker dropdowns (center). User avatar + settings (right). Font: Inter 14px, subtle dividers.

**Zone 2 — Track map (top left, ~40% width, ~35% height):** 2D track rendering with the current car position as a pulsing dot. Ghost trace showing the rest of the current lap. Sector boundaries marked. Zoom/pan controls in the corner. Click any point on the track to jump the playhead to that location.

**Zone 3 — Tire array (top right, ~40% width, ~35% height):** Four tire widgets in a 2x2 grid arranged like a top-down car view (FL top-left, FR top-right, RL bottom-left, RR bottom-right). Each tire widget shows:
- A circular gauge (thickness proportional to contact pressure, color mapped to temperature)
- Numeric temperature (large, center)
- Three small readouts below: current grip %, cumulative energy (MJ), slip angle (°)

**Zone 4 — Multi-chart main panel (bottom-left, ~60% width, ~55% height):** Three stacked charts sharing an x-axis (lap distance or time):
- Top chart: lap times (bar chart, one bar per lap, with predicted vs. observed overlaid)
- Middle chart: sliding power per tire (4 colored line traces, one per tire)
- Bottom chart: tread temperature per tire (4 colored line traces)
Zoom with mouse wheel, pan by dragging, playhead scrubs as user drags. Font: monospace 11px for axes.

**Zone 5 — Control panel (right, ~30% width, ~55% height):** Tabbed interface with three tabs:
- **Scenario** — sliders for compound override, track temperature, fuel load, aero balance, downforce level, roll stiffness split. Each slider shows its current value numerically. A "reset to actual" button restores the historical values.
- **Physics** — expandable tree showing the model's internal parameters (fitted values for this race/compound). Read-only in default mode; "expert mode" toggle makes them editable.
- **Output** — CSV/JSON download buttons, shareable link generator, embed snippet for blogs.

**Zone 6 — Transport bar (bottom, full width, 48px):** Play/pause, step forward/back one lap, jump to start/end, speed control (0.5x / 1x / 2x / 4x), scrub bar with colored segments indicating sector boundaries and pit stops. Current lap/total laps readout on the right.

**Zone 7 — Status/log (collapsible, bottom):** Running log of model events: "Lap 4: tire temperatures reached operating window." "Lap 11: front-left approaching thermal limit." "Lap 16: thermal degradation threshold exceeded." Useful for learning, collapsible to save space.

---

## Interactions

**Keyboard shortcuts:**

- `Space` — play/pause
- `← / →` — step back/forward one lap
- `Shift + ← / →` — step back/forward one sector
- `Home / End` — jump to first/last lap
- `1 / 2 / 3 / 4` — focus the FL / FR / RL / RR tire widget
- `T` — toggle track map overlay
- `C` — open compound comparison
- `W` — open what-if panel
- `E` — toggle educational annotations
- `S` — save/share current scenario
- `?` — open keyboard shortcuts help
- `Esc` — close any open modal/panel

**File / sample interaction:**

- Drag-and-drop a FastF1 `.ff1` cache file onto the app to load a session without re-fetching from the API
- Drag a saved scenario `.json` onto the app to load that scenario's parameters
- Right-click any chart → "Export as PNG/SVG/CSV"
- Right-click any tire widget → "Copy metric" (puts the current values in clipboard as formatted text for sharing)
- Charts are linked: hovering on any chart highlights the same time point on all other charts and on the track map
- Clicking a tire on the track map focuses that tire's charts and dims the others
- Scenario state encoded in URL hash — reloading the URL restores the exact scenario

---

## Slogan

**"See what the tires see."**

---

## Instructions to the backend (Claude Code)

Build the backend as a Python service implementing the algorithm specified in `model_v1_complete.html` (seven-module architecture: kinematic front-end, vertical loads, force distribution, Hertzian contact + friction, slip inversion + sliding power, thermal ODE, cumulative energy + degradation) and the calibration pipeline specified in `model_calibration_strategy.html` (four-stage sequential Bayesian calibration).

Key implementation requirements:

1. Use `fastf1` library to pull raw telemetry. Cache aggressively — a given (race, driver, stint) query should fetch-once, run-many.
2. Implement each module as a standalone class with unit tests. The modules should be composable — future contributors should be able to swap the thermal module for an improved version without touching the rest.
3. Expose a REST API with these endpoints (at minimum):
   - `GET /races` — list available races
   - `GET /races/{race_id}/drivers` — list drivers who completed that race
   - `GET /stints/{race_id}/{driver_id}` — list the driver's stints
   - `POST /simulate` — given a stint and optional scenario overrides, run the model and return per-lap, per-tire predictions
   - `POST /calibrate` — trigger a re-calibration run on a specified dataset (admin only)
4. Calibrated model parameters should be stored in a versioned parameter database (SQLite initially, Postgres later). Every simulation result is tagged with the model version that produced it.
5. Keep per-stint simulation under 2 seconds end-to-end (the frontend animates the result live).
6. Publish a Jupyter notebook alongside the backend showing how each module works in isolation, for educational users who want to learn the physics.
7. Write comprehensive docstrings citing the source papers for every equation (Pacejka, Castellano, Kobayashi, Sorniotti, Kenins, Greenwood-Williamson, Grosch, WLF).
8. Expose uncertainty: every prediction should come with confidence intervals from the Bayesian parameter posterior, not just point estimates.

The frontend (separate scope, built after backend) will consume this API to render the dashboard described above.
