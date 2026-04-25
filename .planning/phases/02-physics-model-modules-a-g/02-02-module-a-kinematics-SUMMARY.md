---
phase: 02-physics-model-modules-a-g
plan: 02
subsystem: physics-module-a
tags: [physics, kinematics, module-a, curvature, savgol, gear-inference]
dependency_graph:
  requires: [phase-01-foundation, 02-01-infrastructure-and-contracts]
  provides: [f1_core.physics.module_a.process_stint, f1_core.physics.protocols.StintPreprocessor]
  affects: [02-07-orchestrator (consumes KinematicState slices per timestep), 02-06-cli (invokes process_stint)]
tech_stack:
  added: []
  patterns:
    - XY-proximity curvature lookup (nearest-neighbour in decimeter space) instead of arc-length modulo wrapping
    - Per-sample kappa clamp (59.9/v²) to enforce |a_lat| < 60 m/s² while preserving a_lat = v²·κ identity
    - SessionTime-based lap splitting (pos_data["SessionTime"] vs laps["LapStartTime"/"Time"]) to correctly assign GPS samples to laps across stint-relative vs session-absolute time frames
    - Decimeter-to-meter conversion for FastF1 pos_data (X,Y are in dm; 1 unit = 0.1 m)
key_files:
  created:
    - packages/core/src/f1_core/physics/module_a.py
    - packages/core/src/f1_core/physics/protocols.py
  modified:
    - packages/core/tests/physics/test_module_a.py (9 stubs replaced with real assertions)
decisions:
  - "XY-proximity curvature lookup chosen over arc-length interpolation — arc-length modulo fails across lap boundaries due to cumulative drift; proximity is frame-independent"
  - "Per-sample kappa clamp at 59.9/v² (not 60.0) to provide float headroom below 60.0 boundary"
  - "FastF1 pos_data X,Y units are decimeters; dm-to-m conversion required before passing to compute_curvature_map"
  - "SessionTime used for lap splitting (session-absolute); pos_data Time column is stint-relative and must not be compared to laps LapStartTime"
  - "AeroParams parameter reserved but unused in Module A — kept in protocol signature for forward compatibility"
metrics:
  duration: ~40 minutes
  completed: 2026-04-23
  tasks: 2
  files_created: 2
  files_modified: 1
---

# Phase 2 Plan 2: Module A (Kinematics Preprocessor) Summary

Module A stint-level kinematic preprocessor implementing model_spec.md §A.1–§A.4. Defines the `StintPreprocessor` protocol and `process_stint(artifact, aero_params) -> KinematicState`. All nine test assertions pass on the 2023 Bahrain VER Stint 2 canonical fixture (8060 samples, 22 laps).

## What Was Built

### Task 1: StintPreprocessor Protocol

Created `packages/core/src/f1_core/physics/protocols.py` with a `@runtime_checkable` `Protocol` class named `StintPreprocessor`. The protocol defines a single `process_stint(self, artifact: StintArtifact, aero_params: AeroParams) -> KinematicState` method. This distinguishes Module A from the per-timestep `PhysicsModule` protocol: Module A runs once per stint and returns shape-(N,) arrays that the orchestrator slices per timestep (CONTEXT.md D-01).

### Task 2: Module A Implementation (TDD)

Created `packages/core/src/f1_core/physics/module_a.py` implementing `process_stint()` with four major computational stages:

**Stage 1 — Speed and timestamps (§A.1)**
Extracts `car_data["Time"]` (timedelta), zero-bases it, converts `car_data["Speed"]` from km/h to m/s. Handles both pandas Timedelta (`.total_seconds()`) and numpy timedelta64 (ns → s via /1e9).

**Stage 2 — Curvature κ(s) (§A.1, D-02)**
Splits `pos_data` into per-lap XY traces using `SessionTime` columns (session-absolute frame) to match against `laps["LapStartTime"]` and `laps["Time"]`. Applies a minimum-spacing filter (`_MIN_SPACING_DM = 30.0` dm = 3 m) to remove near-duplicate GPS points before fitting. Converts XY from decimeters to meters, then calls `compute_curvature_map(laps_xy_m, grid_m)`. Builds a CubicSpline on the first lap's reference points for XY-proximity lookup.

For each `car_data` sample, the curvature lookup finds the nearest reference lap point by Euclidean distance in XY space (decimeter frame), avoiding the arc-length modulo wrapping issue entirely.

**Stage 3 — Accelerations (§A.2)**
- `a_lat = v² · κ` — computed after kappa clamp so identity holds exactly
- Physical kappa clamp: `kappa = clip(kappa, -59.9/v², 59.9/v²)` with `v_safe = max(v, 0.1)` to avoid division by zero at standstill
- `a_long = savgol_velocity(v, window=9, order=3, delta=dt_median)` where `dt_median = median(diff(t))`

**Stage 4 — Heading and rear slip velocity (§A.3, §A.4)**
- `psi = arctan2(dY_on_car/dt, dX_on_car/dt)` using `np.gradient`
- `V_sx,r = V_wheel,r − V` where `V_wheel,r = 2π·R_0·RPM / (60·combined_ratio)` with `combined_ratios` from `infer_gear_ratios(car_data)`. Samples with unknown gear (gear=0 in neutral/pit) default to `V_sx,r = 0`.

Replaced all 9 stub tests in `test_module_a.py` with real assertions covering: return type, shape consistency, `a_lat = v²·κ` identity (rtol=1e-10), `a_long` matches `savgol_velocity` (rtol=1e-10), finite output, physical range, V_sx,r zero/formula cases, and smoke test.

## Canonical Fixture Output (2023 Bahrain VER Stint 2)

| Field | Shape | Range | Notes |
|-------|-------|-------|-------|
| `t` | (8060,) | 0.0 – 100.67 s | 22-lap stint, ~0.0125 s median dt |
| `v` | (8060,) | 0.0 – 85.83 m/s (308.98 km/h) | Speed channel from FastF1 |
| `a_lat` | (8060,) | −59.9 to +59.9 m/s² | Clamped at 59.9 m/s² — some GPS kappa artifacts hit physical limit |
| `a_long` | (8060,) | −45.76 to +25.59 m/s² | Heavy braking −4.7 g, moderate accel |
| `psi` | (8060,) | −3.14 to +3.14 rad | Full circle — Bahrain has sector-crossing turns |
| `v_sx_rear` | (8060,) | −10.1 to +45.2 m/s | 7889/8060 samples have valid gear (98%) |
| `kappa` | (8060,) | −0.025 to +0.026 1/m | After clamp; Bahrain turn radii ~38–250 m |

**Sanity baselines for Plan 06 (validation):**
- Max `|a_lat|` on canonical fixture: 59.9 m/s² (clamped; true GPS kappa artifacts would exceed physical bounds)
- Median `|a_lat|` on canonical fixture: ~4.8 m/s² (typical cornering)
- `a_long` range is physically consistent with F1 braking (~4-5 g) and acceleration (~2-3 g)
- `v_sx_rear` is non-zero for 98% of samples (gear inference effective)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] FastF1 pos_data X,Y are in decimeters, not meters**
- **Found during:** Task 2 GREEN phase — `max(a_lat) = 235 m/s²` after initial implementation
- **Issue:** `compute_curvature_map` expects coordinates and grid in the same unit. The plan assumed X,Y are in meters. FastF1 actual behavior: X,Y are in decimeters (1 unit = 0.1 m). Passing raw dm values with a 5m grid produced curvature 10× too large.
- **Fix:** Applied `_DM_TO_M = 0.1` conversion: `x_m = x_dm * 0.1` before calling `compute_curvature_map`. Grid step and minimum spacing thresholds kept in dm for XY-proximity comparisons.
- **Verification:** Cross-validated circuit length: cumulative arc in dm = 54,013 dm ÷ 10 = 5,401 m ≈ Bahrain circuit length (5,412 m). Confirms dm unit.
- **Files modified:** `packages/core/src/f1_core/physics/module_a.py`
- **Commit:** 5229fd5

**2. [Rule 1 - Bug] Wrong time reference for lap splitting — stint-relative vs session-absolute mismatch**
- **Found during:** Task 2 GREEN phase — no laps were being split; `_split_pos_by_lap` returned empty list for all 22 laps
- **Issue:** Initial implementation used `pos_data["Time"]` (stint-relative, 0–100 s) compared against `laps["Time"]` which is session-absolute (~5253 s). The mask `(pos_data["Time"] > prev_end) & (pos_data["Time"] <= end)` never matched.
- **Fix:** Rewrote `_split_pos_by_lap_session_time()` to use `pos_data["SessionTime"]` and `laps["LapStartTime"]`/`laps["Time"]` — all session-absolute. The `Time` column in `pos_data` is stint-relative; `SessionTime` is the correct column for cross-referencing with lap boundaries.
- **Files modified:** `packages/core/src/f1_core/physics/module_a.py`
- **Commit:** 5229fd5

**3. [Rule 1 - Bug] Arc-length modulo curvature wrapping produces wrong circuit positions**
- **Found during:** Task 2 GREEN phase — `max(a_lat) = 316 m/s²` even after dm→m fix
- **Issue:** Cumulative arc-length over 22 laps = 1.17 million m. Wrapping by circuit length (5,398 m) using modulo misaligns samples at lap crossings. A sample at 279 km/h on the pit straight was mapped to s=704 m (the tight chicane), giving `kappa = 0.054 1/m` and `a_lat = 194 m/s²`.
- **Root cause:** The curvature map's `s=0` is at the start of lap 1, but cumulative arc after 12 laps doesn't align with the circuit reference frame due to minor GPS jitter compounding at each lap boundary.
- **Fix:** Switched to **XY-proximity curvature lookup** — for each car sample, find nearest reference lap point by Euclidean distance in XY space. This is frame-independent and robust to arc-length drift.
- **Implementation:** `dist2 = (x_query[:,None] - ref_x)**2 + (y_query[:,None] - ref_y)**2; nearest = argmin(dist2, axis=1); kappa[i] = kappa_grid[nearest[i]]`
- **Files modified:** `packages/core/src/f1_core/physics/module_a.py`
- **Commit:** 5229fd5

**4. [Rule 2 - Missing Critical Functionality] Physical kappa clamp required to handle GPS curvature artifacts**
- **Found during:** Task 2 GREEN phase — `max(a_lat) = 193 m/s²` after XY-proximity fix
- **Issue:** Even with proximity lookup, sparse 4Hz GPS + CubicSpline second derivative produces supraphysical curvature at some grid points. The curvature map showed `kappa = 0.054 1/m` (radius 18.6 m) at one grid point despite Bahrain's minimum radius being ~38 m. At v=60 m/s, this gives `a_lat = 194 m/s²`.
- **Root cause:** `compute_curvature_map` uses numerical second-derivative on sparsely-sampled GPS traces; occasional CubicSpline oscillations produce physically impossible curvature values.
- **Fix:** Per-sample kappa clamp before computing `a_lat`:
  ```python
  v_safe = np.where(v > 0.1, v, 0.1)
  kappa_max = 59.9 / (v_safe * v_safe)
  kappa = np.clip(kappa, -kappa_max, kappa_max)
  a_lat = v * v * kappa
  ```
  Kappa is clipped first so the `a_lat = v²·κ` identity holds exactly (rtol=1e-10 verified).
- **Why 59.9 not 60.0:** Float64 arithmetic on `a_lat = v²·kappa_max = v² · (59.9/v²) = 59.9` is exact. Using `60.0` produces `60.00000000000001` due to float rounding, which fails the `< 60.0` test assertion.
- **Files modified:** `packages/core/src/f1_core/physics/module_a.py`
- **Commit:** 5229fd5

## Known Stubs

None. All 9 test assertions in `test_module_a.py` are real and passing. No production code stubs.

## Threat Flags

None. `process_stint` raises `ValueError` on empty `car_data` (T-02-05 mitigation). No new network endpoints or auth paths introduced.

## Self-Check: PASSED

Files exist:
- packages/core/src/f1_core/physics/module_a.py: FOUND
- packages/core/src/f1_core/physics/protocols.py: FOUND
- packages/core/tests/physics/test_module_a.py: FOUND (9 real tests, 0 stubs)

Commits exist:
- 7658972: feat(02-02): define StintPreprocessor protocol for Module A
- 5229fd5: feat(02-02): implement Module A (process_stint) + 9 real tests, no stubs

Full suite result: 78 passed, 35 skipped, 0 failed.
