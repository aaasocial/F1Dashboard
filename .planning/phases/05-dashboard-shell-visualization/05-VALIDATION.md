---
phase: 5
slug: dashboard-shell-visualization
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-24
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest 2.1.9 |
| **Config file** | `frontend/vitest.config.ts` — Wave 0 gap |
| **Quick run command** | `npm run test --prefix frontend` |
| **Full suite command** | `npm run test:coverage --prefix frontend` |
| **Estimated runtime** | ~5 seconds (unit tests only) |

---

## Sampling Rate

- **After every task commit:** Run `npm run test --prefix frontend`
- **After every plan wave:** Run `npm run test:coverage --prefix frontend`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | DASH-04 | — | CSS tokens applied: --bg, --accent on body | unit/smoke | `npm run test --prefix frontend` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 1 | DASH-01 | — | Cascade picker: race → driver → stint sequential enabling | unit | `vitest run src/api/queries.test.ts` | ❌ W0 | ⬜ pending |
| 05-02-02 | 02 | 1 | DASH-03 | — | SSE progress: module events update store; simulation_complete populates data | unit | `vitest run src/lib/sse.test.ts` | ❌ W0 | ⬜ pending |
| 05-03-01 | 03 | 2 | VIZ-02, VIZ-06 | — | tempToViridis(60) returns blue; COMPOUND_COLORS.SOFT === '#FF3333' | unit | `vitest run src/lib/scales.test.ts` | ❌ W0 | ⬜ pending |
| 05-03-02 | 03 | 2 | VIZ-01 | — | normalizeTrackPoints maps GPS to [0,1]²; path closes | unit | `vitest run src/lib/track.test.ts` | ❌ W0 | ⬜ pending |
| 05-04-01 | 04 | 2 | VIZ-05 | — | useUIStore.setHoveredLap triggers re-render in subscribed components | unit | `vitest run src/stores/useUIStore.test.ts` | ❌ W0 | ⬜ pending |
| 05-05-01 | 05 | 3 | VIZ-03, VIZ-04 | — | CI band path is non-empty for valid data; empty for 0 laps | unit | `vitest run src/components/PhysicsPanel/PhysicsChart.test.ts` | ❌ W0 | ⬜ pending |
| 05-06-01 | 06 | 3 | VIZ-07 | — | Status log collapses/expands; filtered by hoveredLap | unit | `vitest run src/components/StatusLog/StatusLog.test.ts` | ❌ W0 | ⬜ pending |
| 05-07-01 | 07 | 3 | DASH-02 | — | Layout renders without overflow at ≥1280px and ≥1600px | visual/manual | Manual browser check | Manual | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/vitest.config.ts` — Vitest config with jsdom environment
- [ ] `frontend/src/test/setup.ts` — MSW server setup for vitest
- [ ] `frontend/src/mocks/server.ts` — MSW Node server (for unit tests)
- [ ] `frontend/src/mocks/handlers.ts` — MSW handlers matching Phase 4 response schema
- [ ] `frontend/src/lib/scales.test.ts` — stubs for VIZ-02, VIZ-06
- [ ] `frontend/src/lib/track.test.ts` — stubs for VIZ-01
- [ ] `frontend/src/lib/formatters.test.ts` — stubs for fmtLapTime, fmtDelta, fmtCI
- [ ] `frontend/src/stores/useUIStore.test.ts` — stubs for VIZ-05
- [ ] `frontend/src/lib/sse.test.ts` — stubs for DASH-03

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Layout fits at ≥1280px and ≥1600px without overflow | DASH-02 | CSS layout overflow is visual; no DOM assertion reliably captures it | Open app in Chrome DevTools at 1280px and 1600px; verify no horizontal scroll on any panel |
| Hover sync across Car/Lap/Map/Physics panels | VIZ-05 | Cross-component DOM interaction in real browser | Hover a physics chart point at lap N; verify all 4 panels reflect lap N simultaneously |
| JetBrains Mono renders correctly on numerics | DASH-04 | Font loading is a runtime asset | Check computed font-family on big lap time in DevTools |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
