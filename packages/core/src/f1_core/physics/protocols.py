"""Protocols for Phase 2 physics module shapes.

Module A is NOT a PhysicsModule — it processes a full stint in one call,
not per timestep. CONTEXT.md D-01 leaves the protocol name to the planner;
StintPreprocessor is the canonical name chosen here.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from f1_core.contracts import KinematicState
from f1_core.ingestion.cache import StintArtifact
from f1_core.physics.params import AeroParams


@runtime_checkable
class StintPreprocessor(Protocol):
    """A stint-level preprocessor (Module A). One call per stint.

    Implementations MUST be stateless and MUST return a KinematicState whose
    arrays are all shape (N,) for the same N.
    """

    def process_stint(
        self,
        artifact: StintArtifact,
        aero_params: AeroParams,
    ) -> KinematicState: ...


__all__ = ["StintPreprocessor"]
