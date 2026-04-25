"""Pydantic v2 schemas for POST /sessions/upload (API-06, D-07, D-08)."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SessionUploadResponse(BaseModel):
    """Returned on successful upload."""

    model_config = ConfigDict(frozen=True)
    session_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    expires_at: str  # ISO-8601 UTC timestamp


__all__ = ["SessionUploadResponse"]
