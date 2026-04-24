---
phase: 03-bayesian-calibration-pipeline
plan: "05"
subsystem: calibration
tags: [calibration, jax, parity, module-f, module-g, tdd]
dependency_graph:
  requires: [03-01, 03-02]
  provides: [jax_model.py for Stage 4 MCMC (03-06)]
  affects: [packages/calibration/src/f1_calibration/jax_model.py]
tech_stack:
  added: [jax, jax.lax.scan]
  patterns: [pure-function-scan, closed-over-params, float64-enforcement, tdd-red-green]
key_files:
  created:
    - packages/calibration/src/f1_calibration/jax_model.py
    - packages/calibration/tests/test_jax_model.py
  modified: []
decisions:
  - "Closed-over params in lax.scan step fn (not carried in state tuple) — cleaner JAX tracing"
  - "simulate_mu_0 carries only (mu_0, d_tread) — minimal carry matching D-06 design"
  - "thermal_scan provided as optional utility (not in Stage 4 likelihood path)"
metrics:
  duration_minutes: 12
  completed_date: "2026-04-23"
  tasks_completed: 1
  files_created: 2
  files_modified: 0
  tests_added: 7
  tests_passing: 7
---

# Phase 03 Plan 05: JAX Model Parity (Module F + G) Summary

**One-liner:** JAX-native `simulate_mu_0` using `lax.scan` with x64 enforcement, Arrhenius clamping at ±20, and 200-step NumPy parity verified to |Δ| < 1e-6.

## What Was Built

`packages/calibration/src/f1_calibration/jax_model.py` — pure-JAX parity copy of
`f1_core.physics.module_g.degradation_step` for Stage 4 MCMC (CONTEXT D-06).

Key design: since Stages 1–3 pre-compute `T_tread_traj` and `P_slide_traj` as FIXED
inputs to Stage 4, `simulate_mu_0` only steps the scalar `mu_0` and per-tire `d_tread`
via `jax.lax.scan`. This is a minimal 3-parameter scan — extremely fast per MCMC sample.

### Exports

| Symbol | Type | Purpose |
|--------|------|---------|
| `simulate_mu_0` | function | (N,) mu_0 trajectory via lax.scan — Stage 4 core |
| `log_likelihood_f_g` | function | Per-lap Gaussian LL on §G.4 lap-time predictions |
| `thermal_scan` | function | Optional full F thermal scan (not in Stage 4 path) |
| `DT` | float | 0.25 — mirrors `DT_THERMAL` from constants.py |
| `T_REF_AGING` | float | 80.0 — mirrors production constant |
| `ARRHENIUS_EXP_CLAMP` | float | 20.0 — mirrors `module_g.ARRHENIUS_EXP_CLAMP` |

## Parity Guarantees

| Check | Result |
|-------|--------|
| 200-step JAX vs NumPy module_g.degradation_step | max |Δmu_0| < 1e-6 |
| Single-step hand-computed closed form | |Δ| < 1e-10 |
| Arrhenius clamp at T=1000°C (arg=36.8, should clamp to 20) | matches NumPy < 1e-6 |
| jax_enable_x64 after import | True |
| lax.scan in source | 2 occurrences (simulate_mu_0 + thermal_scan) |

## Tests

`packages/calibration/tests/test_jax_model.py` — 7 tests, all passing:

1. `test_constants_match_numpy` — DT, T_REF_AGING, ARRHENIUS_EXP_CLAMP mirror production
2. `test_x64_enabled` — Pitfall 1: x64 True after import
3. `test_simulate_mu_0_single_step_closed_form` — hand-computed step to 1e-10
4. `test_parity_with_numpy_module_g` — THE parity test: 200-step max Δ < 1e-6
5. `test_parity_with_clamped_arrhenius` — Pitfall 4 regression at T=1000°C
6. `test_log_likelihood_returns_scalar` — returns shape-() finite jnp scalar
7. `test_uses_lax_scan` — structural: lax.scan in source

## Commits

| Hash | Type | Description |
|------|------|-------------|
| `8dc8aed` | test | TDD RED — 7 failing tests for jax_model |
| `8cc2e4a` | feat | GREEN — jax_model.py with simulate_mu_0, log_likelihood_f_g, thermal_scan |

## Decisions Made

1. **Closed-over params in scan step** — `beta_therm`, `T_act`, `k_wear` are closed over by the inner `_step` function rather than carried in the state tuple. This gives cleaner JAX tracing and avoids dtype confusion in the carry.

2. **Minimal carry: only (mu_0, d_tread)** — D-06 design constraint honored. The carry does NOT include `e_tire` (not needed for Stage 4 likelihood) or thermal state (T_tread is fixed input).

3. **thermal_scan as optional utility** — Provided for completeness and future experiments, but not in the Stage 4 likelihood path. Follows the same scan pattern as simulate_mu_0.

## Deviations from Plan

None — plan executed exactly as written. The implementation followed the plan's action block directly, with minor structural adjustments:
- Parameters are closed over (not in carry), which is cleaner JAX idiom vs. plan's carry-based example
- `_simulate_mu_0_step` was inlined as a nested closure `_step` inside `simulate_mu_0` for cleaner closure semantics

Both approaches produce identical outputs — verified by parity tests.

## Self-Check: PASSED

- [x] `packages/calibration/src/f1_calibration/jax_model.py` — created
- [x] `packages/calibration/tests/test_jax_model.py` — created
- [x] Commit `8dc8aed` — test(03-05) RED exists
- [x] Commit `8cc2e4a` — feat(03-05) GREEN exists
- [x] All 7 tests pass
- [x] x64 enforced
- [x] lax.scan used (2 occurrences)
- [x] ARRHENIUS_EXP_CLAMP = 20.0 matches module_g
- [x] 200-step parity < 1e-6

## Known Stubs

None. All functions are fully implemented and verified.

## Threat Flags

No new trust boundaries introduced. `jax_model.py` consumes in-process numeric arrays only — no file I/O, no subprocess, no network, no CLI surface.
