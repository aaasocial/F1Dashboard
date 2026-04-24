"""GET /races/{race_id}/drivers — API-02."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from f1_api.dependencies import RaceId
from f1_api.schemas.drivers import DriverSummaryResponse
from f1_api.services.stints import list_drivers_for_race

router = APIRouter()


@router.get("/races/{race_id}/drivers", response_model=list[DriverSummaryResponse])
def get_drivers(
    race_id: RaceId,
    response: Response,
) -> list[DriverSummaryResponse]:
    """Return drivers who completed the given race with stint counts.

    T-01-10: race_id is validated by Pydantic StringConstraints in dependencies.RaceId
    BEFORE this handler runs.
    """
    try:
        drivers = list_drivers_for_race(race_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return [DriverSummaryResponse.model_validate(d) for d in drivers]
