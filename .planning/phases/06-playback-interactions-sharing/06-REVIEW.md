---
phase: 06-playback-interactions-sharing
reviewed: 2026-04-25T00:00:00Z
depth: standard
files_reviewed: 43
files_reviewed_list:
  - .gitignore
  - frontend/package.json
  - frontend/playwright.config.ts
  - frontend/src/App.test.tsx
  - frontend/src/App.tsx
  - frontend/src/components/CarPanel/CarFooter.tsx
  - frontend/src/components/CarPanel/CarWheel.tsx
  - frontend/src/components/LapPanel/StatusLog.test.tsx
  - frontend/src/components/LapPanel/StatusLog.tsx
  - frontend/src/components/PhysicsPanel/ChartContextMenu.test.tsx
  - frontend/src/components/PhysicsPanel/ChartContextMenu.tsx
  - frontend/src/components/PhysicsPanel/PhysicsChart.tsx
  - frontend/src/components/PhysicsPanel/PhysicsPanel.tsx
  - frontend/src/components/TopStrip/Scrubber.test.tsx
  - frontend/src/components/TopStrip/Scrubber.tsx
  - frontend/src/components/TopStrip/TopStrip.tsx
  - frontend/src/components/shared/DropOverlay.tsx
  - frontend/src/components/shared/MapFullscreenOverlay.test.tsx
  - frontend/src/components/shared/MapFullscreenOverlay.tsx
  - frontend/src/components/shared/ProvenanceModal.test.tsx
  - frontend/src/components/shared/ProvenanceModal.tsx
  - frontend/src/components/shared/ShortcutsModal.test.tsx
  - frontend/src/components/shared/ShortcutsModal.tsx
  - frontend/src/components/shared/Toast.tsx
  - frontend/src/hooks/useDragUpload.test.ts
  - frontend/src/hooks/useDragUpload.ts
  - frontend/src/lib/export.test.ts
  - frontend/src/lib/export.ts
  - frontend/src/lib/keyboard.test.ts
  - frontend/src/lib/keyboard.ts
  - frontend/src/lib/sse.ts
  - frontend/src/lib/tireClipboard.test.ts
  - frontend/src/lib/tireClipboard.ts
  - frontend/src/lib/useHashSync.test.ts
  - frontend/src/lib/useHashSync.ts
  - frontend/src/mocks/handlers.ts
  - frontend/src/stores/useSimulationStore.ts
  - frontend/src/stores/useUIStore.test.ts
  - frontend/src/stores/useUIStore.ts
  - frontend/tests/export.spec.ts
  - frontend/tests/hash.spec.ts
  - frontend/tests/keyboard.spec.ts
  - frontend/tests/tire-copy.spec.ts
  - frontend/tests/upload.spec.ts
  - frontend/vitest.config.ts
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-04-25
**Depth:** standard
**Files Reviewed:** 43 (44 listed, vitest.config.ts counted once)
**Status:** issues_found

## Summary

Phase 6 delivers playback interactions (keyboard shortcuts, scrubber drag, speed control), sharing features (URL hash sync, URL copy, clipboard tire metrics), export (CSV/SVG/PNG via context menu), and new overlays (ShortcutsModal, MapFullscreenOverlay, ProvenanceModal, DropOverlay). Test coverage is solid — unit tests cover stores, pure functions, and components; E2E tests cover all five INT requirements.

The implementation is well-structured. No security vulnerabilities or data-loss bugs were found. There are four warnings (logic/correctness risks) and four info items (quality/maintainability).

The most impactful finding is the store's `playing: true` default, which starts the animation RAF loop immediately on mount before data is loaded. The remaining warnings concern a type-assertion pattern that silently bypasses fallback defaults, a stale hash write after clearing the race picker, and missing pointer capture on the scrubber.

---

## Warnings

### WR-01: `playing: true` initial state starts animation loop before simulation data exists

**File:** `frontend/src/stores/useUIStore.ts:45`
**Issue:** The Zustand store initializes `playing: true`. On App mount, the `useEffect` animation loop in `App.tsx` (lines 51-74) fires immediately and begins incrementing `pos`. At this point `maxLap` falls back to `22` (line 36: `s.data?.laps.length ?? 22`), so the scrubber advances through a phantom 22-lap range with no data loaded. This produces unnecessary `seek()` calls and could confuse URL hash writes (WR-03 is an indirect consequence). It also means every unit test that touches `useUIStore` must explicitly reset `playing` to `false` in `beforeEach` — the test files do this (`App.test.tsx:20`, `useUIStore.test.ts:8`, etc.) as a workaround, but test setup should not need to compensate for a wrong default.

**Fix:** Initialize `playing` to `false`. The user should explicitly press play or press Space to start playback:
```typescript
// useUIStore.ts line 45
playing: false,
```

---

### WR-02: `as T ??` pattern does not coerce — `as` assertion is purely compile-time

**File:** `frontend/src/lib/sse.ts:29-47, 111`
**Issue:** Lines like:
```typescript
round: (md as Record<string, unknown>)['round'] as number ?? 0,
```
In TypeScript, `as number` is a compile-time-only type assertion with no runtime effect. The `??` fallback correctly fires when the value is `null` or `undefined`. However, if the backend sends the field as a string (e.g., `"2024"` instead of `2024`), the `as number` cast does not coerce it — the field will silently be the string `"2024"` at runtime while TypeScript believes it is `number`. This is particularly relevant for `season`, `round`, and `driver_number`, which affect display formatting (e.g., `String(data?.meta.race.round ?? 0).padStart(2, '0')` in TopStrip will produce `"2024"` rather than the padded integer). The same issue appears at line 111 for `lap_count`.

**Fix:** Use explicit `Number(...)` coercion instead of type assertions for numeric fields sourced from an untyped backend payload:
```typescript
// sse.ts — metadata extraction
round:  Number((md as Record<string, unknown>)['round'] ?? 0),
season: Number((md as Record<string, unknown>)['season'] ?? 0),
// ...and similarly for driver_number, stint_index, start_lap, end_lap, start_age

// sse.ts line 111 — module_complete event
lap_count: Number(payload['lap_count'] ?? 0),
```

---

### WR-03: Clearing race picker writes stale `stint=0` to URL hash

**File:** `frontend/src/components/TopStrip/TopStrip.tsx:75` / `frontend/src/lib/useHashSync.ts:54`
**Issue:** When the user selects the blank "RACE…" option, `onRaceChange` calls:
```typescript
useSimulationStore.getState().setSelection('', '', 0)
```
This sets `selectedStintIndex` to `0` (not `null`). The `useHashSync` lap-writer effect (line 54) guards with `if (!selectedRaceId || !selectedDriverCode || selectedStintIndex != null)`. Since `0 != null` is `true`, the guard passes and the hash writer remains active even though the race has been deselected. On the next integer-lap boundary crossing, `useHashSync` will write `stint=0` to the hash with an empty race. This stale hash can then be read back on page reload, calling `setSelection('', '', 0)` which has no effect but leaves a misleading hash in the URL.

**Fix:** Reset `selectedStintIndex` to `null` when the race or driver is cleared, so the `!= null` guard in `useHashSync` correctly suppresses hash writes:
```typescript
// TopStrip.tsx onRaceChange
function onRaceChange(e: React.ChangeEvent<HTMLSelectElement>) {
  const raceId = e.target.value || null
  // Reset to null so hash sync guard fires correctly
  useSimulationStore.setState({
    selectedRaceId: raceId ?? null,
    selectedDriverCode: null,
    selectedStintIndex: null,
  })
}
```
Alternatively, add a `clearSelection` action to `useSimulationStore` that sets all three to `null`.

---

### WR-04: Scrubber drag missing `setPointerCapture` — pointer events may be lost on fast moves

**File:** `frontend/src/components/TopStrip/Scrubber.tsx:60`
**Issue:** The scrubber's `onPointerDown` handler (line 60) sets `dragging = true` and attaches `pointermove` / `pointerup` listeners to `window`. It does not call `e.currentTarget.setPointerCapture(e.pointerId)`. Without pointer capture, if the user moves the pointer very quickly off the scrubber element before the window listeners attach (particularly on low-end devices or under heavy load), the browser may route events to a different element and the `window` listeners will still fire — but touchscreen behavior can differ. By contrast, `PhysicsChart.tsx:102` correctly calls `(e.target as HTMLElement).setPointerCapture?.(e.pointerId)` for its drag. The inconsistency means the scrubber's drag is less robust on touch devices.

**Fix:** Add pointer capture in the `onPointerDown` handler:
```typescript
// Scrubber.tsx — update onPointerDown
onPointerDown={e => {
  setDragging(true)
  onPointer(e)
  ;(e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId)
}}
```
And add a corresponding `onPointerUp` React handler to release capture and clear `dragging`, replacing the imperative `window` listeners.

---

## Info

### IN-01: `ChartContextMenu` uses `React.CSSProperties` without importing `React`

**File:** `frontend/src/components/PhysicsPanel/ChartContextMenu.tsx:48`
**Issue:** The file imports `{ useEffect, useRef } from 'react'` (no default `React` import) but uses `React.CSSProperties` as a type annotation on line 48. With the automatic JSX transform (used in this project's Vite + React 19 setup), `React` is not in scope by default. TypeScript resolves `React.CSSProperties` correctly at compile time via the `@types/react` namespace, so there is no runtime crash — but this is an implicit global namespace access and will fail if strict module isolation is ever enforced (e.g., `isolatedModules: true` without `@types/react` in scope).

**Fix:**
```typescript
// ChartContextMenu.tsx — replace implicit React.CSSProperties
import { useEffect, useRef } from 'react'
import type { CSSProperties } from 'react'

// line 48:
const itemStyle: CSSProperties = {
```

---

### IN-02: `generateEvents` in `StatusLog` is not memoized — recomputes on every render

**File:** `frontend/src/components/LapPanel/StatusLog.tsx:51`
**Issue:** `generateEvents(laps)` is called unconditionally on every render of `StatusLog`. The function iterates over `laps.length × 4 corners` — at 22 laps this is 88 iterations, and it runs on every parent re-render that changes any UI state (hover, pos changes, etc.). While 88 iterations is not expensive, the `LapPanel` re-renders frequently during playback because `pos` changes on every animation frame.

**Fix:** Wrap with `useMemo` so it only recomputes when `laps` changes (which is only on new simulation load):
```typescript
import { useMemo } from 'react'

// inside StatusLog:
const events = useMemo(() => generateEvents(laps), [laps])
```

---

### IN-03: `seek` action clamps to minimum `1.0` but not to `maxLap`

**File:** `frontend/src/stores/useUIStore.ts:61`
**Issue:** The `seek` action clamps `pos` to a minimum of `1.0` but has no upper bound:
```typescript
seek: pos => set({ pos: Math.max(1.0, pos) }),
```
In `App.tsx` the animation loop manually clamps to `maxLap + 0.999` before calling `seek`, so in practice this is handled correctly for playback. However, callers like `keyboard.ts` also clamp before calling `seek` (e.g., `Math.min(maxLap, ...)`). The store-level clamp is asymmetric — a future caller that forgets to cap at `maxLap` would silently set `pos` above `maxLap`, causing the physics panel to show `revealedLaps.length === maxLap` (already fully revealed) and the scrubber fraction to exceed `1.0` (visually clipped by CSS but technically incorrect).

**Fix:** Add an upper-bound parameter or document the single-source upper-bound clearly. If `maxLap` is unavailable in the store (it belongs to simulation data), at minimum clamp to a generous sentinel and add a comment:
```typescript
// seek: clamps to [1.0, ∞). Callers are responsible for capping at maxLap.
// Upper bound is not enforced here because maxLap is owned by SimulationStore.
seek: pos => set({ pos: Math.max(1.0, pos) }),
```
Or pass `maxLap` through `seek(pos, maxLap?)` to enable full clamping.

---

### IN-04: `handleKey` 'S' — toast shown even when clipboard write is skipped

**File:** `frontend/src/lib/keyboard.ts:124-129`
**Issue:** The `'S'` handler (URL copy) calls `showToast('URL COPIED')` unconditionally, even if `navigator.clipboard` is unavailable (non-HTTPS contexts) or `writeText` is not a function:
```typescript
if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
  void navigator.clipboard.writeText(window.location.href)
}
ui.showToast('URL COPIED')
```
In non-secure contexts (HTTP localhost during dev, or if permissions are denied), the clipboard write is silently skipped but the toast still says "URL COPIED", misleading the user.

**Fix:** Show a distinct message when clipboard is unavailable, or at minimum show the URL itself:
```typescript
if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
  void navigator.clipboard.writeText(window.location.href)
  ui.showToast('URL COPIED')
} else {
  ui.showToast('URL: ' + window.location.href)
}
```
Note: in practice this only affects HTTP deployments; the app targets HTTPS production (Vercel) where `navigator.clipboard` is always available.

---

_Reviewed: 2026-04-25_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
