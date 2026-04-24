# Architecture Research — F1 Tire Degradation Analyzer

**Domain:** Physics-informed scientific web app (FastAPI + React/D3/Three.js)
**Researched:** 2026-04-23
**Overall confidence:** MEDIUM-HIGH (patterns well-established; F1-specific specifics are opinionated recommendations)

---

## System Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                             BROWSER                                     │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                     React + TypeScript SPA                         │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │ │
│  │  │ Picker Bar   │  │  Track Map   │  │    Tire Array (2x2)       │  │ │
│  │  │ (Zone 1)     │  │ (Zone 2,R3F) │  │    (Zone 3, SVG/D3)       │  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │ │
│  │  ┌─────────────────────────┐  ┌─────────────────────────────────┐  │ │
│  │  │ Multi-Chart Panel       │  │  Control Panel / Transport Bar  │  │ │
│  │  │ (Zone 4, visx/D3)       │  │  (Zone 5, 6)                    │  │ │
│  │  └─────────────────────────┘  └─────────────────────────────────┘  │ │
│  │  ┌─────────────────────────────────────────────────────────────┐   │ │
│  │  │  Status/Event Log (Zone 7)                                   │  │ │
│  │  └─────────────────────────────────────────────────────────────┘   │ │
│  │                                                                    │ │
│  │  State: Zustand (UI + scrub) + TanStack Query (server cache)       │ │
│  └────────────────────────────┬───────────────────────────────────────┘ │
└───────────────────────────────┼─────────────────────────────────────────┘
                                │ HTTPS (JSON)
                                ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          FASTAPI (ASGI)                                 │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Routers: /races, /drivers, /stints, /simulate                    │ │
│  │  Middleware: CORS, compression, request logging                    │ │
│  └───────────┬──────────────────────────────────┬────────────────────┘ │
│              │                                   │                       │
│              ▼                                   ▼                       │
│  ┌────────────────────────┐         ┌────────────────────────────────┐ │
│  │  Telemetry Service     │         │   Simulation Orchestrator       │ │
│  │  (FastF1 wrapper)      │         │   (runs 7 physics modules)      │ │
│  └───────────┬────────────┘         └───────────┬────────────────────┘ │
│              │                                   │                       │
│              ▼                                   ▼                       │
│  ┌────────────────────────┐         ┌────────────────────────────────┐ │
│  │  Physics Core           │         │   Parameter Store               │ │
│  │  7 modules, pure funcs  │◀────────│   (SQLite + NetCDF files)       │ │
│  │  1. Kinematic FE        │         │   Posterior samples per compound│ │
│  │  2. Vertical loads      │         └────────────────────────────────┘ │
│  │  3. Force distribution  │                                             │
│  │  4. Hertz + friction    │                                             │
│  │  5. Brush slip inversion│                                             │
│  │  6. Thermal ODE         │                                             │
│  │  7. Degradation accum.  │                                             │
│  └────────────────────────┘                                              │
└────────────────────────────────────────────────────────────────────────┘
                │                                   │
                ▼                                   ▼
   ┌─────────────────────────┐      ┌──────────────────────────────┐
   │  FastF1 Cache           │      │  Offline Calibration Pipeline │
   │  (disk + requests-cache)│      │  (PyMC, runs via CLI/cron)    │
   │  .ff1 files by session  │      │  Writes NetCDF posteriors      │
   └─────────────────────────┘      └──────────────────────────────┘
```

**Confidence:** HIGH — this is a conventional scientific-web-app layout.

---

## Backend Architecture

### Q1. Seven Physics Modules — Structure & Data Contracts

**Recommendation:** Each module is a pure class implementing a narrow `Protocol`, passing typed Pydantic/dataclass records between stages. Use **stdlib `@dataclass(frozen=True, slots=True)` for internal step-to-step records** (fast instantiation, numpy-friendly) and **Pydantic `BaseModel` for API-surface schemas** (validation at the edge).

This hybrid is the modern Python consensus: Pydantic at the "edge," dataclasses in the "core" — Pydantic validation is a real bottleneck inside tight loops.

**Module Protocol (one pattern to rule them all):**

```python
from typing import Protocol
from dataclasses import dataclass

class PhysicsModule(Protocol):
    """Every physics module is a callable taking a typed input
    and returning a typed output. Stateless w.r.t. lap data."""
    def run(self, inp: ModuleInput, params: CompoundParams) -> ModuleOutput: ...
```

**Seven concrete modules (each in its own file in `backend/physics/`):**

| # | Module | Input | Output |
|---|--------|-------|--------|
| 1 | `KinematicFrontEnd` | `LapTelemetry` (pos, speed, RPM) | `VehicleState` (steer angle, slip angle, yaw rate) |
| 2 | `VerticalLoads` | `VehicleState` | `WheelLoads` (Fz per wheel) |
| 3 | `ForceDistribution` | `VehicleState, WheelLoads` | `WheelForces` (Fx, Fy per wheel) |
| 4 | `HertzianContact` | `WheelForces, WheelLoads` | `ContactPatch` (area, pressure dist.) |
| 5 | `BrushSlipInversion` | `ContactPatch, WheelForces` | `SlipState` (slip ratio, slip angle per wheel) |
| 6 | `ThermalODE` | `SlipState, ContactPatch` (per dt) | `TireTemp` (carcass + tread, per wheel) |
| 7 | `DegradationAccumulator` | `SlipState, TireTemp` | `DegradationState` (grip %, cum energy) |

**Data contract rules:**

1. **One dataclass per inter-module record.** Named tightly (`VehicleState`, `WheelLoads`). Frozen so numpy array ownership is clear.
2. **Time is always explicit** — every record carries `t: np.ndarray` and shape `(N_laps, N_samples)` or `(N_laps, 4, N_samples)` for per-wheel data.
3. **Units in field names or comments.** `fz_N`, `temp_C`, `energy_MJ`. Do not trust tribal knowledge.
4. **Each module takes a `CompoundParams` bundle** (Pydantic model loaded from the Parameter Store), never reaches into globals.
5. **Orchestrator assembles the pipeline.** Modules know nothing of each other; `SimulationOrchestrator` calls them in order.

**Why classes (vs functions):** the brief explicitly says "standalone class with unit tests, swappable." Classes give you a clear `__init__` for injecting RNG seeds, logging handles, and parameter objects. They also give mypy/pyright a clean type to work against for the `PhysicsModule` protocol.

**Why not a DAG framework (Prefect/Dagster):** overkill for 7 sequential stages running in <2 s. A plain `for module in modules: state = module.run(state, params)` loop is more debuggable. Only reach for Prefect if calibration grows into a multi-week pipeline.

**Confidence:** HIGH (protocol + hybrid dataclass/Pydantic is standard Python scientific computing practice).

### Q2. FastF1 Server-Side Caching Strategy

**Recommendation:** **Two-layer cache on disk, no Redis for v1.**

1. **Layer 1 — FastF1's native cache** via `fastf1.Cache.enable_cache(path)`. This cache stores raw API responses (requests-cache SQLite) plus parsed session pickles, structured by `year/event/session`. Always on. This is the cheapest and highest-hit-rate cache.
2. **Layer 2 — App-level pickle cache per `(race_id, driver_id, stint_index)`.** After you extract and pre-process telemetry for a stint (interpolation, sector alignment, outlier filtering), pickle the resulting dataclass to `.tmp/stints/{race}_{driver}_{stint}.pkl.gz`. This is the "fetch-once" artifact the simulator consumes.

**Why not Redis:** the brief says "fetch-once, run-many per stint" — stint data is cold-read and immutable once produced. A persistent file cache survives restarts and deploys (mount as a volume on Fly.io/Railway). Redis buys you sub-millisecond reads you don't need and adds a service to deploy.

**Why not SQLite for telemetry:** telemetry is dense numpy (10–20 Hz, thousands of samples per stint). SQLite BLOBs work but are clumsier than parquet/pickle for numeric arrays. SQLite is reserved for **parameter storage** where relational queries matter (see Q3).

**Cache invalidation:** keyed on `(fastf1_version, race_id, driver_id, stint_index, preprocessing_version)`. When preprocessing code changes, bump `preprocessing_version` in a config constant and the app will re-derive. FastF1 itself exposes `ignore_version=False` which already invalidates when its format changes.

**Deployment note:** FastF1 cache folders can get large (hundreds of MB per season). Plan for a mounted volume (Fly.io volume, Railway volume, or S3 fallback). On cold start, prewarm with the 3–5 most-recent races.

**Optional Layer 3:** an **LRU in-memory cache** (`functools.lru_cache` or `cachetools.TTLCache`) for the last 10 stints deserialized, keyed by the same tuple. Cheap, saves pickle-unpickle on repeat simulations.

**Confidence:** HIGH for FastF1 layer (this is the documented pattern); MEDIUM-HIGH for app layer (opinionated but standard).

### Q3. Bayesian Calibration ↔ Simulation Interaction

**Recommendation:** **Calibration is offline and writes NetCDF; simulation reads NetCDF via a thin `ParameterStore` facade backed by SQLite (metadata) + NetCDF files (posterior samples).**

**Rationale:** ArviZ's `InferenceData` is the de-facto standard for PyMC/Bayesian output and serializes to NetCDF natively (`idata.to_netcdf`, `az.from_netcdf`). NetCDF is self-describing, multilingual, and handles labeled arrays (compound × parameter × sample) cleanly. SQLite tracks *metadata* about each calibration run so the API can answer "what parameters are active for SOFT in the 2024 dry regime?"

**Data model:**

```
SQLite tables:
─────────────────────────────────────────────────────────────────────
calibration_runs
  id (PK), version (semver-ish "v1.2.0"), created_at, stage (aero/
  friction/thermal/degradation), seed, input_races (JSON array),
  heldout_races (JSON array), commit_sha, notes

parameter_sets
  id (PK), run_id (FK), compound (SOFT/MED/HARD), regime (dry/wet),
  netcdf_path (relative path), posterior_mean (JSON),
  posterior_std (JSON), ess_min, rhat_max, active (bool)

simulation_results
  id (PK), race_id, driver_id, stint_index,
  param_set_ids (JSON array), created_at, result_path

Filesystem:
  data/posteriors/v1.2.0/soft_dry.nc
  data/posteriors/v1.2.0/medium_dry.nc
  data/posteriors/v1.2.0/hard_dry.nc
```

**Versioning contract:**
- Each calibration run gets a semver version tag. Only one `parameter_set` per `(compound, regime)` is `active=true` at a time (cheap SQL constraint).
- Every `simulation_result` records which `param_set_ids` were used — reproducibility guarantee.
- On API `POST /simulate`, response JSON includes `parameter_version` so the frontend can display it ("calibrated v1.2.0, posterior ESS=1200").

**How simulation consumes posteriors:**
- `ParameterStore.get_active(compound)` returns an `InferenceData` (or a lightweight view over it).
- For point-estimate runs: use posterior mean.
- For confidence intervals (the required feature): sample K=500 draws from posterior, run simulator K times, compute per-lap percentiles. This is the standard Monte Carlo posterior-predictive approach.
- **Performance note:** to hit the <2 s budget with K=500 draws, the physics core must be vectorized over draws (numpy broadcasting on a leading "draw" axis). This is the single most important performance decision in the project.

**Why not Postgres v1:** brief explicitly says SQLite first; Postgres later. NetCDF lives on the filesystem either way — Postgres would only replace the metadata tables, not the posterior storage.

**Confidence:** HIGH (InferenceData + NetCDF is the official PyMC/ArviZ recommendation).

### Q4. Long-Running Computations — Sync vs Async

**Recommendation:** **For v1, make `POST /simulate` synchronous** (target <2 s, well within HTTP timeout budgets). Calibration is a CLI tool, not an API endpoint (the brief confirms: "`POST /calibrate` admin endpoint — out of scope for v1").

**Endpoint taxonomy:**

| Endpoint | Shape | Duration | Concurrency model |
|----------|-------|----------|-------------------|
| `GET /races` | sync | ms | async def, reads SQLite |
| `GET /races/{id}/drivers` | sync | ms | async def |
| `GET /stints/{race}/{driver}` | sync, may trigger FastF1 fetch | 1–5 s first time, ms cached | async def; wrap blocking FastF1 call in `asyncio.to_thread` |
| `POST /simulate` | sync | <2 s target | async def; wrap numpy/scipy core in `asyncio.to_thread` |

**Why `asyncio.to_thread`:** FastAPI is ASGI/async, but numpy/scipy/PyMC are sync and CPU-bound. Running them directly in an `async def` blocks the event loop. `asyncio.to_thread` releases the loop while the physics runs on a worker thread. This is the standard FastAPI pattern for CPU-bound work.

**Why not a job queue (Celery/ARQ):** sub-2-second workloads don't need one. The tradeoffs:
- **BackgroundTasks** (FastAPI built-in): fire-and-forget, no tracking. No good for our case — user wants results back.
- **ARQ**: async-native, Redis-backed. Use this if `/simulate` grows past 10 s (e.g., K=5000 posterior draws or full-race simulation). It's a low-friction upgrade path.
- **Celery**: overkill. Multi-broker support, priority queues, mature ecosystem, but heavy — adds Redis + worker process dependency for features v1 doesn't need.

**Decision rule for future:** if any single endpoint exceeds 10 s, migrate it to ARQ + a `GET /jobs/{id}` polling endpoint. Until then, sync with `asyncio.to_thread` is simpler and observably faster for small workloads.

**Frontend UX:** the "~3s animated progress indicator" in the brief is a pure UI concern — show a fake progress bar during the <2 s wait. No server-side progress events needed for v1. If the simulation ever does cross the 5 s mark, adopt **Server-Sent Events (SSE)** for progress streaming (simpler than WebSockets, works through proxies, used in this repo's prior Word2Vec work per memory).

**Confidence:** HIGH.

---

## Frontend Architecture

### Q5. State Management

**Recommendation: hybrid — TanStack Query + Zustand. Avoid Redux Toolkit for v1.**

- **TanStack Query** owns all server state (race list, driver list, stint metadata, simulation results). This is the 2026 consensus: server state is categorically different from UI state and deserves its own tool (caching, stale-while-revalidate, request deduplication, background refetch, cache invalidation).
- **Zustand** owns UI state: current scrub position (lap index, sub-lap time), selected tire, hover timestamp, zoom/brush selection, panel collapse state, playback state (playing/paused/speed), keyboard focus.
- **URL hash** is the source of truth for `(race_id, driver_id, stint_index)` selection (brief requires shareable URLs). A small sync layer reads the hash on load and writes back on change. Zustand subscribes to the hash.

**Why not Redux Toolkit:** Redux's ~15 kB bundle + boilerplate buys you time-travel debugging and strict action patterns you don't need. Zustand is ~3 kB, has fine-grained subscriptions (critical for linked charts — only the panels subscribing to `hoverTime` re-render on hover, not the whole app), and integrates cleanly with React 18+ concurrent features.

**Why not Context:** hover events fire 60 Hz. Context-based propagation re-renders every consumer every time. Zustand's `useStore(selector)` with shallow equality is the correct primitive for high-frequency updates.

**Store shape (single Zustand store, sliced):**

```typescript
{
  selection: { raceId, driverId, stintIndex }        // synced to URL
  scrub:     { lapIndex, subLapT, playing, speed }   // transport bar
  hover:     { t: number | null, source: 'chart'|'map'|'tire' }
  panels:    { tireDetailExpanded, logExpanded, ... }
  actions:   { setHover, setScrub, play, pause, ... }
}
```

**Confidence:** HIGH (this is the dominant 2026 pattern for data-dense React dashboards).

### Q6. D3 Integration

**Recommendation:** **`visx` (Airbnb) for most charts; raw D3 refs only for the track map scrub overlay.** Do **not** use Recharts (too high-level, fights you on custom interactions). Do **not** use Observable Plot in a React app (designed for notebooks; limited interaction hooks).

**Rationale:**
- visx = D3 scales, shapes, and math + React components that render SVG. React owns the DOM; D3 does the math. No `useRef`/`useEffect` imperative escape hatch for 90% of the charts. Works naturally with TypeScript.
- For the **linked-hover behavior** (hover any chart → highlight same time across all charts + track map), visx charts emit events through React's synthetic event system, which routes cleanly into Zustand (`setHover(t)`). Other panels subscribe via `useStore(s => s.hover.t)`.
- visx supports both **SVG and Canvas** rendering. Use SVG for the multi-chart panel (thousands of points, but readable on retina and exportable to PNG/SVG as the brief requires). Use Canvas fallback only if profiling shows dropped frames.

**When to drop to raw D3 refs:**
- Complex custom brush-and-zoom with momentum.
- Track map scrub overlay (intermediate between pure D3 and React — the base track is Three.js, the scrub needle is an SVG overlay updated at 60 Hz — a `useRef` + requestAnimationFrame imperative update is the right tool to bypass React's reconciler for that layer).

**Export handling:** SVG export is trivial (serialize the `<svg>` DOM node). PNG via `canvg` or DOM-to-Canvas. CSV from the chart's underlying data series already in memory. Keep a `<ChartExportMenu>` component that takes a ref to the SVG and the raw data.

**Confidence:** HIGH for visx (well-established); MEDIUM for the track map hybrid pattern (opinionated, depends on rendering choice — see Q7).

### Q7. Three.js Track Map Integration

**Recommendation: `@react-three/fiber` + `@react-three/drei`.** Do not write vanilla Three.js inside React.

**Rationale:**
- R3F gives you declarative JSX for the 3D scene, React lifecycle for adding/removing objects (the animated car marker, sector boundaries), and hooks (`useFrame`) for the per-frame animation loop — which is where scrub playback lives.
- The whole R3F ecosystem (`drei` for controls/helpers, `postprocessing` if you want a subtle glow on the car marker) is designed around this stack.
- 2026 caveat: R3F does not yet fully support WebGPU. We don't need WebGPU for a 2D track extruded into a ribbon — WebGL is plenty. Revisit only if scaling to full 3D race replays.

**The track map is actually 2D-in-3D:**
- Track centerline polyline (from FastF1 `pos_data`) extruded to a 2D ribbon on the XY plane.
- Sector boundary markers as sprites or small extrusions.
- Car position: a small colored sprite/mesh translated along the centerline via `useFrame`, driven by `scrub.subLapT`.
- Camera: orthographic, top-down, fixed. This kills 90% of the complexity of "real" 3D.

**Why not a Canvas2D/SVG alternative:** FastF1 track data is dense (thousands of points). Canvas 2D path rendering works but doesn't compose with the per-frame animated marker cleanly. SVG works too but re-rendering a 2000-point path on every scrub tick is wasteful. R3F keeps the track geometry static (one-time upload to GPU) and animates only the marker.

**Click-to-scrub:** raycaster on the track ribbon, convert hit point to the nearest centerline t, dispatch `setScrub(t)` to Zustand. drei has `useCursor` for the hover state.

**Integration boundary:** R3F owns a `<Canvas>` element. React owns everything around it. The SVG scrub-cursor overlay (Q6) sits absolutely-positioned on top of the R3F canvas for crisper hairline rendering that doesn't need GPU.

**Confidence:** HIGH (R3F is the standard 2026 answer for "Three.js in React").

### Q8. Seven-Zone Component Architecture

**Layout primitive:** CSS Grid with named areas at the top-level `<AppShell>`. This maps cleanly to the brief's seven zones.

```
┌──────────────────────────────────────────────────────────┐
│                   Zone 1: TopBar                          │
├──────────────────┬──────────────────────┬────────────────┤
│                  │                       │                │
│  Zone 2:         │  Zone 4:              │  Zone 3:       │
│  TrackMap        │  MultiChartPanel      │  TireArray     │
│  (R3F)           │  (visx)               │  (SVG/visx)    │
│                  │                       │                │
├──────────────────┴──────────────────────┴────────────────┤
│                   Zone 5: ControlPanel                    │
├──────────────────────────────────────────────────────────┤
│                   Zone 6: TransportBar                    │
├──────────────────────────────────────────────────────────┤
│                   Zone 7: StatusLog (collapsible)         │
└──────────────────────────────────────────────────────────┘
```

**Component inventory (one file per component, grouped by zone):**

```
frontend/src/
├── app/
│   ├── AppShell.tsx              # Grid layout
│   ├── store.ts                  # Zustand
│   ├── queries.ts                # TanStack Query definitions
│   └── urlSync.ts                # hash <-> store
├── zones/
│   ├── topbar/
│   │   ├── TopBar.tsx
│   │   ├── RacePicker.tsx
│   │   ├── DriverPicker.tsx
│   │   └── StintPicker.tsx
│   ├── trackmap/
│   │   ├── TrackMap.tsx          # R3F Canvas
│   │   ├── TrackRibbon.tsx       # extruded path mesh
│   │   ├── CarMarker.tsx         # animated sprite
│   │   ├── SectorBoundaries.tsx
│   │   └── ScrubOverlay.tsx      # SVG atop canvas
│   ├── tirearray/
│   │   ├── TireArray.tsx         # 2x2 grid
│   │   └── TireWidget.tsx        # gauge + metrics
│   ├── charts/
│   │   ├── MultiChartPanel.tsx   # stacks below
│   │   ├── LapTimeChart.tsx
│   │   ├── SlidingPowerChart.tsx
│   │   ├── TreadTempChart.tsx
│   │   ├── SharedXAxis.tsx       # shared scale context
│   │   ├── HoverOverlay.tsx      # linked crosshair
│   │   └── ExportMenu.tsx
│   ├── control/
│   │   ├── ControlPanel.tsx
│   │   └── RunModelButton.tsx
│   ├── transport/
│   │   ├── TransportBar.tsx
│   │   ├── ScrubBar.tsx
│   │   └── SpeedControl.tsx
│   └── log/
│       ├── StatusLog.tsx
│       └── LogEntry.tsx
├── hooks/
│   ├── useKeyboardShortcuts.ts
│   ├── usePlaybackLoop.ts        # requestAnimationFrame driven
│   └── useLinkedHover.ts
└── types/
    └── simulation.ts              # mirrors backend Pydantic models
```

**Cross-zone communication:**
- **Scrub position** (`scrub.lapIndex`, `scrub.subLapT`): written by TransportBar, TrackMap (click), Charts (brush); read by all visualization zones.
- **Hover timestamp** (`hover.t`): written by whichever panel the mouse is in; read by all other panels to render a crosshair. Cleared on mouse-leave.
- **Selected tire** (`selection.tire`): written by TireArray; read by MultiChartPanel to highlight that wheel's series.
- **Run Model click** → TanStack Query mutation → simulation result cached → charts render from cache.

**Shared x-axis pattern:** `SharedXAxis` is a React Context providing a `scaleLinear` domain/range for the three stacked charts. All three charts compute their x position from the same scale. Hover events on any chart compute the inverse (`scale.invert(mouseX)`) → `setHover(t)` → crosshairs rendered on all three via a `HoverOverlay` child.

**Keyboard shortcuts:** a single `useKeyboardShortcuts` hook attached at `<AppShell>` dispatches to Zustand actions. Centralizing avoids focus-management bugs.

**Playback loop:** a single `usePlaybackLoop` hook mounted at `<AppShell>` uses `requestAnimationFrame` to advance `scrub.subLapT` while `playing=true`. One driver, not one-per-component.

**Confidence:** HIGH for the zonal decomposition (maps directly to the brief); MEDIUM-HIGH for the specific file layout (opinionated).

---

## Data Flow

### End-to-end flow: "User loads a stint, hits Run Model, scrubs laps"

```
1. User loads page with hash #race=2024-monaco&driver=VER&stint=2
   ↓
2. urlSync reads hash → Zustand.selection set
   ↓
3. TanStack Query fires: GET /races, GET /races/{id}/drivers, GET /stints/{race}/{driver}
   ↓  (FastAPI serves metadata from FastF1 cache; first hit triggers FastF1 fetch)
   ↓
4. User clicks "Run Model" → mutation POST /simulate {race, driver, stint}
   ↓
5. FastAPI handler:
   a. Telemetry service loads stint from layer-2 pickle cache (or fetches via FastF1 + preprocesses + writes cache)
   b. ParameterStore.get_active(compound) loads NetCDF posterior
   c. SimulationOrchestrator:
      - Samples K=500 draws from posterior
      - Runs 7-module pipeline, vectorized over K draws
      - Computes per-lap percentiles (median, 5%, 95%)
   d. Returns JSON: { laps: [...], tires: [...], events: [...], parameter_version: "v1.2.0" }
   ↓
6. TanStack Query caches result under key [race, driver, stint, parameter_version]
   ↓
7. Components render from cached result:
   - TrackMap: renders track once (cached per race)
   - TireArray: reads tires[hoveredTime] via selector
   - MultiChartPanel: renders full lap series with confidence bands
   - StatusLog: renders events[]
   ↓
8. User hovers chart:
   - MouseMove → scale.invert(x) → setHover(t)
   - TireArray subscribes to hover.t → re-renders gauges for that instant
   - TrackMap subscribes to hover.t → moves car marker
   - Other charts subscribe to hover.t → render crosshair
   ↓
9. User hits Space:
   - Keyboard hook dispatches store.play()
   - usePlaybackLoop starts advancing scrub.subLapT at 60 Hz
   - All panels re-render against updated scrub position
```

**Data dependencies (what must exist before what):**
- Race/driver/stint metadata before simulation can run.
- Parameter posteriors before simulation (populated by offline calibration; v1 ships with precomputed posteriors).
- Simulation result before any visualization.
- Track centerline (from FastF1 pos_data) before TrackMap can render — loaded alongside stint metadata.

---

## Build Order

**The critical insight:** build backend end-to-end with stub physics first, then swap in real physics. Otherwise the frontend has nothing to render and motivation tanks.

### Phase A: Backend skeleton (stub physics → real pipeline later)

1. **FastAPI project + routes returning mock data.** `GET /races` returns hard-coded list; `POST /simulate` returns fake curves. Frontend can start immediately.
2. **FastF1 wrapper + layer-1 cache.** `GET /races` and `GET /stints` now real.
3. **Telemetry preprocessing + layer-2 pickle cache.** Stint objects are deterministic artifacts.
4. **Physics module scaffolding** — all 7 modules with `Protocol` signature and stub `run()` returning plausible shapes. All unit tests in place (skipped `@pytest.mark.xfail` where unimplemented). **This unblocks everything — frontend and calibration pipeline both depend only on the contracts, not the implementations.**
5. **SimulationOrchestrator** wiring the stubs together; `POST /simulate` returns a stub result that matches the real schema.

### Phase B: Frontend skeleton (against stub backend)

6. **AppShell + grid layout + Zustand store + TanStack Query.**
7. **TopBar (pickers) + URL sync.** Users can select. Calls to `/races` etc. work against real or stub backend.
8. **MultiChartPanel with one chart.** Renders stub simulation data. Proves the visx pipeline end-to-end.
9. **Linked hover + shared x-axis.** Get the interaction model right before replicating.
10. **Remaining charts (SlidingPower, TreadTemp).**
11. **TireArray widgets.**
12. **TrackMap (R3F Canvas).** Static track first, animated car marker second.
13. **TransportBar + playback loop + keyboard shortcuts.**
14. **StatusLog.**
15. **Export, clipboard, drag-and-drop `.ff1`, theming polish.**

### Phase C: Real physics (swap stubs out one module at a time)

16. **Parameter store + NetCDF loading** (initially with hand-picked prior means, no posterior yet).
17. **Module 1: KinematicFrontEnd.** Unit tests pass; orchestrator integration still using stubs for 2–7.
18. **Module 2: VerticalLoads.**
19. **... through Module 7.**
20. **Vectorization pass:** make the pipeline broadcast over a posterior-draw axis. This is the performance-critical step to hit <2 s with K=500 draws.

### Phase D: Calibration pipeline (separate from web app)

21. **CLI tool `python -m calibration.run --stage aero --compound soft`.**
22. **Stage 1 (aero) → Stage 2 (friction) → Stage 3 (thermal) → Stage 4 (degradation).** Writes NetCDF to `data/posteriors/{version}/{compound}_{regime}.nc`, updates SQLite metadata.
23. **API reads posteriors via ParameterStore.**

**Dependency map (what blocks what):**
- Frontend Phase B blocks on contract from Phase A step 5 (not real physics).
- Real physics Phase C can proceed in parallel with Frontend Phase B once contracts are stable.
- Calibration Phase D depends on Phase C (real physics forward model) being correct before it can be calibrated.
- Therefore: **contracts first, stubs everywhere, then parallelize frontend + physics, then calibrate.**

---

## Open Questions

1. **Simulation vectorization target.** Is K=500 posterior draws the right count for the <2 s budget? Needs a performance spike early — a naïve Python-loop implementation will blow the budget. Decide: pure numpy broadcasting, numba JIT, or jax? (Jax is overkill; numba is a reasonable middle ground if vectorization is awkward.)

2. **FastF1 cache size and persistence strategy.** How big does the cache get for a full season's worth of stints? Affects deployment choice (Fly.io volume size, S3 sync strategy, cold-start warmup list).

3. **ParameterStore versioning semantics.** Semver vs date-stamped vs git-commit tags? Need to choose before first calibration writes results.

4. **Posterior predictive sampling cost.** Running the full 7-module pipeline 500× per simulation might dominate the 2 s budget. Alternative: pre-compute a surrogate (Gaussian process over parameter space) at calibration time, use it online. Decide after first end-to-end timing.

5. **Linked-chart hover frequency vs Zustand re-render cost.** 60 Hz mouse updates into a global store will re-render many subscribers. Profile early; if it's a problem, the fix is either a separate high-frequency store slice with `subscribeWithSelector` middleware, or a `useSyncExternalStore` custom subscription that bypasses React reconciler for the crosshair layer.

6. **R3F bundle size vs load time.** R3F + drei + three.js is ~200 kB gzipped. Code-split the TrackMap zone (React.lazy) so the initial dashboard renders before three.js arrives.

7. **Export interactivity.** Does PNG export need to preserve the hover crosshair or be "clean"? Design call — probably clean; trivial to implement but worth deciding upfront.

8. **Drag-and-drop `.ff1` file ingestion.** Does the file get POSTed to the server (so server can reuse its cache logic) or parsed client-side (so no round-trip needed)? Server-side is simpler and reuses existing FastF1 parsing; recommend server-side with a dedicated `POST /sessions/upload` endpoint.

---

## Sources

- [FastAPI Background Tasks vs Celery vs Arq](https://medium.com/@komalbaparmar007/fastapi-background-tasks-vs-celery-vs-arq-picking-the-right-asynchronous-workhorse-b6e0478ecf4a)
- [Managing Background Tasks in FastAPI: ARQ vs Built-in](https://davidmuraya.com/blog/fastapi-background-tasks-arq-vs-built-in/)
- [FastAPI Background Tasks docs](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [State Management in 2026: Zustand vs Jotai vs Redux Toolkit](https://dev.to/jsgurujobs/state-management-in-2026-zustand-vs-jotai-vs-redux-toolkit-vs-signals-2gge)
- [State Management in React 2026 (Redux Toolkit vs Zustand vs Jotai)](https://teachmeidea.com/state-management-react-2026/)
- [Zustand vs Redux Toolkit vs Jotai — Better Stack](https://betterstack.com/community/guides/scaling-nodejs/zustand-vs-redux-toolkit-vs-jotai/)
- [D3 Best Practices in React](https://timothycurchod.com/writings/d3-best-practices)
- [visx — better React integration than D3](https://staedi.github.io/posts/visx)
- [Top React Chart Libraries 2026](https://querio.ai/articles/top-react-chart-libraries-data-visualization)
- [React Three Fiber vs Three.js (2026)](https://www.creativedevjobs.com/blog/react-three-fiber-vs-threejs)
- [React Three Fiber vs Three.js — Graffersid 2026](https://graffersid.com/react-three-fiber-vs-three-js/)
- [FastF1 General Functions docs (caching)](https://docs.fastf1.dev/fastf1.html)
- [FastF1 cache handling discussion](https://github.com/theOehrly/Fast-F1/discussions/787)
- [Pydantic Dataclasses docs](https://docs.pydantic.dev/latest/concepts/dataclasses/)
- [Pydantic vs Dataclasses — when to use each](https://www.hrekov.com/blog/dataclasses-or-pydantic-basemodels)
- [ArviZ InferenceData schema](https://python.arviz.org/en/v0.17.1/schema/schema.html)
- [Refitting PyMC models with ArviZ (netcdf save/load)](https://python.arviz.org/en/stable/user_guide/pymc_refitting.html)
- [TanStack Query docs](https://tanstack.com/query/latest/docs/framework/react/overview)
- [Cross-filtering dashboards with TanStack React Charts](https://borstch.com/blog/development/implementing-cross-filtering-in-dashboards-with-tanstack-react-charts)
