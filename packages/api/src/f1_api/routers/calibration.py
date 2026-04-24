"""GET /calibration/{compound} -- API-05.

`def` route (not async) -- the DB + NetCDF read is a few ms, but we keep
the project-wide convention of `def` routes for simplicity.
"""
from __future__ import annotations
import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import StringConstraints

from f1_api.schemas.calibration import CalibrationResponse
from f1_api.services.calibration import build_calibration_summary

log = logging.getLogger(__name__)
router = APIRouter()

# Pydantic-level whitelist at the path-param layer. Service re-validates
# via f1_calibration.db.validate_compound for defense-in-depth (T-4-SQL).
CompoundCode = Annotated[
    str,
    StringConstraints(pattern=r"^[Cc][1-5]$", min_length=2, max_length=2),
]


@router.get("/calibration/{compound}", response_model=CalibrationResponse)
def get_calibration(compound: CompoundCode) -> CalibrationResponse:
    """Return per-stage parameter summary for compound (D-09)."""
    try:
        return build_calibration_summary(compound)
    except ValueError as e:
        msg = str(e)
        if "no calibration" in msg.lower() or "missing" in msg.lower():
            raise HTTPException(status_code=404, detail=msg) from e
        # Compound-regex failures from validate_compound (defense-in-depth)
        raise HTTPException(status_code=422, detail=msg) from e
