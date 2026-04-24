# Phase 2: Physics Model (Modules A–G) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 02-physics-model-modules-a-g
**Areas discussed:** Module execution model, Parameters structure, Simulate CLI scope, Numerical integration

---

## Module Execution Model

### Question 1: Pipeline execution shape

| Option | Description | Selected |
|--------|-------------|----------|
| Hybrid: A preprocesses stint, B–G per-sample | Module A runs once on full stint; orchestrator loops per-timestep for B–G | ✓ |
| All modules vectorized | Every module receives full stint arrays and returns full arrays | |
| Pre-smooth outside the pipeline | Speed signal smoothed by orchestrator before Module A; keeps step() uniform for all 7 | |

**User's choice:** Hybrid — Module A preprocesses the full stint, B–G run in a per-timestep loop.

### Question 2: Curvature map consumption

| Option | Description | Selected |
|--------|-------------|----------|
| Module A calls curvature.py directly | Module A imports compute_curvature_map() from f1_core.curvature inside process_stint() | ✓ |
| Curvature map passed as a param | Orchestrator pre-builds the map; Module A only does lookup | |

**User's choice:** Module A calls curvature.py directly (self-contained, Phase 1 infrastructure reused).

---

## Parameters Structure

### Question 1: Parameter organization

| Option | Description | Selected |
|--------|-------------|----------|
| Per-stage nested dataclasses | AeroParams, FrictionParams, ThermalParams, DegradationParams — matches Phase 3 calibration stages | ✓ |
| One flat PhysicsParams dataclass | All 15–20 fields in a single @dataclass | |
| YAML defaults file + one dataclass | Parameters loaded from YAML at startup | |

**User's choice:** Per-stage nested dataclasses (clean boundary, natural fit for Phase 3's stage-by-stage calibration).

### Question 2: Default values for Phase 2

| Option | Description | Selected |
|--------|-------------|----------|
| Nominal priors from model_spec.md | FIXED and SEMI-CONSTRAINED values from spec + reasonable mid-range calibrated estimates | ✓ |
| Phase 2 unit-tests only, no nominal run | Only physical invariant tests on synthetic inputs | |
| Hardcoded Bahrain 2023 reference params | Circuit/car-specific estimates | |

**User's choice:** Nominal priors from model_spec.md — Phase 2 produces real (if rough) output against the canonical fixture.

---

## Simulate CLI Scope

### Question 1: CLI scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full working CLI with per-lap output | simulate produces per-lap table on stdout using nominal params | ✓ |
| Library only + unit tests | No CLI in Phase 2; API in Phase 4 | |
| Minimal CLI for benchmarking only | Benchmark script only, not user-facing | |

**User's choice:** Full working CLI that proves the complete A→G pipeline on real FastF1 data.

### Question 2: Output format

| Option | Description | Selected |
|--------|-------------|----------|
| Per-lap table to stdout | Human-readable: lap / compound / age / pred / obs / Δ / grip / T_tread / E | ✓ |
| JSON to stdout | Machine-readable per-timestep JSON | |
| CSV file | Written to .data/results/<stint_id>.csv | |

**User's choice:** Per-lap table to stdout — easy to eyeball correctness without file I/O.

---

## Numerical Integration

### Question: Thermal ODE integration method

| Option | Description | Selected |
|--------|-------------|----------|
| Forward Euler | T(t+Δt) = T(t) + Ṫ(t)·Δt at Δt=0.25s — spec says stable for thermal time constants > 5s | ✓ |
| RK4 at same Δt | 4th-order accuracy, 4× function evaluations, same Δt | |

**User's choice:** Forward Euler — simplest, stable per spec, RK4 deferred to Phase 4 if calibration reveals temperature bias.

---

## Claude's Discretion

- Savitzky-Golay parameters: window=9, order=3
- Module file layout: `packages/core/src/f1_core/physics/` with module_a.py–module_g.py + orchestrator.py + defaults.py
- Benchmark: `@pytest.mark.benchmark` on canonical fixture asserting < 200 ms
- `simulate` CLI entry point: `f1-simulate` console script in packages/core/pyproject.toml
- Module G G.2: μ_0 ages as a scalar using mean(T_tread) across all four tires

## Deferred Ideas

None — discussion stayed within phase scope.
