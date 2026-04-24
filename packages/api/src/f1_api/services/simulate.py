"""Simulation service — orchestrates the 7-module physics engine.

This module provides run_simulation_with_uncertainty, the core entry point
called by both POST /simulate (sync, via FastAPI threadpool) and
POST /simulate/stream (async, via asyncio.to_thread).

The actual implementation lives in the Phase 4 service layer; this module
exposes the public API consumed by the routers.
"""
from __future__ import annotations

from f1_api.schemas.simulate import (
    ParameterOverrides,
    SimulateResponse,
)


def run_simulation_with_uncertainty(
    race_id: str,
    driver_code: str,
    stint_index: int,
    overrides: ParameterOverrides | None,
    session_id: str | None,
) -> SimulateResponse:
    """Run 7-module physics simulation with K=100 posterior draws.

    Returns SimulateResponse with per-timestep, per-lap, and per-stint CI triplets.
    Track geometry fields (track, sector_bounds, turns) are NOT populated here;
    they are added by the SSE endpoint after this call returns.

    Raises:
        ValueError: If no calibration data exists for the compound, or if the
                   specified stint index is not found in the race data.
    """
    raise NotImplementedError(
        "run_simulation_with_uncertainty is provided by the Phase 4 service layer. "
        "This stub should be replaced or the real implementation should be present."
    )
