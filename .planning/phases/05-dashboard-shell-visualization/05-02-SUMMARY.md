---
phase: 05-dashboard-shell-visualization
plan: "02"
subsystem: frontend-foundation
tags: [typescript, zustand, tanstack-query, d3, viridis, okabe-ito, url-hash, dash-01]
dependency_graph:
  requires:
    - frontend/package.json (Plan 01 — all npm packages pre-installed)
    - frontend/src/lib/types.ts (Plan 01 stub — extended here)
    - frontend/vitest.config.ts (Plan 01 — test infrastructure)
    - frontend/src/mocks/ (Plan 01 — MSW handlers)
  provides:
    - frontend/src/lib/types.ts (CI, LapData, SimulationResult, SimulateApiResponse, Race, Driver, Stint, Corner, SSEModuleEvent, getLapCornerMetric)
    - frontend/src/lib/scales.ts (tempToViridis, COMPOUND_COLORS, CORNER_COLORS, CORNER_LABELS, compoundColor, safeDomain)
    - frontend/src/lib/formatters.ts (fmtLapTime, fmtDelta, fmtCI, fmtTemp, fmtGrip, fmtEnergy, fmtSlip)
    - frontend/src/stores/useUIStore.ts (Zustand UIStore — hoveredLap, hoveredCorner, mode, playing, pos, speed)
    - frontend/src/stores/useSimulationStore.ts (Zustand SimulationStore — data, loading, error, moduleProgress, selection)
    - frontend/src/api/client.ts (apiFetch wrapper)
    - frontend/src/api/queries.ts (useRaces, useDrivers, useStints TanStack Query hooks)
    - frontend/src/lib/useHashSync.ts (DASH-01 URL-hash sync hook)
  affects:
    - All Phase 5 panel plans (Plans 03–09 import from these files)
tech_stack:
  added: []
  patterns:
    - d3-scale-chromatic interpolateViridis for tire temperature color mapping (60–120°C)
    - Okabe-Ito palette for corner colors (FL/FR/RL/RR — colorblind-safe)
    - Zustand 5 create() with inline state + actions (no slices needed at this scale)
    - TanStack Query v5 object API (queryKey/queryFn/enabled/staleTime) — no positional args
    - staleTime: Infinity for immutable historical race data (prevents unnecessary refetches)
    - URL hash sync via custom useEffect hook (no router) per CLAUDE.md guidance
    - parseInt + isNaN guard for URL-sourced stint index (threat model T-05-02-05)
key_files:
  created:
    - frontend/src/lib/scales.ts
    - frontend/src/lib/formatters.ts
    - frontend/src/stores/useUIStore.ts
    - frontend/src/stores/useSimulationStore.ts
    - frontend/src/api/client.ts
    - frontend/src/api/queries.ts
    - frontend/src/lib/useHashSync.ts
  modified:
    - frontend/src/lib/types.ts (added SimulateApiResponse, Race, Driver, Stint, getLapCornerMetric)
    - frontend/src/lib/scales.test.ts (replaced 9 it.todo stubs with 15 real assertions)
    - frontend/src/lib/formatters.test.ts (replaced 5 it.todo stubs with 10 real assertions)
    - frontend/src/stores/useUIStore.test.ts (replaced 5 it.todo stubs with 8 real assertions)
decisions:
  - d3-scale-chromatic v3 interpolateViridis returns hex strings (e.g. '#440154'), not 'rgb(...)' — test assertions updated to use string equality against interpolateViridis(0/1) rather than regex on 'rgb('
  - useUIStore setMode('replay') sets playing=false per design reference cockpit-app.jsx onModeChange behavior
  - useHashSync only triggers setSelection when all three params (race, driver, stint) are present — partial hashes silently ignored to avoid partial state corruption
  - apiFetch uses VITE_API_URL prefix (empty string fallback for same-origin) — public URL, not a secret (T-05-02-03 accepted)
metrics:
  duration_seconds: 360
  completed_date: "2026-04-24"
  tasks_completed: 3
  tasks_total: 3
  files_created: 7
  files_modified: 4
---

# Phase 5 Plan 02: TypeScript Foundation Layer Summary

**One-liner:** TypeScript types (CI triplets, full Phase 4 API schema), D3 viridis + Okabe-Ito + FIA compound color utils, Zustand UIStore + SimulationStore, TanStack Query cascade hooks, and useHashSync URL-hash bookmarking per DASH-01 — the complete foundation consumed by all Wave 2/3 panel plans.

## What Was Built

### Task 1 — Types + Color/Format Utils + Tests

**`frontend/src/lib/types.ts`** extended with:
- `SimulateApiResponse` — raw backend shape before mapper (for Plan 08/09 SSE consumer)
- `Race`, `Driver`, `Stint` — cascade picker data types
- `getLapCornerMetric()` — helper to index per-corner CI from LapData by corner key

**`frontend/src/lib/scales.ts`** (new):
- `tempToViridis(tempC)` — maps 60–120°C to viridis color via `d3-scale-chromatic` `interpolateViridis`
- `CORNER_COLORS` — Okabe-Ito: FL `#E69F00`, FR `#56B4E9`, RL `#009E73`, RR `#F0E442`
- `COMPOUND_COLORS` — FIA: SOFT `#FF3333`, MEDIUM `#FFD700`, HARD `#FFFFFF`, INTER `#22C55E`, WET `#3B82F6`
- `compoundColor()`, `safeDomain()` helpers

**`frontend/src/lib/formatters.ts`** (new):
- `fmtLapTime(s)` — `93.851 → "1:33.851"`, NaN/Infinity → `"—:—.—"`
- `fmtDelta(d)` — `+0.123` / `–0.123` (en-dash, not hyphen) / `±0.000` / `—`
- `fmtCI()`, `fmtTemp()`, `fmtGrip()`, `fmtEnergy()`, `fmtSlip()` — CI triplet display helpers

Test files replaced stubs: 15 assertions for scales, 10 for formatters.

### Task 2 — Zustand Stores + TanStack Query + UIStore Tests

**`frontend/src/stores/useUIStore.ts`** (new):
- `hoveredLap: number | null`, `hoveredCorner: Corner | null` — D-04 lap-discrete hover
- `mode: 'live' | 'replay'`, `playing: boolean`, `pos: number`, `speed: 1|2|4|8`
- `setMode('replay')` automatically pauses — per design reference `cockpit-app.jsx` `onModeChange`
- `seek(pos)` clamps to minimum 1.0

**`frontend/src/stores/useSimulationStore.ts`** (new):
- `data`, `loading`, `error`, `moduleProgress` — simulation lifecycle state
- `selectedRaceId`, `selectedDriverCode`, `selectedStintIndex` — cascade picker selection
- `setSelection()`, `reset()` actions

**`frontend/src/api/client.ts`** (new):
- `apiFetch<T>()` wrapper using `VITE_API_URL` env var (empty string fallback for same-origin)

**`frontend/src/api/queries.ts`** (new):
- `useRaces()`, `useDrivers(raceId)`, `useStints(raceId, driverCode)` — TanStack Query v5 object API
- `staleTime: Infinity` — historical race data is immutable
- `enabled: !!raceId` / `enabled: !!raceId && !!driverCode` — cascade guards prevent early fetches

UIStore test file replaced 5 stubs with 8 real assertions covering all state transitions.

### Task 3 — useHashSync (DASH-01)

**`frontend/src/lib/useHashSync.ts`** (new):
- On mount: parses `#race={raceId}&driver={driverCode}&stint={stintIndex}` from `window.location.hash`, calls `setSelection` if all three params present and stint is a valid integer
- On selection change: writes current `selectedRaceId/driverCode/stintIndex` back to hash
- No router added — plain `useEffect` with `window.location.hash` per CLAUDE.md guidance

## Verification Results

| Check | Result |
|-------|--------|
| `npm run test` | Exits 0 — 33 passed, 8 todo, 0 failed |
| `npm run build` | Exits 0 — 215KB JS, 7KB CSS |
| `types.ts` has `lo_95` | Confirmed |
| `types.ts` has `SimulateApiResponse` | Confirmed |
| `scales.ts` COMPOUND_COLORS.SOFT | `'#FF3333'` — confirmed |
| `useUIStore.ts` has `hoveredLap` | Confirmed |
| `queries.ts` `enabled: !!raceId` | Confirmed |
| `queries.ts` `staleTime: Infinity` | Confirmed |
| `useHashSync.ts` `window.location.hash` | Confirmed |
| `useHashSync.ts` `URLSearchParams` | Confirmed |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] d3-scale-chromatic v3 interpolateViridis returns hex, not rgb()**
- **Found during:** Task 1 — first `npm run test` run
- **Issue:** Plan specified `expect(tempToViridis(60)).toMatch(/^rgb\(/)` but `d3-scale-chromatic@3.x` `interpolateViridis` returns hex strings like `'#440154'` not `'rgb(68,1,84)'`
- **Fix:** Updated `scales.test.ts` to assert `toBeTruthy()` for non-empty string, and use `toBe(interpolateViridis(0/1))` for endpoint equality — tests still verify correct viridis mapping without format assumption
- **Files modified:** `frontend/src/lib/scales.test.ts`
- **Commit:** cf90fa8

**2. [Rule 3 - Blocking] node_modules absent from worktree**
- **Found during:** Task 1 — `npm run test` returned "'vitest' is not recognized"
- **Issue:** The worktree working directory had no `node_modules/` — packages installed in main repo are not automatically available in git worktrees
- **Fix:** Ran `npm install` in the worktree's `frontend/` directory
- **Files modified:** none (runtime only — `node_modules/` is gitignored)
- **Commit:** N/A (not committed — gitignored)

## Known Stubs

None that affect this plan's goal. The following stubs in other files remain from Plan 01 (resolved by their respective plans):

| File | Count | Resolved in |
|------|-------|-------------|
| `src/lib/track.test.ts` | 4 todos | Plan 05 |
| `src/lib/sse.test.ts` | 4 todos | Plans 08+09 |

## Threat Flags

No new security surface beyond what is documented in the plan's threat model. All T-05-02-xx entries are accounted for:
- T-05-02-01 (apiFetch response parsing): TypeScript generics enforce shape — mitigated
- T-05-02-02 (Zustand external mutation): In-memory client state only — accepted
- T-05-02-03 (VITE_API_URL in bundle): Public Fly.io URL, not a secret — accepted
- T-05-02-04 (staleTime: Infinity): Correct for immutable historical data — accepted
- T-05-02-05 (hash → setSelection): parseInt + isNaN guard implemented — mitigated

## Self-Check: PASSED
