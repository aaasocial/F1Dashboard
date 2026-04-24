---
phase: 06-playback-interactions-sharing
plan: "04"
subsystem: frontend-export-clipboard
tags: [context-menu, export, clipboard, car-panel, physics-panel, wave-2]
dependency_graph:
  requires:
    - export-pure-functions   # 06-01 (export.ts)
    - extended-ui-store-phase6  # 06-02 (showToast)
    - toast-component          # 06-01 (Toast.tsx)
  provides:
    - chart-context-menu
    - tire-clipboard-copy
    - physics-panel-png-svg-csv-export
  affects:
    - frontend/src/components/PhysicsPanel/PhysicsPanel.tsx (context menu + export wiring)
    - frontend/src/components/CarPanel/CarWheel.tsx (right-click clipboard)
    - frontend/src/components/CarPanel/CarFooter.tsx (right-click clipboard)
tech_stack:
  added: []
  patterns:
    - "SVG composition pattern: querySelectorAll('svg') on tabpanel ref → clone children into stacked <g> elements with translate(0, y) offsets"
    - "Context menu dismiss pattern: mousedown outside + Esc keydown + scroll + resize listeners added/removed via useEffect cleanup"
    - "Clipboard copy with graceful degradation: try/catch around navigator.clipboard.writeText; toast fires regardless of clipboard success"
    - "onContextMenu with e.preventDefault() on SVG <g> elements prevents browser native menu"
key_files:
  created:
    - frontend/src/lib/tireClipboard.ts
    - frontend/src/lib/tireClipboard.test.ts
    - frontend/src/components/PhysicsPanel/ChartContextMenu.tsx
    - frontend/src/components/PhysicsPanel/ChartContextMenu.test.tsx
  modified:
    - frontend/src/components/PhysicsPanel/PhysicsPanel.tsx
    - frontend/src/components/CarPanel/CarWheel.tsx
    - frontend/src/components/CarPanel/CarFooter.tsx
decisions:
  - "SVG composition uses querySelectorAll('svg') on tabpanelRef rather than passing refs into each PhysicsChart — avoids prop drilling and keeps PhysicsChart opaque"
  - "ChartContextMenu uses position:fixed (not absolute) so it escapes any overflow:hidden parent containers"
  - "formatTireMetrics uses .toFixed(1) for t_tread, .toFixed(2) for grip, .toFixed(1) for e_tire, .toFixed(1) for slip_angle — exact D-15 spec values"
  - "handleExport is async inside PhysicsPanel (not ChartContextMenu) so it has access to data and metric state without prop drilling"
metrics:
  duration: "~20 minutes"
  completed: "2026-04-25"
  tasks_completed: 3
  files_created: 4
  files_modified: 3
---

# Phase 6 Plan 04: Chart Export Context Menu + Tire Clipboard Copy Summary

Right-click context menu for PhysicsPanel chart area (PNG/SVG/CSV export composing all 4 corner SVGs) and right-click clipboard copy from CarWheel and CarFooter tire widgets, both surfacing a COPIED toast.

## What Was Built

### Task 1: tireClipboard.ts (TDD — 6 tests)

**`frontend/src/lib/tireClipboard.ts`**
- `formatTireMetrics(corner, lap)`: builds the D-15 clipboard string `"FL | 94.2°C | Grip 1.31μ | Wear 3.2 MJ | Slip 2.1°"` from `LapData` CI mean values
  - Corner uppercased; t_tread 1dp; grip 2dp; e_tire 1dp; slip_angle 1dp
- `copyTireMetrics(corner, lap)`: async — calls `navigator.clipboard.writeText(text)` wrapped in try/catch, then `useUIStore.getState().showToast('COPIED <CORNER>')`
- Graceful degradation: toast fires even if clipboard permission is denied or API throws

**`frontend/src/lib/tireClipboard.test.ts`** — 6 tests:
- `formatTireMetrics('fl', lap)` matches D-15 example string exactly
- Corner code is uppercased
- RR corner formatted correctly with its specific values
- `copyTireMetrics` calls `navigator.clipboard.writeText` with the formatted string
- `copyTireMetrics` sets `toastMessage` to `'COPIED RL'`
- Toast still fires when `clipboard.writeText` throws

### Task 2: ChartContextMenu + PhysicsPanel Integration (TDD — 7 tests)

**`frontend/src/components/PhysicsPanel/ChartContextMenu.tsx`**
- `position: fixed` overlay, `width: 160px`, `zIndex: 150`
- 3 `<button role="menuitem">` items: Export PNG, Export SVG, Export CSV
- Viewport clamping: `left = Math.min(x, window.innerWidth - 160 - 8)`, `top = Math.min(y, window.innerHeight - 110 - 8)`
- Dismiss listeners (all cleaned up via useEffect return):
  - `document.mousedown` (click outside)
  - `document.keydown` with `e.code === 'Escape'`
  - `window.scroll` (capture phase)
  - `window.resize`
- Returns `null` when `open=false` (no DOM node)

**`frontend/src/components/PhysicsPanel/PhysicsPanel.tsx`** (updated)
- Added `tabPanelRef` on the `<div role="tabpanel">` containing the 4 PhysicsChart instances
- `onContextMenu` handler on that div: `e.preventDefault()` + `setMenuPos({ open: true, x: e.clientX, y: e.clientY })`
- `composeExportSvg()`: queries `root.querySelectorAll('svg')` — finds all 4 chart SVGs — clones their child nodes into `<g transform="translate(0, y)">` elements stacked vertically in a single composed `<svg>`
- `handleExport(format)`:
  - `'csv'`: `exportCsv(data.laps, metric, 'physics-<metric>.csv')` + `showToast('CSV DOWNLOADED')`
  - `'svg'`: `exportSvg(composed, 'physics-<metric>.svg')` + `showToast('SVG DOWNLOADED')`
  - `'png'`: `await exportPng(composed, 'physics-<metric>.png')` + `showToast('PNG DOWNLOADED')`
  - Errors caught → `showToast('EXPORT FAILED — <message>')`
- `<ChartContextMenu>` rendered at component root level (sibling to tabpanel)

**`frontend/src/components/PhysicsPanel/ChartContextMenu.test.tsx`** — 7 tests:
- Returns null when `open=false`
- Renders 3 items when `open=true`
- Clicking CSV calls `onExport('csv')`
- Clicking PNG calls `onExport('png')`
- Clamps left to `windowWidth - 160 - 8 = 32` at `innerWidth=200`
- Esc keydown calls `onClose`
- Mousedown outside calls `onClose`

### Task 3: CarWheel + CarFooter Right-Click Clipboard

**`frontend/src/components/CarPanel/CarWheel.tsx`**
- Added `import { copyTireMetrics } from '../../lib/tireClipboard'`
- Added `onContextMenu` to the root `<g>`:
  ```tsx
  onContextMenu={(e) => {
    e.preventDefault()
    if (lap) void copyTireMetrics(corner, lap)
  }}
  ```
- Guard: `if (lap)` — no-op when no simulation loaded

**`frontend/src/components/CarPanel/CarFooter.tsx`**
- Added `import { copyTireMetrics } from '../../lib/tireClipboard'`
- Added `onContextMenu` to each corner `<div>` in `CORNERS.map(c => ...)`:
  ```tsx
  onContextMenu={(e) => {
    e.preventDefault()
    if (lap) void copyTireMetrics(c, lap)
  }}
  ```

## SVG Composition Strategy

The `composeExportSvg` function in PhysicsPanel uses a DOM query approach:

1. `tabPanelRef.current.querySelectorAll('svg')` collects all 4 `<svg>` elements rendered by PhysicsChart instances
2. For each SVG, `getBoundingClientRect()` gives the rendered dimensions
3. A new composed `<svg>` is created with `width = max(chartWidths)` and `height = sum(chartHeights)`
4. Each chart's child nodes are cloned into a `<g transform="translate(0, y)">` where `y` accumulates
5. The composed SVG is passed to `exportSvg` or `exportPng` from `export.ts`

This approach keeps PhysicsChart opaque (no ref props needed) and correctly handles the dynamic sizing from ResizeObserver.

## Context Menu Dismiss Listeners

Four event types handled, all registered/unregistered within a single `useEffect([open, onClose])`:

| Event | Target | Why |
|-------|--------|-----|
| `mousedown` | `document` | Click anywhere outside the menu div |
| `keydown` | `document` | Esc key press |
| `scroll` | `window` (capture) | Page scroll shifts menu out of position |
| `resize` | `window` | Window resize invalidates clamped position |

The `ref.current.contains(e.target)` check on mousedown ensures clicks *inside* the menu (e.g., on the hover highlight) don't close it before the click handler fires.

## Deviations from Plan

None — plan executed exactly as written. All TDD phases followed: RED (missing file error), GREEN (implementation), verify.

## Threat Surface Check

| Flag | File | Status |
|------|------|--------|
| T-6-SVG | composeExportSvg in PhysicsPanel.tsx | Mitigated — only numeric chart DOM elements cloned, no user-supplied strings |
| T-6-CSV | exportCsv call in handleExport | Mitigated — metric key constrained to MetricKey union, all values numeric |
| T-6-CLIP | copyTireMetrics in tireClipboard.ts | Mitigated — clipboard string built from LapData numeric fields + corner enum only |
| T-6-MENU | ChartContextMenu | Accepted — hardcoded text nodes, no dangerouslySetInnerHTML |
| T-6-DOWNLOAD | triggerDownload called with metric-keyed filename | Mitigated — filename from MetricKey union, no path traversal possible |

## Known Stubs

None. All plan goals are fully implemented.

## Verification Results

| Check | Result |
|-------|--------|
| `npx tsc -b --noEmit` | Exit 0 (clean) |
| `npx vitest run` | 128 passed, 4 todo, 1 file skipped (sse.test.ts) |
| `tireClipboard.test.ts` | 6 passed |
| `ChartContextMenu.test.tsx` | 7 passed |
| `CarWheel.tsx` imports `copyTireMetrics` | PASS |
| `CarWheel.tsx` contains `onContextMenu` on root `<g>` | PASS |
| `CarWheel.tsx` calls `e.preventDefault()` | PASS |
| `CarFooter.tsx` imports `copyTireMetrics` | PASS |
| `CarFooter.tsx` contains `onContextMenu` per corner div | PASS |
| `PhysicsPanel.tsx` contains `onContextMenu={e =>` | PASS |
| `PhysicsPanel.tsx` contains `e.preventDefault()` | PASS |
| `PhysicsPanel.tsx` calls `exportCsv(data.laps, metric,` | PASS |
| `PhysicsPanel.tsx` calls `exportSvg(composed,` | PASS |
| `PhysicsPanel.tsx` calls `exportPng(composed,` | PASS |
| `PhysicsPanel.tsx` calls `root.querySelectorAll('svg')` | PASS |

## Self-Check: PASSED

- `frontend/src/lib/tireClipboard.ts` — FOUND
- `frontend/src/lib/tireClipboard.test.ts` — FOUND
- `frontend/src/components/PhysicsPanel/ChartContextMenu.tsx` — FOUND
- `frontend/src/components/PhysicsPanel/ChartContextMenu.test.tsx` — FOUND
- Commits 562cd08, 920e00c, b658c91 — FOUND in git log
