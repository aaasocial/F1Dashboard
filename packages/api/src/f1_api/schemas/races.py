"""Pydantic v2 response models for /races (API-01)."""

from __future__ import annotations

import datetime as _dt

from pydantic import BaseModel, ConfigDict


class RaceSummaryResponse(BaseModel):
    """One completed race (immutable history)."""

    model_config = ConfigDict(from_attributes=True)

    year: int
    round: int
    name: str
    country: str = ""
    date: _dt.date | None = None
