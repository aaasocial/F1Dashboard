"""GET /stints/{race_id}/{driver_id} — API-03."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from f1_api.dependencies import DriverCode, RaceId
from f1_api.schemas.stints import StintSummaryResponse
from f1_api.services.stints import list_stints_for_driver

router = APIRouter()


@router.get(
    "/stints/{race_id}/{driver_id}",
    response_model=list[StintSummaryResponse],
)
def get_stints(
    race_id: RaceId,
    driver_id: DriverCode,
) -> list[StintSummaryResponse]:
    """Return stints for (race_id, driver_id) with compound, lap count, quality.

    T-01-10: both path params validated by Pydantic BEFORE filesystem/FastF1 touch.
    """
    try:
        stints = list_stints_for_driver(race_id, driver_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return [StintSummaryResponse.model_validate(s) for s in stints]
