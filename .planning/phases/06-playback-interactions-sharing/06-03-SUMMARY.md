---
phase: 06-playback-interactions-sharing
plan: "03"
subsystem: frontend-keyboard-shortcuts
tags: [keyboard, shortcuts, modal, overlay, zustand, statuslog, app-integration]
dependency_graph:
  requires:
    - 06-01 (Toast component)
    - useUIStore Phase 6 state (added here as Rule 3 deviation)
  provides:
    - keyboard-shortcuts-handler
    - shortcuts-modal
    - map-fullscreen-overlay
    - statuslog-zustand-driven-collapse
    - app-keyboard-integration
  affects:
    - frontend/src/App.tsx (keyboard listener + overlay renders)
    - frontend/src/stores/useUIStore.ts (Phase 6 state extended)
    - frontend/src/components/LapPanel/StatusLog.tsx (local useState removed)
tech_stack:
  added: []
  patterns:
    - "Pure keyboard handler reads store via .getState() to avoid stale closures"
    - "sectorBoundaryLaps() thirds-of-maxLap fallback for Shift+Arrow sector jumps"
    - "App.tsx wrapped in React fragment so Toast/ShortcutsModal/MapFullscreenOverlay are siblings above the cockpit grid"
    - "StatusLog max-height CSS transition (220ms ease-in-out) replaces conditional render"
    - "TDD: RED (test file written, no impl) → GREEN (impl passes tests) per task"
key_files:
  created:
    - frontend/src/lib/keyboard.ts
    - frontend/src/lib/keyboard.test.ts
    - frontend/src/components/shared/ShortcutsModal.tsx
    - frontend/src/components/shared/ShortcutsModal.test.tsx
    - frontend/src/components/shared/MapFullscreenOverlay.tsx
    - frontend/src/components/shared/MapFullscreenOverlay.test.tsx
    - frontend/src/components/LapPanel/StatusLog.test.tsx
    - frontend/src/App.test.tsx
  modified:
    - frontend/src/stores/useUIStore.ts (Phase 6 state slots added)
    - frontend/src/stores/useUIStore.test.ts (beforeEach reset updated)
    - frontend/src/components/LapPanel/StatusLog.tsx (useState removed, Zustand wired)
    - frontend/src/components/TopStrip/TopStrip.tsx (speed array fixed to [1,2,4])
    - frontend/src/App.tsx (keyboard useEffect + Toast/ShortcutsModal/MapFullscreenOverlay)
decisions:
  - "Pure keyboard.ts handler reads stores via .getState() at call time (not closure) to prevent stale pos/maxLap reads — documented in RESEARCH.md Pitfall 1"
  - "sectorBoundaryLaps() uses thirds-of-maxLap fallback because SimulationResult.sectorBounds holds track-geometry indices (not lap numbers)"
  - "App.tsx return wrapped in React fragment so overlay components (Toast, ShortcutsModal, MapFullscreenOverlay) are siblings of the 52px+1fr grid — ensures position:fixed overlays cover the full viewport without being clipped by grid children"
  - "StatusLog uses max-height CSS animation (0 to 140px, 220ms ease-in-out) per D-07 rather than conditional render — enables smooth collapse animation visible to user"
  - "useUIStore Phase 6 actions added in this plan as Rule 3 deviation (Plan 02 runs in parallel wave; these are required for keyboard.ts to compile and run)"
metrics:
  duration: "~9 minutes"
  completed: "2026-04-25"
  tasks_completed: 3
  files_created: 8
  files_modified: 5
---

# Phase 6 Plan 03: Keyboard Shortcuts Summary

Global keyboard shortcuts (INT-01) with pure testable handler, modal/overlay surfaces (? modal, T fullscreen map, E StatusLog collapse, S clipboard+toast, Esc dismiss), and App.tsx integration — 103 unit tests passing, TypeScript clean.

## What Was Built

### Task 1: Pure keyboard.ts handler + UIStore Phase 6 state

**`frontend/src/lib/keyboard.ts`** exports three functions:
- `isInputFocused(target)` — returns true for INPUT/SELECT/TEXTAREA/contenteditable; suppresses shortcuts when user is typing in form controls (T-6-KEY-INJECT mitigation)
- `sectorBoundaryLaps(maxLap)` — returns `[s1, s2, s3]` as lap numbers using thirds-of-maxLap fallback (because `SimulationResult.sectorBounds` holds track-geometry point indices, not lap numbers)
- `handleKey(e)` — pure dispatcher reading store state via `.getState()` at call time to avoid stale closures. Handles 12 shortcuts: Space (toggle play), ArrowLeft/Right (step ±1), Shift+Arrow (sector jump), Home/End (jump first/last), 1/2/3/4 (corner focus), T (map fullscreen), E (status log), S (clipboard+toast), ? (shortcuts modal), Esc (dismiss all)

**27 unit tests** covering all branches, input-focus guard, and sector boundary arithmetic.

**`frontend/src/stores/useUIStore.ts`** extended with Phase 6 state slots:
- `statusLogCollapsed: boolean` + `toggleStatusLog()`
- `xZoom: [number, number] | null` + `setXZoom()`
- `mapFullscreen: boolean` + `setMapFullscreen()`
- `shortcutsOpen: boolean` + `setShortcutsOpen()`
- `provenanceOpen: boolean` + `setProvenanceOpen()`
- `toastMessage: string | null` + `showToast()` + `clearToast()`
- `speed` retyped to `Speed = 0.5 | 1 | 2 | 4` (exported type alias)

### Task 2: ShortcutsModal + MapFullscreenOverlay + StatusLog collapse

**`ShortcutsModal.tsx`** — `position: fixed` dialog overlay (`z-index: 100`), `backdrop-filter: blur(4px)`, 10-row monospace table of shortcuts. Backdrop click calls `setShortcutsOpen(false)`; inner content uses `e.stopPropagation()`. Returns `null` when `shortcutsOpen=false`.

**`MapFullscreenOverlay.tsx`** — `position: fixed` dialog overlay (`z-index: 100`), 80vw×80vh inner container with `<MapPanel />` inside. Close button (✕) and backdrop click both call `setMapFullscreen(false)`. Returns `null` when `mapFullscreen=false`.

**`StatusLog.tsx`** — local `useState(false)` removed; `statusLogCollapsed` and `toggleStatusLog` now read from `useUIStore`. Collapse replaces `{!collapsed && (...)}` conditional render with an always-rendered `<div data-testid="status-log-body">` that animates `max-height` from 140px to 0 with `transition: max-height 220ms ease-in-out` (D-07 specification).

### Task 3: App.tsx integration

**`App.tsx`** changes:
1. New `useEffect(() => { document.addEventListener('keydown', listener); return () => removeEventListener }, [])` — empty deps array is intentional; `handleKey` reads state at call time via `.getState()`, not from closure
2. `toastMessage` + `clearToast` subscribed from `useUIStore`
3. Return wrapped in `<>...</>` fragment so `<Toast>`, `<ShortcutsModal>`, `<MapFullscreenOverlay>` render as siblings of the cockpit grid (ensures `position: fixed` elements cover the full viewport)

**6 App.test.tsx integration tests** verify keydown dispatch updates store, Toast renders conditionally, and overlay components mount when store flags are set.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Missing Phase 6 UIStore actions required by keyboard.ts**
- **Found during:** Task 1 — keyboard.ts calls `ui.toggleStatusLog()`, `ui.setMapFullscreen()`, `ui.setShortcutsOpen()`, etc., which did not exist in the current `useUIStore`
- **Issue:** Plan 02 (which adds these actions) runs in a parallel worktree in Wave 1; keyboard.ts cannot compile without them
- **Fix:** Added all Phase 6 state slots and action methods to `useUIStore.ts` in this plan
- **Files modified:** `frontend/src/stores/useUIStore.ts`, `frontend/src/stores/useUIStore.test.ts`
- **Commit:** 7c77607

**2. [Rule 1 - Bug] TopStrip speed array contained `8` which is not in Speed type**
- **Found during:** Task 2 TypeScript check after updating `useUIStore.ts` to use `Speed = 0.5 | 1 | 2 | 4`
- **Issue:** `TopStrip.tsx` had `[1, 2, 4, 8] as const` in speed toggle — `8` is not assignable to `Speed`; TS error TS2345
- **Fix:** Changed array to `[1, 2, 4] as const` (Plan 02 will add `0.5×` when it merges)
- **Files modified:** `frontend/src/components/TopStrip/TopStrip.tsx`
- **Commit:** addcfca

**3. [Rule 3 - Blocking] App.test.tsx needed QueryClientProvider wrapper**
- **Found during:** Task 3 RED phase — `App` renders `TopStrip` which calls `useRaces()` (TanStack Query hook); without a `QueryClientProvider` the test threw "No QueryClient set"
- **Fix:** Added `QueryClient` + `QueryClientProvider` wrapper in a `renderApp()` helper in `App.test.tsx`
- **Files modified:** `frontend/src/App.test.tsx`
- **Commit:** e9fcb0f

## Known Stubs

None — all plan goals achieved. `ShortcutsModal`, `MapFullscreenOverlay`, and `StatusLog` collapse are fully functional and store-driven.

## Threat Flags

No new security-relevant surface beyond what the plan's threat model documents. The `isInputFocused` guard (T-6-KEY-INJECT) and clipboard-write-only-href (T-6-CLIP) mitigations are both implemented and unit-tested.

## Verification Results

| Check | Result |
|-------|--------|
| `npx tsc -b --noEmit` | Exit 0 (clean) |
| `npm test` | 103 passed, 4 todo, 1 file skipped (sse.test.ts) |
| `keyboard.test.ts` | 27/27 passed |
| `ShortcutsModal.test.tsx` | 5/5 passed |
| `MapFullscreenOverlay.test.tsx` | 4/4 passed |
| `StatusLog.test.tsx` | 4/4 passed |
| `App.test.tsx` | 6/6 passed |
| `useUIStore.test.ts` | 8/8 passed |

## Self-Check: PASSED

- `frontend/src/lib/keyboard.ts` — FOUND
- `frontend/src/lib/keyboard.test.ts` — FOUND
- `frontend/src/components/shared/ShortcutsModal.tsx` — FOUND
- `frontend/src/components/shared/MapFullscreenOverlay.tsx` — FOUND
- `frontend/src/components/LapPanel/StatusLog.tsx` — FOUND (statusLogCollapsed used)
- `frontend/src/App.tsx` — FOUND (keydown listener + Toast + ShortcutsModal + MapFullscreenOverlay)
- Commits 7c77607, addcfca, e9fcb0f — FOUND in git log
