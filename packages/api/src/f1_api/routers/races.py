"""GET /races — API-01."""

from __future__ import annotations

from fastapi import APIRouter, Query, Response

from f1_api.schemas.races import RaceSummaryResponse
from f1_api.services.stints import list_races

router = APIRouter()


@router.get("/races", response_model=list[RaceSummaryResponse])
def get_races(
    response: Response,
    start_year: int = Query(2022, ge=2022, le=2100),
    end_year: int | None = Query(None, ge=2022, le=2100),
) -> list[RaceSummaryResponse]:
    """Return the schedule of completed races from start_year to end_year (inclusive).

    T-01-12: year bounds enforced by Query.
    """
    summaries = list_races(start_year=start_year, end_year=end_year)
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return [RaceSummaryResponse.model_validate(r) for r in summaries]
