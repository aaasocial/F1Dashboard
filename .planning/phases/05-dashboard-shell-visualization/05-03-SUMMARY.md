---
phase: 05-dashboard-shell-visualization
plan: "03"
subsystem: frontend-shell
tags: [react, typescript, topstrip, scrubber, cascade-pickers, zustand, tanstack-query, panel-header, skeleton, dash-01, dash-04]
dependency_graph:
  requires:
    - frontend/src/stores/useUIStore.ts (Plan 02 — pos, mode, playing, speed, seek, setMode, togglePlaying, setSpeed)
    - frontend/src/stores/useSimulationStore.ts (Plan 02 — selectedRaceId, selectedDriverCode, selectedStintIndex, setSelection)
    - frontend/src/api/queries.ts (Plan 02 — useRaces, useDrivers, useStints TanStack Query hooks)
    - frontend/src/lib/scales.ts (Plan 02 — compoundColor for stint compound color)
    - frontend/src/lib/types.ts (Plan 02 — Race, Driver, Stint, SSEModuleEvent types)
  provides:
    - frontend/src/components/shared/PanelHeader.tsx (38px accent-tick panel header used by all five panels)
    - frontend/src/components/shared/Skeleton.tsx (inline + full-panel loading skeletons)
    - frontend/src/components/TopStrip/TopStrip.tsx (52px top bar: cascade pickers, mode toggle, scrubber, lap counter)
    - frontend/src/components/TopStrip/Scrubber.tsx (draggable scrubber with pointer events)
  affects:
    - Plans 04-09 (all panel plans import PanelHeader; App.tsx wraps TopStrip in Plan 09)
tech_stack:
  added: []
  patterns:
    - cascade-disable pattern (driver disabled until race selected, stint disabled until driver selected)
    - global pointer event pattern (pointermove/pointerup with useEffect cleanup for scrubber drag)
    - Zustand getState() for non-reactive mutations inside event handlers (avoids stale closure)
    - inline style React components matching design reference token variables (var(--panel-header) etc.)
key_files:
  created:
    - frontend/src/components/shared/PanelHeader.tsx
    - frontend/src/components/shared/Skeleton.tsx
    - frontend/src/components/TopStrip/TopStrip.tsx
    - frontend/src/components/TopStrip/Scrubber.tsx
  modified: []
decisions:
  - "RUN MODEL button is a placeholder (console.log) — SSE stream wiring deferred to Plan 09 per plan spec"
  - "currentDriver derived from data.meta.driver (post-simulation) or cascade Driver lookup (pre-simulation) — both have same shape for display fields"
  - "Scrubber uses useCallback to memoize onPointer — prevents stale closure on maxLap/seek in useEffect"
  - "Zustand getState() used in SELECT handlers instead of store state — event handlers capture stale closure on direct Zustand state"

requirements-completed:
  - DASH-01
  - DASH-04

duration: 25min
completed: "2026-04-24"
---

# Phase 5 Plan 03: TopStrip Shell Components Summary

**52px TopStrip with cascade pickers (race/driver/stint), LIVE/REPLAY mode toggle, draggable scrubber with per-lap ticks, speed toggle, and lap counter; plus shared PanelHeader (38px accent-tick) and Skeleton used by all five dashboard panels.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-04-24
- **Tasks:** 2
- **Files created:** 4
- **Files modified:** 0

## Accomplishments

- `PanelHeader` component: 38px dark header strip with 2px cyan accent tick, title + subtitle slots, optional right content — faithfully matches design reference `CarHeader`/`PhysicsHeader` pattern from `cockpit-car.jsx` and `cockpit-physics.jsx`
- `Skeleton` + `PanelSkeleton` components: inline and full-panel loading placeholders with pulsed background fill
- `TopStrip`: 52px header at `var(--panel-header)` with 3-column `auto 1fr auto` grid; cascade dropdowns (race → driver → stint) wire directly to `useSimulationStore` via `setSelection`; mode toggle LIVE/REPLAY with `blink-red 1.6s infinite` live indicator animation
- `Scrubber`: draggable seek bar with global `pointermove`/`pointerup` listeners, accent fill, per-lap tick marks, `boxShadow: '0 0 8px rgba(0,229,255,0.7)'` handle glow
- All four files pass `npm run build` (TypeScript strict + Vite) with 0 errors

## Task Commits

1. **Task 1: Shared components** - `4050734` (feat)
2. **Task 2: TopStrip + Scrubber** - `270fc4b` (feat)

## Files Created/Modified

- `frontend/src/components/shared/PanelHeader.tsx` — 38px panel header with 2px accent tick, title, subtitle, right slot
- `frontend/src/components/shared/Skeleton.tsx` — inline Skeleton + PanelSkeleton full-panel loading state
- `frontend/src/components/TopStrip/TopStrip.tsx` — 52px top strip: cascade pickers, mode toggle, play controls, scrubber, speed toggle, lap counter
- `frontend/src/components/TopStrip/Scrubber.tsx` — draggable scrubber with pointer event global listeners

## Decisions Made

- **RUN MODEL placeholder**: The plan spec explicitly says "Add a placeholder that console.logs for now; the wiring happens in Plan 09." Implemented as `console.log('[TopStrip] RUN MODEL — wired in Plan 09')` with conditional enable/disable based on selection state.
- **currentDriver derivation**: When `data` (simulation result) is present, driver identity comes from `data.meta.driver`; otherwise falls back to `drivers?.find(d => d.code === selectedDriverCode)`. Both have compatible shapes for the display fields used (code, team, teamColor).
- **`useSimulationStore.getState()` in event handlers**: Event handlers (onChange callbacks) use `getState()` instead of reactive Zustand state to avoid stale closure capturing old selection values. Standard Zustand pattern for non-reactive writes.
- **`useCallback` on `onPointer`**: The scrubber's pointer handler is memoized with `useCallback([seek, maxLap])` so the `useEffect` dependency array correctly captures changes to `maxLap` when simulation data arrives.

## Deviations from Plan

None - plan executed exactly as written. All four files match the plan's action blocks closely; no bugs, missing features, or blocking issues encountered.

## Known Stubs

| File | Line | Stub | Reason |
|------|------|------|--------|
| `frontend/src/components/TopStrip/TopStrip.tsx` | ~163 | `RUN MODEL` button calls `console.log` | Plan spec: SSE stream wiring in Plan 09; the button is enabled/disabled based on cascade selection state |

This stub does not prevent the plan's goal from being achieved — the plan's goal is TopStrip/Scrubber/cascade pickers rendering with correct UIStore and SimulationStore wiring. The simulation trigger is explicitly deferred.

## Threat Flags

No new security surface introduced beyond what is documented in the plan's threat model:
- T-05-03-01: Cascade picker values from API-provided IDs — no frontend SQL injection risk, FastAPI validates on backend
- T-05-03-02: Mode toggle affects client-side playback only — no security boundary crossed
- T-05-03-03: Scrubber pointermove listener has proper cleanup in useEffect return — no leak

## Self-Check: PASSED

Files confirmed present:
- `frontend/src/components/shared/PanelHeader.tsx` — exists
- `frontend/src/components/shared/Skeleton.tsx` — exists
- `frontend/src/components/TopStrip/TopStrip.tsx` — exists
- `frontend/src/components/TopStrip/Scrubber.tsx` — exists

Commits confirmed:
- `4050734` — feat(05-03): shared components
- `270fc4b` — feat(05-03): TopStrip + Scrubber

Build: `npm run build` exits 0 (215KB JS, 7.81KB CSS).
