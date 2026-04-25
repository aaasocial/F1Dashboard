# Phase 1: Foundation, Data Pipeline & Module Contracts - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1 delivers the structural foundation that unblocks all downstream phases:
- FastF1 data ingestion with a two-layer disk cache (fetch-once, run-many)
- Data integrity layer: quality scoring, sentinel detection, corrupt-stint flagging
- Per-circuit curvature map κ(s) and per-team gear-ratio inference
- Lap annotation: compound→C1–C5, tire age, fuel estimate, weather, in/out-lap and SC/VSC flags
- Seven typed dataclass contracts + SimulationState scaffold (the module API that Phases 2–4 implement)
- Three FastAPI GET endpoints serving real cached data (GET /races, /races/{id}/drivers, /stints/{race_id}/{driver_id})

New capabilities (physics simulation, calibration, frontend, API simulation endpoint) belong in Phases 2–4.

</domain>

<decisions>
## Implementation Decisions

### Repo Layout
- **D-01:** Monorepo with a deeper package structure at root:
  ```
  F1 Dashboard/
  ├── packages/
  │   ├── core/          # physics contracts, data pipeline, curvature/gear inference
  │   ├── api/           # FastAPI app, depends on core
  │   └── calibration/   # offline CLI calibration pipeline, depends on core
  ├── frontend/          # React + TypeScript + Vite
  ├── notebooks/         # educational Jupyter notebooks
  ├── scripts/           # prewarm, fetch CLI, etc.
  ├── .planning/
  └── pyproject.toml     # uv workspace root
  ```
- **D-02:** Python inter-package dependencies managed via **uv workspaces** — single `pyproject.toml` at repo root declares all three packages as workspace members; uv resolves a shared lockfile. No manual `pip install -e .` steps.

### Physics Contract Type System
- **D-03:** The seven physics state contracts use **plain Python `@dataclass`** — zero construction overhead in the 4 Hz simulation hot path. Matches the "typed dataclass contracts" language in REQUIREMENTS (PHYS-08, PHYS-09). The seven contracts: `KinematicState`, `WheelLoads`, `ContactPatch`, `SlipState`, `ThermalState`, `DegradationState`, `SimulationState`.
- **D-04:** FastAPI **response schemas are separate Pydantic v2 `BaseModel` classes** defined in `packages/api/`. They accept dataclass inputs via `model_config = ConfigDict(from_attributes=True)`. Physics types never import Pydantic. Clear boundary: physics stays fast, serialization happens at the API layer only.
- **D-05:** The `PhysicsModule` protocol is a **`typing.Protocol`** (structural subtyping). Any class with the correct method signatures satisfies it at type-check time without inheritance. Mypy/pyright enforces compliance statically. No ABC boilerplate. Placeholder modules for Phase 1 testing require zero special base class.

### Development Fixture
- **D-06:** Canonical development fixture throughout all 7 phases: **2023 Bahrain Grand Prix, Verstappen, Stint 2 (MEDIUM compound, laps 16–38, ~23 laps)**. This stint shows visible grip degradation (~0.4s pace drop over the stint), all three thermal-cycling phases, representative lateral loads, and no data anomalies. This is the integration test baseline, the Phase 2 benchmark target, and the Phase 3 calibration validation case.

### Claude's Discretion
- Cache directory path (for local dev: `.data/` gitignored; Fly.io: `/data` persistent volume — planner decides the config abstraction)
- Savitzky-Golay filter window (7–11, order 2–3 per spec — pick based on FastF1 4 Hz sample rate)
- Lint/format tooling (Ruff is the obvious choice given uv workspace; planner decides)
- CI trigger configuration (GitHub Actions, test-on-PR — standard)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Physics Model Specification
- `model_v1_complete.html` — Seven-module architecture, all equations with source paper citations. Authoritative spec for Module A–G contracts. Read the Module A section for KinematicState fields, Module B for WheelLoads, etc.
- `model_spec.md` — Markdown equivalent of the physics spec. Covers Modules A through G with implementation notes.
- `model_calibration_strategy.html` — Four-stage Bayesian calibration spec. Phase 1 only needs the parameter naming convention from Stage 1–2 to define the right fields in the contracts.

### Project Requirements
- `.planning/REQUIREMENTS.md` — All 49 v1 requirements with traceability. Phase 1 covers: DATA-01 through DATA-06, PHYS-08 (contract portion), PHYS-09 (state-object portion), API-01, API-02, API-03.
- `.planning/ROADMAP.md` — Phase 1 success criteria (6 items). Use these as the acceptance checklist.

### Project Context
- `brief.md` — Original project brief. Useful for understanding intent behind data pipeline choices.
- `.planning/PROJECT.md` — Non-negotiables and key decisions already locked (physics-first, public data only, SQLite, offline calibration).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — fresh start. No prior codebase to carry forward (per PROJECT.md: "Prior F1 Dashboard code is archived/not carried forward").

### Established Patterns
- None yet — Phase 1 establishes the patterns. Key ones to define:
  - `@dataclass` for all physics state objects (D-03)
  - `typing.Protocol` for module contracts (D-05)
  - uv workspace `packages/` layout (D-01, D-02)
  - Pydantic v2 `BaseModel` for API schemas only (D-04)

### Integration Points
- `packages/core` will be imported by `packages/api` and `packages/calibration`
- FastAPI app in `packages/api` will use `packages/core` data pipeline functions for GET endpoints
- Phase 2 physics modules will implement the `PhysicsModule` protocol defined in `packages/core`

</code_context>

<specifics>
## Specific Ideas

- **Fixture reference:** `fastf1.get_session(2023, 'Bahrain', 'R')`, driver `VER`, stint index 1 (0-indexed), compound MEDIUM, laps 16–38. This is the exact stint to hardcode in integration test fixtures and the Phase 2 benchmark.
- **uv workspace layout:** Root `pyproject.toml` with `[tool.uv.workspace] members = ["packages/core", "packages/api", "packages/calibration"]`. Each sub-package has its own `pyproject.toml` with pinned dependencies. Frontend uses a separate `package.json` inside `frontend/`.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-foundation-data-pipeline-module-contracts*
*Context gathered: 2026-04-23*
