---
phase: 02-physics-model-modules-a-g
plan: 04
subsystem: physics
tags: [physics, friction, hertzian-contact, slip, module-d, module-e, brush-model, events]
dependency_graph:
  requires:
    - 02-01 (f1_core.physics package, FrictionParams, ThermalParams, StatusEvent, MAX_EVENTS)
    - 02-02 (Module A kinematic output: v, v_sx_rear)
    - 02-03 (Module B f_z inputs to D; Module C f_y/f_x inputs to E)
  provides:
    - f1_core.physics.module_d: contact_and_friction_step(f_z, t_tread_prev, mu_0, params_friction, params_thermal) -> (a_cp, p_bar, mu)
    - f1_core.physics.module_e: slip_inversion_step(...) -> SlipSample; SlipSample dataclass
  affects:
    - 02-05 (Module F thermal ODE consumes p_total from Module E SlipSample)
    - 02-06 (Orchestrator wires D and E into the per-timestep loop; reads t_tread_prev from SimulationState)
    - 02-07 (Module G consumes p_total from SlipSample for cumulative energy)
tech_stack:
  added: []
  patterns:
    - "Module D/E are pure functions (no class, no state) — per-timestep array-in, array-out"
    - "Explicit t_tread_prev parameter name encodes Pitfall 3 (prev-step causality) at the API level"
    - "np.cbrt() for cube-root inversion — avoids domain errors vs ** (1/3) with negative floats"
    - "np.where() guard for division-by-zero defense in depth (belt-and-suspenders with Module B floor)"
    - "MAX_EVENTS cap checked before and inside the for-loop (double guard prevents off-by-one at boundary)"
    - "SlipSample frozen=True dataclass — consistent with established Phase 2 pattern for module outputs"
key_files:
  created:
    - packages/core/src/f1_core/physics/module_d.py
    - packages/core/src/f1_core/physics/module_e.py
    - packages/core/tests/physics/test_module_d.py
    - packages/core/tests/physics/test_module_e.py
  modified: []
decisions:
  - "f_z_target formula in μ identity test corrected: plan template had K_rad/(2·R_0) but algebra gives (2·R_0)/K_rad — derived inline from p̄=f_z/(4·a_cp·b) and a_cp=√(2·R_0·f_z/K_rad)"
  - "SlipSample defined in module_e.py (not contracts.py) — it is a local per-timestep container, not a cross-module contract; the orchestrator unpacks the fields it needs"
  - "np.cbrt() used for (...)^(1/3) to guarantee correct sign handling and avoid nan on negative argument"
  - "μ values above μ_0_fresh=1.8 on canonical fixture are expected with nominal priors (pressure factor exceeds 1 when contact pressure < p̄_0); Phase 3 calibration will correct this"
metrics:
  duration: ~15 minutes
  completed: 2026-04-23
  tasks: 2
  files_created: 4
  files_modified: 0
---

# Phase 2 Plan 4: Modules D and E (Hertzian Contact + Friction, Brush-Model Slip Inversion) Summary

**Hertzian contact geometry and complete friction coefficient (Module D) plus brush-model slip inversion with diagnostic event logging (Module E) — μ(T_opt, p̄_0)=μ_0 identity verified to rtol=1e-12; Θ=1 at full grip verified; MAX_EVENTS=500 cap enforced under 800-event storm; 16 tests passing.**

## What Was Built

### Module D — Hertzian Contact Geometry + Friction (`module_d.py`)

`contact_and_friction_step(f_z, t_tread_prev, mu_0, params_friction, params_thermal) -> (a_cp, p_bar, mu)`

All three return values are `(4,)` float64 arrays.

Implements model_spec.md §D.1–§D.5:

- **§D.1 (Gim 1988):** `a_cp,i = √(2·R_0·F_z,i/K_rad)` — contact-patch half-length scales as F_z^(1/2)
- **§D.2:** `p̄_i = F_z,i / (4·a_cp,i·b_tread)` — mean Hertzian pressure, per-tire b_tread (0.15 m front, 0.20 m rear)
- **§D.3 (Greenwood-Williamson 1966):** `μ^pressure = μ_0·(p̄_0/p̄)^(1−n)` — sub-linear real contact area
- **§D.4 (Grosch 1963):** `g(T) = exp(−(T−T_opt)²/(2σ_T²))` — bell-curve temperature factor; g(T_opt)=1 exactly
- **§D.5:** `μ_i = μ_0(t)·pressure_factor·temp_factor` — complete coefficient

Key design: explicit `t_tread_prev` parameter name enforces Pitfall 3 causal ordering at the API level — the orchestrator must pass the previous timestep's tread temperature, not the current one.

### Module E — Brush-Model Slip Inversion + Sliding Power (`module_e.py`)

`slip_inversion_step(*, f_y, f_x, mu, f_z, a_cp, v, v_sx_rear, t, params, events) -> SlipSample`

Returns a frozen `SlipSample` dataclass with fields: `theta, alpha, v_sy, p_slide, p_rr, p_total`.

Implements model_spec.md §E.1–§E.7:

- **§E.1 (Pacejka 2012):** `C_α,i = c_py·a_cp,i²` — cornering stiffness
- **§E.2:** `Θ_i = 1 − (1 − |F_y|/(μ·F_z))^(1/3)` — brush model inversion; clipped to 1 on over-demand
- **§E.3:** `α_i = sgn(F_y)·arctan(3·μ·F_z·Θ/C_α)` — slip angle
- **§E.4:** `V_sy,i = V·sin(α)` — lateral slip velocity
- **§E.5 (Kobayashi 2019, Castellano 2021):** `P_slide = |F_y||V_sy| + |F_x||V_sx|` — sliding power ≥ 0 always
- **§E.6:** `P_rr = C_RR·F_z·V` — rolling resistance
- **§E.7:** `P_total = P_slide + P_rr`

Over-demand detection appends a `StatusEvent(kind="over_demand_lat", ratio>1, tire_index, t)` to the caller's mutable `events` list. The list is capped at `MAX_EVENTS=500` (T-02-09 mitigation).

## Canonical Fixture Results (Diagnostic)

Canonical inputs: v=50 m/s, a_lat=15 m/s², a_long=0, f_z=[3200, 4800, 4000, 6200] N, T_tread=T_opt=95°C, nominal params.

| Metric | Value |
|--------|-------|
| μ per tire (FL, FR, RL, RR) | [2.177, 2.090, 2.255, 2.158] |
| μ range | [2.09, 2.25] |
| θ per tire | [0.121, 0.127, 0.116, 0.122] |
| P_slide per tire (W) | [335, 505, 472, 735] |
| Over-demand events | **0** |

**Note on μ > μ_0_fresh:** The nominal p̄_0=1.5e5 Pa reference pressure produces a pressure factor > 1 at the actual contact pressures for the test loads (actual p̄ < p̄_0 at these loads). This is expected with nominal priors before calibration — Phase 3 will fit p̄_0 to observed friction data, which will bring μ into the physically expected range. Zero over-demand events confirms nominal params are not producing pathological grip demand.

**Note on 50 N clip cascade:** The Module B floor (50 N minimum F_z) is not triggered at realistic cornering loads. Module D has a secondary defense: `np.where(grip_capacity > 0, grip_capacity, 1.0)` substitutes 1.0 if grip_capacity is somehow zero — this path is unreachable at normal F_z values but prevents NaN propagation.

## Task Commits

1. **Task 1: Module D (Hertzian contact + friction)** — `8b7c279`
2. **Task 2: Module E (slip inversion + event log)** — `9c7e067`

## Files Created/Modified

- `packages/core/src/f1_core/physics/module_d.py` — `contact_and_friction_step`; cites §D.1–§D.5, Gim (1988), Greenwood-Williamson (1966), Grosch (1963)
- `packages/core/src/f1_core/physics/module_e.py` — `slip_inversion_step`, `SlipSample`; cites §E.1–§E.7, Pacejka (2012), Kobayashi et al. (2019), Castellano et al. (2021)
- `packages/core/tests/physics/test_module_d.py` — replaced 4-stub file with 7 real tests
- `packages/core/tests/physics/test_module_e.py` — replaced 5-stub file with 9 real tests

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] f_z_target formula inverted in μ identity test**

- **Found during:** Task 1 TDD GREEN phase — `test_module_d_mu_identity_at_T_opt_and_p_bar_0` failed with p̄ values 378,000× too large
- **Issue:** The plan template used `f_z_target = (p̄_0·4·b)²·K_rad/(2·R_0)`. Correct derivation from `p̄ = √(f_z·K_rad)/(4·b·√(2·R_0))` gives `f_z = (p̄_0·4·b)²·(2·R_0)/K_rad` — the K_rad and 2·R_0 are in opposite positions.
- **Fix:** Changed to `f_z_target = (p.friction.p_bar_0 * 4.0 * b_per) ** 2 * (2.0 * R_0) / k_rad` with inline derivation comment
- **Files modified:** `packages/core/tests/physics/test_module_d.py`
- **Commit:** `8b7c279` (included in Task 1 commit)

This is a test formula error, not a physics model error — module_d.py was correct throughout.

## Known Stubs

None. Both module files are complete physics implementations. No hardcoded empty values, placeholder text, or TODO/FIXME markers.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced. The threat register mitigations for T-02-09, T-02-10, and T-02-11 are all implemented as specified.

## Self-Check: PASSED

Files exist:
- packages/core/src/f1_core/physics/module_d.py: FOUND
- packages/core/src/f1_core/physics/module_e.py: FOUND
- packages/core/tests/physics/test_module_d.py: FOUND
- packages/core/tests/physics/test_module_e.py: FOUND

Commits exist:
- 8b7c279: feat(02-04): implement Module D (Hertzian contact + friction) with μ identity test
- 9c7e067: feat(02-04): implement Module E (brush-model slip inversion + event log) with cap enforcement

Full suite result: 39 passed, 19 skipped, 0 failed.
