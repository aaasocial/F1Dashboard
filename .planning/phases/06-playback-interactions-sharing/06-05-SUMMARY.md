---
phase: 06-playback-interactions-sharing
plan: "05"
subsystem: frontend-hash-sync-drag-upload
tags: [url-hash, drag-upload, xhr, progress, drop-overlay, wave-2]
dependency_graph:
  requires:
    - extended-ui-store-phase6   # 06-02: seek, pos, showToast
    - extended-sim-store-phase6  # 06-02: setSessionId, setLastRunParams
    - drag-upload-hook-scaffold  # 06-01: useDragUpload scaffold + MSW upload handler
  provides:
    - url-hash-lap-sync          # INT-04: lap parameter in hash, round-trip on reload
    - drag-upload-full           # INT-05: full drag-and-drop zip upload with progress
    - drop-overlay-component     # DropOverlay UI component
  affects:
    - frontend/src/lib/useHashSync.ts (lap parameter added)
    - frontend/src/hooks/useDragUpload.ts (scaffold replaced with full implementation)
    - frontend/src/components/shared/DropOverlay.tsx (new component)
    - frontend/src/App.tsx (useDragUpload mounted, DropOverlay rendered)
tech_stack:
  added: []
  patterns:
    - "Integer-lap throttle: useRef(lastIntegerLap) prevents redundant hash writes when pos fractional part changes"
    - "dragCounter pattern: increment on dragenter, decrement on dragleave, show overlay when > 0 — prevents flicker on child element traversal"
    - "XHR for upload progress: fetch has no upload progress events; XMLHttpRequest.upload.progress provides 0..1 progress"
    - "Defense-in-depth ZIP validation: check both .zip extension (case-insensitive) AND MIME type (empty OR application/zip OR application/x-zip-compressed)"
    - "Auto-simulate after upload: after setSessionId, check selectedRaceId/driverCode/stintIndex and auto-fire runSimulationStream if complete"
    - "waitFor in test: React hook state after async rejection needs waitFor to flush state before assertion"
key_files:
  created:
    - frontend/src/lib/useHashSync.test.ts
    - frontend/src/components/shared/DropOverlay.tsx
  modified:
    - frontend/src/lib/useHashSync.ts
    - frontend/src/hooks/useDragUpload.ts
    - frontend/src/hooks/useDragUpload.test.ts
    - frontend/src/App.tsx
decisions:
  - "lap parameter stored as Math.floor(pos) integer — float precision not needed, integer lap is the unit of navigation"
  - "useRef(lastIntegerLap) used for hash write throttle — avoids writing on every RAF tick when pos changes fractionally within same lap"
  - "DropOverlay uses pointerEvents:none so underlying document.body drag events still fire through the overlay"
  - "waitFor() used in non-zip rejection test to wait for React state flush after async rejection"
  - "unused 'vi' import removed from useDragUpload.test.ts to satisfy TypeScript TS6133 noUnusedLocals"
metrics:
  duration: "~5 minutes"
  completed: "2026-04-25"
  tasks_completed: 3
  files_created: 2
  files_modified: 4
---

# Phase 6 Plan 05: URL Hash Lap Sync + Drag-and-Drop Upload Summary

Hash sync extended to encode lap with integer-boundary throttle (INT-04); useDragUpload fully implemented with dragCounter flicker prevention, XHR progress, and auto-simulate on success; DropOverlay wired into App.tsx (INT-05).

## What Was Built

### Task 1: useHashSync Lap Extension (INT-04)

**`frontend/src/lib/useHashSync.ts`**
- Added `pos` (from `useUIStore`) and `seek` subscriptions
- Mount effect reads `params.get('lap')` → calls `seek(lap)` if lap >= 1, stores in `lastIntegerLap.current`
- New `useEffect([pos, ...])`: computes `intLap = Math.max(1, Math.floor(pos))`, skips write if equal to `lastIntegerLap.current` (throttle), writes `lap=<n>` to hash only when selection is complete
- Selection write effect preserved: uses `URLSearchParams` on existing hash to preserve any existing `lap` parameter across race/driver/stint changes
- Hash format: `#race=2024_bahrain&driver=LEC&stint=0&lap=7`

**`frontend/src/lib/useHashSync.test.ts`** (new)
- 4 tests: full mount restore (race+driver+stint+lap), no-seek when lap missing, boundary crossing writes lap (1→5, 5→6), no hash write when selection incomplete

### Task 2: Full useDragUpload + DropOverlay (INT-05)

**`frontend/src/hooks/useDragUpload.ts`** (replaced Plan 01 scaffold)
- `isZipFile(file)`: validates `.zip` extension (case-insensitive) AND MIME type (empty or `application/zip` or `application/x-zip-compressed`) — T-6-ZIP defense-in-depth
- `uploadFile`: XHR to `/api/sessions/upload`, `xhr.upload.progress` events update `progress` state (0..1), rejects with toast on non-zip or HTTP error
- `handleSuccess(sessionId)`: `setSessionId`, `showToast('UPLOAD OK — SESSION …')`, auto-fires `runSimulationStream` if `selectedRaceId + selectedDriverCode + selectedStintIndex` are all present
- `useEffect`: registers `dragenter`/`dragleave`/`dragover`/`drop` on `document.body`; dragCounter pattern prevents flicker; `drop` calls `uploadFile` then `handleSuccess`; cleanup removes all listeners on unmount

**`frontend/src/hooks/useDragUpload.test.ts`** (replaced Plan 01 smoke test)
- 6 tests: initial state, dragenter→active, dragenter+dragleave→inactive, two enters+one leave→still active (counter pattern), non-zip rejection + toast, zip accepted + session_id from MSW mock

**`frontend/src/components/shared/DropOverlay.tsx`** (new)
- Returns `null` when `!active && !uploading`
- `position: fixed; inset: 0; z-index: 120; pointerEvents: none`
- `background: rgba(5,7,11,0.85); backdropFilter: blur(4px)` backdrop
- Inner panel: `border: 2px dashed var(--accent)`, no border-radius (CLAUDE.md rule)
- Text: `DROP FASTF1 CACHE ZIP HERE` or `UPLOADING…` (accent color, monospace, letter-spacing: 3)
- Progress bar: `data-testid="upload-progress"`, width `${Math.round(progress * 100)}%` with 80ms transition
- Error display: rendered as JSX text node (not dangerouslySetInnerHTML) — T-6-DROP-XSS mitigated

### Task 3: App.tsx Integration

**`frontend/src/App.tsx`**
- Added imports: `useDragUpload`, `DropOverlay`
- Calls `useDragUpload()` in App body, destructures `{ dragActive, uploading, progress, error: uploadError }`
- Renders `<DropOverlay active={dragActive} uploading={uploading} progress={progress} error={uploadError} />` as last sibling inside the fragment (after Toast/ShortcutsModal/MapFullscreenOverlay)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] React hook state not flushed after async rejection in test**
- **Found during:** Task 2 — first green-phase test run
- **Issue:** `result.current.error` was `null` after `await expect(...).rejects.toThrow()` because React batches state updates; reading `result.current` after an await without `waitFor` reads stale state
- **Fix:** Wrapped `expect(result.current.error).toBeTruthy()` in `waitFor(() => {...})` to wait for the React re-render cycle
- **Files modified:** `frontend/src/hooks/useDragUpload.test.ts`
- **Commit:** 0708aa8

**2. [Rule 1 - Bug] Unused `vi` import causing TypeScript TS6133 error**
- **Found during:** Task 3 — `tsc -b --noEmit` after App.tsx edits
- **Issue:** `vi` was imported from vitest in useDragUpload.test.ts but never used; TypeScript strict `noUnusedLocals` rejects this
- **Fix:** Removed `vi` from the import destructure
- **Files modified:** `frontend/src/hooks/useDragUpload.test.ts`
- **Commit:** 7181b8c

## Threat Surface Coverage

All T-6-* threat items from the plan's threat model are addressed:

| Threat | Status |
|--------|--------|
| T-6-ZIP: non-zip file upload | Mitigated — `isZipFile()` checks extension + MIME; rejects with toast before XHR |
| T-6-XHR: XHR target injection | Mitigated — target built from `${VITE_API_URL ?? ''}/api/sessions/upload` (build-time env var) |
| T-6-HASH-INJECT: hash param injection | Mitigated — `parseInt(..., 10)` + `isNaN` guard; strings flow through Pydantic-validated API |
| T-6-DROP-XSS: error string rendering | Mitigated — `{error.toUpperCase()}` JSX text interpolation, React escapes all interpolated text |
| T-6-AUTOSIM: auto-simulate after upload | Accepted — uses already-selected params, same threat model as RUN MODEL button |

## Known Stubs

None — all plan goals achieved. The drag-upload stub from Plan 01 is fully replaced.

The following Plan 01 stub is now resolved:
- `frontend/src/hooks/useDragUpload.ts` (lines 63-68) — document.body drag event listeners now wired

## Verification Results

| Check | Result |
|-------|--------|
| `tsc -b --noEmit` | Exit 0 (clean) |
| `npm test` (vitest) | 124 passed, 4 todo, 1 file skipped (sse.test.ts) |
| `useHashSync` tests | 4/4 passing |
| `useDragUpload` tests | 6/6 passing |
| `useHashSync.ts` reads `params.get('lap')` | PASS |
| `useHashSync.ts` calls `seek(lap)` on mount | PASS |
| `useHashSync.ts` uses `useRef` for `lastIntegerLap` | PASS |
| `useDragUpload.ts` registers all 4 document.body listeners | PASS |
| `useDragUpload.ts` uses `dragCounter.current` | PASS |
| `useDragUpload.ts` calls `setSessionId` on success | PASS |
| `useDragUpload.ts` calls `runSimulationStream` on success | PASS |
| `DropOverlay.tsx` returns null when inactive | PASS |
| `DropOverlay.tsx` contains `DROP FASTF1 CACHE ZIP HERE` | PASS |
| `App.tsx` imports `useDragUpload` and `DropOverlay` | PASS |
| `App.tsx` renders `<DropOverlay active={dragActive}...>` | PASS |

## Self-Check: PASSED

- `frontend/src/lib/useHashSync.ts` — FOUND
- `frontend/src/lib/useHashSync.test.ts` — FOUND
- `frontend/src/hooks/useDragUpload.ts` — FOUND
- `frontend/src/hooks/useDragUpload.test.ts` — FOUND
- `frontend/src/components/shared/DropOverlay.tsx` — FOUND
- `frontend/src/App.tsx` (modified) — FOUND
- Commits 2283122, 0708aa8, 7181b8c — FOUND in git log
