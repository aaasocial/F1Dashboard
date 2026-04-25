"""Cache-directory resolution + path-param validation.

Per CONTEXT.md (Claude's discretion): local default `.data/fastf1_cache`, env override
`F1_CACHE_DIR`. Production (Phase 7) will set F1_CACHE_DIR=/data/fastf1_cache.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# Threat T-01-04: race_id / driver_id MUST match these regexes before filesystem use.
RACE_ID_PATTERN = re.compile(r"^[0-9]{4}-[a-z0-9_]+$")
DRIVER_CODE_PATTERN = re.compile(r"^[A-Z]{3}$")


def get_cache_dir() -> Path:
    """Resolve the FastF1 + Layer-2 cache root.

    Reads F1_CACHE_DIR env var; falls back to `.data/fastf1_cache` in the cwd.
    """
    raw = os.environ.get("F1_CACHE_DIR", ".data/fastf1_cache")
    p = Path(raw).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def validate_race_id(race_id: str) -> str:
    """Return race_id if it matches RACE_ID_PATTERN, else raise ValueError.

    Format: `YYYY-event_slug`, e.g. `2023-bahrain`. Lowercase event slug only.
    """
    if not RACE_ID_PATTERN.fullmatch(race_id):
        raise ValueError(f"Invalid race_id {race_id!r}: must match ^[0-9]{{4}}-[a-z0-9_]+$")
    return race_id


def validate_driver_code(driver_code: str) -> str:
    """Return driver_code if it's a 3-letter uppercase code, else raise ValueError."""
    if not DRIVER_CODE_PATTERN.fullmatch(driver_code):
        raise ValueError(f"Invalid driver_code {driver_code!r}: must match ^[A-Z]{{3}}$")
    return driver_code


def parse_race_id(race_id: str) -> tuple[int, str]:
    """Split `YYYY-event_slug` into (year, event_slug). Validates first."""
    validate_race_id(race_id)
    year_str, slug = race_id.split("-", 1)
    return int(year_str), slug
