---
phase: 06-playback-interactions-sharing
plan: "02"
subsystem: frontend-stores-topstrip-scrubber
tags: [zustand, topstrip, scrubber, playback, error-retry, sector-colors, pit-markers, wave-1]
dependency_graph:
  requires:
    - playwright-e2e-infrastructure  # 06-01
  provides:
    - extended-ui-store-phase6
    - extended-sim-store-phase6
    - topstrip-transport-bar
    - scrubber-sector-colored
  affects:
    - frontend/src/stores/useUIStore.ts (Speed type, 6 new state slots)
    - frontend/src/stores/useSimulationStore.ts (sessionId, lastRunParams)
    - frontend/src/lib/sse.ts (lastRunParams recorded before fetch)
    - frontend/src/components/TopStrip/TopStrip.tsx (full transport bar upgrade)
    - frontend/src/components/TopStrip/Scrubber.tsx (sector segments + pit markers)
tech_stack:
  added: []
  patterns:
    - "Dynamic import pattern: setSimulationData calls import('./useUIStore') to avoid circular dep when resetting xZoom"
    - "Fragment return pattern: TopStrip returns <> to sibling the fixed-position error banner outside the 52px grid row"
    - "position:fixed top:52 zIndex:50 for error banner — sits below 52px TopStrip without altering App.tsx grid"
    - ".test.tsx convention for test files that render JSX via @testing-library/react"
key_files:
  created:
    - frontend/src/components/TopStrip/Scrubber.test.tsx
  modified:
    - frontend/src/stores/useUIStore.ts
    - frontend/src/stores/useUIStore.test.ts
    - frontend/src/stores/useSimulationStore.ts
    - frontend/src/lib/sse.ts
    - frontend/src/components/TopStrip/TopStrip.tsx
    - frontend/src/components/TopStrip/Scrubber.tsx
decisions:
  - "Speed union retyped from 1|2|4|8 to 0.5|1|2|4 (D-03 spec); TopStrip speed array updated in same commit"
  - "setSimulationData triggers setXZoom(null) via dynamic import to avoid circular module reference between stores"
  - "Error banner uses position:fixed top:52 rather than altering App.tsx gridTemplateRows — preserves the 52px 1fr grid contract"
  - "Scrubber test file uses .test.tsx extension (not .test.ts) because it imports JSX via @testing-library/react"
  - "onPointerDown test validates cursor style rather than element.onpointerdown — React uses event delegation, not DOM property assignment"
metrics:
  duration: "~6 minutes"
  completed: "2026-04-24"
  tasks_completed: 3
  files_created: 1
  files_modified: 6
---

# Phase 6 Plan 02: Store Extension + TopStrip Transport Bar + Scrubber Sector Coloring Summary

Extended Zustand stores with all Phase 6 state slots, upgraded TopStrip with a full transport bar (⏮ ◄ play ► ⏭ + 0.5×–4× speed + ⓘ provenance + error/RETRY banner), and upgraded Scrubber with sector-colored segments and white pit-stop markers.

## What Was Built

### Task 1: Store Extension + sse.ts lastRunParams

**`frontend/src/stores/useUIStore.ts`**
- `Speed` type alias exported: `0.5 | 1 | 2 | 4` (was `1 | 2 | 4 | 8`)
- 6 new state fields: `statusLogCollapsed`, `xZoom`, `mapFullscreen`, `shortcutsOpen`, `provenanceOpen`, `toastMessage`
- 7 new actions: `setStatusLogCollapsed`, `toggleStatusLog`, `setXZoom`, `setMapFullscreen`, `setShortcutsOpen`, `setProvenanceOpen`, `showToast`, `clearToast`
- All existing Phase 5 fields and actions preserved

**`frontend/src/stores/useSimulationStore.ts`**
- `RunParams` interface exported: `{ raceId, driverCode, stintIndex }`
- 2 new state fields: `sessionId: string | null`, `lastRunParams: RunParams | null`
- 2 new actions: `setSessionId`, `setLastRunParams`
- `setSimulationData` triggers `setXZoom(null)` via dynamic import (avoids circular module reference)
- `reset()` preserves `sessionId` and `lastRunParams` so RETRY survives a reset

**`frontend/src/lib/sse.ts`**
- `setLastRunParams({ raceId, driverCode, stintIndex })` called before the `try` block — ensures RETRY works even if the request errors immediately

### Task 2: TopStrip Transport Bar Upgrade

**`frontend/src/components/TopStrip/TopStrip.tsx`**
- MIDDLE BLOCK now contains: `⏮` (jump to lap 1), `◄` (step back, clamped at 1), play/pause, `►` (step forward, clamped at maxLap), `⏭` (jump to maxLap)
- Speed selector changed from `[1, 2, 4, 8]` to `[0.5, 1, 2, 4]` — matching new `Speed` type
- RIGHT BLOCK: `ⓘ` button before LAP counter calls `setProvenanceOpen(true)`
- Error banner: `position:fixed top:52 zIndex:50`, renders when `useSimulationStore.error` is non-null
  - `data-testid="error-banner"` + `role="alert"` for accessibility
  - RETRY button calls `runSimulationStream(lastRunParams...)` via `handleRetry` callback
  - Dismiss `✕` button calls `setError(null)`
- Component returns a React fragment `<>` to accommodate the sibling error banner

### Task 3: Scrubber Sector Segments + Pit Markers

**`frontend/src/components/TopStrip/Scrubber.tsx`**
- Reads `useSimulationStore(s => s.data?.laps)` for pit detection
- 3 sector segment divs (equal thirds of maxLap range): `#3a98b4`, `#2a7a93`, `#1d6278` (opacity 0.65)
- `derivePitLaps()`: filters `laps.filter(l => l.lap_number > 1 && l.stint_age === 0)`
- White 2×16px pit markers at `((lapNum-1)/(maxLap-1))*100%` left position
- All `data-testid` attributes: `scrubber`, `sector-segment-{0,1,2}`, `pit-marker`
- Original pointer-drag logic preserved verbatim

**`frontend/src/components/TopStrip/Scrubber.test.tsx`** (new)
- 4 tests: sector colors (rgb equivalents), no pit markers when none qualify, pit marker at 75% for lap 4/5, cursor style verification

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] TypeScript error: TopStrip speed array `[1,2,4,8]` incompatible with new `Speed` type**
- **Found during:** Task 1 — `tsc -b --noEmit` after useUIStore.ts rewrite
- **Issue:** TopStrip.tsx still had `([1, 2, 4, 8] as const)` which includes `8` — not assignable to `Speed = 0.5|1|2|4`
- **Fix:** Changed to `([0.5, 1, 2, 4] as const)` in Task 1 commit (fix included with store changes)
- **Files modified:** `frontend/src/components/TopStrip/TopStrip.tsx`
- **Commit:** 8436181

**2. [Rule 1 - Bug] Scrubber test pointer-drag assertion incorrect**
- **Found during:** Task 3 — first test run
- **Issue:** Test checked `typeof element.onpointerdown === 'function'` — but React uses event delegation, so the DOM property is `null` (type `object`)
- **Fix:** Changed assertion to check `element.style.cursor === 'pointer'` — correctly verifies the interactive drag container identity
- **Files modified:** `frontend/src/components/TopStrip/Scrubber.test.tsx`

### Decision: `.test.tsx` for Scrubber tests

The plan noted to check convention (`.test.ts` vs `.test.tsx`). `PhysicsChart.test.ts` uses `.test.ts` but tests D3 math only (no JSX). The Scrubber test imports and renders a React component via `@testing-library/react`, which requires JSX transform. Used `.test.tsx` — correct for JSX-containing test files. Vitest config's `include: ['src/**/*.{test,spec}.{ts,tsx}']` picks up both extensions.

## Threat Surface Check

The threat model items are addressed:

| Threat | Status |
|--------|--------|
| T-6-XSS-ERR: error string in banner | Mitigated — rendered as JSX text node `{error.toUpperCase()}`, React escapes by default |
| T-6-RETRY-CSRF: RETRY re-issues same-origin POST | Accepted — same attack surface as original RUN MODEL |
| T-6-PIT-INJECT: pit marker positions | Mitigated — computed from numeric `lap_number` values only |
| T-6-CLIP: clipboard (Plan 03 scope) | Out of scope for this plan — `toastMessage` slot added, clipboard logic in Plan 03 |

## Verification Results

| Check | Result |
|-------|--------|
| `tsc -b --noEmit` | Exit 0 (clean) |
| `npm test` (vitest) | 69 passed, 4 todo, 1 file skipped (sse.test.ts) |
| `useUIStore.ts` contains `Speed = 0.5 \| 1 \| 2 \| 4` | PASS |
| `useUIStore.ts` contains `statusLogCollapsed` | PASS |
| `useSimulationStore.ts` contains `sessionId` | PASS |
| `useSimulationStore.ts` contains `lastRunParams` | PASS |
| `sse.ts` calls `setLastRunParams` before try block | PASS |
| `TopStrip.tsx` contains `⏮`, `⏭`, `◄`, `►` | PASS |
| `TopStrip.tsx` contains `RETRY` | PASS |
| `TopStrip.tsx` contains `data-testid="error-banner"` | PASS |
| `TopStrip.tsx` contains `setProvenanceOpen(true)` | PASS |
| `TopStrip.tsx` contains `ⓘ` | PASS |
| `TopStrip.tsx` speed array is `[0.5, 1, 2, 4]` (no `8×`) | PASS |
| `Scrubber.tsx` contains `#3a98b4`, `#2a7a93`, `#1d6278` | PASS |
| `Scrubber.tsx` filters `lap_number > 1 && stint_age === 0` | PASS |
| `Scrubber.tsx` renders `data-testid="pit-marker"` | PASS |

## Self-Check: PASSED

- `frontend/src/stores/useUIStore.ts` — FOUND
- `frontend/src/stores/useUIStore.test.ts` — FOUND
- `frontend/src/stores/useSimulationStore.ts` — FOUND
- `frontend/src/lib/sse.ts` — FOUND
- `frontend/src/components/TopStrip/TopStrip.tsx` — FOUND
- `frontend/src/components/TopStrip/Scrubber.tsx` — FOUND
- `frontend/src/components/TopStrip/Scrubber.test.tsx` — FOUND
- Commits 8436181, 4b1d6b3, 43f31ac — FOUND in git log
