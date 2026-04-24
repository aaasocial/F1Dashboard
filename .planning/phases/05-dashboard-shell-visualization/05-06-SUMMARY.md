---
phase: 05-dashboard-shell-visualization
plan: "06"
subsystem: frontend-lap-panel
tags: [react, typescript, d3, zustand, lappanel, pacetrace, statuslog, linked-hover, viz-03, viz-07]
dependency_graph:
  requires:
    - frontend/src/lib/types.ts (Plan 02 — LapData, CI, Corner, SimulationResult)
    - frontend/src/lib/formatters.ts (Plan 02 — fmtLapTime, fmtDelta)
    - frontend/src/stores/useUIStore.ts (Plan 02 — hoveredLap, setHoveredLap, pos)
    - frontend/src/stores/useSimulationStore.ts (Plan 02 — data)
    - frontend/src/components/shared/PanelHeader.tsx (Plan 03 — 38px panel header)
    - frontend/src/components/shared/Skeleton.tsx (Plan 03 — PanelSkeleton)
  provides:
    - frontend/src/components/LapPanel/LapPanel.tsx (Full lap info panel — column 2)
    - frontend/src/components/LapPanel/PaceTrace.tsx (D3 line+area chart with linked hover)
    - frontend/src/components/LapPanel/StatusLog.tsx (Collapsible event log, VIZ-07)
  affects:
    - Plans 09 (App.tsx will import LapPanel into the 3-column grid layout)
tech_stack:
  added: []
  patterns:
    - D3 for math, React for DOM (d3-scale, d3-shape, d3-array compute paths; JSX renders SVG elements)
    - ResizeObserver wrapped in requestAnimationFrame to prevent loop error (Pitfall 3)
    - Zustand hoveredLap as single source of truth for cross-panel linked hover
    - Client-side threshold event generation from CI data (no backend event field required)
    - grid-template-rows 38px/auto/auto/1fr/auto/auto for fixed-header + flex body
key_files:
  created:
    - frontend/src/components/LapPanel/PaceTrace.tsx
    - frontend/src/components/LapPanel/StatusLog.tsx
    - frontend/src/components/LapPanel/LapPanel.tsx
  modified: []
decisions:
  - "StatusLog events derived client-side from CI thresholds (thermal >112°C, grip <1.25, wear >18MJ) — no backend event field required per 05-CONTEXT.md open question #3"
  - "Δ MODEL computed as lap_time.mean - lap_time.lo_95 (actual vs Bayesian optimistic 95th percentile) — shows how far actual lap is from the model's best-case estimate"
  - "PaceTrace crosshair snaps to hoveredLap when set, falls back to currentLapIdx+1 during normal playback"
  - "Sector times estimated as lap_time.mean / 3 — exact sector splits not in Phase 4 API schema; good enough for visual display"
metrics:
  duration_seconds: 162
  completed_date: "2026-04-24"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 0
---

# Phase 5 Plan 06: LapPanel — Big Time, Pace Trace, Status Log Summary

**One-liner:** Full-height column 2 LapPanel with 56px weight-300 JetBrains Mono lap timer (cyan glow), Δ PB / Δ MODEL delta blocks with 2px left color borders, 3 sector cards, D3 pace trace SVG chart with ResizeObserver+rAF guard and hoveredLap crosshair, 4-stat stint projection grid, and collapsible StatusLog (VIZ-07) with client-side threshold event generation.

## What Was Built

### Task 1 — PaceTrace D3 Chart + StatusLog Collapsible

**`frontend/src/components/LapPanel/PaceTrace.tsx`** (new):
- D3 `scaleLinear` for X (lap 1..maxLap) and Y (lap time domain with 0.1s padding)
- D3 `line` + `area` generators; area fill at 0.1 opacity, line at 1.6px round joins
- ResizeObserver with `requestAnimationFrame` wrapper prevents "ResizeObserver loop limit exceeded" browser error (Pitfall 3)
- Best lap marker rendered in `var(--purple)` at r=3 with panel-bg stroke ring
- Vertical dashed crosshair follows `hoveredLap` (from Zustand) or falls back to `currentLapIdx+1`
- `onMouseMove` maps cursor X to nearest lap number, clamps to `[1, revealedLaps.length]`, calls `setHoveredLap`
- Y axis labels at top/bottom in 7px mono; X axis labels every 5 laps
- Empty data guard: returns bare div if `revealedLaps.length < 2` (Pitfall 4)

**`frontend/src/components/LapPanel/StatusLog.tsx`** (new):
- `collapsed` state with single-click toggle; `aria-expanded` accessibility attribute
- `generateEvents()` derives events client-side from `LapData` CI means vs three thresholds:
  - `t_tread > 112°C` → critical; `t_tread > 106°C` → info
  - `grip < 1.25` → warn
  - `e_tire > 18 MJ` → critical
- Events rendered with level color from `{ info: accent, warn, critical: hot }`
- `hoveredLap === evt.lap` → 2px left border in level color + `var(--panel-header-hi)` background highlight
- Event count shown in header: `· N EVENTS`

### Task 2 — LapPanel Shell

**`frontend/src/components/LapPanel/LapPanel.tsx`** (new):
- `grid-template-rows: '38px auto auto 1fr auto auto'` — header / big-time / sectors / pace trace / projection / status-log
- **Big lap time block:** 56px weight-300 `var(--text)` with `textShadow: '0 0 24px rgba(0,229,255,0.25)'` cyan glow; shows `elapsed = lap_time.mean * lapFrac` (in-progress), `/FINAL` suffix in 14px muted
- **Delta blocks:** Δ PB (vs min of revealedLaps) and Δ MODEL (vs lo_95) side-by-side; 2px colored left borders; `var(--ok)` / `var(--warn)` / `var(--hot)` thresholds
- **Sector cards:** 3-column grid, each with colored 3px left border (`purple/ok/warn`), active sector gets `var(--accent)` 2px top border + `0 0 4px rgba(0,229,255,0.5)` box-shadow and full opacity
- **PaceTrace:** embedded in `1fr` flex row with PACE·STINT header label
- **Stint projection (2×2):** NEXT LAP (linear estimate), STINT END (projected degradation), AVG WEAR (% of 22MJ capacity, color-coded), CLIFF IN (laps until grip drops below 1.2, green/amber/red)
- **StatusLog:** embedded as last row (VIZ-07)
- Skeleton: `PanelSkeleton` rendered when `data` is null

## Verification Results

| Check | Result |
|-------|--------|
| `npm run build` | Exits 0 — 215KB JS, 8.14KB CSS |
| `fontSize: 56` in LapPanel | Confirmed line 77 |
| `fontWeight: 300` in LapPanel | Confirmed line 77 |
| `textShadow: '0 0 24px rgba(0,229,255,0.25)'` | Confirmed line 79 |
| `gridTemplateRows: '38px auto auto 1fr auto auto'` | Confirmed line 56 |
| `Δ PB` and `Δ MODEL` delta blocks | Confirmed lines 92–93 |
| `STINT MODEL · PROJECTION` | Confirmed line 156 |
| `<StatusLog` embedded | Confirmed line 179 |
| `NEXT LAP` and `CLIFF IN` stats | Confirmed lines 160, 163 |
| `requestAnimationFrame` in PaceTrace | Confirmed line 26 |
| `d3-scale` import in PaceTrace | Confirmed line 2 |
| `d3-shape` import in PaceTrace | Confirmed line 3 |
| `setHoveredLap` on mouse move | Confirmed lines 62, 73 |
| `var(--purple)` best lap marker | Confirmed line 94 |
| `collapsed` state in StatusLog | Confirmed line 48 |
| `aria-expanded` in StatusLog | Confirmed line 74 |
| `hoveredLap` linked hover in StatusLog | Confirmed line 97 |
| `approaching thermal limit` event text | Confirmed line 20 |

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | PaceTrace D3 chart + StatusLog collapsible | ad6e50b | `LapPanel/PaceTrace.tsx`, `LapPanel/StatusLog.tsx` |
| 2 | LapPanel shell — big time, deltas, sectors, pace trace, projection | 0e88ee6 | `LapPanel/LapPanel.tsx` |

## Deviations from Plan

None — plan executed exactly as written. All code blocks from the plan were implemented faithfully. The only adaptation was using `&middot;` HTML entity in StatusLog's header separator (replacing the inline `·` literal) to avoid potential JSX string interpolation issues.

## Known Stubs

| File | Stub | Reason |
|------|------|--------|
| `LapPanel.tsx` | Sector times estimated as `lap_time.mean / 3` | Phase 4 API does not expose sector-level timing; equal thirds is visually adequate for Phase 5 |
| `LapPanel.tsx` | NEXT LAP/STINT END use linear extrapolation (`0.02 * lapNumber`) | Real degradation trend computation deferred; physics-based projection available from Phase 4 data in Plan 08 |

These stubs do not prevent the plan's goal — the LapPanel renders with real LapData, all layouts match design reference, and the delta/projection blocks show informative values.

## Threat Flags

No new security surface introduced:
- T-05-06-01 (fmtLapTime/fmtDelta non-finite input): Guards present — `!isFinite` returns `—:—.—` / `—`
- T-05-06-02 (StatusLog message strings): Assembled from compile-time constants + `.toFixed()` numerics; rendered as JSX text nodes (auto-escaped)
- T-05-06-03 (ResizeObserver loop): `requestAnimationFrame` wrapping implemented

## Self-Check: PASSED

Files confirmed present:
- `frontend/src/components/LapPanel/PaceTrace.tsx` — FOUND
- `frontend/src/components/LapPanel/StatusLog.tsx` — FOUND
- `frontend/src/components/LapPanel/LapPanel.tsx` — FOUND

Commits confirmed:
- `ad6e50b` — feat(05-06): PaceTrace D3 chart + StatusLog collapsible
- `0e88ee6` — feat(05-06): LapPanel shell — big time, deltas, sectors, pace trace, projection

Build: `npm run build` exits 0 (215KB JS, 8.14KB CSS).
