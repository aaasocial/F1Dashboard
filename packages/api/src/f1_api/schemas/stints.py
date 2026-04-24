"""Pydantic v2 response models for /stints/{race_id}/{driver_id} (API-03).

Per D-04: Pydantic BaseModel with ConfigDict(from_attributes=True) wraps the
f1_core.stint_annotation.AnnotatedStint dataclasses at the HTTP boundary.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StintSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stint_index: int
    compound: str
    compound_letter: str = ""
    lap_count: int
    start_lap: int
    end_lap: int
    pit_in_lap: int | None = None
    pit_out_lap: int | None = None
    tire_age_at_start: int
    quality_score: float = Field(ge=0.0, le=1.0)
    quality_verdict: str  # "ok" / "warn" / "exclude" / "refuse"
