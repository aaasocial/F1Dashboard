---
phase: 02-physics-model-modules-a-g
plan: 03
type: execute
wave: 1
depends_on: [01]
files_modified:
  - packages/core/src/f1_core/physics/module_b.py
  - packages/core/src/f1_core/physics/module_c.py
  - packages/core/tests/physics/test_module_b.py
  - packages/core/tests/physics/test_module_c.py
autonomous: true
requirements: [PHYS-02, PHYS-03]
tags: [physics, loads, forces, module-b, module-c]

must_haves:
  truths:
    - "Module B per-timestep step() returns a (4,) ndarray of F_z values (FL/FR/RL/RR order) with the 50 N floor clip"
    - "ΣF_z (pre-clip) = M_tot·g + F_aero(V) within rtol=1e-10 on synthetic inputs outside clip region (PHYS-02, Criterion 1)"
    - "Module C per-timestep step() returns two (4,) ndarrays (f_y, f_x) such that ΣF_y = M·a_lat exactly (rtol=1e-12)"
    - "Module C applies brake bias to front/rear during braking and zero power to fronts (RWD) during acceleration"
    - "Every equation cites its model_spec.md section (§B.1–B.5 / §C.1–C.3) and Castellano (2021) source paper"
  artifacts:
    - path: "packages/core/src/f1_core/physics/module_b.py"
      provides: "wheel_loads_step(v, a_lat, a_long, params) -> (4,) F_z array + unclipped variant"
      exports: ["wheel_loads_step", "_wheel_loads_step_unclipped"]
    - path: "packages/core/src/f1_core/physics/module_c.py"
      provides: "force_distribution_step(f_z, v, a_lat, a_long, params) -> (f_y, f_x)"
      exports: ["force_distribution_step"]
  key_links:
    - from: "packages/core/src/f1_core/physics/module_b.py"
      to: "packages/core/src/f1_core/physics/constants.py"
      via: "import M_TOT, WB, T_F, T_R, RHO_AIR, G"
      pattern: "from f1_core.physics.constants import"
    - from: "packages/core/src/f1_core/physics/module_c.py"
      to: "packages/core/src/f1_core/physics/constants.py"
      via: "import C_RR for drag is OUT OF SCOPE; C only needs RHO_AIR via AeroParams.C_DA"
      pattern: "RHO_AIR"
---

<objective>
Implement Modules B and C — vertical load distribution and total-force distribution — as per-timestep closed-form functions with exact force-balance invariants (PHYS-02, PHYS-03). Both satisfy Criterion 1 from ROADMAP.md ("ΣF_z equals total weight plus aerodynamic downforce within tolerance, ΣF_y equals M·a_lat within tolerance").

These two modules are grouped because C's output depends on B's output (per-tire load shares drive C's force distribution), but both are pure functions of the current-timestep kinematic slice — they have no thermal/degradation state dependency. Implementing them together lets the plan own exactly one closed force-balance subsystem.

Output: Two new module files + two fully-implemented test files exercising algebraic identity closures (hypothesis-style), shape contracts, sign conventions, and edge cases (braking vs power, clip boundary).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/02-physics-model-modules-a-g/02-CONTEXT.md
@.planning/phases/02-physics-model-modules-a-g/02-RESEARCH.md
@model_spec.md
@packages/core/src/f1_core/physics/constants.py
@packages/core/src/f1_core/physics/params.py

<interfaces>
From f1_core.physics.params (frozen dataclasses — import, don't redefine):
```python
@dataclass(frozen=True)
class AeroParams:
    C_LA: float
    C_DA: float
    xi: float           # aero balance, front fraction
    K_rf_split: float   # K_rf / (K_rf + K_rr)
    WD: float           # static front weight fraction
    H_CG: float
    BB: float           # brake bias, front fraction
```

From f1_core.physics.constants:
```python
M_TOT: float         # 848.0 kg (dry + nominal fuel)
WB: float = 3.6
T_F: float = 1.60
T_R: float = 1.60
RHO_AIR: float = 1.20
G: float = 9.81
```

Per-tire index convention (enforced across B, C, D, E, F, G):
  0 = FL (front-left)
  1 = FR (front-right)
  2 = RL (rear-left)
  3 = RR (rear-right)
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement Module B (vertical loads) with hypothesis invariant tests</name>
  <files>
    packages/core/src/f1_core/physics/module_b.py,
    packages/core/tests/physics/test_module_b.py
  </files>
  <read_first>
    - model_spec.md §B.1, §B.2, §B.3, §B.4, §B.5
    - packages/core/src/f1_core/physics/constants.py (M_TOT, WB, T_F, T_R, RHO_AIR, G values)
    - packages/core/src/f1_core/physics/params.py (AeroParams fields)
    - .planning/phases/02-physics-model-modules-a-g/02-RESEARCH.md §"Pattern 1" and §"Pitfall 2"
  </read_first>
  <behavior>
    - Test 1: For `v=70, a_lat=0, a_long=0`, ΣF_z = M_TOT · G + 0.5·RHO_AIR·C_LA·v² within rtol=1e-10
    - Test 2: Return shape is exactly `(4,)` float64
    - Test 3: Sign convention — at `a_lat > 0` (right turn), left tires (indices 0=FL, 2=RL) carry more load than right tires (1=FR, 3=RR)
    - Test 4: At `a_long > 0` (acceleration), rear tires (2=RL, 3=RR) carry more load than fronts
    - Test 5: `_wheel_loads_step_unclipped(v=20, a_lat=50, a_long=0, params=nominal)` — one inside tire should go near-zero or negative; `wheel_loads_step` with the same inputs returns F_z ≥ 50 N everywhere (clip fires)
    - Test 6 (hypothesis): For v ∈ [20, 90] m/s, a_lat ∈ [-25, 25] m/s², a_long ∈ [-30, 15] m/s² (clip-free region), `_wheel_loads_step_unclipped` satisfies ΣF_z = M_TOT·G + F_aero to rtol=1e-10 on 100 random draws
    - Test 7: Aero split — with ξ=1.0, all aero downforce goes to front axle; with ξ=0.0, all to rear
  </behavior>
  <action>
    Create `packages/core/src/f1_core/physics/module_b.py` with this EXACT implementation:

    ```python
    """Module B — Vertical loads per tire (model_spec.md §B.1–§B.5).

    Source: Castellano et al. (2021), Eqs. 1–9, with simplified elastic lateral
    transfer (CONTEXT.md §Specifics) because roll-angle sensors are unavailable.

    Per-tire index convention: 0=FL, 1=FR, 2=RL, 3=RR.
    Sign conventions (model_spec.md §B.5):
      - a_lat > 0  → right turn, loads LEFT tires  (FL, RL)
      - a_long > 0 → acceleration,  loads REAR tires (RL, RR)

    This module is pure numpy — no Python for-loop over tires. RESEARCH.md
    §"Pattern 1" and PHYS-09 architecture test enforce this.
    """
    from __future__ import annotations

    import numpy as np

    from f1_core.contracts import F64Array
    from f1_core.physics.constants import G, M_TOT, RHO_AIR, T_F, T_R, WB
    from f1_core.physics.params import AeroParams

    # Clip floor — model_spec.md §B.5 "Floor". Prevents division-by-zero in
    # Modules D/E when vertical curvature produces near-zero loads at crests.
    F_Z_FLOOR_N: float = 50.0


    def _wheel_loads_step_unclipped(
        v: float,
        a_lat: float,
        a_long: float,
        params: AeroParams,
    ) -> F64Array:
        """Per-tire F_z BEFORE the 50 N floor clip.

        Used by invariant tests where the algebraic identity
        ΣF_z = M_tot·g + F_aero must hold exactly (Pitfall 2, RESEARCH.md).
        """
        # Static loads — model_spec §B.1 (Castellano 2021 Eq. 1)
        sl_f = M_TOT * params.WD / 2.0                  # per front tire
        sl_r = M_TOT * (1.0 - params.WD) / 2.0          # per rear tire

        # Longitudinal load transfer — §B.2 (Castellano Eq. 3)
        # a_long > 0 → loads rear (positive adds to rear, subtracts from front)
        dfz_long = (M_TOT * a_long * params.H_CG) / WB

        # Lateral load transfer (elastic approximation) — §B.3
        # Per-axle magnitude, distributed by roll-stiffness split.
        # a_lat > 0 → loads LEFT side tires
        k_split = params.K_rf_split
        dfz_lat_f = (M_TOT * a_lat * params.H_CG / T_F) * k_split
        dfz_lat_r = (M_TOT * a_lat * params.H_CG / T_R) * (1.0 - k_split)

        # Aerodynamic downforce — §B.4 (½·ρ·C_L·A·V²)
        fz_aero_total = 0.5 * RHO_AIR * params.C_LA * v * v
        fz_aero_front = params.xi * fz_aero_total         # split by balance
        fz_aero_rear = (1.0 - params.xi) * fz_aero_total
        # Within each axle, split L/R equally (§B.4 last sentence)
        fz_aero_per_front_tire = 0.5 * fz_aero_front
        fz_aero_per_rear_tire = 0.5 * fz_aero_rear

        # Per-tire assembly — §B.5
        f_z = np.array([
            sl_f - dfz_long + dfz_lat_f + fz_aero_per_front_tire,   # FL
            sl_f - dfz_long - dfz_lat_f + fz_aero_per_front_tire,   # FR
            sl_r + dfz_long + dfz_lat_r + fz_aero_per_rear_tire,    # RL
            sl_r + dfz_long - dfz_lat_r + fz_aero_per_rear_tire,    # RR
        ], dtype=np.float64)
        return f_z


    def wheel_loads_step(
        v: float,
        a_lat: float,
        a_long: float,
        params: AeroParams,
    ) -> F64Array:
        """Module B step — per-tire F_z with 50 N floor (model_spec §B.5).

        Args:
            v:      scalar speed [m/s]
            a_lat:  scalar lateral accel [m/s²]  (convention: > 0 = right turn)
            a_long: scalar long. accel  [m/s²]   (convention: > 0 = accelerate)
            params: AeroParams carrying C_LA, ξ, K_rf_split, WD, H_CG

        Returns:
            (4,) ndarray, FL/FR/RL/RR order, F_z ≥ 50 N each tire.

        Note: The clip uses np.maximum which has zero gradient at F_z=50 N. If
        Phase 3 calibration needs smooth gradients, swap for softplus (Pitfall 5,
        RESEARCH.md). Phase 2 does not need smooth gradients.
        """
        f_z_raw = _wheel_loads_step_unclipped(v, a_lat, a_long, params)
        return np.maximum(f_z_raw, F_Z_FLOOR_N)


    __all__ = ["F_Z_FLOOR_N", "_wheel_loads_step_unclipped", "wheel_loads_step"]
    ```

    Now rewrite `packages/core/tests/physics/test_module_b.py`:

    ```python
    """PHYS-02 — Module B (Vertical loads) invariants. model_spec.md §B."""
    from __future__ import annotations

    import numpy as np
    import pytest
    from hypothesis import given, strategies as st

    from f1_core.physics.constants import G, M_TOT, RHO_AIR
    from f1_core.physics.defaults import make_nominal_params
    from f1_core.physics.module_b import (
        F_Z_FLOOR_N,
        _wheel_loads_step_unclipped,
        wheel_loads_step,
    )


    def _expected_sum_fz(v: float, params) -> float:
        """ΣF_z = M·g + ½·ρ·C_LA·V²  (model_spec §B.5 invariant)."""
        return M_TOT * G + 0.5 * RHO_AIR * params.C_LA * v * v


    def test_module_b_returns_shape_4_float64():
        p = make_nominal_params().aero
        f_z = wheel_loads_step(v=70.0, a_lat=0.0, a_long=0.0, params=p)
        assert f_z.shape == (4,)
        assert f_z.dtype == np.float64


    def test_module_b_force_balance_exact_at_zero_accel():
        """model_spec §B.5: ΣF_z = M·g + F_aero when no load transfer."""
        p = make_nominal_params().aero
        f_z = _wheel_loads_step_unclipped(v=70.0, a_lat=0.0, a_long=0.0, params=p)
        np.testing.assert_allclose(f_z.sum(), _expected_sum_fz(70.0, p), rtol=1e-10)


    def test_module_b_right_turn_loads_left_tires():
        """Sign convention: a_lat > 0 → left tires (FL=0, RL=2) carry more."""
        p = make_nominal_params().aero
        f_z = _wheel_loads_step_unclipped(v=50.0, a_lat=20.0, a_long=0.0, params=p)
        assert f_z[0] > f_z[1], "FL must exceed FR in right turn"
        assert f_z[2] > f_z[3], "RL must exceed RR in right turn"


    def test_module_b_acceleration_loads_rear():
        """Sign convention: a_long > 0 → rear tires carry more."""
        p = make_nominal_params().aero
        f_z = _wheel_loads_step_unclipped(v=50.0, a_lat=0.0, a_long=10.0, params=p)
        assert (f_z[2] + f_z[3]) > (f_z[0] + f_z[1])


    def test_module_b_floor_clip_fires_on_extreme_lateral():
        """model_spec §B.5 floor: F_z ≥ 50 N even when unclipped would go negative."""
        p = make_nominal_params().aero
        # Extreme lateral: push one side's inside tires toward zero.
        f_z_raw = _wheel_loads_step_unclipped(v=20.0, a_lat=60.0, a_long=0.0, params=p)
        # Confirm unclipped would indeed dip below floor
        assert f_z_raw.min() < F_Z_FLOOR_N, (
            "Test precondition: unclipped F_z must dip below floor at these inputs"
        )
        f_z = wheel_loads_step(v=20.0, a_lat=60.0, a_long=0.0, params=p)
        assert f_z.min() >= F_Z_FLOOR_N


    def test_module_b_aero_split_xi_1_puts_all_on_front():
        """model_spec §B.4: ξ=1 → all aero to front axle."""
        from dataclasses import replace
        p = replace(make_nominal_params().aero, xi=1.0)
        f_z = _wheel_loads_step_unclipped(v=80.0, a_lat=0.0, a_long=0.0, params=p)
        # Front axle aero = F_aero_total; rear aero = 0
        f_aero_total = 0.5 * RHO_AIR * p.C_LA * 80.0 * 80.0
        static_f = M_TOT * p.WD / 2.0
        static_r = M_TOT * (1.0 - p.WD) / 2.0
        np.testing.assert_allclose(f_z[0], static_f + 0.5 * f_aero_total, rtol=1e-12)
        np.testing.assert_allclose(f_z[1], static_f + 0.5 * f_aero_total, rtol=1e-12)
        np.testing.assert_allclose(f_z[2], static_r, rtol=1e-12)
        np.testing.assert_allclose(f_z[3], static_r, rtol=1e-12)


    def test_module_b_aero_split_xi_0_puts_all_on_rear():
        from dataclasses import replace
        p = replace(make_nominal_params().aero, xi=0.0)
        f_z = _wheel_loads_step_unclipped(v=80.0, a_lat=0.0, a_long=0.0, params=p)
        f_aero_total = 0.5 * RHO_AIR * p.C_LA * 80.0 * 80.0
        static_f = M_TOT * p.WD / 2.0
        static_r = M_TOT * (1.0 - p.WD) / 2.0
        np.testing.assert_allclose(f_z[0], static_f, rtol=1e-12)
        np.testing.assert_allclose(f_z[2], static_r + 0.5 * f_aero_total, rtol=1e-12)


    @given(
        v=st.floats(min_value=20.0, max_value=90.0, allow_nan=False, allow_infinity=False),
        a_lat=st.floats(min_value=-25.0, max_value=25.0, allow_nan=False, allow_infinity=False),
        a_long=st.floats(min_value=-30.0, max_value=15.0, allow_nan=False, allow_infinity=False),
    )
    def test_module_b_force_balance_invariant_in_clip_free_range(v, a_lat, a_long):
        """hypothesis: ΣF_z = M·g + F_aero  (unclipped, in clip-free input region).

        Range chosen per RESEARCH.md §"Pitfall 2" so the 50 N floor never fires
        (otherwise the invariant cannot hold simultaneously with clipping).
        """
        p = make_nominal_params().aero
        f_z = _wheel_loads_step_unclipped(v=v, a_lat=a_lat, a_long=a_long, params=p)
        np.testing.assert_allclose(f_z.sum(), _expected_sum_fz(v, p), rtol=1e-10)
    ```
  </action>
  <verify>
    <automated>uv run pytest packages/core/tests/physics/test_module_b.py -x --benchmark-disable</automated>
  </verify>
  <acceptance_criteria>
    - `uv run pytest packages/core/tests/physics/test_module_b.py -x --benchmark-disable` exits 0 with 8 tests passing (7 explicit + hypothesis property test)
    - `grep -c "model_spec.md §B" packages/core/src/f1_core/physics/module_b.py` returns at least 5 (one citation per sub-section B.1–B.5)
    - `grep -c "Castellano" packages/core/src/f1_core/physics/module_b.py` returns at least 1
    - `grep -q "for " packages/core/src/f1_core/physics/module_b.py` returns NO python for-loop in module_b.py (per RESEARCH.md §"Pattern 1" / Pitfall 5)
    - `grep -q "pytest.skip" packages/core/tests/physics/test_module_b.py` returns NO matches (every stub replaced)
    - Module_b.py uses the `np.array([...])` pattern (4-element literal constructor), NOT a Python loop, as the vectorization
  </acceptance_criteria>
  <done>Module B returns per-tire F_z with correct signs, clips to 50 N floor, satisfies the ΣF_z = M·g + F_aero identity to rtol=1e-10 across 100 random clip-free samples; every eq cited.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement Module C (force distribution) with closure identity test</name>
  <files>
    packages/core/src/f1_core/physics/module_c.py,
    packages/core/tests/physics/test_module_c.py
  </files>
  <read_first>
    - model_spec.md §C.1, §C.2, §C.3
    - packages/core/src/f1_core/physics/constants.py (RHO_AIR, M_TOT)
    - packages/core/src/f1_core/physics/params.py (AeroParams.C_DA, BB)
    - packages/core/src/f1_core/physics/module_b.py (to understand f_z input shape from Task 1)
  </read_first>
  <behavior>
    - Test 1: For any f_z input (4,) from Module B, ΣF_y = M_TOT · a_lat exactly (rtol=1e-12 — pure load-proportional allocation, no clipping)
    - Test 2: For F_x,G > 0 (acceleration), F_x,FL = F_x,FR = 0 (RWD per §C.3)
    - Test 3: For F_x,G < 0 (braking), front fraction of total braking force = BB · |F_x,G|
    - Test 4: Returns tuple (f_y, f_x), both shape (4,) float64
    - Test 5 (hypothesis): For a_lat ∈ [-30, 30], a_long ∈ [-40, 15], v ∈ [20, 90] with nominal params, ΣF_y identity holds to rtol=1e-12 on 100 samples
  </behavior>
  <action>
    Create `packages/core/src/f1_core/physics/module_c.py`:

    ```python
    """Module C — Force distribution (model_spec.md §C.1–§C.3).

    Source: Castellano et al. (2021), Eqs. 10–27.

    Distributes total lateral + longitudinal forces proportionally to vertical
    load share per tire. Brake bias scales front/rear during braking; power is
    applied to rear axle only (RWD per CONTEXT.md constraints).

    Per-tire index convention: 0=FL, 1=FR, 2=RL, 3=RR.
    """
    from __future__ import annotations

    import numpy as np

    from f1_core.contracts import F64Array
    from f1_core.physics.constants import M_TOT, RHO_AIR
    from f1_core.physics.params import AeroParams


    def force_distribution_step(
        f_z: F64Array,            # shape (4,) from Module B
        v: float,
        a_lat: float,
        a_long: float,
        params: AeroParams,
    ) -> tuple[F64Array, F64Array]:
        """Distribute total F_y and F_x across the four tires.

        Args:
            f_z:    (4,) per-tire vertical loads from Module B (FL/FR/RL/RR)
            v:      scalar speed [m/s]
            a_lat:  scalar lateral accel [m/s²]
            a_long: scalar long accel [m/s²]
            params: AeroParams carrying C_DA, BB

        Returns:
            (f_y, f_x): each (4,) ndarray, FL/FR/RL/RR.
            ΣF_y = M·a_lat exactly.
            ΣF_x = M·a_long − F_drag(V).

        Citations (model_spec.md):
          §C.1 total forces from Newton's 2nd law, minus drag
          §C.2 load-proportional lateral distribution (Castellano Eq. 10–14)
          §C.3 brake-bias + RWD longitudinal distribution (Castellano Eq. 15–27)
        """
        # §C.1 — total lateral
        f_y_total = M_TOT * a_lat

        # §C.1 — total longitudinal (includes aerodynamic drag subtraction)
        f_drag = 0.5 * RHO_AIR * params.C_DA * v * v
        f_x_total = M_TOT * a_long - f_drag

        # Load fractions — used by §C.2 and §C.3 (Castellano Eq. 10)
        f_z_sum = f_z.sum()
        load_frac = f_z / f_z_sum   # (4,), sums to 1.0

        # §C.2 — lateral force, purely load-proportional (sign: carries a_lat sign)
        f_y = f_y_total * load_frac

        # §C.3 — longitudinal: split into brake and power components, combine.
        # brake active when f_x_total < 0; per-tire magnitude proportional to load,
        # then scaled by BB on fronts and (1-BB) on rears.
        brake_scale = np.array([
            params.BB,        # FL
            params.BB,        # FR
            1.0 - params.BB,  # RL
            1.0 - params.BB,  # RR
        ], dtype=np.float64)
        # 2.0 * brake_scale because axle total equals BB*f_x_total on front,
        # distributed evenly L/R by load_frac; equivalent to
        # f_x_brake_i = min(f_x_total*load_frac_i, 0) * brake_scale_i * 2.0
        # WRONG — instead use the clean form: split total brake force to axles
        # by BB/(1-BB), then split within axle by load fraction relative to axle total.
        # (See Castellano Eq. 15–18.)
        if f_x_total < 0.0:
            f_x_front_axle = params.BB * f_x_total         # negative
            f_x_rear_axle = (1.0 - params.BB) * f_x_total  # negative
            # Relative load within each axle (guarded against f_z=0)
            f_z_front_sum = f_z[0] + f_z[1]
            f_z_rear_sum = f_z[2] + f_z[3]
            if f_z_front_sum > 0:
                f_x_brake = np.array([
                    f_x_front_axle * (f_z[0] / f_z_front_sum),
                    f_x_front_axle * (f_z[1] / f_z_front_sum),
                    f_x_rear_axle * (f_z[2] / f_z_rear_sum) if f_z_rear_sum > 0 else 0.0,
                    f_x_rear_axle * (f_z[3] / f_z_rear_sum) if f_z_rear_sum > 0 else 0.0,
                ], dtype=np.float64)
            else:
                f_x_brake = np.zeros(4, dtype=np.float64)
        else:
            f_x_brake = np.zeros(4, dtype=np.float64)

        # Power component — §C.3: RWD, all positive F_x on rears, split by rear load frac
        if f_x_total > 0.0:
            f_z_rear_sum = f_z[2] + f_z[3]
            if f_z_rear_sum > 0:
                f_x_power = np.array([
                    0.0,                                              # FL
                    0.0,                                              # FR
                    f_x_total * (f_z[2] / f_z_rear_sum),              # RL
                    f_x_total * (f_z[3] / f_z_rear_sum),              # RR
                ], dtype=np.float64)
            else:
                f_x_power = np.zeros(4, dtype=np.float64)
        else:
            f_x_power = np.zeros(4, dtype=np.float64)

        f_x = f_x_brake + f_x_power

        # Ensure we produced arrays (type-narrow for callers)
        return f_y.astype(np.float64), f_x.astype(np.float64)


    __all__ = ["force_distribution_step"]
    ```

    Now rewrite `packages/core/tests/physics/test_module_c.py`:

    ```python
    """PHYS-03 — Module C (Force distribution) invariants. model_spec.md §C."""
    from __future__ import annotations

    import numpy as np
    import pytest
    from hypothesis import given, strategies as st

    from f1_core.physics.constants import M_TOT, RHO_AIR
    from f1_core.physics.defaults import make_nominal_params
    from f1_core.physics.module_b import wheel_loads_step
    from f1_core.physics.module_c import force_distribution_step


    def test_module_c_returns_tuple_of_4_vectors():
        p = make_nominal_params().aero
        f_z = wheel_loads_step(v=60.0, a_lat=5.0, a_long=0.0, params=p)
        f_y, f_x = force_distribution_step(f_z=f_z, v=60.0, a_lat=5.0, a_long=0.0, params=p)
        assert f_y.shape == (4,)
        assert f_x.shape == (4,)
        assert f_y.dtype == np.float64
        assert f_x.dtype == np.float64


    def test_module_c_sum_f_y_equals_m_a_lat_exactly():
        """model_spec §C.2: ΣF_y,i = M·a_lat (pure load allocation, exact identity)."""
        p = make_nominal_params().aero
        f_z = wheel_loads_step(v=60.0, a_lat=10.0, a_long=0.0, params=p)
        f_y, _ = force_distribution_step(f_z=f_z, v=60.0, a_lat=10.0, a_long=0.0, params=p)
        np.testing.assert_allclose(f_y.sum(), M_TOT * 10.0, rtol=1e-12)


    def test_module_c_power_only_on_rear_rwd():
        """model_spec §C.3: F_x^power = 0 on FL, FR during acceleration."""
        p = make_nominal_params().aero
        f_z = wheel_loads_step(v=60.0, a_lat=0.0, a_long=8.0, params=p)
        _, f_x = force_distribution_step(f_z=f_z, v=60.0, a_lat=0.0, a_long=8.0, params=p)
        # f_x_total = M·a_long − f_drag; still > 0 at a_long=8 for nominal C_DA
        f_drag = 0.5 * RHO_AIR * p.C_DA * 60.0 * 60.0
        f_x_total = M_TOT * 8.0 - f_drag
        assert f_x_total > 0.0, "precondition: test assumes positive net longitudinal force"
        np.testing.assert_allclose(f_x[0], 0.0, atol=1e-12)  # FL
        np.testing.assert_allclose(f_x[1], 0.0, atol=1e-12)  # FR
        # Rear total matches f_x_total exactly
        np.testing.assert_allclose(f_x[2] + f_x[3], f_x_total, rtol=1e-12)


    def test_module_c_braking_applies_brake_bias():
        """model_spec §C.3: braking total front = BB·|F_x,G|, rear = (1-BB)·|F_x,G|."""
        p = make_nominal_params().aero
        f_z = wheel_loads_step(v=50.0, a_lat=0.0, a_long=-15.0, params=p)
        _, f_x = force_distribution_step(f_z=f_z, v=50.0, a_lat=0.0, a_long=-15.0, params=p)
        f_drag = 0.5 * RHO_AIR * p.C_DA * 50.0 * 50.0
        f_x_total = M_TOT * (-15.0) - f_drag   # strongly negative
        front_total = f_x[0] + f_x[1]
        rear_total = f_x[2] + f_x[3]
        np.testing.assert_allclose(front_total, p.BB * f_x_total, rtol=1e-10)
        np.testing.assert_allclose(rear_total, (1.0 - p.BB) * f_x_total, rtol=1e-10)


    def test_module_c_load_proportional_allocation_f_y():
        """Heavier tire gets proportionally more F_y."""
        p = make_nominal_params().aero
        f_z = wheel_loads_step(v=60.0, a_lat=15.0, a_long=0.0, params=p)
        f_y, _ = force_distribution_step(f_z=f_z, v=60.0, a_lat=15.0, a_long=0.0, params=p)
        # f_y / f_z should be constant across tires (ratio = a_lat in g-equivalent)
        ratios = f_y / f_z
        np.testing.assert_allclose(ratios, np.full(4, ratios[0]), rtol=1e-12)


    @given(
        v=st.floats(min_value=20.0, max_value=90.0, allow_nan=False, allow_infinity=False),
        a_lat=st.floats(min_value=-30.0, max_value=30.0, allow_nan=False, allow_infinity=False),
        a_long=st.floats(min_value=-40.0, max_value=15.0, allow_nan=False, allow_infinity=False),
    )
    def test_module_c_sum_f_y_identity_holds_for_any_kinematic(v, a_lat, a_long):
        """hypothesis: ΣF_y = M·a_lat for any reasonable kinematic state."""
        p = make_nominal_params().aero
        f_z = wheel_loads_step(v=v, a_lat=a_lat, a_long=a_long, params=p)
        f_y, _ = force_distribution_step(f_z=f_z, v=v, a_lat=a_lat, a_long=a_long, params=p)
        np.testing.assert_allclose(f_y.sum(), M_TOT * a_lat, rtol=1e-12)
    ```
  </action>
  <verify>
    <automated>uv run pytest packages/core/tests/physics/test_module_c.py -x --benchmark-disable</automated>
  </verify>
  <acceptance_criteria>
    - `uv run pytest packages/core/tests/physics/test_module_c.py -x --benchmark-disable` exits 0 with 6 tests passing
    - `grep -c "model_spec.md §C" packages/core/src/f1_core/physics/module_c.py` returns at least 3 (C.1, C.2, C.3 cited)
    - `grep -c "Castellano" packages/core/src/f1_core/physics/module_c.py` returns at least 1
    - `grep -qE "^\s*for [a-z_]+ in " packages/core/src/f1_core/physics/module_c.py` returns NO matches (no per-tire Python for-loops)
    - `grep -q "pytest.skip" packages/core/tests/physics/test_module_c.py` returns NO matches
    - Full physics suite still green: `uv run pytest packages/core/tests/physics/ --benchmark-disable` exits 0
  </acceptance_criteria>
  <done>Module C returns (f_y, f_x); ΣF_y = M·a_lat exactly (rtol=1e-12) across 100 hypothesis samples; RWD + brake-bias distribution correct; no Python for-loops over tires.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Kinematic scalars → Modules B/C | Values from Module A's output arrays, already validated for finiteness there. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-07 | Tampering | Division by zero if f_z_sum or axle sums are zero | mitigate | Module C explicitly guards against f_z_front_sum == 0 and f_z_rear_sum == 0 before dividing. Module B's 50 N floor ensures f_z_sum ≥ 200 N in practice. |
| T-02-08 | Integrity | 50 N clip breaks ΣF_z identity at extreme inputs (Pitfall 2) | mitigate | `_wheel_loads_step_unclipped` separates the algebraic identity from the physical guard; invariant tests call unclipped variant and restrict hypothesis to clip-free input ranges. |
</threat_model>

<verification>
- `uv run pytest packages/core/tests/physics/test_module_b.py packages/core/tests/physics/test_module_c.py -x --benchmark-disable` — all tests pass
- `uv run pytest packages/core/tests/physics/ --benchmark-disable` — full physics suite still green (other stubs skip)
- No Python for-loops over tires in either module file
- Every equation cites its model_spec.md section and (where applicable) Castellano (2021)
</verification>

<success_criteria>
- Module B: wheel_loads_step + _wheel_loads_step_unclipped implemented, 50 N floor applied in clipped variant
- Module C: force_distribution_step implemented, ΣF_y = M·a_lat identity exact
- Hypothesis tests: B invariant on 100 samples (clip-free range), C invariant on 100 samples (any range)
- PHYS-02 force balance closure verified (unclipped)
- PHYS-03 ΣF_y identity verified to rtol=1e-12
- RWD + brake-bias sign conventions correct
</success_criteria>

<output>
After completion, create `.planning/phases/02-physics-model-modules-a-g/02-03-SUMMARY.md` documenting:
- Observed F_z per-tire ranges on canonical fixture (min, max, mean for each of FL/FR/RL/RR)
- How many times the 50 N clip fires on canonical fixture (diagnostic for Plan 07 benchmark realism)
- Any deviations from Castellano (2021) equations (there should be none)
</output>
