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
