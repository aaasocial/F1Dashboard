# Plan 05-09 Summary: App Shell Wiring

**Completed:** 2026-04-24
**Status:** Complete — user approved Phase 5

## What Was Built

- `App.tsx` cockpit grid: `grid-template-rows: 52px 1fr`, three-column main area (33%/32%/35%), CarPanel spanning col 1 full height, LapPanel col 2, MapPanel col 3 row 1, PhysicsPanel col 3 row 2, 1px gutters on `var(--rule)`
- RAF playback loop advancing `pos` via `useUIStore` when `playing=true`, respecting `speed` and `mode` from the UI store
- SSE consumer (`frontend/src/lib/sse.ts`) — `fetch` + `ReadableStream` POST to `/api/simulate/stream`; parses `module_complete` and `simulation_complete` events; `mapApiResponseToSimulationResult` bridges backend shape to frontend `SimulationResult` type
- MSW bootstrap in `main.tsx` (dev-only): `worker.start({ onUnhandledRequest: 'bypass' })` before React root mount
- `ErrorBoundary` wrapping each panel so a single panel crash cannot take down the whole dashboard
- URL hash sync (`useHashSync`) persisting race/driver/stint selection across reloads
- `useHashSync` hook wiring Zustand selection state ↔ `window.location.hash`

## Bugs Fixed During Phase Approval

- `handlers.ts` was sending `laps: []` in the `simulation_complete` SSE event — all lap-indexed panels crashed or showed nothing. Fixed by importing `BAHRAIN_LEC_S1` fixture and using real 22-lap data.
- `LapPanel.tsx` had no guard for empty `laps` array — added `if (!lap) return <PanelSkeleton />` after `lapIdx` computation.
- Fixture `baseGrip` was `0.92` (below chart domain `[1.10, 1.50]`) — updated to `1.35 - degradation * 5`.
- Fixture `baseTemp` started at `85` (below chart domain floor `88`) — updated to `90 + age * 0.5`.
- Fixture `sectorBounds` referenced indices `[86, 172, 258]` on a 20-point track array (all out of range) — replaced with `[[0,18],[18,43],[43,58]]` matching the new 59-point Bahrain layout.
- Track array replaced: 20-point placeholder oval → 59-waypoint Bahrain International Circuit approximation with correct hairpin geometry, back straight, and T11–T15 bottom complex.

## Known Gaps (Carry Into Phase 6)

- **SC-3 partial**: `useSimulationStore.error` is set on SSE failure but never read by any component — users see a silent failure with no retry affordance. Add error banner + retry button to TopStrip in Phase 6.
- **SC-4**: Mouse-wheel zoom / drag-to-pan on PhysicsPanel shared x-axis was scoped out of Phase 5 per research doc. Implement in Phase 6.
