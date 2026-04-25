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
