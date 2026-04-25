"""Shared FastAPI dependencies: validated path-param types."""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

# Reuse the exact regexes from f1_core.ingestion.config (T-01-10 mitigation).
# Duplicating here keeps API schema explicit in OpenAPI docs.
RaceId = Annotated[
    str,
    StringConstraints(pattern=r"^[0-9]{4}-[a-z0-9_]+$", min_length=6, max_length=48),
]
DriverCode = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Z]{3}$", min_length=3, max_length=3),
]
