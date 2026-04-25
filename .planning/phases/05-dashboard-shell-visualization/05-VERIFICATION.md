---
phase: 05-dashboard-shell-visualization
verified: 2026-04-24T22:55:00Z
status: human_needed
score: 5/7
overrides_applied: 0
gaps:
  - truth: "FastF1 errors surface a retry affordance; flagged-quality stints display a warning badge while still rendering results"
    status: failed
    reason: "SSE consumer calls setError() on simulation_error event, but no UI component reads or renders the error state. No retry button or quality badge exists anywhere in the component tree."
    artifacts:
      - path: "frontend/src/lib/sse.ts"
        issue: "setError called on simulation_error but error state never consumed in UI"
      - path: "frontend/src/components/TopStrip/TopStrip.tsx"
        issue: "No error state read; no retry affordance rendered"
    missing:
      - "Error display component reading useSimulationStore(s => s.error)"
      - "Retry button or affordance in TopStrip that calls runSimulationStream again on error"
      - "Quality warning badge for flagged-quality stints (no mechanism at all)"
  - truth: "Multi-chart main panel stacks traces on a shared x-axis with mouse-wheel zoom, drag-to-pan"
    status: failed
    reason: "PhysicsPanel renders CI band charts on a shared time axis with hover crosshair, but mouse-wheel zoom and drag-to-pan are not implemented. The research doc explicitly deferred 'brush/zoom' from Phase 5 scope (VIZ-03 note), but the ROADMAP success criterion still lists them."
    artifacts:
      - path: "frontend/src/components/PhysicsPanel/PhysicsChart.tsx"
        issue: "No wheel event handler, no d3-zoom, no panning logic"
    missing:
      - "Mouse-wheel zoom on PhysicsChart shared x-axis (or explicit deferral note in ROADMAP)"
      - "Drag-to-pan on PhysicsChart (or explicit deferral note in ROADMAP)"
human_verification:
  - test: "Load the dev server at http://localhost:5173 and verify the full Run model flow end to end"
    expected: "All 5 panels populate after Run — CarPanel shows 4 tire wheels with viridis fill, LapPanel shows 56px lap time, MapPanel shows Bahrain circuit SVG, PhysicsPanel shows CI band charts in 4 tabs. Module progress increments 1/7 through 7/7 in TopStrip before data populates."
    why_human: "SSE streaming with 760ms mock delay, visual correctness of CI band rendering, and panel population sequence require a running browser"
  - test: "Verify linked hover: hover a PhysicsChart line, confirm CarPanel footer row and LapPanel pace trace crosshair update"
    expected: "Hovering PhysicsChart highlights the same lap in CarPanel footer (corner highlight) and PaceTrace crosshair moves. Leaving PhysicsChart clears all highlights."
    why_human: "Interactive mouse event behavior across components requires browser testing"
  - test: "Verify URL hash bookmarking: select race/driver/stint, copy URL, paste in new tab, confirm selections restored"
    expected: "Hash updates to #race=2024_bahrain&driver=LEC&stint=0 after selection. Fresh tab pre-populates pickers from the hash."
    why_human: "Browser hash behavior and page load restoration require live browser session"
  - test: "Verify MSW service worker activation"
    expected: "Browser DevTools > Application > Service Workers shows MSW worker registered. Console shows [MSW] Mocking enabled."
    why_human: "Service worker registration is a browser API visible only in DevTools"
---

# Phase 5: Dashboard Shell & Visualization — Verification Report

**Phase Goal:** A user visiting the deployed frontend can pick a race, driver, and stint, click "Run model," and see all six dashboard zones populate with the returned simulation — CI bands on predicted traces, linked hover across every zone, and correct FIA compound colors throughout.
**Verified:** 2026-04-24T22:55:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Top bar hosts cascade dropdowns wiring race→driver→stint with URL hash sync | VERIFIED | TopStrip.tsx cascade pickers, useHashSync wired in App.tsx, TanStack Query enabled/disabled chain confirmed |
| 2 | All five panel zones render without overflow at >=1280px desktop | VERIFIED | App.tsx cockpit grid with exact design-ref dimensions (33%/32%/35% columns); DASH-02 scope scoped to >=1280px per plan must_have; Zone 6 transport bar explicitly deferred to Phase 6 |
| 3 | "Run model" triggers SSE stream with module-by-module progress; FastF1 errors surface retry affordance; quality stints show warning badge | FAILED | SSE stream and 7-module progress indicator are implemented and wired. However, `simulation_error` events call `setError()` but no UI component reads/renders the error state — no retry affordance exists. No quality warning badge mechanism exists anywhere in the codebase. |
| 4 | Multi-chart PhysicsPanel shows CI bands on shared x-axis with mouse-wheel zoom and drag-to-pan | FAILED | PhysicsPanel implemented with 4 tabs × 4 corner CI band charts, D3 area paths for CI bands, hover crosshair. Mouse-wheel zoom and drag-to-pan are absent. Research doc scoped these out ("brush/zoom not in Phase 5 scope") but ROADMAP SC-4 still requires them. |
| 5 | Tire array shows 4 widgets with temperature/grip/energy/slip angle updating in sync with hover | VERIFIED | CarPanel.tsx: 4 CarWheel components with viridis temp fill, grip ladders, wear bands, slip tick. CarFooter renders T/μ/WEAR/α/BRK CI readouts. Hover sync via Zustand hoveredCorner confirmed. |
| 6 | Hovering any chart, tire widget, or track SVG highlights the same lap/timepoint in every other zone | VERIFIED | PhysicsChart sets setHoveredLap + setHoveredCorner; PaceTrace reads hoveredLap for crosshair; CarFooter reads hoveredCorner for highlighting; MapPanel reads hoveredLap for car position; StatusLog reads hoveredLap for event highlight. Full chain verified. |
| 7 | FIA compound colors, Okabe-Ito palette, viridis temperatures, dark navy background, JetBrains Mono typography applied site-wide | VERIFIED | global.css: all 17 CSS tokens at exact locked values. scales.ts: COMPOUND_COLORS, CORNER_COLORS, tempToViridis all match design lock spec. border-radius:0 !important enforced globally. font-feature-settings "tnum" "ss01" applied on body. |

**Score:** 5/7 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/src/App.tsx` | App shell with cockpit grid, RAF animation, ErrorBoundaries, useHashSync | VERIFIED | 107-line file; exact design-ref grid dimensions; animation tick with requestAnimationFrame; per-panel ErrorBoundaries; useHashSync() called |
| `frontend/src/main.tsx` | Bootstrap with MSW worker.start() from browser.ts in DEV | VERIFIED | Imports from `./mocks/browser` (not server); worker.start() before createRoot; QueryClientProvider at root |
| `frontend/src/lib/sse.ts` | runSimulationStream + mapApiResponseToSimulationResult | VERIFIED | Both exports present; mapper transforms per_lap→laps, metadata→meta, sector_bounds→sectorBounds; SSE consumer uses fetch+ReadableStream POST |
| `frontend/src/components/shared/ErrorBoundary.tsx` | React class ErrorBoundary | VERIFIED | getDerivedStateFromError, componentDidCatch, fallback renders PANEL ERROR in hot color |
| `frontend/src/components/TopStrip/TopStrip.tsx` | Cascade pickers + Run model wired to runSimulationStream | VERIFIED | runSimulationStream imported and called from handleRunModel; no console.log placeholder remains; module progress display wired |
| `frontend/src/components/CarPanel/CarPanel.tsx` | SF-24 chassis SVG + 4 CarWheel components | VERIFIED | CarChassis + 4 CarWheel with viridis temp fill, wear bands, grip ladders, CI halo; CarFooter with CI readouts |
| `frontend/src/components/MapPanel/MapPanel.tsx` | SVG circuit with 3-sector coloring, car dot, turn labels | VERIFIED | Polyline sectors, car dot with glow filter, trail, turn labels, sector boundary markers, S/F line |
| `frontend/src/components/LapPanel/LapPanel.tsx` | Big lap time, deltas, sector cards, pace trace, projection, status log | VERIFIED | 56px/weight-300 lap time; Δ PB and Δ MODEL deltas; 3 sector cards; PaceTrace D3 chart; 4-cell stint projection; collapsible StatusLog |
| `frontend/src/components/PhysicsPanel/PhysicsPanel.tsx` | 4 metric tabs × 4 CI band charts | VERIFIED | TREAD TEMP/GRIP μ/WEAR E/SLIP α PEAK tabs; 4 PhysicsChart stacked per tab; D3 CI area + mean line |
| `frontend/src/stores/useSimulationStore.ts` | Zustand store with SimulationResult data + module progress | VERIFIED | data, loading, error, moduleProgress, selectedRaceId/Code/Index; all actions typed |
| `frontend/src/stores/useUIStore.ts` | Zustand store with pos, speed, hoveredLap, hoveredCorner | VERIFIED | hoveredLap, hoveredCorner, mode, playing, pos, speed; all setters present |
| `frontend/src/lib/useHashSync.ts` | Hash read on mount + write on selection change | VERIFIED | Reads hash on mount, parses race/driver/stint params; writes on selectedRaceId/Code/Index change |
| `frontend/src/mocks/handlers.ts` | MSW handlers for all 4 endpoints including /simulate/stream | VERIFIED | http.get for /races, /drivers, /stints; http.post for /simulate/stream with ReadableStream 7 module_complete events + simulation_complete |
| `frontend/src/mocks/fixtures/bahrain-lec-s1.ts` | 22-lap deterministic fixture in SimulationResult shape | VERIFIED | BAHRAIN_LEC_S1 exported; 22 laps with CI triplets for all 16 per-corner metrics; track (59 waypoints), sectorBounds, turns |
| `frontend/src/lib/types.ts` | CI, LapData, SimulationResult, SimulateApiResponse types | VERIFIED | All types defined; CI triplet {mean, lo_95, hi_95}; all per-corner metrics on LapData; both raw API and mapped frontend shapes |
| `frontend/src/lib/scales.ts` | tempToViridis, CORNER_COLORS, COMPOUND_COLORS, compoundColor | VERIFIED | All color constants at design-lock values |
| `frontend/src/lib/formatters.ts` | fmtLapTime, fmtDelta, fmtCI, fmtTemp, fmtGrip, fmtEnergy, fmtSlip | VERIFIED | All 7 formatters implemented with correct M:SS.SSS format |
| `frontend/src/lib/track.ts` | normalizeTrackPoints, smoothMovingAverage, trackToSvgPath, lapFracToTrackIndex | VERIFIED | All 4 utilities present and unit tested |
| `packages/api/src/f1_api/routers/simulate.py` | POST /simulate/stream SSE endpoint | VERIFIED | AsyncGenerator wrapped in StreamingResponse; 7 module_complete events; asyncio.to_thread for CPU-bound work; track geometry extraction with Savitzky-Golay smoothing and [0,1] normalization |
| `frontend/src/styles/global.css` | All 17 CSS custom property tokens at exact design-lock values | VERIFIED | :root and @theme blocks verified; border-radius:0 !important; font-feature-settings tnum+ss01; self-hosted JetBrains Mono + Inter |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `App.tsx` | `TopStrip.tsx` | `<TopStrip />` in row 1 of outer grid | WIRED | gridTemplateRows: '52px 1fr'; TopStrip in row 1 |
| `App.tsx` | `CarPanel, LapPanel, MapPanel, PhysicsPanel` | ErrorBoundary wrappers in cockpit grid | WIRED | All 4 panels wrapped with `<ErrorBoundary label="...">` |
| `App.tsx` | `useHashSync` | `useHashSync()` called in App body | WIRED | Line 10 import + line 17 call |
| `sse.ts` | `useSimulationStore` | `setModuleProgress, setSimulationData, setLoading, setError` via `getState()` | WIRED | All 4 store actions called from runSimulationStream |
| `sse.ts` | `mapApiResponseToSimulationResult` | Called on `simulation_complete` payload (backend shape); direct store pass for MSW frontend shape | WIRED | Shape detection via `'meta' in payload` |
| `main.tsx` | `./mocks/browser` | `import('./mocks/browser')` dynamic import in DEV | WIRED | Imports browser.ts (not server.ts); worker.start() before render |
| `PhysicsChart.tsx` | `useUIStore` | `setHoveredLap, setHoveredCorner` on mouse events | WIRED | onMouseMove calls setHoveredLap; onMouseEnter calls setHoveredCorner; onMouseLeave clears both |
| `CarFooter.tsx` | `useUIStore.hoveredCorner` | `active = hoveredCorner === c` | WIRED | Footer cell highlights when hoveredCorner matches |
| `PaceTrace.tsx` | `useUIStore.hoveredLap` | `crosshairX = hoveredLap != null ? sx(hoveredLap) : sx(currentLapIdx + 1)` | WIRED | Crosshair position driven by hoveredLap |
| `MapPanel.tsx` | `useUIStore.hoveredLap` | `lapIdx = hoveredLap != null ? hoveredLap - 1 : ...` | WIRED | Car position uses hoveredLap when set |
| `StatusLog.tsx` | `useUIStore.hoveredLap` | `active = hoveredLap === evt.lap` | WIRED | Log row highlights when hoveredLap matches event lap |
| `TopStrip.tsx` | `runSimulationStream` | `handleRunModel` calls `runSimulationStream(selectedRaceId, driverCode, stintIdx, signal)` | WIRED | RUN MODEL button onClick calls handleRunModel |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `PhysicsChart.tsx` | `revealedLaps` prop | `useSimulationStore(s => s.data?.laps)` via PhysicsPanel | Yes — fixture has 22 laps with deterministic CI values | FLOWING |
| `CarPanel.tsx` | `lap` (LapData) | `useSimulationStore(s => s.data?.laps[lapIdx])` | Yes — 16 per-corner CI fields per lap | FLOWING |
| `MapPanel.tsx` | `track, sectorBounds, turns` | `useSimulationStore(s => s.data?.track/sectorBounds/turns)` | Yes — 59-waypoint Bahrain fixture | FLOWING |
| `LapPanel.tsx` | `data.laps` | `useSimulationStore(s => s.data)` | Yes — laps array with CI lap times | FLOWING |
| `TopStrip.tsx` (cascade pickers) | `races, drivers, stints` | TanStack Query hooks: `useRaces(), useDrivers(), useStints()` → MSW intercept | Yes — MSW handlers return fixture arrays | FLOWING |
| `TopStrip.tsx` (module progress) | `moduleProgress` | `useSimulationStore(s => s.moduleProgress)` ← `setModuleProgress` from sse.ts SSE consumer | Yes — 7 module_complete events from MSW | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Frontend build exits 0 | `npm run build --prefix frontend` | `✓ built in 239ms` — 306KB JS, 8KB CSS | PASS |
| All unit tests pass | `npm run test --prefix frontend` | `50 passed, 4 todo (54)` — 5/6 test files green; 1 skipped (sse.test.ts has 4 it.todo stubs) | PASS |
| App.tsx has cockpit grid | `grep "gridTemplateColumns.*minmax(460" frontend/src/App.tsx` | Confirmed at line 70 | PASS |
| SSE consumer is non-hook getState | `grep "useSimulationStore.getState()" frontend/src/lib/sse.ts` | Confirmed at line 71 | PASS |
| MSW imports from browser (not server) | `grep "import.*browser" frontend/src/main.tsx` | Confirmed at line 20 | PASS |
| Per_lap→laps mapping in sse.ts | `grep "raw.per_lap" frontend/src/lib/sse.ts` | Confirmed at line 57 | PASS |
| No console.log placeholder in TopStrip | `grep "console.log" frontend/src/components/TopStrip/TopStrip.tsx` | Empty — placeholder removed | PASS |
| Error state not rendered anywhere | grep for `s.error` in components/ | No component reads simulation store error state | FAIL |
| No zoom/pan in PhysicsChart | grep for "zoom|wheel|pan" in PhysicsChart.tsx | No wheel handler or d3-zoom usage | FAIL |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|------------|------------|-------------|--------|---------|
| DASH-01 | 05-02, 05-03, 05-09 | Cascade pickers + URL hash state | SATISFIED | TopStrip pickers, useHashSync hook |
| DASH-02 | 05-09 | >=1280px five-zone layout | SATISFIED (scoped) | Plan 09 explicitly scoped to >=1280px desktop; tablet adaptation explicitly deferred; Zone 6 deferred to Phase 6 |
| DASH-03 | 05-08, 05-09 | SSE progress + FastF1 error retry + quality badge | PARTIAL | SSE progress and 7-module display SATISFIED; retry affordance and quality badge NOT SATISFIED |
| DASH-04 | 05-01 | Dark theme tokens + typography | SATISFIED | All 17 tokens at locked values; self-hosted fonts; border-radius:0 |
| VIZ-01 | 05-05 | 2D SVG track map | SATISFIED | MapPanel: polyline circuit, car dot, sector colors, turn labels |
| VIZ-02 | 05-04 | Tire array 4 widgets | SATISFIED | CarPanel: 4 CarWheel with viridis/grip/wear/CI; CarFooter readouts |
| VIZ-03 | 05-07 | Multi-chart with CI bands + zoom/pan | PARTIAL | CI band charts SATISFIED; zoom/pan absent; research scoped out of Phase 5 but ROADMAP SC still requires them |
| VIZ-04 | 05-07 | 95% CI bands distinct from mean | SATISFIED | D3 area at opacity 0.12 (CI band) + solid mean line at full opacity |
| VIZ-05 | 05-02, 05-07, 05-09 | Linked hover across all zones | SATISFIED | Full hover chain verified: Physics→Car→Lap→Map→StatusLog |
| VIZ-06 | 05-01, 05-04 | FIA colors, Okabe-Ito, viridis | SATISFIED | All color constants at locked values |
| VIZ-07 | 05-06 | Status log collapsible + per-lap events | SATISFIED | StatusLog collapses/expands; generates events from CI thresholds; highlights on hoveredLap |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/lib/sse.test.ts` | 4–7 | 4 `it.todo()` stubs for SSE consumer behavior | Warning | SSE consumer integration tests not written; the most critical path (simulation_complete → store population) has no automated coverage |
| `frontend/src/components/MapPanel/MapPanel.tsx` | 57–59 | Pseudo-speed derived from `Math.sin(lapFrac * Math.PI * 4.3)` — hardcoded placeholder | Info | Cosmetic only — HUD speed/throttle/brake values are synthetic; comment says "real telemetry comes from backend in Phase 8" which doesn't exist; acceptable for v1 |
| `frontend/src/stores/useSimulationStore.ts` | — | `error` field set by `setError()` in sse.ts but no component reads it | Blocker | Error state is silently discarded; user gets no feedback when SSE stream fails; no retry affordance |

---

## Human Verification Required

### 1. End-to-End Run Model Flow

**Test:** Start `npm run dev` in `frontend/`, visit http://localhost:5173, select Bahrain 2024 → LEC → Stint 1, click RUN MODEL.
**Expected:** TopStrip shows "MODULE 1/7 — KINEMATICS" through "7/7 — MONTE CARLO ROLL-UP" over ~760ms, then all 5 panels populate. CarPanel shows 4 tire widgets with viridis fill. LapPanel shows 92.x second lap time at 56px. MapPanel shows Bahrain circuit with car dot at S/F. PhysicsPanel shows CI band charts in 4 tabs.
**Why human:** SSE streaming timing, visual rendering correctness, and the full panel population sequence cannot be verified without a running browser.

### 2. Linked Hover Behavior

**Test:** After simulation data is loaded, hover over one of the PhysicsPanel charts.
**Expected:** A vertical crosshair appears in the hovered chart. The CarPanel footer row for that corner highlights with accent color. The LapPanel PaceTrace crosshair moves to the same lap. Hovering a different chart corner changes the highlighted corner in CarPanel footer. Leaving the chart area clears all highlights.
**Why human:** Cross-component reactive behavior driven by mouse events requires a live browser session with visible synchronization.

### 3. URL Hash Bookmarking (DASH-01)

**Test:** Select race/driver/stint in TopStrip. Inspect browser URL bar. Copy the URL. Open a new tab and paste it.
**Expected:** URL bar updates to `#race=2024_bahrain&driver=LEC&stint=0`. New tab loads with all three pickers pre-populated (though simulation does not auto-run).
**Why human:** Browser hash mechanics and page-load restoration require a live session.

### 4. MSW Service Worker Registration

**Test:** Open DevTools → Application → Service Workers while on localhost:5173.
**Expected:** MSW service worker registered and active. Browser console shows `[MSW] Mocking enabled.` No 404 errors on `/api/` calls.
**Why human:** Service worker registration is a browser API state visible only in DevTools.

---

## Gaps Summary

Two gaps prevent the phase goal from being fully achieved:

**Gap 1 — No retry affordance for FastF1 errors (SC-3):**
The SSE consumer correctly calls `setError(message)` on `simulation_error` events, but no UI component reads the simulation store's `error` field. A user who encounters a FastF1 backend error sees nothing — the dashboard stays in skeleton state with no indication of what went wrong and no way to retry without refreshing the page. The quality warning badge for flagged-quality stints (the second half of SC-3) was never implemented in any plan.

**Gap 2 — No zoom/pan on PhysicsPanel multi-chart (SC-4):**
The ROADMAP success criterion explicitly requires "mouse-wheel zoom, drag-to-pan" on the multi-chart shared x-axis. The Phase 5 research document scoped this out ("brush/zoom not in Phase 5 scope") but the ROADMAP was not updated to reflect this decision. The gap is real but may be intentional — if the developer agrees zoom/pan belongs in Phase 6, an override should be added to carry it forward.

These two gaps require a gap-closure plan before Phase 5 can be marked complete. Human verification of the browser-based behaviors (linked hover, Run model flow, URL hash, MSW) is also required.

---

*Verified: 2026-04-24T22:55:00Z*
*Verifier: Claude (gsd-verifier)*
