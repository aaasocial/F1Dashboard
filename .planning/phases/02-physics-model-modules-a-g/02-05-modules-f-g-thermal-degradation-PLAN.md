---
phase: 02-physics-model-modules-a-g
plan: 05
type: execute
wave: 1
depends_on: [01]
files_modified:
  - packages/core/src/f1_core/physics/module_f.py
  - packages/core/src/f1_core/physics/module_g.py
  - packages/core/tests/physics/test_module_f.py
  - packages/core/tests/physics/test_module_g.py
autonomous: true
requirements: [PHYS-06, PHYS-07]
tags: [physics, thermal, degradation, module-f, module-g]

must_haves:
  truths:
    - "Module F integrates a three-node thermal ODE (tread/carcass/gas) per tire using forward Euler at Δt=0.25 s (PHYS-06, D-06)"
    - "Thermal steady state: if RHS of each ODE is zero at (T_tread, T_carc, T_gas), one Euler step returns those same temperatures to within 1e-10 °C (Criterion 4)"
    - "60-lap synthetic stint (constant P_total) does not diverge — T_tread bounded within 50°C of analytical steady-state prediction (Criterion 4)"
    - "Module G cumulative energy E_tire is monotonically non-decreasing (Criterion 6)"
    - "Module G tread thickness d_tread is monotonically non-increasing (Criterion 6)"
    - "Module G μ_0 scalar declines under sustained T_tread > T_ref (Criterion 6)"
    - "Module G Δt_lap = (t_ref/2)·(μ_0^fresh − μ_0(t))/μ_0^fresh (model_spec §G.4)"
    - "Arrhenius exponent clamped to avoid overflow (Pitfall 4)"
  artifacts:
    - path: "packages/core/src/f1_core/physics/module_f.py"
      provides: "thermal_step(t_tread, t_carc, t_gas, p_total, v, t_air, params) -> (t_tread, t_carc, t_gas)"
      exports: ["thermal_step", "DT_THERMAL"]
    - path: "packages/core/src/f1_core/physics/module_g.py"
      provides: "degradation_step(e_tire, mu_0, d_tread, p_total, p_slide, t_tread, params) -> (e_tire, mu_0, d_tread); delta_t_lap(mu_0_fresh, mu_0_now, t_ref)"
      exports: ["degradation_step", "delta_t_lap", "ARRHENIUS_EXP_CLAMP"]
  key_links:
    - from: "packages/core/src/f1_core/physics/module_f.py"
      to: "packages/core/src/f1_core/physics/constants.py"
      via: "A_TREAD_F/R, A_CARC_F/R, H_CARC imports"
      pattern: "A_TREAD_F|A_CARC_F|H_CARC"
    - from: "packages/core/src/f1_core/physics/module_g.py"
      to: "packages/core/src/f1_core/physics/constants.py"
      via: "T_REF_AGING import"
      pattern: "T_REF_AGING"
---

<objective>
Implement Modules F (thermal ODE) and G (energy + degradation) — the two time-integrating modules. Both use forward Euler at Δt=0.25 s per CONTEXT.md D-06. F writes the carryover tread/carcass/gas temperatures; G writes cumulative energy, μ_0 aging, and tread wear. Together they close the feedback loop: F's T_tread feeds D's μ next step (handled causally), and G's μ_0 feeds D's baseline μ next step.

This plan satisfies PHYS-06 (thermal ODE + steady state + no divergence, Criterion 4) and PHYS-07 (monotonicity + Arrhenius decline, Criterion 6).

Output: Two module files + two real test files with steady-state, monotonicity, Arrhenius decline, and 60-lap stability tests.
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
From f1_core.physics.params:
```python
@dataclass(frozen=True)
class ThermalParams:
    T_opt: float; sigma_T: float
    C_tread: float; C_carc: float; C_gas: float
    R_tc: float; R_cg: float
    h_0: float; h_1: float
    alpha_p: float
    delta_T_blanket: float

@dataclass(frozen=True)
class DegradationParams:
    beta_therm: float
    T_act: float
    k_wear: float
```

From f1_core.physics.constants:
```python
A_TREAD_F: float; A_TREAD_R: float   # per-tire tread convective area [m²]
A_CARC_F: float; A_CARC_R: float     # per-tire carcass convective area [m²]
H_CARC: float = 5.0                  # W/m²K (carcass convection coeff)
T_REF_AGING: float = 80.0            # °C reference for Arrhenius aging (model_spec §G.2)
```

Convention: tread/carcass/gas temperatures stored as (4,) per-tire arrays. μ_0 is a SCALAR (per model_spec §G.2 and CONTEXT.md §Specifics: "μ_0 is a scalar that ages the same for all four tires"). T_tread used in §G.2's Arrhenius is the MEAN tread temperature across all four tires (per CONTEXT.md §Specifics).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement Module F (thermal ODE) with steady-state + stability tests</name>
  <files>
    packages/core/src/f1_core/physics/module_f.py,
    packages/core/tests/physics/test_module_f.py
  </files>
  <read_first>
    - model_spec.md §F.1, §F.2, §F.3, §F.4, §F.5, §F.6, §F.7
    - packages/core/src/f1_core/physics/constants.py (A_TREAD_F/R, A_CARC_F/R, H_CARC)
    - packages/core/src/f1_core/physics/params.py (ThermalParams fields)
    - .planning/phases/02-physics-model-modules-a-g/02-RESEARCH.md §"Pattern 2" (ODE step function template)
  </read_first>
  <behavior>
    - Test 1: `thermal_step(...)` returns tuple of three (4,) arrays (t_tread, t_carc, t_gas), all float64
    - Test 2: Δt = 0.25 s exactly (exported as DT_THERMAL)
    - Test 3: Steady state — construct P_total such that dT_tread/dt = 0 at initial condition; call thermal_step; assert T_tread unchanged to within 1e-8 °C
    - Test 4: 60 × 25 = 1500 consecutive calls with v=50, T_air=25, P_total=2000 W/tire — T_tread stays finite, doesn't overshoot 300°C, converges toward equilibrium
    - Test 5: T_tread(t+Δt) = T_tread(t) + Δt · dT/dt formula verified explicitly
    - Test 6: Higher v increases h_air → more convection → lower equilibrium T_tread (sanity)
  </behavior>
  <action>
    Create `packages/core/src/f1_core/physics/module_f.py`:

    ```python
    """Module F — Thermal ODE (model_spec.md §F.1–§F.7).

    Sources:
      §F.1–§F.3: Three-node lumped model — Sorniotti (2009); Farroni et al. (2015);
                 Kenins et al. (2019)
      §F.4:      Heat partition α_p — Farroni et al. (2015)
      §F.5:      Speed-dependent convection — Reynolds analogy flat-plate
      §F.7:      Forward Euler, Δt = 0.25 s (per CONTEXT.md D-06)

    Three coupled linear ODEs per tire, all four tires updated in one vectorized
    expression. RESEARCH.md §"Pattern 2" is the canonical implementation shape.
    """
    from __future__ import annotations

    import numpy as np

    from f1_core.contracts import F64Array
    from f1_core.physics.constants import (
        A_CARC_F,
        A_CARC_R,
        A_TREAD_F,
        A_TREAD_R,
        H_CARC,
    )
    from f1_core.physics.params import ThermalParams

    # D-06: Forward Euler timestep locked at telemetry rate. RK4 deferred.
    DT_THERMAL: float = 0.25

    # Per-tire convective areas (FL, FR, RL, RR) — fronts and rears differ.
    _A_TREAD_PER_TIRE: F64Array = np.array(
        [A_TREAD_F, A_TREAD_F, A_TREAD_R, A_TREAD_R], dtype=np.float64
    )
    _A_CARC_PER_TIRE: F64Array = np.array(
        [A_CARC_F, A_CARC_F, A_CARC_R, A_CARC_R], dtype=np.float64
    )


    def thermal_step(
        *,
        t_tread: F64Array,          # (4,) previous tread temperature [°C]
        t_carc: F64Array,           # (4,) previous carcass temperature [°C]
        t_gas: F64Array,            # (4,) previous gas temperature [°C]
        p_total: F64Array,          # (4,) total dissipated power this step [W]
        v: float,                    # scalar speed [m/s]
        t_air: float,                # scalar ambient air temperature [°C]
        params: ThermalParams,
    ) -> tuple[F64Array, F64Array, F64Array]:
        """One forward Euler step of the three-node thermal ODE (model_spec §F.7).

        Returns (t_tread_new, t_carc_new, t_gas_new), each (4,).

        Equations (all per-tire, elementwise on (4,) arrays):
          §F.1  C_tread·dT_tread/dt = α_p·P_total
                                      − h_air(V)·A_tread·(T_tread − T_air)
                                      − (T_tread − T_carc)/R_tc
          §F.2  C_carc·dT_carc/dt   = (T_tread − T_carc)/R_tc
                                      − h_carc·A_carc·(T_carc − T_air)
                                      − (T_carc − T_gas)/R_cg
          §F.3  C_gas·dT_gas/dt     = (T_carc − T_gas)/R_cg
          §F.5  h_air(V)            = h_0 + h_1·√max(V, 0)
          §F.7  T(t+Δt)             = T(t) + Δt·Ṫ(t)
        """
        # §F.5 — convection coefficient (scalar); guard sqrt against negative/NaN v
        v_safe = max(float(v), 0.0)
        h_air = params.h_0 + params.h_1 * np.sqrt(v_safe)

        # §F.1 — tread node RHS (4,)
        q_heat = params.alpha_p * p_total
        q_conv_tread = h_air * _A_TREAD_PER_TIRE * (t_tread - t_air)
        q_tc = (t_tread - t_carc) / params.R_tc
        dT_tread = (q_heat - q_conv_tread - q_tc) / params.C_tread

        # §F.2 — carcass node RHS (4,)
        q_conv_carc = H_CARC * _A_CARC_PER_TIRE * (t_carc - t_air)
        q_cg = (t_carc - t_gas) / params.R_cg
        dT_carc = (q_tc - q_conv_carc - q_cg) / params.C_carc

        # §F.3 — gas node RHS (4,)
        dT_gas = q_cg / params.C_gas

        # §F.7 — forward Euler (Δt=0.25s)
        t_tread_new = t_tread + DT_THERMAL * dT_tread
        t_carc_new = t_carc + DT_THERMAL * dT_carc
        t_gas_new = t_gas + DT_THERMAL * dT_gas

        return (
            t_tread_new.astype(np.float64),
            t_carc_new.astype(np.float64),
            t_gas_new.astype(np.float64),
        )


    __all__ = ["DT_THERMAL", "thermal_step"]
    ```

    Now rewrite `packages/core/tests/physics/test_module_f.py`:

    ```python
    """PHYS-06 — Module F (Thermal ODE) invariants. model_spec.md §F."""
    from __future__ import annotations

    import numpy as np

    from f1_core.physics.constants import A_CARC_F, A_TREAD_F, H_CARC
    from f1_core.physics.defaults import make_nominal_params
    from f1_core.physics.module_f import DT_THERMAL, thermal_step


    def test_module_f_dt_is_0_25s():
        """D-06: forward Euler with Δt = 0.25 s locked."""
        assert DT_THERMAL == 0.25


    def test_module_f_returns_three_4vectors():
        p = make_nominal_params().thermal
        t_tread = np.full(4, 80.0)
        t_carc = np.full(4, 70.0)
        t_gas = np.full(4, 60.0)
        out = thermal_step(
            t_tread=t_tread, t_carc=t_carc, t_gas=t_gas,
            p_total=np.full(4, 1000.0),
            v=60.0, t_air=25.0, params=p,
        )
        assert len(out) == 3
        for arr in out:
            assert arr.shape == (4,)
            assert arr.dtype == np.float64


    def test_module_f_steady_state_zero_derivative():
        """model_spec §F + Criterion 4: if each dT/dt = 0, Euler step leaves T unchanged.

        Construct a steady state:
          dT_gas/dt = 0  ⇔ T_carc = T_gas
          dT_carc/dt = 0 ⇔ (T_tread − T_carc)/R_tc = h_carc·A_carc·(T_carc − T_air)
                           [gas-carcass term zero already]
          dT_tread/dt = 0 ⇔ α_p·P = h_air·A_tread·(T_tread − T_air) + (T_tread − T_carc)/R_tc

        Pick T_air=25, v=60, T_carc=T_gas=70, T_tread=85; solve P to nullify dT_tread.
        """
        p = make_nominal_params().thermal
        v = 60.0
        t_air = 25.0
        h_air = p.h_0 + p.h_1 * np.sqrt(v)
        # Step 1: pick T_tread, T_carc s.t. carcass steady-state holds
        T_carc = np.full(4, 70.0)
        T_gas = np.full(4, 70.0)  # → dT_gas = 0 automatically
        # Solve carcass steady: (T_tread − T_carc)/R_tc = H_CARC·A_carc·(T_carc − T_air)
        rhs_carc = H_CARC * A_CARC_F * (70.0 - t_air)   # use front area for FL/FR; rear is close
        # For a clean steady state without per-tire heterogeneity, use the same ΔT for all.
        # Approximation: rear A_CARC differs slightly; we satisfy to within per-axle tolerance.
        delta_T_tc = rhs_carc * p.R_tc
        T_tread = T_carc + delta_T_tc
        # Step 2: solve P_total s.t. tread steady:
        #   α_p·P = h_air·A_tread·(T_tread − T_air) + (T_tread − T_carc)/R_tc
        q_conv = h_air * A_TREAD_F * (T_tread - t_air)
        q_tc = (T_tread - T_carc) / p.R_tc
        P_total = (q_conv + q_tc) / p.alpha_p   # per-front-tire
        # Tolerance: rear slightly off because A differs, so we only assert on FL
        t_tread_new, t_carc_new, t_gas_new = thermal_step(
            t_tread=T_tread, t_carc=T_carc, t_gas=T_gas,
            p_total=P_total,
            v=v, t_air=t_air, params=p,
        )
        # FL index tread stays within 1e-8 °C of initial
        np.testing.assert_allclose(t_tread_new[0], T_tread[0], atol=1e-8)
        np.testing.assert_allclose(t_carc_new[0], T_carc[0], atol=1e-8)
        np.testing.assert_allclose(t_gas_new[0], T_gas[0], atol=1e-12)


    def test_module_f_euler_formula_verified_explicitly():
        """model_spec §F.7: T_new = T_old + Δt · dT/dt. Verify by hand calculation."""
        p = make_nominal_params().thermal
        t_tread = np.full(4, 50.0)
        t_carc = np.full(4, 45.0)
        t_gas = np.full(4, 40.0)
        v = 50.0
        t_air = 25.0
        p_total = np.full(4, 2000.0)
        h_air = p.h_0 + p.h_1 * np.sqrt(v)
        # By-hand compute for FL tire
        q_heat = p.alpha_p * 2000.0
        q_conv = h_air * A_TREAD_F * (50.0 - 25.0)
        q_tc = (50.0 - 45.0) / p.R_tc
        dT_tread_expected = (q_heat - q_conv - q_tc) / p.C_tread
        expected_t_tread_fl = 50.0 + DT_THERMAL * dT_tread_expected
        t_tread_new, _, _ = thermal_step(
            t_tread=t_tread, t_carc=t_carc, t_gas=t_gas,
            p_total=p_total, v=v, t_air=t_air, params=p,
        )
        np.testing.assert_allclose(t_tread_new[0], expected_t_tread_fl, rtol=1e-10)


    def test_module_f_60_lap_synthetic_stint_no_divergence():
        """Criterion 4: 60 × 25 s × 4 Hz = 6000 steps; T stays bounded and monotonic-ish.

        Use constant kinematics (no lateral cornering, low power), so T should
        converge toward a steady state rather than blow up.
        """
        p = make_nominal_params().thermal
        t_tread = np.full(4, 60.0)  # start cold-ish
        t_carc = np.full(4, 60.0)
        t_gas = np.full(4, 60.0)
        for _ in range(6000):
            t_tread, t_carc, t_gas = thermal_step(
                t_tread=t_tread, t_carc=t_carc, t_gas=t_gas,
                p_total=np.full(4, 1500.0),  # steady power, not overwhelming
                v=50.0, t_air=25.0, params=p,
            )
            assert np.all(np.isfinite(t_tread))
            assert np.all(np.isfinite(t_carc))
            assert np.all(np.isfinite(t_gas))
        # No divergence: T_tread stays below 250°C (Pitfall 4 ceiling)
        assert t_tread.max() < 250.0
        # Nor negative: temperatures shouldn't drop below ambient (25°C) by construction
        assert t_tread.min() > 20.0


    def test_module_f_higher_v_gives_lower_equilibrium():
        """Sanity: higher speed → more convection → lower steady-state T_tread.

        Run 6000 steps at v=50 and v=100 with same P; compare final T_tread.
        """
        p = make_nominal_params().thermal
        def run(v):
            t_tread = np.full(4, 80.0)
            t_carc = np.full(4, 80.0)
            t_gas = np.full(4, 80.0)
            for _ in range(6000):
                t_tread, t_carc, t_gas = thermal_step(
                    t_tread=t_tread, t_carc=t_carc, t_gas=t_gas,
                    p_total=np.full(4, 1500.0),
                    v=v, t_air=25.0, params=p,
                )
            return t_tread
        t_low = run(50.0)
        t_high = run(100.0)
        assert (t_high < t_low).all(), "higher speed must cool the tread more"
    ```
  </action>
  <verify>
    <automated>uv run pytest packages/core/tests/physics/test_module_f.py -x --benchmark-disable</automated>
  </verify>
  <acceptance_criteria>
    - `uv run pytest packages/core/tests/physics/test_module_f.py -x --benchmark-disable` exits 0 with 6 tests passing
    - `grep -c "model_spec.md §F" packages/core/src/f1_core/physics/module_f.py` returns at least 5 (F.1, F.2, F.3, F.5, F.7 cited)
    - `grep -c "Sorniotti\|Farroni\|Kenins" packages/core/src/f1_core/physics/module_f.py` returns at least 2
    - `grep -q "DT_THERMAL = 0.25" packages/core/src/f1_core/physics/module_f.py` matches exactly
    - `grep -q "pytest.skip" packages/core/tests/physics/test_module_f.py` returns NO matches
    - 60-lap synthetic stint test completes in < 2 seconds (fast enough for Plan 07 benchmark)
  </acceptance_criteria>
  <done>Module F computes three-node thermal update with forward Euler Δt=0.25s; steady-state preserved; 6000-step synthetic stint stable; higher-v cooling verified.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement Module G (energy + Arrhenius aging + wear) with monotonicity tests</name>
  <files>
    packages/core/src/f1_core/physics/module_g.py,
    packages/core/tests/physics/test_module_g.py
  </files>
  <read_first>
    - model_spec.md §G.1, §G.2, §G.3, §G.4
    - packages/core/src/f1_core/physics/constants.py (T_REF_AGING = 80.0)
    - packages/core/src/f1_core/physics/params.py (DegradationParams: beta_therm, T_act, k_wear)
    - .planning/phases/02-physics-model-modules-a-g/02-RESEARCH.md §"Pitfall 4" (Arrhenius overflow guard)
    - .planning/phases/02-physics-model-modules-a-g/02-CONTEXT.md §"Specifics" (μ_0 is scalar; uses MEAN T_tread)
  </read_first>
  <behavior>
    - Test 1: `degradation_step(...)` returns (e_tire, mu_0, d_tread) — ndarrays (4,), float, (4,)
    - Test 2: E_tire(t+Δt) = E_tire(t) + P_total·Δt; monotonically non-decreasing for P_total ≥ 0
    - Test 3: d_tread(t+Δt) = d_tread(t) − Δt·k_wear·P_slide; monotonically non-increasing for P_slide ≥ 0
    - Test 4: Arrhenius — dμ_0/dt uses MEAN T_tread (scalar). If all four T_tread = T_ref, dμ_0/dt = −β_therm·μ_0·exp(0) = −β_therm·μ_0
    - Test 5: Sustained T_tread = T_ref + 4·T_act (4x doublings above reference): after 1000 Δt (250 s simulated), μ_0 is materially lower than initial μ_0^fresh
    - Test 6: Pitfall 4 — Arrhenius exponent clamped so that even T_tread = 400°C does not overflow (μ_0 stays finite)
    - Test 7: `delta_t_lap(mu_0_fresh=1.8, mu_0_now=1.5, t_ref=90)` matches formula (t_ref/2)·(1.8-1.5)/1.8
  </behavior>
  <action>
    Create `packages/core/src/f1_core/physics/module_g.py`:

    ```python
    """Module G — Cumulative energy + degradation (model_spec.md §G.1–§G.4).

    Sources:
      §G.1 cumulative energy: Todd et al. (2025); Castellano (2021)
      §G.2 thermal aging:     Arrhenius-style; typical T_act ≈ 25°C halves/doubles
                              rate every ±25°C from T_ref
      §G.3 mechanical wear:   Wear proportional to sliding power (classical Archard-like)
      §G.4 lap-time penalty:  First-order expansion V ∝ √μ

    Per CONTEXT.md §Specifics: μ_0 is a SCALAR that ages the same for all four tires.
    The T_tread used in §G.2 is the MEAN tread temperature across the four tires.

    Per RESEARCH.md Pitfall 4: the Arrhenius exponent is clamped to prevent
    numerical overflow when T_tread drifts unreasonably high.
    """
    from __future__ import annotations

    import numpy as np

    from f1_core.contracts import F64Array
    from f1_core.physics.constants import T_REF_AGING
    from f1_core.physics.module_f import DT_THERMAL
    from f1_core.physics.params import DegradationParams

    # Pitfall 4: hard cap on the Arrhenius exponent to prevent overflow.
    # exp(20) ≈ 4.9e8 — already absurd; anything larger is a numerical bug.
    ARRHENIUS_EXP_CLAMP: float = 20.0


    def degradation_step(
        *,
        e_tire: F64Array,           # (4,) previous cumulative tire energy [J]
        mu_0: float,                 # scalar previous reference friction
        d_tread: F64Array,          # (4,) previous tread thickness [m]
        p_total: F64Array,          # (4,) total dissipated power this step [W]
        p_slide: F64Array,          # (4,) sliding power this step [W]
        t_tread: F64Array,          # (4,) current tread temperature [°C] from Module F output
        params: DegradationParams,
    ) -> tuple[F64Array, float, F64Array]:
        """One forward Euler step of energy, μ_0 aging, and wear.

        Returns (e_tire_new, mu_0_new, d_tread_new).

        Equations:
          §G.1  E_tire(t+Δt) = E_tire(t) + P_total·Δt
          §G.2  dμ_0/dt     = −β_therm·μ_0·exp((T_tread_mean − T_ref)/T_act)
          §G.3  dd_tread/dt = −k_wear·P_slide
        """
        # §G.1 — per-tire cumulative energy (non-decreasing because P_total ≥ 0 from E.7)
        e_tire_new = e_tire + p_total * DT_THERMAL

        # §G.2 — μ_0 scalar ages using the MEAN tread temperature across all four tires.
        # Pitfall 4: clamp exponent to prevent exp() overflow on runaway thermal states.
        t_tread_mean = float(np.mean(t_tread))
        arg = (t_tread_mean - T_REF_AGING) / params.T_act
        arg_clamped = float(np.clip(arg, -ARRHENIUS_EXP_CLAMP, ARRHENIUS_EXP_CLAMP))
        d_mu_0_dt = -params.beta_therm * mu_0 * np.exp(arg_clamped)
        mu_0_new = mu_0 + DT_THERMAL * d_mu_0_dt
        # Safety floor: μ_0 should not go negative in physically reasonable time
        mu_0_new = max(mu_0_new, 0.0)

        # §G.3 — per-tire wear, non-increasing (P_slide ≥ 0 per E.5)
        d_tread_new = d_tread - DT_THERMAL * params.k_wear * p_slide
        # Floor wear at zero — fully worn tire
        d_tread_new = np.maximum(d_tread_new, 0.0)

        return (
            e_tire_new.astype(np.float64),
            float(mu_0_new),
            d_tread_new.astype(np.float64),
        )


    def delta_t_lap(
        mu_0_fresh: float,
        mu_0_now: float,
        t_lap_ref: float,
    ) -> float:
        """model_spec §G.4: Δt_lap ≈ (t_ref/2)·(μ_0^fresh − μ_0(t))/μ_0^fresh.

        Args:
            mu_0_fresh: initial μ_0 at start of fresh stint
            mu_0_now:   current μ_0
            t_lap_ref:  reference fresh-tire lap time [s]
        Returns:
            predicted lap-time penalty [s] relative to fresh-tire baseline
        """
        if mu_0_fresh <= 0.0:
            return 0.0
        return 0.5 * t_lap_ref * (mu_0_fresh - mu_0_now) / mu_0_fresh


    __all__ = ["ARRHENIUS_EXP_CLAMP", "degradation_step", "delta_t_lap"]
    ```

    Now rewrite `packages/core/tests/physics/test_module_g.py`:

    ```python
    """PHYS-07 — Module G (Energy + Degradation) invariants. model_spec.md §G."""
    from __future__ import annotations

    import numpy as np

    from f1_core.physics.constants import T_REF_AGING
    from f1_core.physics.defaults import make_nominal_params
    from f1_core.physics.module_f import DT_THERMAL
    from f1_core.physics.module_g import (
        ARRHENIUS_EXP_CLAMP,
        degradation_step,
        delta_t_lap,
    )


    def test_module_g_returns_correct_shapes():
        p = make_nominal_params()
        e_tire = np.zeros(4)
        d_tread = np.full(4, 0.008)
        e_new, mu_new, d_new = degradation_step(
            e_tire=e_tire, mu_0=1.8, d_tread=d_tread,
            p_total=np.full(4, 1000.0), p_slide=np.full(4, 500.0),
            t_tread=np.full(4, T_REF_AGING),
            params=p.degradation,
        )
        assert e_new.shape == (4,)
        assert isinstance(mu_new, float)
        assert d_new.shape == (4,)


    def test_module_g_e_tire_monotonically_non_decreasing():
        """model_spec §G.1 + Criterion 6: ΔE = P_total·Δt ≥ 0 for P_total ≥ 0."""
        p = make_nominal_params()
        e_tire = np.zeros(4)
        d_tread = np.full(4, 0.008)
        mu = 1.8
        for _ in range(100):
            prev = e_tire.copy()
            e_tire, mu, d_tread = degradation_step(
                e_tire=e_tire, mu_0=mu, d_tread=d_tread,
                p_total=np.full(4, 1000.0), p_slide=np.full(4, 500.0),
                t_tread=np.full(4, 90.0),
                params=p.degradation,
            )
            assert (e_tire >= prev).all(), "E_tire must be non-decreasing step-to-step"


    def test_module_g_d_tread_monotonically_non_increasing():
        """model_spec §G.3 + Criterion 6: dd/dt = -k_wear·P_slide ≤ 0."""
        p = make_nominal_params()
        e_tire = np.zeros(4)
        d_tread = np.full(4, 0.008)
        mu = 1.8
        for _ in range(100):
            prev = d_tread.copy()
            e_tire, mu, d_tread = degradation_step(
                e_tire=e_tire, mu_0=mu, d_tread=d_tread,
                p_total=np.full(4, 1000.0), p_slide=np.full(4, 500.0),
                t_tread=np.full(4, 90.0),
                params=p.degradation,
            )
            assert (d_tread <= prev).all(), "d_tread must be non-increasing"


    def test_module_g_e_tire_formula_verified():
        """§G.1: E(t+Δt) = E(t) + P·Δt."""
        p = make_nominal_params()
        e_tire = np.full(4, 100.0)
        p_total = np.array([1000.0, 1500.0, 2000.0, 2500.0])
        e_new, _, _ = degradation_step(
            e_tire=e_tire, mu_0=1.8, d_tread=np.full(4, 0.008),
            p_total=p_total, p_slide=np.zeros(4),
            t_tread=np.full(4, T_REF_AGING), params=p.degradation,
        )
        expected = e_tire + p_total * DT_THERMAL
        np.testing.assert_allclose(e_new, expected, rtol=1e-14)


    def test_module_g_mu_0_declines_at_reference_temperature():
        """§G.2: At T_tread_mean = T_ref, dμ_0/dt = -β_therm·μ_0·exp(0) = -β_therm·μ_0."""
        p = make_nominal_params()
        mu_initial = 1.8
        _, mu_new, _ = degradation_step(
            e_tire=np.zeros(4), mu_0=mu_initial, d_tread=np.full(4, 0.008),
            p_total=np.zeros(4), p_slide=np.zeros(4),
            t_tread=np.full(4, T_REF_AGING),  # exp(0) = 1
            params=p.degradation,
        )
        expected = mu_initial + DT_THERMAL * (-p.degradation.beta_therm * mu_initial)
        assert mu_new < mu_initial
        np.testing.assert_allclose(mu_new, expected, rtol=1e-10)


    def test_module_g_mu_0_declines_faster_at_high_temperature():
        """Criterion 6: sustained T_tread > T_ref drives μ_0 down faster."""
        p = make_nominal_params()
        mu_initial = 1.8
        # 1000 steps at T_ref + 4·T_act (= 180 °C with nominal T_act=25)
        mu = mu_initial
        for _ in range(1000):
            _, mu, _ = degradation_step(
                e_tire=np.zeros(4), mu_0=mu, d_tread=np.full(4, 0.008),
                p_total=np.zeros(4), p_slide=np.zeros(4),
                t_tread=np.full(4, T_REF_AGING + 4.0 * p.degradation.T_act),
                params=p.degradation,
            )
        # Should drop more than the T_ref case would
        mu_at_ref = mu_initial
        for _ in range(1000):
            _, mu_at_ref, _ = degradation_step(
                e_tire=np.zeros(4), mu_0=mu_at_ref, d_tread=np.full(4, 0.008),
                p_total=np.zeros(4), p_slide=np.zeros(4),
                t_tread=np.full(4, T_REF_AGING),
                params=p.degradation,
            )
        assert mu < mu_at_ref
        assert mu < mu_initial


    def test_module_g_arrhenius_overflow_clamped():
        """Pitfall 4: T_tread → 400°C must not overflow exp()."""
        p = make_nominal_params()
        _, mu_new, _ = degradation_step(
            e_tire=np.zeros(4), mu_0=1.8, d_tread=np.full(4, 0.008),
            p_total=np.zeros(4), p_slide=np.zeros(4),
            t_tread=np.full(4, 400.0),  # way above T_ref
            params=p.degradation,
        )
        assert np.isfinite(mu_new)
        assert 0.0 <= mu_new <= 1.8   # floor applied, still finite


    def test_module_g_delta_t_lap_formula():
        """model_spec §G.4: Δt_lap = (t_ref/2)·(μ^fresh - μ(t))/μ^fresh."""
        dt = delta_t_lap(mu_0_fresh=1.8, mu_0_now=1.5, t_lap_ref=90.0)
        expected = 0.5 * 90.0 * (1.8 - 1.5) / 1.8
        np.testing.assert_allclose(dt, expected, rtol=1e-14)


    def test_module_g_delta_t_lap_zero_when_fresh():
        dt = delta_t_lap(mu_0_fresh=1.8, mu_0_now=1.8, t_lap_ref=90.0)
        np.testing.assert_allclose(dt, 0.0, atol=1e-14)


    def test_module_g_clamp_constant_is_20():
        assert ARRHENIUS_EXP_CLAMP == 20.0
    ```
  </action>
  <verify>
    <automated>uv run pytest packages/core/tests/physics/test_module_g.py -x --benchmark-disable</automated>
  </verify>
  <acceptance_criteria>
    - `uv run pytest packages/core/tests/physics/test_module_g.py -x --benchmark-disable` exits 0 with 9 tests passing
    - `grep -c "model_spec.md §G" packages/core/src/f1_core/physics/module_g.py` returns at least 4 (G.1, G.2, G.3, G.4 cited)
    - `grep -c "Arrhenius\|Todd\|Castellano" packages/core/src/f1_core/physics/module_g.py` returns at least 2
    - `grep -q "ARRHENIUS_EXP_CLAMP" packages/core/src/f1_core/physics/module_g.py` matches
    - `grep -q "np.clip" packages/core/src/f1_core/physics/module_g.py` matches (overflow guard present)
    - `grep -q "pytest.skip" packages/core/tests/physics/test_module_g.py` returns NO matches
    - `uv run pytest packages/core/tests/physics/ --benchmark-disable` — full physics suite green (A, B, C, D, E, F, G all implemented; orchestrator/benchmark still stubs per Plan 06/07)
  </acceptance_criteria>
  <done>Module G computes E_tire (monotonic non-decreasing), d_tread (monotonic non-increasing), μ_0 (declines under high T, clamp-safe), and delta_t_lap; every formula cites its model_spec.md §G.X section.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| p_total / p_slide from Module E → Modules F, G | Both are ≥ 0 by construction (§E.5, §E.7). No validation needed. |
| T_tread carried across timesteps | Bounded by the physical system and the overflow clamp in Module G. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-12 | Denial of Service | Arrhenius `exp()` overflow crashes the simulation (Pitfall 4) | mitigate | `ARRHENIUS_EXP_CLAMP = 20.0` clamps the exponent before exp(). Test `test_module_g_arrhenius_overflow_clamped` verifies T=400°C produces finite μ_0. |
| T-02-13 | Availability | Negative μ_0 makes μ physically invalid | mitigate | `mu_0_new = max(mu_0_new, 0.0)` floor in module_g.py; test verifies μ_0 ∈ [0, 1.8] under extreme conditions. |
| T-02-14 | Availability | Negative d_tread (worn past zero) | mitigate | `d_tread_new = np.maximum(d_tread_new, 0.0)` floor; monotonicity test remains valid (floor is still non-increasing). |
</threat_model>

<verification>
- `uv run pytest packages/core/tests/physics/test_module_f.py packages/core/tests/physics/test_module_g.py -x --benchmark-disable` — all tests pass
- `uv run pytest packages/core/tests/physics/ --benchmark-disable` — full physics suite green
- 60-lap (6000-step) synthetic stint completes in < 2 seconds without divergence (budget input for Plan 07)
- Monotonicity invariants verified (E non-decreasing, d_tread non-increasing)
- Arrhenius overflow guard verified at T=400°C
</verification>

<success_criteria>
- Module F thermal_step: three-node ODE forward Euler at Δt=0.25s
- Module G degradation_step: cumulative energy + Arrhenius aging (with clamp) + wear
- delta_t_lap helper matches §G.4 formula
- Criterion 4: steady-state preserved; 60-lap stint doesn't diverge
- Criterion 6: E_tire non-decreasing, d_tread non-increasing, μ_0 declines under high T
- Every equation cites its model_spec.md §F.X / §G.X section and at least one source paper
</success_criteria>

<output>
After completion, create `.planning/phases/02-physics-model-modules-a-g/02-05-SUMMARY.md` documenting:
- Steady-state equilibrium temperatures predicted by analytical solve vs Module F 6000-step simulation
- μ_0 decline rate observed over 6000 steps at T=T_ref and T=T_ref+4·T_act
- Number of overflow-clamp trips (should be 0 on canonical fixture — diagnostic for Plan 07)
</output>
