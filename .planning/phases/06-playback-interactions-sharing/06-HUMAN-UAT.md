---
status: partial
phase: 06-playback-interactions-sharing
source: [06-VERIFICATION.md]
started: 2026-04-25T09:24:00Z
updated: 2026-04-25T09:24:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Playwright E2E suite passes
expected: `cd frontend && npx playwright test` runs against Chromium — all 5 spec files (keyboard, export, tire-copy, hash, upload) with at least 9 total tests pass without failures
result: [pending]

### 2. Synchronized chart zoom/pan
expected: Mouse wheel on any PhysicsChart zooms the x-axis; all four corner charts zoom and pan together; RESET button appears and clicking it returns to full range
result: [pending]

### 3. URL hash lap round-trip on reload
expected: Navigate to a stint, scrub to lap 7 — URL hash updates to `#...&lap=7`; reload the page — lap position restores to 7 and the scrubber and lap counter show lap 7
result: [pending]

### 4. Drag-and-drop upload flow
expected: Drag a `.zip` file onto the browser window — blue dashed overlay appears with "DROP FASTF1 CACHE ZIP HERE"; release — progress bar animates during upload; on success the app loads the session and runs simulation automatically
result: [pending]

### 5. Chart context menu file download
expected: Right-click on a PhysicsPanel chart — native browser context menu is suppressed; three-item menu appears (Export PNG / Export SVG / Export CSV); clicking any item triggers a file download with the correct extension and valid content
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
