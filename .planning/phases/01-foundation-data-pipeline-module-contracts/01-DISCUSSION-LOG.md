# Phase 1: Foundation, Data Pipeline & Module Contracts - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 01-foundation-data-pipeline-module-contracts
**Areas discussed:** Repo layout, Physics contract types, Development fixture race

---

## Repo Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Monorepo, flat | backend/ and frontend/ at root | |
| Monorepo, deeper | Separate packages: core/, api/, calibration/ | ✓ |

**User's choice:** Monorepo, deeper — `packages/core`, `packages/api`, `packages/calibration` + `frontend/`, `notebooks/`

---

### Workspace tool follow-up

| Option | Description | Selected |
|--------|-------------|----------|
| uv workspaces | Single pyproject.toml at root, shared lockfile | ✓ |
| pip install -e . | Editable install into shared venv, no lockfile | |
| Single flat package | Reconsider deeper structure | |

**User's choice:** uv workspaces

---

## Physics Contract Types

| Option | Description | Selected |
|--------|-------------|----------|
| Plain @dataclass | Zero overhead, separate Pydantic schemas at API boundary | ✓ |
| Pydantic v2 BaseModel | One type system everywhere, ~5–15% overhead | |

**User's choice:** Plain `@dataclass` for physics contracts; separate Pydantic v2 `BaseModel` for API schemas

---

### PhysicsModule protocol follow-up

| Option | Description | Selected |
|--------|-------------|----------|
| typing.Protocol | Structural subtyping, static enforcement | ✓ |
| ABC | Nominal subtyping, runtime TypeError on missing methods | |

**User's choice:** `typing.Protocol`

---

## Development Fixture Race

| Option | Description | Selected |
|--------|-------------|----------|
| 2023 Bahrain GP | Rich degradation, all compounds, high-quality data | ✓ |
| 2024 Monaco GP | Low degradation, atypical race | |
| 2024 Singapore GP | High lateral loads, no high-speed aero paths | |
| You decide | Leave to planner | |

**User's choice:** 2023 Bahrain Grand Prix

---

### Driver/stint follow-up

| Option | Description | Selected |
|--------|-------------|----------|
| Verstappen, Stint 2 MEDIUM | Laps 16–38, visible degradation, no anomalies | ✓ |
| Leclerc, Stint 1 SOFT | Laps 1–15, high early degradation | |
| You decide | Leave to planner | |

**User's choice:** Verstappen, Stint 2, MEDIUM compound, laps 16–38

---

## Claude's Discretion

- Cache directory path abstraction (local vs Fly.io volume)
- Savitzky-Golay filter window parameters
- Lint/format tooling (Ruff recommended)
- CI trigger configuration (GitHub Actions)

## Deferred Ideas

None
