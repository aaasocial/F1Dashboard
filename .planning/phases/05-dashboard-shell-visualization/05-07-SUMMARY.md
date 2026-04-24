---
phase: 05-dashboard-shell-visualization
plan: "07"
subsystem: frontend-physics-panel
tags: [react, typescript, d3, ci-bands, okabe-ito, linked-hover, zustand, vitest, viz-03, viz-04, viz-05, viz-06]
dependency_graph:
  requires:
    - frontend/src/lib/types.ts (Plan 02 — LapData CI triplets, Corner type)
    - frontend/src/lib/scales.ts (Plan 02 — CORNER_COLORS Okabe-Ito)
    - frontend/src/stores/useUIStore.ts (Plan 02 — hoveredCorner, hoveredLap, setHoveredCorner, setHoveredLap, pos)
    - frontend/src/stores/useSimulationStore.ts (Plan 02 — data, laps array)
    - frontend/src/components/shared/PanelHeader.tsx (Plan 03 — 38px panel header)
    - frontend/src/components/shared/Skeleton.tsx (Plan 03 — PanelSkeleton loading state)
  provides:
    - frontend/src/components/PhysicsPanel/PhysicsPanel.tsx (Tabbed physics panel: 4 metric tabs × 4 corner small-multiple charts)
    - frontend/src/components/PhysicsPanel/PhysicsChart.tsx (Single-corner CI band chart with D3 scales, hover crosshair, tooltip)
    - frontend/src/components/PhysicsPanel/PhysicsChart.test.ts (5 D3 path generation tests)
  affects:
    - Plan 09 (App.tsx wires PhysicsPanel into the grid layout)
tech_stack:
  added: []
  patterns:
    - D3 for math, React for DOM — area() CI band + line() mean line, paths as SVG strings
    - ResizeObserver with requestAnimationFrame guard prevents infinite resize loops
    - useShallow from zustand/react/shallow prevents re-renders on unrelated UIStore changes
    - Empty data guard (return null) before all D3 computation
    - Linked hover via UIStore setHoveredCorner (enter/leave) + setHoveredLap (mousemove)
    - CI band at opacity 0.12 (area polygon) + mean line at 1.5px strokeWidth (visually distinct, VIZ-04)
key_files:
  created:
    - frontend/src/components/PhysicsPanel/PhysicsChart.tsx
    - frontend/src/components/PhysicsPanel/PhysicsChart.test.ts
    - frontend/src/components/PhysicsPanel/PhysicsPanel.tsx
  modified: []
decisions:
  - "Tooltip format: L{lap}  {cfg.fmt(mean)}  ±{half.toFixed(1)} — all React JSX text nodes, auto-escaped, no dangerouslySetInnerHTML"
  - "METRICS config values copied exactly from cockpit-physics.jsx: domains [88,118], [1.10,1.50], [0,22], [1.5,5.5]; accents #FFD700, #00E5FF, #FFB020, #A855F7"
  - "CI band path uses d3-shape area() y0=lo_95 y1=hi_95; NaN inputs produce no-op path segments (d3-shape default behavior)"
  - "PhysicsChart.test.ts tests D3 math inline (not React component) to avoid jsdom SVG rendering gaps"
metrics:
  duration_seconds: 900
  completed_date: "2026-04-24"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 0
---

# Phase 5 Plan 07: PhysicsPanel Summary

**One-liner:** PhysicsPanel with 4 metric tabs (TREAD TEMP/GRIP μ/WEAR E/SLIP α PEAK) × 4 Okabe-Ito cornerwise CI band charts using D3 area()+line() math with React DOM rendering, hover crosshair linked to UIStore (VIZ-03/04/05/06).

## What Was Built

### Task 1 — PhysicsChart + PhysicsChart.test.ts (TDD)

**`frontend/src/components/PhysicsPanel/PhysicsChart.tsx`** (new):
- Single-corner CI band chart with D3 `scaleLinear` for x/y, `area()` for CI polygon, `line()` for mean line
- CI band rendered as `<path fill={color} opacity={0.12}>` — visually distinct from solid 1.5px mean line (VIZ-04)
- `ResizeObserver` with `requestAnimationFrame` guard for responsive SVG sizing
- `useShallow` on UIStore subscription to prevent unnecessary re-renders
- Hover syncs `setHoveredCorner(corner)` on enter, `setHoveredCorner(null)` on leave, `setHoveredLap(lap)` on mousemove — full linked hover (VIZ-05)
- Floating tooltip: `L{lap}  {value}  ±{CI half-width}` with corner-color border, auto-escaped React text nodes
- Corner badge: black bg, corner-color border, Okabe-Ito label in corner color (VIZ-06)
- Y axis: 3 ticks at domain min/mid/max; X axis labels (L1, L5, L10…) on last chart only
- Empty data guard: returns null for 0 laps

**`frontend/src/components/PhysicsPanel/PhysicsChart.test.ts`** (new):
- 5 tests: CI band non-empty for 3-lap data, CI path starts with M, mean path non-empty, CI band empty for 0 laps, SVG y-axis orientation (hi values → lower SVG y)
- Tests the D3 path logic directly (no React rendering required) — avoids jsdom SVG gaps

### Task 2 — PhysicsPanel Shell

**`frontend/src/components/PhysicsPanel/PhysicsPanel.tsx`** (new):
- 4 metric tabs with exact `label/unit/domain/accent` from cockpit-physics.jsx design reference
- Active tab: `var(--panel-header-hi)` background + 2px bottom border in tab accent color
- Inactive tabs: transparent background, `var(--text-dim)` color
- 4 stacked equal-height PhysicsChart via `gridTemplateRows: 'repeat(4, 1fr)'`
- `PanelHeader` with title "PHYSICS", subtitle "LAP-BY-LAP · CI₉₅", right slot shows `{revealed}/{total} LAPS`
- `PanelSkeleton` when no simulation data loaded
- `revealedLaps` sliced from `data.laps` by `Math.floor(pos - 1)` — scrubber-driven progressive reveal
- ARIA: `role="tab"` + `aria-selected` on buttons, `role="tabpanel"` on chart grid

## Verification Results

| Check | Result |
|-------|--------|
| `npm run test` | Exits 0 — 50 passed, 4 todo |
| `npm run build` | Exits 0 — 215KB JS, 8.14KB CSS |
| `opacity={0.12}` in PhysicsChart.tsx | Confirmed (CI band VIZ-04) |
| `strokeWidth={1.5}` in PhysicsChart.tsx | Confirmed (mean line VIZ-04) |
| `setHoveredCorner` in PhysicsChart.tsx | Confirmed ×4 (VIZ-05) |
| `setHoveredLap` in PhysicsChart.tsx | Confirmed (VIZ-05) |
| `useShallow` in PhysicsChart.tsx | Confirmed |
| `requestAnimationFrame` in PhysicsChart.tsx | Confirmed |
| `#FFD700` (TREAD TEMP accent) in PhysicsPanel.tsx | Confirmed |
| `domain: [88, 118]` in PhysicsPanel.tsx | Confirmed |
| `domain: [1.10, 1.50]` in PhysicsPanel.tsx | Confirmed |
| `gridTemplateRows: 'repeat(4, 1fr)'` | Confirmed |
| `role="tab"` + `aria-selected` | Confirmed |

## Task Commits

1. **Task 1: PhysicsChart + test** — `cad9f85`
2. **Task 2: PhysicsPanel shell** — `2a4464f`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Unused variable `iw` in PhysicsChart.test.ts**
- **Found during:** Task 2 build verification (`npm run build`)
- **Issue:** The last test's inline `const padL = 40, iw = w - padL - 12` declared `iw` but never used it — TypeScript strict TS6133 error
- **Fix:** Removed `padL`, `w`, and `iw` from that test's local scope; the test only needed `ih`, `padT`, `padB`, and `sy`
- **Files modified:** `frontend/src/components/PhysicsPanel/PhysicsChart.test.ts`
- **Commit:** 2a4464f (included in Task 2 commit)

## Known Stubs

None — all four PhysicsChart metric fields (`t_tread_*`, `grip_*`, `e_tire_*`, `slip_angle_*`) are wired from the `LapData` CI triplets. The component returns `null` when `revealedLaps` is empty but this is correct behavior, not a stub.

## Threat Flags

No new security surface beyond the plan's threat model:
- T-05-07-01: D3 area/line paths from API numeric values — TypeScript CI shape enforced; NaN inputs produce no-op segments — mitigated
- T-05-07-02: Tooltip content — all React JSX text nodes, auto-escaped, no dangerouslySetInnerHTML — mitigated
- T-05-07-03: setHoveredLap on every mousemove — Zustand O(1) setter, useShallow prevents unnecessary re-renders — accepted

## Self-Check: PASSED
