"""PHYS-08, PHYS-09 — Orchestrator execution order and state carry."""
from __future__ import annotations

import numpy as np
import pytest

from f1_core.physics.events import MAX_EVENTS
from f1_core.physics.orchestrator import SimulationResult, run_simulation


def test_orchestrator_runs_on_canonical_fixture(canonical_stint_artifact, nominal_params):
    result = run_simulation(canonical_stint_artifact, nominal_params)
    assert isinstance(result, SimulationResult)
    assert len(result.per_lap) >= 1


def test_orchestrator_per_timestep_array_shapes(canonical_stint_artifact, nominal_params):
    result = run_simulation(canonical_stint_artifact, nominal_params)
    n = len(result.t)
    assert result.f_z.shape == (n, 4)
    assert result.f_y.shape == (n, 4)
    assert result.mu.shape == (n, 4)
    assert result.t_tread.shape == (n, 4)
    assert result.e_tire.shape == (n, 4)
    assert result.mu_0.shape == (n,)


def test_orchestrator_strict_execution_order(
    canonical_stint_artifact, nominal_params, monkeypatch,
):
    """PHYS-09: Module A once, then B->C->D->E->F->G repeated per timestep."""
    call_log: list[str] = []

    # Wrap each module's step function to record its letter
    from f1_core.physics import orchestrator as orch
    orig_a = orch.process_stint
    orig_b = orch.wheel_loads_step
    orig_c = orch.force_distribution_step
    orig_d = orch.contact_and_friction_step
    orig_e = orch.slip_inversion_step
    orig_f = orch.thermal_step
    orig_g = orch.degradation_step

    def wrap(letter, fn):
        def w(*args, **kw):
            call_log.append(letter)
            return fn(*args, **kw)
        return w

    monkeypatch.setattr(orch, "process_stint", wrap("A", orig_a))
    monkeypatch.setattr(orch, "wheel_loads_step", wrap("B", orig_b))
    monkeypatch.setattr(orch, "force_distribution_step", wrap("C", orig_c))
    monkeypatch.setattr(orch, "contact_and_friction_step", wrap("D", orig_d))
    monkeypatch.setattr(orch, "slip_inversion_step", wrap("E", orig_e))
    monkeypatch.setattr(orch, "thermal_step", wrap("F", orig_f))
    monkeypatch.setattr(orch, "degradation_step", wrap("G", orig_g))

    result = run_simulation(canonical_stint_artifact, nominal_params)

    assert call_log[0] == "A", "Module A must be the first call"
    # Remaining calls are groups of six B->C->D->E->F->G
    rest = call_log[1:]
    assert len(rest) % 6 == 0
    stride = ["B", "C", "D", "E", "F", "G"]
    for i in range(0, len(rest), 6):
        assert rest[i:i + 6] == stride, f"Execution out of order at step {i // 6}"


def test_orchestrator_simulation_state_carries_across_steps(
    canonical_stint_artifact, nominal_params,
):
    """State carryover — mu_0 should change from initial after first timestep."""
    result = run_simulation(canonical_stint_artifact, nominal_params)
    # mu_0 at step 0 should be slightly lower than mu_0_fresh due to
    # beta_therm*mu_0*dt aging even at T_ref.
    assert result.mu_0[0] < nominal_params.friction.mu_0_fresh
    # And the trajectory should be monotonically non-increasing.
    assert np.all(np.diff(result.mu_0) <= 1e-15)


def test_orchestrator_per_lap_rows_have_required_columns(
    canonical_stint_artifact, nominal_params,
):
    """D-05 column set."""
    result = run_simulation(canonical_stint_artifact, nominal_params)
    assert len(result.per_lap) > 0
    required = {"Lap", "Compound", "Age", "Pred_s", "Obs_s", "Delta_s",
                "Grip_pct", "T_tread_C", "E_tire_MJ"}
    for row in result.per_lap:
        assert required.issubset(set(row.keys()))


def test_orchestrator_events_capped(canonical_stint_artifact, nominal_params):
    """Pitfall 6: events list never exceeds MAX_EVENTS."""
    result = run_simulation(canonical_stint_artifact, nominal_params)
    assert len(result.events) <= MAX_EVENTS


def test_orchestrator_e_tire_monotonic_on_real_stint(
    canonical_stint_artifact, nominal_params,
):
    """PHYS-07 / Criterion 6 through the full pipeline, not just Module G unit."""
    result = run_simulation(canonical_stint_artifact, nominal_params)
    # Cumulative energy per tire must never decrease step-to-step
    for tire in range(4):
        diffs = np.diff(result.e_tire[:, tire])
        assert (diffs >= -1e-9).all(), f"E_tire non-monotonic on tire {tire}"
