---
phase: 6
slug: playback-interactions-sharing
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-25
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest 2.1.9 (unit) + Playwright 1.59.1 (E2E — Wave 0 gap) |
| **Config file** | `frontend/vitest.config.ts` (exists); `frontend/playwright.config.ts` (Wave 0 gap) |
| **Quick run command** | `cd frontend && npm test` |
| **Full suite command** | `cd frontend && npm test && npx playwright test` |
| **Estimated runtime** | ~10s (unit) + ~60s (E2E) |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npm test`
- **After every plan wave:** Run `cd frontend && npm test && npx playwright test`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds (unit), 70 seconds (full)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 6-01-01 | 01 | 1 | PLAY-01 | — | N/A | unit | `cd frontend && npm test -- useUIStore` | Partial | ⬜ pending |
| 6-01-02 | 01 | 1 | PLAY-01 | — | seek clamps to [1, maxLap] | unit | `cd frontend && npm test -- useUIStore` | Partial | ⬜ pending |
| 6-01-03 | 01 | 1 | PLAY-02 | — | RAF loop uses 0.5× speed correctly | unit | `cd frontend && npm test -- App` | No — Wave 0 | ⬜ pending |
| 6-02-01 | 02 | 1 | INT-01 | — | Space key toggles playing | E2E | `npx playwright test keyboard` | No — Wave 0 | ⬜ pending |
| 6-02-02 | 02 | 1 | INT-01 | — | Arrow keys step lap | E2E | `npx playwright test keyboard` | No — Wave 0 | ⬜ pending |
| 6-02-03 | 02 | 1 | INT-01 | — | Esc closes modal | E2E | `npx playwright test keyboard` | No — Wave 0 | ⬜ pending |
| 6-03-01 | 03 | 2 | INT-02 | T-6-SVG | SVG generated from numeric data only (no user strings) | E2E | `npx playwright test export` | No — Wave 0 | ⬜ pending |
| 6-03-02 | 03 | 2 | INT-02 | — | Export CSV has correct columns | unit | `cd frontend && npm test -- exportCsv` | No — Wave 0 | ⬜ pending |
| 6-03-03 | 03 | 2 | INT-03 | T-6-CLIP | Clipboard write is window.location.href only | E2E | `npx playwright test tire-copy` | No — Wave 0 | ⬜ pending |
| 6-04-01 | 04 | 2 | INT-04 | — | URL hash includes lap; reload restores view | E2E | `npx playwright test hash` | No — Wave 0 | ⬜ pending |
| 6-05-01 | 05 | 2 | INT-05 | T-6-ZIP | ZIP extension + MIME check before upload | unit | `cd frontend && npm test -- useDragUpload` | No — Wave 0 | ⬜ pending |
| 6-05-02 | 05 | 2 | INT-05 | — | XHR upload progress updates UI | unit | `cd frontend && npm test -- useDragUpload` | No — Wave 0 | ⬜ pending |
| 6-05-03 | 05 | 2 | INT-05 | — | Drop zip E2E flow | E2E | `npx playwright test upload` | No — Wave 0 | ⬜ pending |
| 6-06-01 | 06 | 3 | INT-06 | — | Provenance modal renders fastf1_version | unit | `cd frontend && npm test -- ProvenanceModal` | No — Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/playwright.config.ts` — Playwright config (baseURL, webServer, Chromium project)
- [ ] `frontend/tests/keyboard.spec.ts` — keyboard shortcut E2E stubs for INT-01
- [ ] `frontend/tests/export.spec.ts` — chart export E2E stubs for INT-02
- [ ] `frontend/tests/tire-copy.spec.ts` — tire clipboard copy E2E stub for INT-03
- [ ] `frontend/tests/hash.spec.ts` — URL hash round-trip E2E stub for INT-04
- [ ] `frontend/tests/upload.spec.ts` — drag-and-drop upload E2E stub for INT-05
- [ ] `frontend/src/lib/export.ts` — export utilities (unit-testable pure functions)
- [ ] `frontend/src/hooks/useDragUpload.ts` — upload hook (unit-testable)
- [ ] Install Playwright: `cd frontend && npx playwright install --with-deps chromium`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| No visible stutter during playback on mid-range laptop | PLAY-02 | Performance is subjective/hardware-dependent; no automated FPS assertion | Load Bahrain 2023 Leclerc stint, press Space, observe at 1× and 2× for 10 laps |
| SVG export renders correctly without page styles | INT-02 | Font rendering in downloaded SVG depends on OS font stack | Open exported SVG in browser, confirm JetBrains Mono renders and all colors are hex values |
| Drag overlay appears on any file drag (not just zip) | INT-05 | Browser drag APIs vary; requires real user gesture | Drag a `.txt` file onto the window, confirm overlay appears and error toast fires on drop |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s (unit) / 70s (full)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
