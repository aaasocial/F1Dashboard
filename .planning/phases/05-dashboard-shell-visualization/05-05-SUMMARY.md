---
phase: 05-dashboard-shell-visualization
plan: "05"
subsystem: frontend-map-panel
tags: [react, typescript, svg, track-map, d3, vitest, tdd, viz-01]
dependency_graph:
  requires:
    - frontend/src/lib/types.ts (Plan 02 — SimulationResult.track, sectorBounds, turns)
    - frontend/src/stores/useUIStore.ts (Plan 02 — hoveredLap, pos)
    - frontend/src/stores/useSimulationStore.ts (Plan 02 — data)
    - frontend/src/components/shared/PanelHeader.tsx (Plan 03 — shared panel header)
    - frontend/src/components/shared/Skeleton.tsx (Plan 03 — PanelSkeleton)
  provides:
    - frontend/src/lib/track.ts (normalizeTrackPoints, smoothMovingAverage, trackToSvgPath, findNearestPoint, lapFracToTrackIndex)
    - frontend/src/components/MapPanel/MapPanel.tsx (track map SVG with car dot, trail, sector markers, turn labels, HUD)
  affects:
    - Plan 09 (App shell — MapPanel imported into grid layout)
    - VIZ-01 requirement: track map from FastF1 X/Y coordinates
tech_stack:
  added: []
  patterns:
    - SVG viewBox="0 0 1 1" normalized coordinate space — all track geometry in [0,1]²
    - feGaussianBlur SVG filter for car dot glow effect
    - Quadratic alpha fade (i/len)² for car trail opacity
    - TDD RED→GREEN: test stubs written before implementation, all 12 assertions pass
    - Moving average smoothing for GPS noise (window=7, Savitzky-Golay done server-side)
key_files:
  created:
    - frontend/src/lib/track.ts
    - frontend/src/components/MapPanel/MapPanel.tsx
  modified:
    - frontend/src/lib/track.test.ts (replaced 4 it.todo() stubs with 12 real assertions)
decisions:
  - SVG polyline used (not path) for track sectors — simpler serialization, equivalent visual output
  - Car trail uses trailIdxs integer array (not slice) for quadratic alpha per-segment
  - Heading indicator computed from track[carTrackIdx+2] to smooth jitter on tight corners
  - sectorBounds[si][1] used inclusive (+1 in slice) to prevent gap between sector segments
  - pseudoSpeed uses sin profile from lapFrac — real speed from telemetry comes in Plan 08
  - circuitKm cast via (data.meta.race as {km?: number}).km — km not in SimulationResult.meta.race type yet, graceful fallback to 5.412
metrics:
  duration_seconds: 180
  completed_date: "2026-04-24"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 1
---

# Phase 5 Plan 05: MapPanel Track Map Summary

**One-liner:** SVG track map panel with normalized [0,1] coordinate space, 3-sector coloring (#3a98b4/#2a7a93/#1d6278), animated car dot with feGaussianBlur glow and heading indicator, quadratic-fade trail for last 20% of circuit, sector boundary markers, turn labels, start/finish checker stripe, and a HUD showing sector/speed/THR/BRK — all driven by Zustand `hoveredLap` and `pos` state.

## What Was Built

### Task 1 — Track Utilities (TDD)

**`frontend/src/lib/track.ts`** (new):
- `normalizeTrackPoints(pts)` — maps any coordinate range to [0,1] preserving aspect ratio via `Math.max(xRange, yRange)` as scale divisor
- `smoothMovingAverage(pts, window=7)` — symmetric moving average for GPS noise reduction (Savitzky-Golay done server-side per D-01)
- `trackToSvgPath(pts)` — converts `[number, number][]` to SVG `M L L ... Z` path string
- `findNearestPoint(pts, x, y)` — O(n) nearest-index search using squared Euclidean distance
- `lapFracToTrackIndex(trackLen, frac)` — maps lap fraction 0..1 to track array index

**`frontend/src/lib/track.test.ts`** updated:
- Replaced 4 `it.todo()` Wave 0 stubs with 12 real assertions
- TDD RED: tests failed (module not found), TDD GREEN: all 12 pass after implementation
- Covers: normalizeTrackPoints (4 assertions), trackToSvgPath (4), smoothMovingAverage (2), findNearestPoint (2)

### Task 2 — MapPanel Component

**`frontend/src/components/MapPanel/MapPanel.tsx`** (new):
- `viewBox="0 0 1 1"` SVG with `preserveAspectRatio="xMidYMid meet"` — circuit renders correctly at any panel aspect ratio
- Track outer glow: `var(--accent)` polyline at 0.028 stroke, 0.15 opacity
- 3-sector track coloring: S1 `#3a98b4`, S2 `#2a7a93`, S3 `#1d6278` at stepped opacity 0.85/0.75/0.65
- Dashed centerline: 0.0015 stroke at rgba(232,238,247,0.12)
- S2/S3 sector boundary markers: amber (`var(--warn)`) circles + labels at `sectorBounds[1][0]` / `sectorBounds[2][0]`
- Turn labels: `T1..T15` at track fraction positions from `turns` array via `lapFracToTrackIndex`
- Start/finish: checkerboard stripe + "S/F" label at `track[0]`
- Car trail: last 20% of circuit rendered per-segment with quadratic alpha `(i/len)² × 0.85`
- Car dot: 3 concentric circles (r=0.014/0.008/0.004) wrapped in `filter="url(#dot-glow)"` (feGaussianBlur stdDeviation=0.004)
- Heading indicator: line from car center to `track[carTrackIdx+2]` direction
- HUD bottom-right: sector number, pseudo-speed (sin profile), THR bar (`var(--ok)`), BRK bar (`var(--hot)`)
- `hoveredLap` from UIStore drives `lapIdx` for VIZ-05 linked hover readiness
- `PanelSkeleton` shown when `data` is null (no stint selected)

## Verification Results

| Check | Result |
|-------|--------|
| `npm run test` | Exits 0 — 45 passed, 4 todo |
| Track tests | 12/12 pass |
| `npm run build` | Exits 0 — 215KB JS, 7.88KB CSS |
| viewBox="0 0 1 1" | Confirmed in MapPanel.tsx |
| S1 color #3a98b4 | Confirmed |
| S2 color #2a7a93 | Confirmed |
| S3 color #1d6278 | Confirmed |
| feGaussianBlur | Confirmed (dot-glow filter) |
| cx={carPt[0]} | Confirmed (car dot position) |
| trailIdxs | Confirmed (car trail) |
| var(--warn) | Confirmed (sector markers) |
| hoveredLap | Confirmed (4 references) |

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Notes

The plan's action block used `trailPts` (array slicing) for the car trail. The implementation uses `trailIdxs` (integer index array) instead, which enables the per-segment `(i/len)²` quadratic alpha calculation referenced in the design reference `CarTrail` component. This is the correct pattern from `cockpit-map.jsx` — `trailPts` approach was simplified pseudocode in the plan.

## Known Stubs

| Stub | File | Line | Reason |
|------|------|------|--------|
| `pseudoSpeed` = sin profile | MapPanel.tsx | ~57 | Real per-lap speed from telemetry backend — available in Plan 08 when SSE endpoint delivers telemetry per-lap |
| `throttle`/`brake` = cos formula | MapPanel.tsx | ~58-59 | Same source as pseudoSpeed — Plan 08 backend extension |
| `circuitKm` cast | MapPanel.tsx | ~153 | `SimulationResult.meta.race` type does not include `km` yet — Plan 08/09 will wire full meta or fixture will provide it |

These stubs do not block this plan's goal (VIZ-01: track map renders from FastF1 X/Y data). Speed/throttle/brake are HUD cosmetics. The circuit outline, car dot, trail, sector markers, and turn labels all render from actual simulation data.

## Threat Flags

No new security surface beyond the plan's threat model:
- T-05-05-01 (track coordinates → SVG polyline): TypeScript `[number, number][]` enforces float-only — no injection path. SVG polyline `points` attribute renders values outside [0,1] clipped by viewBox overflow.
- T-05-05-02 (circuit name in SVG text): Rendered as React JSX text node child (auto-escaped). No innerHTML or dangerouslySetInnerHTML used anywhere.
- T-05-05-03 (team color hex in SVG): Hardcoded from fixture — not a secret.

## Self-Check: PASSED

Files confirmed present:
- `frontend/src/lib/track.ts` — FOUND
- `frontend/src/lib/track.test.ts` — FOUND (12 assertions)
- `frontend/src/components/MapPanel/MapPanel.tsx` — FOUND

Commits confirmed:
- `28af3df` feat(05-05): track geometry utilities + unit tests — FOUND
- `40fb016` feat(05-05): MapPanel SVG — circuit outline, car dot, trail, sector markers, HUD — FOUND

Build exits 0. Tests exit 0.
