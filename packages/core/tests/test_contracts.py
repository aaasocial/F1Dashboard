"""PHYS-08 (contract portion) + PHYS-09 (state-object portion) tests.

Referenced by 01-VALIDATION.md:
- test_placeholder_satisfies_protocol
- test_all_seven_contracts_importable_from_single_module
- test_simulation_state_shape
"""

from __future__ import annotations

import sys

import numpy as np
from f1_core.contracts import (
    KinematicState,
    PhysicsModule,
    QualityReport,
    QualityVerdict,
    SimulationState,
    WheelLoads,
)


class _PlaceholderModule:
    """Minimal class satisfying PhysicsModule via structural subtyping."""

    def step(self, state_in, telemetry_sample, params):
        return state_in


class _NonConformingClass:
    """Does NOT implement step() — should fail PhysicsModule isinstance check."""

    def do_something(self) -> None:
        pass


def test_placeholder_satisfies_protocol() -> None:
    placeholder = _PlaceholderModule()
    assert isinstance(placeholder, PhysicsModule)


def test_non_conforming_class_fails_protocol() -> None:
    bad = _NonConformingClass()
    assert not isinstance(bad, PhysicsModule)


def test_all_seven_contracts_importable_from_single_module() -> None:
    from f1_core import contracts

    for name in (
        "KinematicState",
        "WheelLoads",
        "ContactPatch",
        "SlipState",
        "ThermalState",
        "DegradationState",
        "SimulationState",
    ):
        assert hasattr(contracts, name), f"missing contract: {name}"


def test_simulation_state_shape() -> None:
    state = SimulationState(
        t_tread=np.full(4, 100.0),
        t_carc=np.full(4, 90.0),
        t_gas=np.full(4, 80.0),
        e_tire=np.zeros(4),
        mu_0=1.5,
        d_tread=np.full(4, 0.008),
    )
    assert state.t_tread.shape == (4,)
    assert state.t_carc.shape == (4,)
    assert state.t_gas.shape == (4,)
    assert state.e_tire.shape == (4,)
    assert state.d_tread.shape == (4,)
    assert isinstance(state.mu_0, float)


def test_contracts_module_does_not_import_pydantic() -> None:
    # D-04: physics types must not import pydantic
    # Clear any pre-imported pydantic, then re-import contracts and check
    import importlib

    for key in list(sys.modules.keys()):
        if key == "pydantic" or key.startswith("pydantic."):
            del sys.modules[key]
    import f1_core.contracts as c

    importlib.reload(c)
    assert "pydantic" not in sys.modules, (
        "contracts.py must not transitively import pydantic (D-04 boundary)"
    )


def test_quality_report_verdict_enum_values() -> None:
    assert QualityVerdict.OK.value == "ok"
    assert QualityVerdict.WARN.value == "warn"
    assert QualityVerdict.EXCLUDE.value == "exclude"
    assert QualityVerdict.REFUSE.value == "refuse"


def test_quality_report_default_construction() -> None:
    report = QualityReport(score=1.0, verdict=QualityVerdict.OK)
    assert report.score == 1.0
    assert report.verdict is QualityVerdict.OK
    assert report.issues == []
    assert report.throttle_sentinel_count == 0


def test_kinematic_state_field_shape_contract() -> None:
    n = 100
    ks = KinematicState(
        t=np.zeros(n),
        v=np.zeros(n),
        a_lat=np.zeros(n),
        a_long=np.zeros(n),
        psi=np.zeros(n),
        v_sx_rear=np.zeros(n),
        kappa=np.zeros(n),
    )
    assert ks.t.shape == (n,)
    assert ks.v.shape == (n,)


def test_wheel_loads_per_tire_shape() -> None:
    n = 100
    wl = WheelLoads(t=np.zeros(n), f_z=np.zeros((n, 4)))
    assert wl.f_z.shape == (n, 4)


import pytest
from dataclasses import FrozenInstanceError


@pytest.mark.parametrize("cls_name,kwargs", [
    ("KinematicState", dict(t=np.zeros(1), v=np.zeros(1), a_lat=np.zeros(1),
                            a_long=np.zeros(1), psi=np.zeros(1),
                            v_sx_rear=np.zeros(1), kappa=np.zeros(1))),
    ("WheelLoads",    dict(t=np.zeros(1), f_z=np.zeros((1, 4)))),
    ("ContactPatch",  dict(t=np.zeros(1), a_cp=np.zeros((1, 4)), p_bar=np.zeros((1, 4)))),
    ("SlipState",     dict(t=np.zeros(1), theta=np.zeros((1, 4)), alpha=np.zeros((1, 4)),
                           v_sy=np.zeros((1, 4)), p_slide=np.zeros((1, 4)),
                           p_total=np.zeros((1, 4)))),
    ("ThermalState",  dict(t=np.zeros(1), t_tread=np.zeros((1, 4)),
                           t_carc=np.zeros((1, 4)), t_gas=np.zeros((1, 4)))),
    ("DegradationState", dict(t=np.zeros(1), e_tire=np.zeros((1, 4)),
                              mu_0=np.zeros(1), d_tread=np.zeros((1, 4)))),
])
def test_module_output_contracts_are_frozen(cls_name, kwargs):
    """PHYS-09 / PHYS-08: per-module outputs are immutable to prevent cross-module mutation."""
    from f1_core import contracts
    cls = getattr(contracts, cls_name)
    obj = cls(**kwargs)
    # Grab first field name to attempt rebind
    first_field = next(iter(kwargs))
    with pytest.raises(FrozenInstanceError):
        setattr(obj, first_field, kwargs[first_field])


def test_simulation_state_is_mutable():
    """SimulationState is the carryover state — must stay mutable for the orchestrator loop."""
    from f1_core.contracts import SimulationState
    s = SimulationState(
        t_tread=np.zeros(4), t_carc=np.zeros(4), t_gas=np.zeros(4),
        e_tire=np.zeros(4), mu_0=1.8, d_tread=np.full(4, 0.008),
    )
    s.mu_0 = 1.7   # must not raise
    assert s.mu_0 == 1.7


def test_f1_core_physics_does_not_import_pydantic():
    """D-03 boundary: physics/ subpackage must not import pydantic (same rule as contracts.py)."""
    from pathlib import Path
    phys_dir = Path("packages/core/src/f1_core/physics")
    if not phys_dir.exists():
        pytest.skip("physics/ not yet created")
    for py_file in phys_dir.rglob("*.py"):
        src = py_file.read_text(encoding="utf-8")
        assert "import pydantic" not in src, f"{py_file} imports pydantic"
        assert "from pydantic" not in src, f"{py_file} imports pydantic"
