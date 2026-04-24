"""PHYS-01 — Module A (Kinematics preprocessor) invariants."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from f1_core.contracts import KinematicState
from f1_core.physics.module_a import process_stint


def test_module_a_process_stint_returns_kinematic_state(canonical_stint_artifact, nominal_params):
    kstate = process_stint(canonical_stint_artifact, nominal_params.aero)
    assert isinstance(kstate, KinematicState)


def test_module_a_all_fields_same_shape(canonical_stint_artifact, nominal_params):
    kstate = process_stint(canonical_stint_artifact, nominal_params.aero)
    n = len(kstate.t)
    assert kstate.v.shape == (n,)
    assert kstate.a_lat.shape == (n,)
    assert kstate.a_long.shape == (n,)
    assert kstate.psi.shape == (n,)
    assert kstate.v_sx_rear.shape == (n,)
    assert kstate.kappa.shape == (n,)


def test_module_a_a_lat_equals_v_squared_kappa(canonical_stint_artifact, nominal_params):
    """model_spec.md §A.2: a_lat(t) = V(t)² · κ(s(t)) exactly."""
    kstate = process_stint(canonical_stint_artifact, nominal_params.aero)
    np.testing.assert_allclose(kstate.a_lat, kstate.v ** 2 * kstate.kappa, rtol=1e-10)


def test_module_a_a_long_is_savgol_of_speed(canonical_stint_artifact, nominal_params):
    """model_spec.md §A.2: a_long = dV/dt via Savitzky-Golay window=9 order=3."""
    from f1_core.filters import savgol_velocity
    kstate = process_stint(canonical_stint_artifact, nominal_params.aero)
    dt_median = float(np.median(np.diff(kstate.t)))
    expected = savgol_velocity(kstate.v, window=9, order=3, delta=dt_median)
    np.testing.assert_allclose(kstate.a_long, expected, rtol=1e-10)


def test_module_a_output_has_no_nan(canonical_stint_artifact, nominal_params):
    kstate = process_stint(canonical_stint_artifact, nominal_params.aero)
    for name in ("t", "v", "a_lat", "a_long", "psi", "v_sx_rear", "kappa"):
        arr = getattr(kstate, name)
        assert np.all(np.isfinite(arr)), f"{name} contains NaN or inf"


def test_module_a_a_lat_within_physical_range(canonical_stint_artifact, nominal_params):
    """F1 max lateral acceleration ≈ 5 g = 50 m/s²; sanity cap at 60 m/s²."""
    kstate = process_stint(canonical_stint_artifact, nominal_params.aero)
    assert np.max(np.abs(kstate.a_lat)) < 60.0


def test_module_a_v_sx_rear_zero_when_gear_unknown(nominal_params):
    """Synthetic: gear=0 everywhere → V_sx,r=0 per §A.4 fallback."""
    from f1_core.physics.module_a import _v_sx_rear_from_telemetry
    rpm = np.array([12000.0, 13000.0, 14000.0])
    gear = np.array([0.0, 0.0, 0.0])
    v = np.array([30.0, 40.0, 50.0])
    combined = {}  # no ratios known
    v_sx = _v_sx_rear_from_telemetry(rpm, gear, v, combined)
    np.testing.assert_array_equal(v_sx, np.zeros(3))


def test_module_a_v_sx_rear_matches_formula_when_gear_known(nominal_params):
    """model_spec.md §A.4: V_wheel,r = 2π·R_0·RPM/(60·combined_ratio); V_sx,r = V_wheel,r − V."""
    from f1_core.gear_inference import R_0_M
    from f1_core.physics.module_a import _v_sx_rear_from_telemetry
    rpm = np.array([10000.0])
    gear = np.array([5.0])
    v = np.array([70.0])
    combined_ratio = 2.5
    combined = {5: combined_ratio}
    expected_wheel = 2.0 * np.pi * R_0_M * 10000.0 / (60.0 * combined_ratio)
    expected_v_sx = expected_wheel - 70.0
    v_sx = _v_sx_rear_from_telemetry(rpm, gear, v, combined)
    np.testing.assert_allclose(v_sx, [expected_v_sx], rtol=1e-12)


def test_module_a_on_canonical_fixture_completes_without_raising(canonical_stint_artifact, nominal_params):
    """Smoke test — pipeline runs end-to-end on the real fixture."""
    kstate = process_stint(canonical_stint_artifact, nominal_params.aero)
    assert len(kstate.t) > 100  # fixture has ~8000 samples
