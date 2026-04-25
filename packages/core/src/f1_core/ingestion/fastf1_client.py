"""FastF1 wrapper: Layer-1 cache init + session/stint loaders (DATA-01).

Pitfalls mitigated:
- P5: fastf1 logger set to WARNING (Jolpica rate-limit messages are INFO by default).
- P6: we never pickle fastf1.Session itself — only the extracted dataframes (cache.py).
- A8: init_cache is idempotent; fastf1.Cache.enable_cache is called at most once.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

import fastf1
import fastf1.core
import pandas as pd

from f1_core.ingestion.cache import (
    PREPROCESSING_VERSION,
    StintArtifact,
    StintKey,
    load_or_fetch,
)
from f1_core.ingestion.config import (
    get_cache_dir,
    validate_driver_code,
)

_cache_lock = threading.Lock()
_cache_initialized = False
_cache_dir: Path | None = None


def init_cache(cache_dir: Path | None = None) -> Path:
    """Call once at app/CLI startup. Idempotent. Returns the resolved cache dir.

    The directory is resolved inside the lock so that two concurrent callers with
    different cache_dir arguments always use the first-registered path (A8).
    """
    global _cache_initialized, _cache_dir
    with _cache_lock:
        if not _cache_initialized:
            resolved = cache_dir or get_cache_dir()
            # P5: silence Jolpica rate-limit chatter at INFO
            logging.getLogger("fastf1").setLevel(logging.WARNING)
            fastf1.Cache.enable_cache(str(resolved))
            _cache_initialized = True
            _cache_dir = resolved
        return _cache_dir  # type: ignore[return-value]


def _extract_artifact(
    session: fastf1.core.Session,
    key: StintKey,
) -> StintArtifact:
    """Pull the subset of `session` we need for Phase 1+2 and pack it into a StintArtifact.

    Phase 1 DOES NOT run physics — it only ingests. Plan 04 filters `laps` by stint.
    """
    # Pick the driver's laps, then this stint.
    drv_laps = session.laps.pick_drivers(key.driver_code)
    stint_laps = drv_laps[drv_laps["Stint"] == key.stint_index].copy()
    if stint_laps.empty:
        raise ValueError(
            f"No laps found for {key.driver_code} stint {key.stint_index} "
            f"in {key.year} round {key.round}"
        )

    # Car telemetry for just this stint's laps (concatenate per-lap telemetry).
    car_frames = []
    pos_frames = []
    for _, lap in stint_laps.iterlaps():
        tel = lap.get_car_data()
        if tel is not None and not tel.empty:
            car_frames.append(tel)
        pos = lap.get_pos_data()
        if pos is not None and not pos.empty:
            pos_frames.append(pos)
    car_data = pd.concat(car_frames, ignore_index=True) if car_frames else pd.DataFrame()
    pos_data = pd.concat(pos_frames, ignore_index=True) if pos_frames else pd.DataFrame()

    weather = session.weather_data.copy() if session.weather_data is not None else pd.DataFrame()
    track_status = (
        session.track_status.copy() if session.track_status is not None else pd.DataFrame()
    )
    rc_messages = (
        session.race_control_messages.copy()
        if session.race_control_messages is not None
        else pd.DataFrame()
    )

    metadata = {
        "year": key.year,
        "round": key.round,
        "event_name": session.event["EventName"] if session.event is not None else "",
        "session_type": "R",
        "driver_code": key.driver_code,
        "stint_index": key.stint_index,
    }

    return StintArtifact(
        key=key,
        car_data=car_data,
        pos_data=pos_data,
        laps=stint_laps.reset_index(drop=True),
        weather=weather,
        track_status=track_status,
        race_control_messages=rc_messages,
        session_metadata=metadata,
        fastf1_version=fastf1.__version__,
        preprocessing_version=PREPROCESSING_VERSION,
    )


def load_stint(
    *,
    year: int,
    event: str,
    session_type: str = "R",
    driver_code: str,
    stint_index: int,
    cache_root: Path | None = None,
) -> StintArtifact:
    """Fetch (or read from Layer-2 cache) a single stint artifact."""
    validate_driver_code(driver_code)
    root = init_cache(cache_root)

    # Look up the round via event schedule, cache by the canonical key.
    schedule = fastf1.get_event_schedule(year)
    row = schedule[schedule["EventName"].str.contains(event, case=False, na=False)]
    if row.empty:
        raise ValueError(f"No event matching {event!r} in {year} schedule")
    round_number = int(row.iloc[0]["RoundNumber"])

    key = StintKey(
        year=year,
        round=round_number,
        driver_code=driver_code,
        stint_index=stint_index,
    )

    def _fetcher(k: StintKey) -> StintArtifact:
        session = fastf1.get_session(year, event, session_type)
        session.load(laps=True, telemetry=True, weather=True, messages=True)
        return _extract_artifact(session, k)

    return load_or_fetch(key, root, _fetcher)


def load_schedule(year: int) -> pd.DataFrame:
    """Return the FastF1 event schedule for a year (used by API-01)."""
    init_cache()
    return fastf1.get_event_schedule(year)
