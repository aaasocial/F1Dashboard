---
phase: 06-playback-interactions-sharing
plan: "01"
subsystem: frontend-test-infrastructure
tags: [playwright, e2e, export, drag-upload, toast, msw, wave-0]
dependency_graph:
  requires: []
  provides:
    - playwright-e2e-infrastructure
    - export-pure-functions
    - drag-upload-hook-scaffold
    - toast-component
    - msw-upload-handler
  affects:
    - frontend/tests/ (all Phase 6 E2E specs build on these stubs)
    - frontend/src/lib/export.ts (downstream plans wire into PhysicsPanel)
    - frontend/src/hooks/useDragUpload.ts (Plan 05 adds drag event listeners)
tech_stack:
  added:
    - "@playwright/test@1.59.1 — E2E test framework"
    - "@testing-library/react@16.3.2 — React hook testing"
    - "Chromium binary (playwright install chromium)"
  patterns:
    - "Vitest include: src/**/*.{test,spec}.{ts,tsx} — excludes tests/ Playwright dir"
    - "MSW handler pattern: http.post + async delay + HttpResponse.json"
    - "Export pure functions: buildCsv (unit-testable) + exportCsv (browser-side effect)"
key_files:
  created:
    - frontend/playwright.config.ts
    - frontend/tests/keyboard.spec.ts
    - frontend/tests/export.spec.ts
    - frontend/tests/tire-copy.spec.ts
    - frontend/tests/hash.spec.ts
    - frontend/tests/upload.spec.ts
    - frontend/src/lib/export.ts
    - frontend/src/lib/export.test.ts
    - frontend/src/hooks/useDragUpload.ts
    - frontend/src/hooks/useDragUpload.test.ts
    - frontend/src/components/shared/Toast.tsx
    - .gitignore
  modified:
    - frontend/package.json (added @playwright/test, @testing-library/react, test:e2e script)
    - frontend/package-lock.json
    - frontend/src/mocks/handlers.ts (added POST /api/sessions/upload handler)
    - frontend/vitest.config.ts (added include/exclude to isolate Vitest from Playwright specs)
decisions:
  - "Split export into buildCsv (pure, unit-testable) + exportCsv (browser side-effect) for testability"
  - "Added vitest include: src/**/*.{test,spec}.{ts,tsx} to prevent Vitest from picking up Playwright specs in tests/ — blocking fix (Rule 3)"
  - "setDragActive referenced in placeholder useEffect to satisfy TypeScript noUnusedLocals in scaffold"
  - "Root .gitignore created (none existed) with Playwright artifact exclusions"
metrics:
  duration: "~15 minutes"
  completed: "2026-04-25"
  tasks_completed: 2
  files_created: 12
  files_modified: 4
---

# Phase 6 Plan 01: Wave 0 Test Infrastructure Summary

Playwright E2E infrastructure + pure-function scaffolds for Phase 6 with 57 unit tests passing and 10 E2E stubs listed.

## What Was Built

### Task 1: Playwright Install + Config
- Installed `@playwright/test@1.59.1` and Chromium browser binary (Windows, no `--with-deps`)
- Created `frontend/playwright.config.ts` with `baseURL: http://localhost:5173`, `testDir: ./tests`, `webServer` auto-start via `npm run dev`, single Chromium project, `workers: 1`
- Added `test:e2e` script to `frontend/package.json`
- Created root `.gitignore` with `frontend/playwright-report/`, `frontend/test-results/`, `frontend/playwright/.cache/` exclusions

### Task 2: E2E Spec Stubs + Pure Function Scaffolds
- **5 Playwright E2E spec stubs** in `frontend/tests/` — all use `test.skip()` placeholders, each referencing its INT requirement:
  - `keyboard.spec.ts` (INT-01): Space, ArrowRight, Esc
  - `export.spec.ts` (INT-02): context menu, CSV download
  - `tire-copy.spec.ts` (INT-03): CarWheel clipboard copy
  - `hash.spec.ts` (INT-04): URL hash encode/reload
  - `upload.spec.ts` (INT-05): ZIP drop, non-ZIP error
- **`frontend/src/lib/export.ts`**: `TOKEN_MAP` (16 design tokens + `--mono`), `substituteTokens`, `triggerDownload`, `buildCsv`, `exportCsv`, `exportSvg`, `exportPng`
- **`frontend/src/lib/export.test.ts`**: 6 passing tests covering header format, row count, CI value formatting, token substitution, TOKEN_MAP completeness
- **`frontend/src/hooks/useDragUpload.ts`**: Scaffold with full state shape (`dragActive`, `progress`, `uploading`, `error`, `uploadFile`), XHR-based upload with `.zip` extension guard (T-6-ZIP mitigation)
- **`frontend/src/hooks/useDragUpload.test.ts`**: Smoke test verifying initial state shape
- **`frontend/src/components/shared/Toast.tsx`**: Auto-dismiss toast with `data-testid="toast"`, `role="status"`, design-token styling, no rounded corners
- **`frontend/src/mocks/handlers.ts`**: Added `POST /api/sessions/upload` returning `{ session_id: 'test-session-abc123' }` with 80ms simulated delay

## Downstream Plan Stubs

| Spec File | Requirement | Implemented By |
|-----------|-------------|----------------|
| `keyboard.spec.ts` | INT-01 | Plan 06-02 (keyboard shortcuts) |
| `export.spec.ts` | INT-02 | Plan 06-04 (chart export context menu) |
| `tire-copy.spec.ts` | INT-03 | Plan 06-03 (clipboard copy) |
| `hash.spec.ts` | INT-04 | Plan 06-02 (URL hash E2E) |
| `upload.spec.ts` | INT-05 | Plan 06-05 (drag-and-drop upload) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Vitest picked up Playwright specs in tests/**
- **Found during:** Task 2 — first `npm test` run after creating spec stubs
- **Issue:** Vitest has no `include` filter by default; it globbed `tests/*.spec.ts` and tried to run Playwright's `test.describe()` in a Vitest context, causing "Playwright Test did not expect test.describe() to be called here" errors
- **Fix:** Added `include: ['src/**/*.{test,spec}.{ts,tsx}']` and `exclude: ['tests/**', 'node_modules/**']` to `frontend/vitest.config.ts`
- **Files modified:** `frontend/vitest.config.ts`
- **Commit:** 1bfc830

**2. [Rule 1 - Bug] TypeScript TS6133 unused variable `setDragActive`**
- **Found during:** Task 2 — `tsc -b --noEmit` after creating useDragUpload scaffold
- **Issue:** Scaffold declares `setDragActive` state but Plan 05 wires the drag event listeners; TypeScript strict mode rejects unused locals
- **Fix:** Added `void setDragActive` reference alongside existing `void dragCounter` in the placeholder `useEffect`
- **Files modified:** `frontend/src/hooks/useDragUpload.ts`
- **Commit:** 1bfc830

## Known Stubs

| File | Description | Resolved By |
|------|-------------|-------------|
| `frontend/src/hooks/useDragUpload.ts` (lines 63-68) | `useEffect` is a placeholder — document.body drag event listeners not yet wired | Plan 06-05 |
| `frontend/tests/keyboard.spec.ts` | All 3 tests are `test.skip()` | Plan 06-02 |
| `frontend/tests/export.spec.ts` | Both tests are `test.skip()` | Plan 06-04 |
| `frontend/tests/tire-copy.spec.ts` | 1 test is `test.skip()` | Plan 06-03 |
| `frontend/tests/hash.spec.ts` | Both tests are `test.skip()` | Plan 06-02 |
| `frontend/tests/upload.spec.ts` | Both tests are `test.skip()` | Plan 06-05 |

These stubs are intentional — they exist solely to establish Playwright infrastructure and requirement traceability. No plan goal is blocked by them.

## Verification Results

| Check | Result |
|-------|--------|
| `npx playwright --version` | Version 1.59.1 |
| `npx playwright test --list` | 10 tests in 5 files |
| `npm test` | 57 passed, 4 todo, 1 file skipped (sse.test.ts) |
| `tsc -b --noEmit` | Exit 0 (clean) |
| `export.ts` TOKEN_MAP keys | 16 (all design tokens + --mono) |
| `useDragUpload` smoke test | Pass |
| MSW `/api/sessions/upload` | Present, returns `test-session-abc123` |

## Self-Check: PASSED

- `frontend/playwright.config.ts` — FOUND
- `frontend/tests/keyboard.spec.ts` — FOUND
- `frontend/tests/export.spec.ts` — FOUND
- `frontend/tests/tire-copy.spec.ts` — FOUND
- `frontend/tests/hash.spec.ts` — FOUND
- `frontend/tests/upload.spec.ts` — FOUND
- `frontend/src/lib/export.ts` — FOUND
- `frontend/src/lib/export.test.ts` — FOUND
- `frontend/src/hooks/useDragUpload.ts` — FOUND
- `frontend/src/hooks/useDragUpload.test.ts` — FOUND
- `frontend/src/components/shared/Toast.tsx` — FOUND
- Commits f352f4f, 1bfc830 — FOUND in git log
