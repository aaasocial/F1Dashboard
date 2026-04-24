"""Status events emitted by Module E when force demand exceeds grip.

Per model_spec.md §E.2 clip path and CONTEXT.md §"Common Pitfalls" Pitfall 6:
the event log is capped at MAX_EVENTS to prevent unbounded memory growth
on pathological parameter sets.
"""
from __future__ import annotations

from dataclasses import dataclass

# Pitfall 6 (Research §"Common Pitfalls"): cap total events in a run.
MAX_EVENTS: int = 500


@dataclass(frozen=True)
class StatusEvent:
    """A single diagnostic event from Module E over-demand clipping.

    Fields:
        t:         timestamp [s] at which the event was emitted
        tire_index: 0=FL, 1=FR, 2=RL, 3=RR
        kind:      short machine-readable kind code, e.g. "over_demand_lat"
        message:   human-readable description for CLI / UI status log
        ratio:     |F_y|/(μ·F_z) at emission time — >=1.0 means demand ≥ grip
    """
    t: float
    tire_index: int
    kind: str
    message: str
    ratio: float


__all__ = ["MAX_EVENTS", "StatusEvent"]
