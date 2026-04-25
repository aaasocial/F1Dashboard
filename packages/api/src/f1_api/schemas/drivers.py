"""Pydantic v2 response models for /races/{race_id}/drivers (API-02)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DriverSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    driver_code: str
    full_name: str
    team: str
    stint_count: int
