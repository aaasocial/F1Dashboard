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
