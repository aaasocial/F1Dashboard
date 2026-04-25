---
phase: 02-physics-model-modules-a-g
plan: 04
type: execute
wave: 1
depends_on: [01]
files_modified:
  - packages/core/src/f1_core/physics/module_d.py
  - packages/core/src/f1_core/physics/module_e.py
  - packages/core/tests/physics/test_module_d.py
  - packages/core/tests/physics/test_module_e.py
autonomous: true
requirements: [PHYS-04, PHYS-05]
tags: [physics, friction, slip, module-d, module-e]

must_haves:
  truths:
    - "Module D returns (a_cp, p_bar, mu) as three (4,) ndarrays; μ(T_opt, p̄_0) = μ_0 exactly (rtol=1e-12)"
    - "Module D reads T_tread from the PREVIOUS timestep (state.t_tread), not the current one (Pitfall 3)"
    - "Module E inverts the brush model: Θ = 1 − (1 − |F_y|/(μ·F_z))^(1/3), clipped to 1 on over-demand"
    - "Module E appends a StatusEvent when |F_y| > μ·F_z on any tire; event list capped at MAX_EVENTS=500"
    - "Module E P_slide,i = |F_y|·|V_sy| + |F_x|·|V_sx| is always ≥ 0"
    - "Every equation cites its model_spec.md section (§D.1–§D.5, §E.1–§E.7) plus source papers (Pacejka 2012, Grosch 1963, Greenwood-Williamson 1966)"
  artifacts:
    - path: "packages/core/src/f1_core/physics/module_d.py"
      provides: "contact_and_friction_step(f_z, t_tread_prev, mu_0, params) -> (a_cp, p_bar, mu)"
      exports: ["contact_and_friction_step"]
    - path: "packages/core/src/f1_core/physics/module_e.py"
      provides: "slip_inversion_step(f_y, f_x, mu, f_z, a_cp, v, v_sx_rear, t, params, events) -> SlipSample"
      exports: ["slip_inversion_step", "SlipSample"]
  key_links:
    - from: "packages/core/src/f1_core/physics/module_e.py"
      to: "packages/core/src/f1_core/physics/events.py"
      via: "StatusEvent construction + MAX_EVENTS enforcement"
      pattern: "StatusEvent|MAX_EVENTS"
    - from: "packages/core/src/f1_core/physics/module_d.py"
      to: "packages/core/src/f1_core/physics/constants.py"
      via: "B_TREAD_F, B_TREAD_R, R_0 imports"
      pattern: "from f1_core.physics.constants import"
---

<objective>
Implement Modules D and E — Hertzian contact + friction, and brush-model slip inversion with diagnostic event logging. D and E are grouped because E's inputs (a_cp, μ) come directly from D and both are closed-form per-tire math with no thermal state update (D *reads* T_tread but does not write it).

This plan satisfies PHYS-04 (μ identity) and PHYS-05 (Θ clip + event log, Criterion 3 of ROADMAP).

Output: Two module files + two real test files covering identity, clip behavior, and event-log cap.
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
@packages/core/src/f1_core/physics/events.py

<interfaces>
From f1_core.physics.params (frozen):
```python
@dataclass(frozen=True)
class FrictionParams:
    mu_0_fresh: float
    p_bar_0: float
    n: float
    c_py: float
    K_rad: float

@dataclass(frozen=True)
class ThermalParams:
    T_opt: float
    sigma_T: float
    # ... other fields (not used by D/E directly)
```

From f1_core.physics.constants:
```python
R_0: float = 0.330
B_TREAD_F: float = 0.15
B_TREAD_R: float = 0.20
C_RR: float = 0.012
```

From f1_core.physics.events:
```python
MAX_EVENTS: int = 500

@dataclass(frozen=True)
class StatusEvent:
    t: float
    tire_index: int
    kind: str
    message: str
    ratio: float
```

Per-tire index: 0=FL, 1=FR, 2=RL, 3=RR. b_tread per tire → (0.15, 0.15, 0.20, 0.20).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement Module D (Hertzian contact + friction) with μ identity test</name>
  <files>
    packages/core/src/f1_core/physics/module_d.py,
    packages/core/tests/physics/test_module_d.py
  </files>
  <read_first>
    - model_spec.md §D.1, §D.2, §D.3, §D.4, §D.5
    - packages/core/src/f1_core/physics/params.py (FrictionParams, ThermalParams)
    - packages/core/src/f1_core/physics/constants.py (R_0, B_TREAD_F, B_TREAD_R)
    - .planning/phases/02-physics-model-modules-a-g/02-RESEARCH.md §"Pitfall 3" (T_tread is from PREVIOUS step)
    - .planning/phases/02-physics-model-modules-a-g/02-RESEARCH.md §"Pitfall 4" (Arrhenius overflow not here — that's Module G, but Grosch g(T) is bounded by exp(0)=1 at T_opt)
  </read_first>
  <behavior>
    - Test 1: With `f_z_i = 5000 N` (all tires), a_cp,FL = √(2·R_0·5000/K_rad); assert per-tire against formula
    - Test 2: p_bar,i = f_z / (4·a_cp·b_tread) — b_tread = 0.15 for fronts, 0.20 for rears
    - Test 3: μ identity — when `t_tread_prev=T_opt` and `p_bar_i = friction.p_bar_0` on every tire, μ = μ_0 scalar exactly (rtol=1e-12)
    - Test 4: Grosch bell `g(T_opt) = 1.0` exactly
    - Test 5: At T far from T_opt (e.g., T_opt + 4σ_T), μ drops to μ_0·exp(-8)·(...) — well below 10% of μ_0
    - Test 6: Signature returns `(a_cp, p_bar, mu)` as a tuple of three (4,) ndarrays
  </behavior>
  <action>
    Create `packages/core/src/f1_core/physics/module_d.py`:

    ```python
    """Module D — Hertzian contact geometry + friction (model_spec.md §D.1–§D.5).

    Sources:
      §D.1 contact geometry: Gim (1988) via Ozerem & Morrey (2019)
      §D.3 load-dep friction: Greenwood & Williamson (1966)
      §D.4 temperature dep:   Grosch (1963) + Williams–Landel–Ferry (1955)
      §D.5 complete μ:        combines D.3 and D.4

    Per CONTEXT.md Pitfall 3: T_tread passed IN is from the previous timestep
    (state.t_tread), NOT the current step's freshly-integrated value. The
    orchestrator is responsible for calling D BEFORE F each timestep.
    """
    from __future__ import annotations

    import numpy as np

    from f1_core.contracts import F64Array
    from f1_core.physics.constants import B_TREAD_F, B_TREAD_R, R_0
    from f1_core.physics.params import FrictionParams, ThermalParams

    # Per-tire tread half-widths (FL, FR, RL, RR). Fronts narrower, rears wider.
    _B_TREAD_PER_TIRE: F64Array = np.array(
        [B_TREAD_F, B_TREAD_F, B_TREAD_R, B_TREAD_R], dtype=np.float64
    )


    def contact_and_friction_step(
        f_z: F64Array,              # (4,) from Module B
        t_tread_prev: F64Array,     # (4,) from SimulationState.t_tread (prev step)
        mu_0: float,                # current reference friction from SimulationState
        params_friction: FrictionParams,
        params_thermal: ThermalParams,
    ) -> tuple[F64Array, F64Array, F64Array]:
        """Compute contact-patch geometry and complete friction coefficient.

        Returns:
            a_cp:  (4,) contact-patch half-length [m]           — §D.1
            p_bar: (4,) mean contact pressure [Pa]               — §D.2
            mu:    (4,) complete friction coefficient [-]        — §D.5

        Equation references (all from model_spec.md):
            §D.1: a_cp,i = √(2·R_0·F_z,i/K_rad)
            §D.2: p̄_i = F_z,i / (4·a_cp,i·b_tread)
            §D.3: μ^pressure(p̄) = μ_0·(p̄_0/p̄)^(1−n)   [Greenwood-Williamson 1966]
            §D.4: g(T) = exp(−(T−T_opt)²/(2·σ_T²))    [Grosch 1963]
            §D.5: μ_i = μ_0(t)·(p̄_0/p̄_i)^(1−n)·g(T_tread,i)
        """
        # §D.1 — contact patch half-length (Gim 1988)
        a_cp = np.sqrt(2.0 * R_0 * f_z / params_friction.K_rad)

        # §D.2 — mean Hertzian contact pressure
        p_bar = f_z / (4.0 * a_cp * _B_TREAD_PER_TIRE)

        # §D.3 — load-dependent friction (Greenwood-Williamson)
        # exponent (1 − n); at p̄=p̄_0 this factor equals 1.0 (identity at ref pressure)
        pressure_factor = (params_friction.p_bar_0 / p_bar) ** (1.0 - params_friction.n)

        # §D.4 — Grosch bell-curve temperature factor; g(T_opt) = 1.0
        dT = t_tread_prev - params_thermal.T_opt
        temp_factor = np.exp(-(dT * dT) / (2.0 * params_thermal.sigma_T * params_thermal.sigma_T))

        # §D.5 — complete friction coefficient
        mu = mu_0 * pressure_factor * temp_factor

        return a_cp.astype(np.float64), p_bar.astype(np.float64), mu.astype(np.float64)


    __all__ = ["contact_and_friction_step"]
    ```

    Now rewrite `packages/core/tests/physics/test_module_d.py`:

    ```python
    """PHYS-04 — Module D (Hertzian contact + friction) invariants. model_spec.md §D."""
    from __future__ import annotations

    import numpy as np
    import pytest

    from f1_core.physics.constants import B_TREAD_F, B_TREAD_R, R_0
    from f1_core.physics.defaults import make_nominal_params
    from f1_core.physics.module_d import contact_and_friction_step


    def test_module_d_returns_three_4vectors():
        p = make_nominal_params()
        f_z = np.array([5000.0, 5000.0, 6000.0, 6000.0])
        t_tread = np.full(4, p.thermal.T_opt)
        a_cp, p_bar, mu = contact_and_friction_step(
            f_z=f_z, t_tread_prev=t_tread, mu_0=p.friction.mu_0_fresh,
            params_friction=p.friction, params_thermal=p.thermal,
        )
        assert a_cp.shape == (4,) and p_bar.shape == (4,) and mu.shape == (4,)
        assert a_cp.dtype == np.float64


    def test_module_d_a_cp_formula_sqrt_2_R_0_F_z_over_K_rad():
        """model_spec §D.1: a_cp,i = √(2·R_0·F_z,i/K_rad)."""
        p = make_nominal_params()
        f_z = np.array([3000.0, 4000.0, 5000.0, 6000.0])
        t_tread = np.full(4, p.thermal.T_opt)
        a_cp, _, _ = contact_and_friction_step(
            f_z=f_z, t_tread_prev=t_tread, mu_0=p.friction.mu_0_fresh,
            params_friction=p.friction, params_thermal=p.thermal,
        )
        expected = np.sqrt(2.0 * R_0 * f_z / p.friction.K_rad)
        np.testing.assert_allclose(a_cp, expected, rtol=1e-14)


    def test_module_d_p_bar_formula_uses_per_tire_b_tread():
        """model_spec §D.2: p̄_i = F_z,i/(4·a_cp·b_tread); b_tread = 0.15 front, 0.20 rear."""
        p = make_nominal_params()
        f_z = np.array([5000.0, 5000.0, 5000.0, 5000.0])
        t_tread = np.full(4, p.thermal.T_opt)
        a_cp, p_bar, _ = contact_and_friction_step(
            f_z=f_z, t_tread_prev=t_tread, mu_0=p.friction.mu_0_fresh,
            params_friction=p.friction, params_thermal=p.thermal,
        )
        expected_front = 5000.0 / (4.0 * a_cp[0] * B_TREAD_F)
        expected_rear = 5000.0 / (4.0 * a_cp[2] * B_TREAD_R)
        np.testing.assert_allclose(p_bar[0], expected_front, rtol=1e-14)
        np.testing.assert_allclose(p_bar[1], expected_front, rtol=1e-14)
        np.testing.assert_allclose(p_bar[2], expected_rear, rtol=1e-14)
        np.testing.assert_allclose(p_bar[3], expected_rear, rtol=1e-14)


    def test_module_d_mu_identity_at_T_opt_and_p_bar_0():
        """model_spec §D.5: μ(T_opt, p̄_0) = μ_0 exactly. PHYS-04 + Criterion 1.

        Construct f_z such that p̄ = p̄_0 on every tire, at T=T_opt.
        """
        p = make_nominal_params()
        # Solve p̄ = p̄_0:
        #   p̄_0 = f_z / (4·√(2·R_0·f_z/K_rad)·b_tread)
        #   => p̄_0 * 4 * b_tread = √(f_z) * √(2·R_0/K_rad)
        #   => f_z = (p̄_0 * 4 * b_tread)² · K_rad / (2·R_0)
        k_rad = p.friction.K_rad
        b_per = np.array([B_TREAD_F, B_TREAD_F, B_TREAD_R, B_TREAD_R])
        f_z_target = (p.friction.p_bar_0 * 4.0 * b_per) ** 2 * k_rad / (2.0 * R_0)
        t_tread = np.full(4, p.thermal.T_opt)
        _, p_bar, mu = contact_and_friction_step(
            f_z=f_z_target, t_tread_prev=t_tread, mu_0=p.friction.mu_0_fresh,
            params_friction=p.friction, params_thermal=p.thermal,
        )
        # Sanity: p̄ should equal p̄_0 on every tire
        np.testing.assert_allclose(p_bar, np.full(4, p.friction.p_bar_0), rtol=1e-12)
        # Identity: μ = μ_0 exactly
        np.testing.assert_allclose(mu, np.full(4, p.friction.mu_0_fresh), rtol=1e-12)


    def test_module_d_grosch_bell_returns_unity_at_T_opt():
        """model_spec §D.4: g(T_opt) = exp(0) = 1. At ref pressure μ = μ_0 · 1 · 1 = μ_0."""
        p = make_nominal_params()
        # Use high K_rad to stay near p̄_0 on nominal f_z
        f_z = np.array([5000.0] * 4)
        t_tread = np.full(4, p.thermal.T_opt)
        _, _, mu = contact_and_friction_step(
            f_z=f_z, t_tread_prev=t_tread, mu_0=1.0,
            params_friction=p.friction, params_thermal=p.thermal,
        )
        # At T_opt, temp factor is 1; mu = pressure_factor only
        _, p_bar, _ = contact_and_friction_step(
            f_z=f_z, t_tread_prev=t_tread, mu_0=1.0,
            params_friction=p.friction, params_thermal=p.thermal,
        )
        expected = (p.friction.p_bar_0 / p_bar) ** (1.0 - p.friction.n)
        np.testing.assert_allclose(mu, expected, rtol=1e-14)


    def test_module_d_mu_decays_away_from_T_opt():
        """Temperature factor bell-curve: μ at T_opt + 4σ drops below 2% of peak."""
        p = make_nominal_params()
        f_z = np.full(4, 5000.0)
        t_opt = p.thermal.T_opt
        sig = p.thermal.sigma_T
        t_tread_peak = np.full(4, t_opt)
        t_tread_far = np.full(4, t_opt + 4.0 * sig)
        _, _, mu_peak = contact_and_friction_step(
            f_z=f_z, t_tread_prev=t_tread_peak, mu_0=p.friction.mu_0_fresh,
            params_friction=p.friction, params_thermal=p.thermal,
        )
        _, _, mu_far = contact_and_friction_step(
            f_z=f_z, t_tread_prev=t_tread_far, mu_0=p.friction.mu_0_fresh,
            params_friction=p.friction, params_thermal=p.thermal,
        )
        # exp(-(4σ)²/(2σ²)) = exp(-8) ≈ 3.35e-4
        assert (mu_far < 0.02 * mu_peak).all()


    def test_module_d_uses_previous_t_tread_not_current():
        """Pitfall 3: Module D reads t_tread_prev; changing this argument changes the output.
        (If Module D accidentally used a current-step temperature, this test would not catch
        it directly, but the orchestrator test in Plan 06 verifies ordering. This test just
        confirms the parameter is actually consumed.)
        """
        p = make_nominal_params()
        f_z = np.full(4, 5000.0)
        _, _, mu_opt = contact_and_friction_step(
            f_z=f_z, t_tread_prev=np.full(4, p.thermal.T_opt),
            mu_0=p.friction.mu_0_fresh,
            params_friction=p.friction, params_thermal=p.thermal,
        )
        _, _, mu_cold = contact_and_friction_step(
            f_z=f_z, t_tread_prev=np.full(4, p.thermal.T_opt - 40.0),
            mu_0=p.friction.mu_0_fresh,
            params_friction=p.friction, params_thermal=p.thermal,
        )
        assert mu_cold[0] < mu_opt[0], "cold tread must give lower μ than at T_opt"
    ```
  </action>
  <verify>
    <automated>uv run pytest packages/core/tests/physics/test_module_d.py -x --benchmark-disable</automated>
  </verify>
  <acceptance_criteria>
    - `uv run pytest packages/core/tests/physics/test_module_d.py -x --benchmark-disable` exits 0 with 7 tests passing
    - `grep -c "model_spec.md §D" packages/core/src/f1_core/physics/module_d.py` returns at least 5 (D.1 through D.5 each cited)
    - `grep -c "Greenwood\|Grosch\|Gim" packages/core/src/f1_core/physics/module_d.py` returns at least 2 (multiple source papers cited)
    - `grep -qE "^\s*for [a-z_]+ in " packages/core/src/f1_core/physics/module_d.py` returns NO Python for-loops
    - `grep -q "pytest.skip" packages/core/tests/physics/test_module_d.py` returns NO matches
    - μ identity test (Criterion 1) passes to rtol=1e-12
  </acceptance_criteria>
  <done>Module D computes a_cp, p̄, and full μ(T, p̄); μ(T_opt, p̄_0)=μ_0 identity verified to rtol=1e-12; per-tire b_tread handled correctly; spec sections + source papers cited.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement Module E (slip inversion + event log) with cap enforcement</name>
  <files>
    packages/core/src/f1_core/physics/module_e.py,
    packages/core/tests/physics/test_module_e.py
  </files>
  <read_first>
    - model_spec.md §E.1, §E.2, §E.3, §E.4, §E.5, §E.6, §E.7
    - packages/core/src/f1_core/physics/events.py (StatusEvent, MAX_EVENTS=500)
    - packages/core/src/f1_core/physics/params.py (FrictionParams.c_py)
    - packages/core/src/f1_core/physics/constants.py (C_RR)
    - .planning/phases/02-physics-model-modules-a-g/02-RESEARCH.md §"Pitfall 6" (event log cap policy)
  </read_first>
  <behavior>
    - Test 1: When |F_y| = μ·F_z exactly on one tire, Θ on that tire = 1.0 (identity at full sliding)
    - Test 2: When |F_y| > μ·F_z (over-demand), Θ = 1.0 (clipped) AND one StatusEvent appended with `ratio > 1.0` and `kind="over_demand_lat"`
    - Test 3: When |F_y| = 0.5·μ·F_z, Θ ≈ 1 − (1-0.5)^(1/3) ≈ 0.206
    - Test 4: α_i = sgn(F_y)·arctan(3·μ·F_z·Θ/C_α); where C_α = c_py · a_cp²
    - Test 5: V_sy = V·sin(α); P_slide ≥ 0 always
    - Test 6: P_rr = C_RR · F_z · V (model_spec §E.6)
    - Test 7: Event cap — invoking Module E 600 times with over-demand inputs appends at most 500 events (rest are silently dropped, with truncated flag set)
  </behavior>
  <action>
    Create `packages/core/src/f1_core/physics/module_e.py`:

    ```python
    """Module E — Brush-model slip inversion + sliding power (model_spec.md §E.1–§E.7).

    Sources:
      §E.1 cornering stiffness: Pacejka (2012), Ch. 3
      §E.2 brush model:        Pacejka (2012), Ch. 3
      §E.5 sliding power:      Kobayashi et al. (2019); Castellano et al. (2021)

    Returns a SlipSample dataclass (local, per-timestep container) carrying the
    slip kinematics and dissipated power per tire. The caller appends to a
    shared events: list[StatusEvent] that is capped at MAX_EVENTS (Pitfall 6).
    """
    from __future__ import annotations

    from dataclasses import dataclass

    import numpy as np

    from f1_core.contracts import F64Array
    from f1_core.physics.constants import C_RR
    from f1_core.physics.events import MAX_EVENTS, StatusEvent
    from f1_core.physics.params import FrictionParams

    _TIRE_NAMES: tuple[str, ...] = ("FL", "FR", "RL", "RR")


    @dataclass(frozen=True)
    class SlipSample:
        """Per-timestep output of Module E (4,) arrays."""
        theta: F64Array     # brush-model slip parameter [0, 1]
        alpha: F64Array     # slip angle [rad]
        v_sy: F64Array      # lateral slip velocity [m/s]
        p_slide: F64Array   # sliding power per tire [W]
        p_rr: F64Array      # rolling-resistance power per tire [W]
        p_total: F64Array   # P_slide + P_rr [W]


    def _v_sx_per_tire(v_sx_rear: float) -> F64Array:
        """Distribute V_sx across tires.

        For RWD, fronts have V_sx ≈ 0 in steady cornering; only rears carry the
        driven-wheel slip. During braking all four tires slip, but Phase 2 uses
        the kinematic rear V_sx estimate as the rear magnitude and zeros on fronts.
        This is an approximation noted in model_spec.md §A.4 last paragraph.
        """
        return np.array([0.0, 0.0, v_sx_rear, v_sx_rear], dtype=np.float64)


    def slip_inversion_step(
        *,
        f_y: F64Array,             # (4,) from Module C
        f_x: F64Array,             # (4,) from Module C
        mu: F64Array,              # (4,) from Module D
        f_z: F64Array,              # (4,) from Module B
        a_cp: F64Array,             # (4,) from Module D
        v: float,                   # scalar speed
        v_sx_rear: float,           # scalar rear long slip velocity (Module A)
        t: float,                   # timestamp [s] for event timestamps
        params: FrictionParams,
        events: list[StatusEvent],  # mutable event log (capped at MAX_EVENTS)
    ) -> SlipSample:
        """Invert the brush model and compute dissipated power per tire.

        Equation references (model_spec.md):
            §E.1: C_α,i = c_py · a_cp,i²   (Pacejka 2012 Ch. 3)
            §E.2: Θ_i = 1 − (1 − |F_y|/(μ·F_z))^(1/3), clipped to 1 on over-demand
            §E.3: α_i = sgn(F_y) · arctan(3·μ·F_z·Θ / C_α)
            §E.4: V_sy,i = V · sin(α)
            §E.5: P_slide,i = |F_y|·|V_sy| + |F_x|·|V_sx|
            §E.6: P_rr,i   = C_RR · F_z · V
            §E.7: P_total  = P_slide + P_rr
        """
        # Grip capacity per tire — denominator of the brush-model ratio
        grip_capacity = mu * f_z
        # Guard against division by zero (F_z floor in Module B prevents this, but defense)
        safe_grip = np.where(grip_capacity > 0, grip_capacity, 1.0)
        ratio = np.abs(f_y) / safe_grip   # (4,), >=0

        # §E.2 — detect over-demand and append events (PHYS-05, Criterion 3)
        over_demand_mask = ratio > 1.0
        if over_demand_mask.any() and len(events) < MAX_EVENTS:
            # Append one event per over-demanded tire at this timestep
            for tire_idx in np.flatnonzero(over_demand_mask):
                if len(events) >= MAX_EVENTS:
                    break
                events.append(StatusEvent(
                    t=float(t),
                    tire_index=int(tire_idx),
                    kind="over_demand_lat",
                    message=(
                        f"Tire {_TIRE_NAMES[tire_idx]} lateral force demand "
                        f"exceeds grip at t={t:.2f}s (ratio={float(ratio[tire_idx]):.3f})"
                    ),
                    ratio=float(ratio[tire_idx]),
                ))

        # §E.2 — Θ with clip at 1.0
        clipped_ratio = np.clip(ratio, 0.0, 1.0)
        theta = 1.0 - np.cbrt(1.0 - clipped_ratio)
        # When ratio > 1, clipped_ratio = 1, so 1 - cbrt(0) = 1 — already exact; no separate clip needed.

        # §E.1 — cornering stiffness per tire
        c_alpha = params.c_py * a_cp * a_cp

        # §E.3 — slip angle (guard against c_alpha=0)
        safe_c_alpha = np.where(c_alpha > 0, c_alpha, 1.0)
        alpha_mag = np.arctan(3.0 * mu * f_z * theta / safe_c_alpha)
        alpha = np.sign(f_y) * alpha_mag

        # §E.4 — lateral slip velocity
        v_sy = v * np.sin(alpha)

        # §E.5 — sliding power per tire
        v_sx_per = _v_sx_per_tire(v_sx_rear)
        p_slide = np.abs(f_y) * np.abs(v_sy) + np.abs(f_x) * np.abs(v_sx_per)

        # §E.6 — rolling resistance
        p_rr = C_RR * f_z * v

        # §E.7 — total dissipated power
        p_total = p_slide + p_rr

        return SlipSample(
            theta=theta.astype(np.float64),
            alpha=alpha.astype(np.float64),
            v_sy=v_sy.astype(np.float64),
            p_slide=p_slide.astype(np.float64),
            p_rr=p_rr.astype(np.float64),
            p_total=p_total.astype(np.float64),
        )


    __all__ = ["SlipSample", "slip_inversion_step"]
    ```

    Now rewrite `packages/core/tests/physics/test_module_e.py`:

    ```python
    """PHYS-05 — Module E (Slip inversion + events) invariants. model_spec.md §E."""
    from __future__ import annotations

    import numpy as np
    import pytest

    from f1_core.physics.constants import C_RR
    from f1_core.physics.defaults import make_nominal_params
    from f1_core.physics.events import MAX_EVENTS, StatusEvent
    from f1_core.physics.module_e import SlipSample, slip_inversion_step


    def _call(**overrides):
        """Helper: build a nominal Module E invocation with supplied overrides."""
        p = make_nominal_params()
        base = dict(
            f_y=np.array([1000.0, 1000.0, 1200.0, 1200.0]),
            f_x=np.zeros(4),
            mu=np.full(4, 1.5),
            f_z=np.full(4, 5000.0),
            a_cp=np.full(4, 0.08),
            v=70.0,
            v_sx_rear=0.5,
            t=0.0,
            params=p.friction,
            events=[],
        )
        base.update(overrides)
        return slip_inversion_step(**base), base["events"]


    def test_module_e_returns_slip_sample():
        out, _ = _call()
        assert isinstance(out, SlipSample)
        assert out.theta.shape == (4,)
        assert out.p_total.shape == (4,)


    def test_module_e_theta_equals_1_when_force_equals_grip():
        """model_spec §E.2 identity: |F_y| = μ·F_z ⇒ Θ = 1 exactly."""
        mu = np.full(4, 1.5)
        f_z = np.full(4, 5000.0)
        f_y = mu * f_z  # exact equality
        out, _ = _call(f_y=f_y, mu=mu, f_z=f_z)
        np.testing.assert_allclose(out.theta, np.ones(4), rtol=1e-12)


    def test_module_e_clips_theta_at_1_when_over_demand():
        """model_spec §E.2: |F_y| > μ·F_z ⇒ Θ clipped at 1."""
        mu = np.full(4, 1.5)
        f_z = np.full(4, 5000.0)
        f_y = 2.0 * mu * f_z  # double the grip (demand > grip)
        out, _ = _call(f_y=f_y, mu=mu, f_z=f_z)
        np.testing.assert_array_equal(out.theta, np.ones(4))


    def test_module_e_emits_event_on_over_demand():
        """PHYS-05 Criterion 3: over-demand appends a StatusEvent."""
        mu = np.full(4, 1.5)
        f_z = np.full(4, 5000.0)
        f_y = np.array([0.0, 0.0, 0.0, 2.0 * mu[0] * f_z[0]])  # only RR over-demands
        events: list[StatusEvent] = []
        _, _ = _call(f_y=f_y, mu=mu, f_z=f_z, events=events, t=5.0)
        assert len(events) == 1
        ev = events[0]
        assert ev.tire_index == 3        # RR
        assert ev.kind == "over_demand_lat"
        assert ev.t == 5.0
        assert ev.ratio > 1.0


    def test_module_e_theta_partial_demand_formula():
        """model_spec §E.2: at |F_y|/(μ·F_z)=0.5, Θ = 1 − (0.5)^(1/3)."""
        mu = np.full(4, 1.5)
        f_z = np.full(4, 5000.0)
        f_y = 0.5 * mu * f_z
        out, _ = _call(f_y=f_y, mu=mu, f_z=f_z)
        expected = 1.0 - (0.5) ** (1.0 / 3.0)
        np.testing.assert_allclose(out.theta, np.full(4, expected), rtol=1e-12)


    def test_module_e_alpha_has_same_sign_as_f_y():
        """model_spec §E.3: α = sgn(F_y) · arctan(...)."""
        f_y = np.array([-1000.0, 1000.0, -1200.0, 1200.0])
        out, _ = _call(f_y=f_y)
        # Signs should match f_y signs (for non-zero demand)
        np.testing.assert_array_equal(np.sign(out.alpha), np.sign(f_y))


    def test_module_e_p_slide_is_nonnegative():
        """model_spec §E.5: P_slide = |F_y|·|V_sy|+|F_x|·|V_sx| ≥ 0 always."""
        out, _ = _call()
        assert (out.p_slide >= 0).all()
        assert (out.p_total >= 0).all()


    def test_module_e_rolling_resistance_formula():
        """model_spec §E.6: P_rr = C_RR · F_z · V."""
        f_z = np.full(4, 5000.0)
        out, _ = _call(f_z=f_z, v=60.0)
        expected = C_RR * f_z * 60.0
        np.testing.assert_allclose(out.p_rr, expected, rtol=1e-14)


    def test_module_e_event_log_caps_at_MAX_EVENTS():
        """Pitfall 6: events list capped at MAX_EVENTS=500 regardless of call count."""
        mu = np.full(4, 1.5)
        f_z = np.full(4, 5000.0)
        f_y = np.array([
            2.0 * mu[0] * f_z[0],
            2.0 * mu[1] * f_z[1],
            2.0 * mu[2] * f_z[2],
            2.0 * mu[3] * f_z[3],
        ])  # ALL four tires over-demand
        events: list[StatusEvent] = []
        # 200 calls × 4 tires = 800 potential events; cap at 500
        for i in range(200):
            _call(f_y=f_y, mu=mu, f_z=f_z, events=events, t=float(i))
        assert len(events) <= MAX_EVENTS
        assert len(events) == MAX_EVENTS  # should actually hit the cap exactly
    ```
  </action>
  <verify>
    <automated>uv run pytest packages/core/tests/physics/test_module_e.py -x --benchmark-disable</automated>
  </verify>
  <acceptance_criteria>
    - `uv run pytest packages/core/tests/physics/test_module_e.py -x --benchmark-disable` exits 0 with 9 tests passing
    - `grep -c "model_spec.md §E" packages/core/src/f1_core/physics/module_e.py` returns at least 6 (E.1 through E.7 with §E.7 being the last, all major sub-sections cited)
    - `grep -c "Pacejka\|Kobayashi\|Castellano" packages/core/src/f1_core/physics/module_e.py` returns at least 2
    - `grep -q "MAX_EVENTS" packages/core/src/f1_core/physics/module_e.py` matches (cap enforced in code)
    - `grep -q "pytest.skip" packages/core/tests/physics/test_module_e.py` returns NO matches
    - Event-cap test passes — `len(events) == MAX_EVENTS` after synthetic over-demand storm
  </acceptance_criteria>
  <done>Module E inverts brush model, emits StatusEvent on over-demand, caps event log at 500, computes P_slide/P_rr/P_total correctly; Θ=1 identity verified; P_slide ≥ 0 always.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| f_z input → Module D | From Module B, floored to ≥ 50 N (safe division). |
| events list → Module E | Orchestrator-owned, mutable; bounded by MAX_EVENTS. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-09 | Denial of Service | Module E event log unbounded growth (Pitfall 6) | mitigate | `slip_inversion_step` checks `len(events) < MAX_EVENTS` before each append; test `test_module_e_event_log_caps_at_MAX_EVENTS` verifies the cap holds under 800-event storm. |
| T-02-10 | Tampering | Division by zero if F_z = 0 | mitigate | Module B's 50 N floor ensures F_z > 0; Module D uses `np.where(grip_capacity > 0, grip_capacity, 1.0)` fallback for defense in depth; Module D a_cp > 0 likewise. |
| T-02-11 | Integrity | Module D accidentally uses current T_tread instead of previous (Pitfall 3) | mitigate | Explicit parameter name `t_tread_prev` in `contact_and_friction_step`; Plan 06's orchestrator test asserts the call order (D read before F write). |
</threat_model>

<verification>
- `uv run pytest packages/core/tests/physics/test_module_d.py packages/core/tests/physics/test_module_e.py -x --benchmark-disable` — all tests pass
- `uv run pytest packages/core/tests/physics/ --benchmark-disable` — full physics suite green (B, C, D, E implemented; A from Plan 02; F, G still stubs; orchestrator/benchmark still stubs)
- μ(T_opt, p̄_0) = μ_0 identity verified to rtol=1e-12
- Event cap enforced at 500
</verification>

<success_criteria>
- Module D: a_cp, p_bar, mu correctly formulated with per-tire b_tread handling
- Module E: Θ inversion with clip, event log capped, P_total = P_slide + P_rr
- All identity invariants verified: μ(T_opt, p̄_0)=μ_0, Θ=1 when |F_y|=μ·F_z
- Every equation cites its model_spec.md section AND at least one source paper (Pacejka, Grosch, Greenwood-Williamson, Gim, Kobayashi, Castellano)
</success_criteria>

<output>
After completion, create `.planning/phases/02-physics-model-modules-a-g/02-04-SUMMARY.md` documenting:
- Over-demand event count on canonical fixture (diagnostic — high count means nominal params need calibration in Phase 3, not a Phase 2 bug)
- Observed μ range per tire on canonical fixture
- Any place where the 50 N clip cascaded into Module D/E issues
</output>
