---
phase: 06-playback-interactions-sharing
fixed_at: 2026-04-25T00:00:00Z
review_path: .planning/phases/06-playback-interactions-sharing/06-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 06: Code Review Fix Report

**Fixed at:** 2026-04-25
**Source review:** .planning/phases/06-playback-interactions-sharing/06-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4
- Fixed: 4
- Skipped: 0

## Fixed Issues

### WR-01: `playing: true` initial state starts animation loop before simulation data exists

**Files modified:** `frontend/src/stores/useUIStore.ts`
**Commit:** b5a1be4
**Applied fix:** Changed `playing: true` to `playing: false` at line 45 of `useUIStore.ts`. The animation RAF loop in `App.tsx` no longer fires on mount before simulation data is loaded; the user must explicitly press Play or Space to start playback.

---

### WR-02: `as T ??` pattern does not coerce — `as` assertion is purely compile-time

**Files modified:** `frontend/src/lib/sse.ts`
**Commit:** 7aba5ad
**Applied fix:** Replaced all `as number ?? fallback` patterns with `Number(... ?? fallback)` for all seven numeric metadata fields extracted from the untyped backend payload: `round`, `season`, `driver_number`, `stint_index`, `start_lap`, `end_lap`, `start_age` (lines 29–47), and `lap_count` (line 111). String values sent by the backend (e.g., `"2024"`) are now correctly coerced to numbers at runtime rather than passing through as strings.

---

### WR-03: Clearing race picker writes stale `stint=0` to URL hash

**Files modified:** `frontend/src/components/TopStrip/TopStrip.tsx`
**Commit:** 5e60b67
**Applied fix:** Replaced `useSimulationStore.getState().setSelection(raceId ?? '', '', 0)` in `onRaceChange` with a direct `useSimulationStore.setState({ selectedRaceId, selectedDriverCode: null, selectedStintIndex: null })` call. Setting `selectedStintIndex` to `null` (not `0`) ensures the `!= null` guard in `useHashSync` correctly suppresses hash writes when no race is selected.

---

### WR-04: Scrubber drag missing `setPointerCapture` — pointer events may be lost on fast moves

**Files modified:** `frontend/src/components/TopStrip/Scrubber.tsx`
**Commit:** 584268f
**Applied fix:** Added `(e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId)` to the `onPointerDown` handler on the scrubber `<div>`. This ensures the element retains pointer ownership for the duration of the drag even if the pointer moves off the element quickly, consistent with the pattern already used in `PhysicsChart.tsx`.

---

_Fixed: 2026-04-25_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
