# Phase 5: Dashboard Shell & Visualization - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 05-dashboard-shell-visualization
**Areas discussed:** Track Map, Progress Bar, Hover Axis, Tooling

---

## Track Map (A)

| Option | Description | Selected |
|--------|-------------|----------|
| FastF1 X/Y (dynamic) | Smooth fastest lap GPS coords into SVG path — automatic for any race | ✓ |
| Curated static SVGs | Pre-built per-circuit files — polished but requires maintenance | |

**User's choice:** FastF1 X/Y telemetry
**Notes:** Automatic coverage for all 2022–present circuits with one smoothing pass.

---

## Progress Bar (B)

| Option | Description | Selected |
|--------|-------------|----------|
| Fake timer animation | JS timer fakes 7 module steps over ~3s — no backend changes | |
| SSE streaming | New `/simulate/stream` SSE endpoint fires real per-module events | ✓ |

**User's choice:** SSE streaming
**Notes:** Authentic module-by-module progress. Phase 5 adds the SSE endpoint to `packages/api/`. The existing `POST /simulate` sync endpoint is retained.

---

## Hover Axis (C)

| Option | Description | Selected |
|--------|-------------|----------|
| Lap-discrete | Hover snaps to lap N — consistent across all 7 zones | ✓ |
| 4 Hz continuous | Hover tracks exact telemetry timestep — complex cross-zone sync | |

**User's choice:** Lap-discrete
**Notes:** Shared Zustand `hoveredLap: number` drives all zones. 4Hz playback animation deferred to Phase 6.

---

## Tooling (D)

| Option | Description | Selected |
|--------|-------------|----------|
| Biome + Vitest now | Single binary linter + unit tests from day one; Playwright in Phase 6 | ✓ |
| ESLint+Prettier + Vitest now | Standard ecosystem; Playwright in Phase 6 | |
| Either linter, tests deferred | Lean Phase 5; all tests in Phase 6 | |

**User's choice:** Biome + Vitest now, Playwright deferred to Phase 6
**Notes:** Vitest covers D3 utilities, Zustand state, CI band math. MSW for API mocking during dev.

---

## Claude's Discretion

- Zustand store slice names and shape
- D3 scale configuration details
- SVG viewport dimensions and track map aspect ratio
- X/Y smoothing algorithm implementation
- CSS Grid template for six-zone layout
- SSE event schema (event names, per-module payload)
- `EventSource` vs `fetch + ReadableStream` for SSE consumption
- Loading skeleton scope (per-zone vs component-level)
- Error boundary scope

## Deferred Ideas

- Three.js 3D track map → v2
- Playwright E2E tests → Phase 6
- Continuous 4Hz car animation → Phase 6
- What-If sliders, compound comparison → v2 per PROJECT.md
