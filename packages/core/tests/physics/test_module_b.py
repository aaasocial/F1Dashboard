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
    # Static loads are forces [N] = M_TOT * G * fraction (model_spec §B.1)
    static_f = M_TOT * G * p.WD / 2.0
    static_r = M_TOT * G * (1.0 - p.WD) / 2.0
    np.testing.assert_allclose(f_z[0], static_f + 0.5 * f_aero_total, rtol=1e-12)
    np.testing.assert_allclose(f_z[1], static_f + 0.5 * f_aero_total, rtol=1e-12)
    np.testing.assert_allclose(f_z[2], static_r, rtol=1e-12)
    np.testing.assert_allclose(f_z[3], static_r, rtol=1e-12)


def test_module_b_aero_split_xi_0_puts_all_on_rear():
    from dataclasses import replace
    p = replace(make_nominal_params().aero, xi=0.0)
    f_z = _wheel_loads_step_unclipped(v=80.0, a_lat=0.0, a_long=0.0, params=p)
    f_aero_total = 0.5 * RHO_AIR * p.C_LA * 80.0 * 80.0
    # Static loads are forces [N] = M_TOT * G * fraction (model_spec §B.1)
    static_f = M_TOT * G * p.WD / 2.0
    static_r = M_TOT * G * (1.0 - p.WD) / 2.0
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
