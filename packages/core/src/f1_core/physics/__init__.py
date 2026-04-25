"""f1_core.physics — seven-module forward simulation pipeline (Phase 2).

model_spec.md §A–G is the authoritative spec. Every equation in submodules
must cite its section (e.g., "model_spec.md §B.2") and its source paper.
"""
from f1_core.physics.events import StatusEvent
from f1_core.physics.params import (
    AeroParams,
    DegradationParams,
    FrictionParams,
    PhysicsParams,
    ThermalParams,
)
from f1_core.physics.defaults import make_nominal_params

__all__ = [
    "AeroParams",
    "DegradationParams",
    "FrictionParams",
    "PhysicsParams",
    "StatusEvent",
    "ThermalParams",
    "make_nominal_params",
]
