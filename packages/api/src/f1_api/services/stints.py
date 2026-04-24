"""Service layer: translates f1_core dataclasses into API-shaped dicts/dataclasses.

Separated from routers so TestClient tests can monkeypatch a single function
(`build_stint_summary_for_driver`) instead of mocking FastF1 at import time.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd
from f1_core.data_integrity import analyze
from f1_core.ingestion import load_schedule, load_stint, parse_race_id
from f1_core.stint_annotation import load_compound_mapping

log = logging.getLogger(__name__)


@dataclass
class StintSummary:
    """Plain dataclass — consumed by StintSummaryResponse.model_validate()."""

    stint_index: int
    compound: str
    compound_letter: str
    lap_count: int
    start_lap: int
    end_lap: int
    pit_in_lap: int | None
    pit_out_lap: int | None
    tire_age_at_start: int
    quality_score: float
    quality_verdict: str


@dataclass
class DriverSummary:
    driver_code: str
    full_name: str
    team: str
    stint_count: int


@dataclass
class RaceSummary:
    year: int
    round: int
    name: str
    country: str
    date: object  # datetime.date or None


def list_races(start_year: int = 2022, end_year: int | None = None) -> list[RaceSummary]:
    """API-01 backend."""
    from datetime import date

    if end_year is None:
        end_year = date.today().year
    out: list[RaceSummary] = []
    for year in range(start_year, end_year + 1):
        try:
            sched = load_schedule(year)
        except Exception as e:
            log.warning("Failed to load schedule for year %d: %s", year, e, exc_info=True)
            continue
        for _, row in sched.iterrows():
            evt_date = row.get("EventDate")
            if isinstance(evt_date, pd.Timestamp):
                evt_date = evt_date.date()
            out.append(
                RaceSummary(
                    year=int(year),
                    round=int(row.get("RoundNumber", 0)),
                    name=str(row.get("EventName", "")),
                    country=str(row.get("Country", "") or ""),
                    date=evt_date,
                )
            )
    return out


def list_drivers_for_race(race_id: str) -> list[DriverSummary]:
    """API-02 backend. Relies on a Session being available from FastF1 cache."""
    import fastf1

    year, slug = parse_race_id(race_id)
    session = fastf1.get_session(year, slug.replace("_", " "), "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    out: list[DriverSummary] = []
    laps = session.laps
    for drv in session.drivers:
        try:
            info = session.get_driver(drv)
        except Exception as e:
            log.warning("get_driver(%s) failed: %s", drv, e, exc_info=True)
            info = {}
        code = str(info.get("Abbreviation", drv))
        full = f"{info.get('FirstName', '')} {info.get('LastName', '')}".strip()
        team = str(info.get("TeamName", ""))
        drv_laps = laps.pick_drivers(code) if code else laps[laps["Driver"] == drv]
        stint_count = int(drv_laps["Stint"].dropna().nunique()) if not drv_laps.empty else 0
        out.append(
            DriverSummary(driver_code=code, full_name=full, team=team, stint_count=stint_count)
        )
    return out


def list_stints_for_driver(race_id: str, driver_code: str) -> list[StintSummary]:
    """API-03 backend. Uses canonical ingestion path + data_integrity + annotation."""
    import fastf1

    year, slug = parse_race_id(race_id)
    session = fastf1.get_session(year, slug.replace("_", " "), "R")
    session.load(laps=True, telemetry=False, weather=True, messages=True)
    round_number = int(session.event["RoundNumber"])

    drv_laps = session.laps.pick_drivers(driver_code)
    if drv_laps.empty:
        return []

    stint_ids = sorted(drv_laps["Stint"].dropna().unique())
    mapping = load_compound_mapping()
    out: list[StintSummary] = []
    for stint_idx in stint_ids:
        stint_laps = drv_laps[drv_laps["Stint"] == stint_idx]
        # Load the actual stint artifact for integrity scoring (uses Layer-2 cache)
        artifact = load_stint(
            year=year,
            event=slug.replace("_", " "),
            driver_code=driver_code,
            stint_index=int(stint_idx),
        )
        report = analyze(
            artifact.car_data,
            artifact.laps,
            artifact.pos_data,
            year=year,
            round_number=round_number,
        )
        compound_series = stint_laps["Compound"].dropna()
        compound = str(compound_series.iloc[0]) if not compound_series.empty else ""
        letter = mapping.get(f"{year}-{round_number:02d}", {}).get(compound.upper(), "")
        pit_in = stint_laps.loc[stint_laps["PitInTime"].notna(), "LapNumber"]
        pit_out = stint_laps.loc[stint_laps["PitOutTime"].notna(), "LapNumber"]
        tyre_life_col = stint_laps["TyreLife"] if "TyreLife" in stint_laps.columns else None
        tire_age = (
            int(tyre_life_col.iloc[0])
            if tyre_life_col is not None and not tyre_life_col.isna().all()
            else 0
        )
        out.append(
            StintSummary(
                stint_index=int(stint_idx),
                compound=compound,
                compound_letter=letter,
                lap_count=len(stint_laps),
                start_lap=int(stint_laps["LapNumber"].min()),
                end_lap=int(stint_laps["LapNumber"].max()),
                pit_in_lap=int(pit_in.iloc[0]) if not pit_in.empty else None,
                pit_out_lap=int(pit_out.iloc[0]) if not pit_out.empty else None,
                tire_age_at_start=tire_age,
                quality_score=float(report.score),
                quality_verdict=str(report.verdict.value),
            )
        )
    return out
