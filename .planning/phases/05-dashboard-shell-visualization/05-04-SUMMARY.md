---
phase: 05-dashboard-shell-visualization
plan: "04"
subsystem: frontend-car-panel
tags: [react, typescript, svg, viridis, d3, okabe-ito, zustand, car-panel, viz-02, viz-05, viz-06]
dependency_graph:
  requires:
    - frontend/src/lib/scales.ts (Plan 02 — tempToViridis, CORNER_COLORS, COMPOUND_COLORS, compoundColor)
    - frontend/src/lib/types.ts (Plan 02 — LapData, Corner, CI)
    - frontend/src/stores/useUIStore.ts (Plan 02 — hoveredCorner, setHoveredCorner, pos)
    - frontend/src/stores/useSimulationStore.ts (Plan 02 — data)
  provides:
    - frontend/src/components/CarPanel/CarPanel.tsx (Car panel with chassis SVG + 4 wheels + footer readouts)
    - frontend/src/components/CarPanel/CarWheel.tsx (Single wheel SVG — viridis fill, wear erosion, grip ladder, CI halo)
    - frontend/src/components/CarPanel/CarChassis.tsx (SF-24 chassis SVG outline paths)
    - frontend/src/components/CarPanel/CarFooter.tsx (4-column footer readout grid with hover sync)
    - frontend/src/components/shared/PanelHeader.tsx (Shared panel header with accent tick, title, right content)
    - frontend/src/components/shared/Skeleton.tsx (PanelSkeleton and Skeleton loading placeholders)
  affects:
    - Plans 03, 05, 06, 07 (shared PanelHeader/Skeleton used by all panels)
    - Plan 09 (App.tsx wires CarPanel into grid layout)
tech_stack:
  added: []
  patterns:
    - D3 viridis via interpolateViridis (d3-scale-chromatic) for rectangular tile temperature fill
    - Okabe-Ito corner colors from scales.ts for FL/FR/RL/RR SVG labels
    - FIA compound colors from scales.ts for compound strip
    - Zustand UIStore hoveredCorner two-way sync between CarWheel and CarFooter
    - SVG inline defs (brake-glow radialGradient, tech-grid pattern) scoped to CarPanel
    - Rectangular top-down tire schematic — no arc/ring circular gauge elements
key_files:
  created:
    - frontend/src/components/CarPanel/CarPanel.tsx
    - frontend/src/components/CarPanel/CarWheel.tsx
    - frontend/src/components/CarPanel/CarChassis.tsx
    - frontend/src/components/CarPanel/CarFooter.tsx
    - frontend/src/components/shared/PanelHeader.tsx
    - frontend/src/components/shared/Skeleton.tsx
  modified: []
decisions:
  - VIZ-02 satisfied by rectangular top-down tire schematic with viridis fill — not a circular arc gauge; per locked design reference cockpit-car.jsx which supersedes REQUIREMENTS.md placeholder text
  - PanelHeader/Skeleton created as shared components in this plan (Rule 3 deviation) — Plan 03 creates these in the same wave but Plan 04 imports them; parallel execution requires self-contained delivery
  - CarFooter uses inline brakeTemp/wearPct helpers (ported from cockpit-car.jsx) rather than importing from formatters.ts — avoids circular dependencies and keeps domain logic co-located with usage
  - stroke={stroke} JSX pattern used in CarChassis (stroke variable = 'var(--rule-strong)') rather than literal string attribute — functionally identical output, TypeScript-idiomatic
metrics:
  duration_seconds: 720
  completed_date: "2026-04-24"
  tasks_completed: 2
  tasks_total: 2
  files_created: 6
  files_modified: 0
---

# Phase 5 Plan 04: CarPanel Summary

**One-liner:** SF-24 top-down car schematic with 4 viridis-temperature-filled rectangular tire widgets (wear erosion, grip ladder, CI halo, slip tick), 4-column footer readouts, and bidirectional UIStore hoveredCorner sync — satisfying VIZ-02, VIZ-05, VIZ-06 per the locked design reference.

## What Was Built

### Task 1 — CarChassis + CarFooter + CarPanel shell + shared components

**`frontend/src/components/CarPanel/CarChassis.tsx`** (new):
- Faithful port of SF-24 top-down silhouette from `cockpit-car.jsx` CarChassis()
- Front wing with endplates, nose cone, front/rear suspension arms, main tub, halo ellipse, cockpit, sidepods, airbox, engine/gearbox with rib lines, floor dashed outline, rear wing + DRS line, diffuser hint, direction arrow
- All strokes via `stroke = 'var(--rule-strong)'` variable; detail lines use `var(--text-muted)`

**`frontend/src/components/CarPanel/CarFooter.tsx`** (new):
- 4-column CSS grid with `gridTemplateColumns: repeat(4, 1fr)`
- Per-corner columns: T (temp with CI range), μ (grip with ±CI), WEAR (% with color threshold), α (slip angle), BRK (brake temp in amber)
- Active column highlighted via `var(--panel-header-hi)` + `2px solid var(--accent)` left border
- `onMouseEnter` calls `setHoveredCorner(c)`, `onMouseLeave` calls `setHoveredCorner(null)`
- Inline `brakeTemp()` and `wearPct()` helpers ported from design reference

**`frontend/src/components/CarPanel/CarPanel.tsx`** (new):
- `gridTemplateRows: '38px 1fr auto'` layout (header / SVG / footer)
- SVG `viewBox="0 0 400 780"` with `preserveAspectRatio="xMidYMid meet"`
- Radial gradient background `radial-gradient(ellipse at center, #0a1018 0%, var(--panel-bg) 70%)`
- Tech grid pattern, centerline dashes, axle reference lines with FRONT/REAR AXLE labels
- Compound strip with FIA compound color (VIZ-06)
- Wheelbase and front-track dimension annotations
- 4 CarWheel instances at exact geometry from plan spec (cx/cy/w/h per FL/FR/RL/RR)
- PanelSkeleton returned when `data === null`

**`frontend/src/components/shared/PanelHeader.tsx`** (new, Rule 3 deviation):
- Accent tick (2px × 14px) + title (bold) + optional subtitle + right slot
- Used by CarPanel; will be reused by all other Wave 2/3 panels

**`frontend/src/components/shared/Skeleton.tsx`** (new, Rule 3 deviation):
- `PanelSkeleton`: full-height centered loading placeholder
- `Skeleton`: inline loading bar with configurable width/height

### Task 2 — CarWheel SVG component

**`frontend/src/components/CarPanel/CarWheel.tsx`** (new):

Rectangular top-down tire schematic per locked design reference (NOT a circular arc gauge). All 13 visual elements present:

1. **Brake glow ellipse** — `url(#brake-glow)` radialGradient; opacity driven by `brakeNorm`
2. **Tire outer rim** — 1.5px inset rect; accent stroke when hovered
3. **Viridis temperature fill** — `tempToViridis(tempMean)` colors the full tile body (60°C=purple, 120°C=yellow); this IS the temperature visualization (VIZ-02)
4. **Tread grooves** — 7 horizontal lines dividing 8 bands, `rgba(0,0,0,0.45)`
5. **Wear erosion** — `wearBands = round(wearPct * 8)` dark rectangles; fronts erode from top, rears from bottom (correct leading-edge physics)
6. **Temperature badge** — centered on tile, `temp.toFixed(0)°` in white mono on dark bg
7. **Corner label** — inboard side in Okabe-Ito `CORNER_COLORS[corner]` (VIZ-06)
8. **Grip ladder** — outboard, 10 segments; `litSegments = round(gripNorm * 10)`; lit: `var(--accent)` at opacity ramp `0.4 + 0.6*(seg/10)`, unlit: `var(--rule-strong)`
9. **Wear bar** — horizontal strip below tire; fill color: green (<45%), amber (45–70%), red (>70%)
10. **Slip angle tick** — rotated line + dot above tire; `rotation = clamp(-6,6,slip) * 2 * direction`
11. **Brake temp readout** — inboard label in amber
12. **CI halo** — outset rect; `ciStroke = 0.6 + min(3, (hi_95 - lo_95) * 0.12)` (VIZ-02 CI bands)
13. **Hover rectangle** — dashed accent box when hovered

Hover sync: `onMouseEnter` → `onHover(corner)`, `onMouseLeave` → `onHover(null)` (VIZ-05).

## Verification Results

| Check | Result |
|-------|--------|
| `npm run build` | Exits 0 — 63 modules, 215KB JS, 7KB CSS |
| `tempToViridis` in CarWheel | Confirmed |
| `wearBands` in CarWheel | Confirmed |
| `ciStroke` in CarWheel | Confirmed |
| `CORNER_COLORS` import in CarWheel | Confirmed |
| `cx: 82` (FL) in CarPanel | Confirmed |
| `cx: 318` (FR) in CarPanel | Confirmed |
| `gridTemplateRows: '38px 1fr auto'` in CarPanel | Confirmed |
| `preserveAspectRatio="xMidYMid meet"` in CarPanel | Confirmed |
| `radial-gradient` background in CarPanel | Confirmed |
| `gridTemplateColumns: 'repeat(4, 1fr)'` in CarFooter | Confirmed |
| `var(--panel-header-hi)` in CarFooter | Confirmed |
| `setHoveredCorner(c)` + `setHoveredCorner(null)` in CarFooter | Confirmed |
| No arc/ring/circular gauge in CarWheel | Confirmed — `circle r="1.5"` is slip tick dot only |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Shared components PanelHeader and Skeleton created in this plan**
- **Found during:** Task 1 — CarPanel.tsx imports `PanelHeader` from `../shared/PanelHeader` and `PanelSkeleton` from `../shared/Skeleton`; these files did not exist (Plan 03 creates them in the same wave but runs in parallel)
- **Fix:** Created `frontend/src/components/shared/PanelHeader.tsx` and `frontend/src/components/shared/Skeleton.tsx` matching the Plan 03 spec (shared panel header with accent tick, PanelSkeleton with centered label text)
- **Files created:** `frontend/src/components/shared/PanelHeader.tsx`, `frontend/src/components/shared/Skeleton.tsx`
- **Commit:** c41622b

**2. [Rule 1 - Bug] CarFooter removed unused formatter re-exports**
- **Found during:** Task 1 — initial CarFooter draft included `export { fmtTemp, fmtGrip, fmtSlip }` re-exports but those were not imported (CarFooter uses inline formatting for better co-location)
- **Fix:** Removed the re-exports and unused import
- **Files modified:** `frontend/src/components/CarPanel/CarFooter.tsx`
- **Commit:** c41622b

## Known Stubs

None — all components render real LapData when `data` is present in SimulationStore. When `data === null`, PanelSkeleton renders the "SELECT STINT AND RUN MODEL" message. No hardcoded empty values flow to UI rendering paths.

## Threat Flags

No new security surface introduced. All threat model entries from the plan are mitigated:
- T-05-04-01 (SVG text injection): React JSX text children auto-escaped — no `dangerouslySetInnerHTML` used
- T-05-04-02 (CI triplet geometry): `Math.max(0, Math.min(1, ...))` clamps on all normalized values; `?? default` guards on all `lap?.` accesses
- T-05-04-03 (SVG `url(#brake-glow)`): Inline `<defs>` in CarPanel SVG — no external URL references
- T-05-04-04 (ResizeObserver): Not used — fixed SVG viewBox with preserveAspectRatio handles scaling

## Self-Check: PASSED

All 6 key files confirmed present on disk:
- `/c/Users/Eason/Desktop/CC/F1 Dashboard/.claude/worktrees/agent-a89e2357/frontend/src/components/CarPanel/CarPanel.tsx` — FOUND
- `/c/Users/Eason/Desktop/CC/F1 Dashboard/.claude/worktrees/agent-a89e2357/frontend/src/components/CarPanel/CarWheel.tsx` — FOUND
- `/c/Users/Eason/Desktop/CC/F1 Dashboard/.claude/worktrees/agent-a89e2357/frontend/src/components/CarPanel/CarChassis.tsx` — FOUND
- `/c/Users/Eason/Desktop/CC/F1 Dashboard/.claude/worktrees/agent-a89e2357/frontend/src/components/CarPanel/CarFooter.tsx` — FOUND
- `/c/Users/Eason/Desktop/CC/F1 Dashboard/.claude/worktrees/agent-a89e2357/frontend/src/components/shared/PanelHeader.tsx` — FOUND
- `/c/Users/Eason/Desktop/CC/F1 Dashboard/.claude/worktrees/agent-a89e2357/frontend/src/components/shared/Skeleton.tsx` — FOUND

Task commits confirmed in git log:
- c41622b (Task 1: CarPanel shell + CarChassis + CarFooter + shared components) — FOUND
- 9e6ca73 (Task 2: CarWheel rectangular tire schematic) — FOUND

Build exits 0: confirmed.
