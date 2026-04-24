---
phase: 02
status: findings
reviewed: 2026-04-23T00:00:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - packages/core/src/f1_core/physics/module_a.py
  - packages/core/src/f1_core/physics/module_b.py
  - packages/core/src/f1_core/physics/module_c.py
  - packages/core/src/f1_core/physics/module_d.py
  - packages/core/src/f1_core/physics/module_e.py
  - packages/core/src/f1_core/physics/module_f.py
  - packages/core/src/f1_core/physics/module_g.py
  - packages/core/src/f1_core/physics/orchestrator.py
  - packages/core/src/f1_core/physics/cli.py
  - packages/core/src/f1_core/physics/params.py
  - packages/core/src/f1_core/physics/defaults.py
  - packages/core/src/f1_core/physics/constants.py
  - packages/core/src/f1_core/physics/events.py
  - packages/core/src/f1_core/physics/protocols.py
  - packages/core/src/f1_core/contracts.py
findings:
  critical: 0
  high: 1
  medium: 3
  low: 4
  total: 8
---

# Phase 02: Code Review Report

**Reviewed:** 2026-04-23
**Depth:** standard
**Files Reviewed:** 15
**Status:** findings

## Summary

The physics pipeline (Modules A–G, orchestrator, CLI, supporting files) is
well-structured and shows careful attention to the documented design decisions:
the forward Euler lag between Module D and Module F is correctly implemented,
the numpy vectorisation constraint is honoured, the Arrhenius exponent clamp
and the 500-event cap are in place, and the CLI correctly suppresses tracebacks
at the boundary. Sign conventions and floor values are internally consistent.

No correctness or security bugs that would produce silently wrong simulation
results were found. One unhandled crash path in the curvature spline builder
is the most actionable finding. Three medium-severity issues relate to
unguarded parameter edge cases and a stale contract type. Four low-severity
issues are misleading comments and a missing NaN sentinel.

---

## Findings

### [HIGH] CubicSpline crash when GPS monotonicity filter removes all distinct points

**File:** `packages/core/src/f1_core/physics/module_a.py:179–185`

**Issue:**
`_build_curvature_on_reference_lap` builds the reference XY spline from the
first lap after filtering for strictly-increasing arc-length samples:

```python
mono = np.concatenate(([True], np.diff(s0) > 0))
s0m = s0[mono]; x0m = x0[mono]; y0m = y0[mono]
cs_x = CubicSpline(s0m, x0m)   # raises ValueError if len(s0m) < 2
cs_y = CubicSpline(s0m, y0m)
```

If the first lap's GPS trace is noisy enough that the monotonicity filter
removes all but one sample (edge case: stationary/pit-lane GPS artifacts),
`CubicSpline` raises `ValueError: x must contain at least 2 elements`. This
exception propagates uncaught through `process_stint` and out of
`run_simulation` as an unhandled crash rather than a clean fallback.

The outer call site at line ~285 has no `try/except`:

```python
grid_s, kappa_grid, ref_x, ref_y = _build_curvature_on_reference_lap(laps_xy_dm)
```

**Fix:**
Add a length guard after the monotonicity filter and fall back to the
zero-curvature path if too few points survive:

```python
mono = np.concatenate(([True], np.diff(s0) > 0))
s0m = s0[mono]; x0m = x0[mono]; y0m = y0[mono]
if len(s0m) < 4:          # CubicSpline needs >= 2; 4 gives meaningful curvature
    # Fall back: return flat grid with zero kappa
    return grid_m, np.zeros_like(grid_m), grid_m * 0.0, grid_m * 0.0
cs_x = CubicSpline(s0m, x0m)
cs_y = CubicSpline(s0m, y0m)
```

Alternatively, wrap the `_build_curvature_on_reference_lap` call in
`process_stint` with a `try/except ValueError` that falls back to
`kappa = np.zeros_like(v)`.

---

### [MEDIUM] ZeroDivisionError when `DegradationParams.T_act == 0`

**File:** `packages/core/src/f1_core/physics/module_g.py:54`

**Issue:**
The Arrhenius aging exponent computes:

```python
arg = (t_tread_mean - T_REF_AGING) / params.T_act
```

`T_act` is a calibration parameter with no constraint enforced in
`DegradationParams` (which is a plain `frozen=True` dataclass with no
`__post_init__`). A caller passing `T_act=0` (plausible during automated
parameter sweeps or badly-formed calibration draws) will produce an
unhandled `ZeroDivisionError` at runtime, crashing the simulation loop.

**Fix:**
Option A — guard in the module:
```python
t_act_safe = params.T_act if params.T_act != 0.0 else 1e-6
arg = (t_tread_mean - T_REF_AGING) / t_act_safe
```

Option B — validate at construction time in `params.py`:
```python
@dataclass(frozen=True)
class DegradationParams:
    ...
    def __post_init__(self) -> None:
        if self.T_act <= 0:
            raise ValueError(f"T_act must be > 0, got {self.T_act}")
```

Option B is preferred because it surfaces the invalid parameter at the
point of construction rather than mid-simulation.

---

### [MEDIUM] ZeroDivisionError when `ThermalParams.sigma_T == 0`

**File:** `packages/core/src/f1_core/physics/module_d.py:60`

**Issue:**
The Grosch temperature factor computes:

```python
temp_factor = np.exp(-(dT * dT) / (2.0 * params_thermal.sigma_T * params_thermal.sigma_T))
```

`sigma_T` is the bell-curve half-width. If `sigma_T == 0` (another
plausible calibration sweep edge case), numpy divides by zero, producing
`inf` in the exponent, and `exp(-inf) = 0.0` for all tires. This makes
`mu = 0` for the entire run — silently wrong physics rather than a crash
(numpy float division by zero produces `inf`/`nan` without raising).

Worse, at exactly `dT == 0` AND `sigma_T == 0`, numpy produces `0.0 / 0.0 = nan`,
which then makes `exp(nan) = nan`, setting `mu = nan` for all tires and
propagating NaN through the rest of the simulation.

**Fix:**
Same two options as above. In `ThermalParams.__post_init__`:
```python
if self.sigma_T <= 0:
    raise ValueError(f"sigma_T must be > 0, got {self.sigma_T}")
```

Or in `module_d.py`:
```python
sigma_sq = max(params_thermal.sigma_T ** 2, 1e-6)
temp_factor = np.exp(-(dT * dT) / (2.0 * sigma_sq))
```

---

### [MEDIUM] `SlipState` contract is missing the `p_rr` field present in `SlipSample`

**File:** `packages/core/src/f1_core/contracts.py:93–109`

**Issue:**
`SlipState` (the typed contract for Module E output) declares:

```python
@dataclass(frozen=True)
class SlipState:
    t: F64Array
    theta: F64Array
    alpha: F64Array
    v_sy: F64Array
    p_slide: F64Array
    p_total: F64Array
```

But the actual return type of `slip_inversion_step` in `module_e.py` is
`SlipSample`, which includes `p_rr: F64Array` as a separate field. The
orchestrator accesses `slip.p_slide` and `slip.p_total` correctly (via
`SlipSample`), but `SlipState` is the published API contract. Any downstream
consumer (e.g., the Phase 4 API layer) that accepts `SlipState` will be
unable to access `p_rr`, which is needed for energy accounting.

Additionally, `WheelLoads`, `ContactPatch`, `SlipState`, `ThermalState`, and
`DegradationState` in `contracts.py` are defined but not returned by any
module implementation — the orchestrator uses raw arrays and local dataclasses
(`SlipSample`). The typed contracts are currently dead code with respect to the
orchestrator, creating a maintenance gap: the contracts describe the intended
interface but not the actual one.

**Fix:**
Add `p_rr` to `SlipState`:
```python
@dataclass(frozen=True)
class SlipState:
    t: F64Array
    theta: F64Array
    alpha: F64Array
    v_sy: F64Array
    p_slide: F64Array
    p_rr: F64Array      # add this
    p_total: F64Array
```

Then either (a) have `slip_inversion_step` return a `SlipState` (replacing
`SlipSample`) or (b) add a conversion step. The broader question of whether
the orchestrator should return typed contract objects instead of raw arrays is
a design decision, but the `p_rr` omission is an immediate correctness gap in
the contract.

---

### [LOW] `_t_air_at` docstring says "interpolate" but always returns `iloc[0]`

**File:** `packages/core/src/f1_core/physics/orchestrator.py:110–114`

**Issue:**
```python
def _t_air_at(artifact: StintArtifact, idx: int, t_now: float) -> float:  # noqa: ARG001
    """Interpolate air temperature from weather data at current stint time."""
    if artifact.weather.empty or "AirTemp" not in artifact.weather.columns:
        return 25.0
    return float(artifact.weather["AirTemp"].iloc[0])
```

The docstring says "interpolate" and the signature accepts `idx` and `t_now`,
but the implementation always returns the first weather sample. The `noqa:
ARG001` correctly suppresses the unused-argument lint warning, but the
misleading docstring will confuse future implementers (e.g., when Phase 4
wires in real time-varying weather).

**Fix:**
Update the docstring to reflect the Phase 2 placeholder behaviour:
```python
def _t_air_at(artifact: StintArtifact, idx: int, t_now: float) -> float:  # noqa: ARG001
    """Return air temperature [°C] at the given simulation time.

    Phase 2 placeholder: returns the first weather sample's AirTemp for the
    full stint. Phase 4 will implement time-linear interpolation using
    artifact.weather["SessionTime"] and t_now.
    """
```

---

### [LOW] `_aggregate_per_lap` comment incorrectly claims `sim_t` is non-monotonic

**File:** `packages/core/src/f1_core/physics/orchestrator.py:133–136`

**Issue:**
```python
# Implementation note: FastF1 car_data["Time"] is per-lap (resets to 0 at
# each lap boundary), so `sim_t` is non-monotonic across laps. We therefore
# partition samples using cumulative per-lap sample counts...
```

`sim_t` is `kstate.t`, which is the output of `process_stint`. Inside
`process_stint`, line 261 does `t = t - t[0]`, making it zero-based and
monotonically increasing for the full stint. `car_data["Time"]` is described
as a "stint-relative timedelta" in the module docstring (not per-lap), so
the comment's claim that it resets at each lap boundary is incorrect.

The duration-based partitioning is still correct and robust, but the stated
rationale is wrong. This can mislead future developers who may incorrectly
believe `sim_t` needs special handling.

**Fix:**
```python
# Implementation note: We partition samples by lap duration rather than
# by time comparison, because FastF1 does not always expose per-lap
# time boundaries in car_data. This is robust to any time reference frame.
```

---

### [LOW] No NaN sentinel on telemetry inputs in Module A

**File:** `packages/core/src/f1_core/physics/module_a.py:263–266`

**Issue:**
```python
v_kmh = car["Speed"].to_numpy(dtype=float)
v = v_kmh / 3.6
```

FastF1 telemetry can contain `NaN` in `Speed`, `RPM`, or `nGear` columns
(e.g., during slow-zone periods or data dropout). A `NaN` in `v` propagates
silently through `a_lat`, `a_long`, and into every downstream module. The
final per-lap table would show `nan` in Grip%, T_tread, and E_tire columns
without any logged event or exception.

The data quality pipeline (QualityReport) upstream may have already flagged
this, but Module A itself has no defence.

**Fix:**
Add a NaN count check and log a warning if significant:
```python
v_kmh = car["Speed"].to_numpy(dtype=float)
nan_count = np.isnan(v_kmh).sum()
if nan_count > 0:
    # Forward-fill NaN gaps (typically 1-2 samples during data dropout)
    v_kmh = pd.Series(v_kmh).ffill().bfill().to_numpy(dtype=float)
v = v_kmh / 3.6
```

Or, at minimum, raise a `ValueError` if the NaN fraction exceeds a threshold,
so the error surfaces cleanly rather than propagating silently.

---

### [LOW] `StintPreprocessor` protocol is not satisfied by `module_a.process_stint`

**File:** `packages/core/src/f1_core/physics/protocols.py:17–28`

**Issue:**
`StintPreprocessor` is a `@runtime_checkable Protocol` that requires
`self.process_stint(artifact, aero_params)` as an instance method. The actual
implementation in `module_a.py` is a module-level function
`process_stint(artifact, aero_params)`, not a method on any class. The
`isinstance(module_a, StintPreprocessor)` check (which `@runtime_checkable`
enables) would return `False`.

Since the protocol is never asserted anywhere in the current codebase, this
causes no runtime failure. But if Plan 07's architecture tests use
`isinstance` or pyright enforces the protocol, the mismatch will surface as
a test failure or type error.

**Fix:**
Either (a) remove `StintPreprocessor` if it is not needed (the orchestrator
calls `process_stint` as a function, not through the protocol), or (b) wrap
the function in a class:
```python
class ModuleAPreprocessor:
    def process_stint(self, artifact, aero_params):
        return process_stint(artifact, aero_params)
```

---

_Reviewed: 2026-04-23_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
