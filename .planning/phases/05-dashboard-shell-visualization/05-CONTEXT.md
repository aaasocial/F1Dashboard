# Phase 5: Dashboard Shell & Visualization - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 5 builds the entire React+TypeScript frontend from scratch and delivers all six dashboard zones populated with real simulation data. A user can visit the app, pick a race/driver/stint from cascade dropdowns, click "Run model," watch a phased SSE-streamed progress indicator, and see CI bands, linked hover, FIA compound colors, and all zone types rendered correctly.

Phase 5 also adds a `/simulate/stream` SSE endpoint to the Phase 4 API package — this is required to support the authentic module-by-module progress animation. This is the only backend change in Phase 5; all other work is frontend.

Phase 5 does NOT include: transport bar playback (Phase 6), keyboard shortcuts (Phase 6), right-click export (Phase 6), URL hash state (Phase 6), drag-and-drop upload (Phase 6), or deployment (Phase 7).

</domain>

<decisions>
## Implementation Decisions

### A — Track Map Circuit Data Source (VIZ-01)
- **D-01:** Circuit outline is derived from **FastF1 X/Y telemetry** — the fastest lap's GPS coordinates are smoothed into an SVG `<path>` and normalized to fit the track map viewport. No external circuit asset files needed; any race from 2022–present is automatically supported. One Gaussian/Savitzky-Golay smoothing pass removes GPS noise. Car position on hover shows the nearest telemetry X/Y point for the hovered lap.

### B — Simulation Progress Animation (DASH-03)
- **D-02:** Use **Server-Sent Events (SSE)** from the backend for authentic module-by-module progress. The Phase 4 `packages/api/` package gets a new `/simulate/stream` endpoint (SSE) that fires one event per physics module (Modules 1–7) as each completes, then sends the full simulation result as the final event. The frontend uses the `EventSource` API (or `fetch` with `ReadableStream`) to consume the stream and update the progress bar and zone data in sequence. This is backend work scoped to Phase 5.

- **D-03:** The existing `POST /simulate` (sync, returns full result) is retained alongside the new stream endpoint. The frontend uses `/simulate/stream` for the "Run model" button; the sync endpoint remains available for programmatic/test use.

### C — Hover X-Axis Granularity (VIZ-05)
- **D-04:** Linked hover is **lap-discrete**. Hovering any chart, tire widget, or track SVG updates a single shared Zustand state `hoveredLap: number | null`. All zones read this and display values for that lap. Lap N values are the end-of-lap aggregated outputs from the simulation. Mouse-wheel zoom and drag-to-pan on Zone 4's shared x-axis zoom into lap detail but hover still snaps to the nearest lap boundary. Intra-lap animation (4Hz continuous) is deferred to Phase 6 playback.

### D — Frontend Tooling & Test Strategy
- **D-05:** **Biome 1.9+** for linting and formatting (replaces ESLint+Prettier in one binary — zero config conflict, faster). Configured from day one alongside the Vite scaffold.
- **D-06:** **Vitest 2.x** unit tests from day one, covering: D3 scale and formatter utilities, Zustand store transitions (hoveredLap, playback state), CI band math helpers. Target: every pure-function utility in `frontend/src/lib/` has a test.
- **D-07:** **Playwright** deferred to Phase 6 — E2E tests require stable UI zones to test against; adding them in Phase 5 would mean rewriting them as zones are built.
- **D-08:** **MSW 2.x** for dev-time mocking of the FastAPI backend. The MSW service worker is set up in Phase 5 with fixture data matching the Phase 4 response schema (per-timestep, per-lap, per-stint CI triplets). This lets frontend development run without the Python stack running locally.

### Claude's Discretion
- Exact Zustand store slice names and shape (e.g., `useSimulationStore`, `useUIStore`)
- D3 scale configuration details (domain padding, tick count, axis label placement)
- SVG viewport dimensions for the track map (aspect ratio determined by circuit bounds)
- Smoothing algorithm for FastF1 X/Y path generation (Savitzky-Golay or simple moving average)
- CSS Grid template for the six-zone layout (column/row fractions)
- SSE event schema (event names, JSON payload shape per module completion event)
- Exact `EventSource` vs `fetch` + `ReadableStream` implementation for SSE consumption
- Loading skeleton design (zone-level vs component-level)
- Error boundary scope (per-zone vs full-page)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Dashboard & Visualization Requirements
- `.planning/REQUIREMENTS.md` §Dashboard Shell — DASH-01, DASH-02, DASH-03, DASH-04
- `.planning/REQUIREMENTS.md` §Visualization — VIZ-01, VIZ-02, VIZ-03, VIZ-04, VIZ-05, VIZ-06, VIZ-07
- `.planning/ROADMAP.md` §Phase 5 — Seven success criteria; use as acceptance checklist

### Physics & API Contract (what the frontend consumes)
- `model_v1_complete.html` — Seven-module output variables; these map to the Zone 4 chart traces and tire widget metrics
- `.planning/phases/04-simulation-api-uncertainty-quantification/04-CONTEXT.md` — D-01 through D-09; defines the CI triplet shape `{mean, lo_95, hi_95}`, per-timestep/per-lap/per-stint levels, and metadata block the frontend must parse
- `packages/api/src/f1_api/app.py` — FastAPI app; the new SSE router goes here
- `packages/api/src/f1_api/routers/stints.py` — Router pattern to follow for the new `/simulate/stream` SSE route

### Stack References (locked in CLAUDE.md)
- `CLAUDE.md` §Frontend — React 19, TypeScript 5.6+, Vite 6, D3 7.9+, Tailwind 4, TanStack Query v5, Zustand 5, Biome, Vitest, Playwright, MSW
- `CLAUDE.md` §Visualization — D3 for math, React for DOM pattern; why Recharts/Nivo rejected
- `CLAUDE.md` §Styling — Dark theme tokens, CSS custom properties
- `.planning/phases/01-foundation-data-pipeline-module-contracts/01-CONTEXT.md` — D-01: monorepo layout; `frontend/` lives at the repo root alongside `packages/`

### Project Context
- `.planning/PROJECT.md` — Core value, constraints, out-of-scope features (no What-If sliders, no compound comparison in v1)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `packages/api/src/f1_api/routers/stints.py` — Router + service split pattern to follow for the new SSE endpoint
- `packages/api/src/f1_api/app.py` — `create_app()` lifespan; new SSE router included here
- `packages/core/src/f1_core/physics/orchestrator.py` — `run_simulation()` is the function the SSE endpoint calls per-module-step; the SSE streaming approach requires hooking into or wrapping this orchestrator to emit events between module executions

### Established Patterns (backend, carried into frontend contracts)
- CI triplet shape: `{"mean": float, "lo_95": float, "hi_95": float}` — every predicted metric at every level uses this
- Per-lap output keys: `lap_number`, `t_tread_{fl,fr,rl,rr}`, `grip_{fl,fr,rl,rr}`, `e_tire_{fl,fr,rl,rr}`, `slip_angle_{fl,fr,rl,rr}`, `sliding_power_total` — from the Phase 4 `/simulate` schema
- `calibration_id`, `model_schema_version`, `fastf1_version` — metadata block echoed in every response

### Integration Points
- Frontend `POST /simulate/stream` → SSE stream → `EventSource` consumer → Zustand simulation store → all zone components re-render per lap
- TanStack Query caches `GET /races`, `GET /races/{id}/drivers`, `GET /stints/{race_id}/{driver_id}` — cascade picker drives these three queries in sequence
- Zustand `hoveredLap` state is read by: Zone 2 (track map dot), Zone 3 (tire widgets), Zone 4 (chart crosshair), Zone 7 (status log highlight)

### No Existing Frontend
- The `frontend/` directory does not yet exist — Phase 5 scaffolds it from scratch with `npm create vite@latest`

</code_context>

<specifics>
## Specific Ideas

- **claude.ai/design**: User wants to use https://claude.ai/design to design the visual UI before/alongside implementation. A design brief document has been prepared (see discussion log) with all design tokens, zone specs, and component inventory for pasting into that tool.

- **SSE endpoint shape**: Each module completion fires `event: module_complete` with `data: {"module": N, "name": "Kinematics", "lap_count": 22}`. Final event fires `event: simulation_complete` with the full result payload. Frontend `EventSource` listener maps these to progress bar updates + result population.

- **FastF1 X/Y → SVG path**: Load the fastest lap's position telemetry (`session.laps.pick_fastest().get_telemetry()`), extract `X` and `Y` columns, apply a Savitzky-Golay filter (window=21, order=3), normalize to `[0,1]` in both axes, scale to SVG viewport. Cache this derived path per circuit per season. The car hover position is the telemetry row nearest to the start of the hovered lap.

- **Viridis for temperatures**: Use `d3-scale-chromatic`'s `interpolateViridis` for the tire temperature circular gauge — maps 60°C (blue/violet) to 120°C (yellow/green).

- **Okabe-Ito palette**: FL/FR/RL/RR tire traces in Zone 4 use `#E69F00`, `#56B4E9`, `#009E73`, `#F0E442` — colorblind-safe, visually distinct on the dark navy background.

</specifics>

<deferred>
## Deferred Ideas

- **SSE vs sync `/simulate` unification** — Eventually `/simulate` could always stream; for now both endpoints coexist (sync for tests/API clients, stream for the UI).
- **Animated car position during playback** — The track map in Phase 5 shows car position for the hovered lap only. Continuous animation while playing back a stint is Phase 6.
- **Playwright E2E tests** — Deferred to Phase 6 when the visualization is stable enough to write reliable selectors against.
- **Three.js 3D track map** — Explicitly deferred to v2; Phase 5 uses SVG (2D) per CLAUDE.md guidance.
- **What-If sliders and compound comparison** — v2 scope per PROJECT.md.

</deferred>

---

*Phase: 05-dashboard-shell-visualization*
*Context gathered: 2026-04-24*
