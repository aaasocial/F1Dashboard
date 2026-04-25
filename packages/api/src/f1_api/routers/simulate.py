"""POST /simulate router — API-04.

CPU-bound (K=100 forward passes) → plain `def` so FastAPI runs it in the
threadpool (Pitfall 1). D-05: service module refuses to load if pymc/
numpyro/pytensor are already imported.
"""
from __future__ import annotations
import logging

from fastapi import APIRouter, HTTPException

from f1_api.schemas.simulate import SimulateRequest, SimulateResponse
from f1_api.services.simulate import run_simulation_with_uncertainty

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/simulate", response_model=SimulateResponse)
def simulate(body: SimulateRequest) -> SimulateResponse:
    """K=100 posterior-draw forward pass; cache hit <50 ms; cold <2 s.

    D-01: three data levels in one response (per-timestep + per-lap + per-stint).
    D-02: CI triplets mean/lo_95/hi_95 at every level.
    D-03: metadata block with calibration_id, model_schema_version, fastf1_version.
    D-04: K=100 draws; overrides apply equally to all K.
    D-05: no PyMC at runtime (enforced by service-module guard).
    D-06: two-layer cache.
    """
    try:
        return run_simulation_with_uncertainty(
            race_id=body.race_id,
            driver_code=body.driver_code,
            stint_index=body.stint_index,
            overrides=body.overrides,
            session_id=body.session_id,
        )
    except ValueError as e:
        msg = str(e)
        if "no calibration" in msg.lower():
            raise HTTPException(status_code=404, detail=msg) from e
        if "stint" in msg.lower() and "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg) from e
        # Default: treat as bad request
        raise HTTPException(status_code=422, detail=msg) from e
