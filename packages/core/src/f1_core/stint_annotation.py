"""DATA-06: per-lap annotation (compound->C1-C5, tire age, fuel, weather, in/out-lap, SC/VSC)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from f1_core.contracts import QualityReport
from f1_core.ingestion.cache import StintKey

DEFAULT_COMPOUND_MAPPING_PATH = Path(__file__).parent / "data" / "compound_mapping.yaml"

# Fuel estimate constants: ~110 kg start load, ~1.7 kg/lap burn (approximate;
# refined in Phase 3 calibration). Good enough for annotation in Phase 1.
FUEL_START_KG = 110.0
FUEL_BURN_KG_PER_LAP = 1.7

# FastF1 track_status numeric codes:
#   1 = green, 2 = yellow, 3 = unused, 4 = SC, 5 = red flag,
#   6 = VSC deployed, 7 = VSC ending
SC_VSC_STATUS_CODES = {4, 6, 7}


@dataclass
class AnnotatedLap:
    """Per-lap annotation with compound letter, tire age, fuel, weather, and flags."""

    lap_number: int
    compound: str
    compound_letter: str  # C1-C5 or "" if unmapped
    tire_age_laps: int
    fresh_tyre: bool
    lap_time_s: float  # NaN for in/out/excluded laps
    fuel_estimate_kg: float
    air_temp_c: float
    track_temp_c: float
    is_in_lap: bool
    is_out_lap: bool
    is_sc_vsc: bool
    exclude_from_degradation: bool


@dataclass
class AnnotatedStint:
    """Bundle of per-lap annotations for a StintArtifact."""

    key: StintKey
    laps: list[AnnotatedLap] = field(default_factory=list)
    quality: QualityReport | None = None


def load_compound_mapping(
    path: Path | None = None,
) -> dict[str, dict[str, str]]:
    """Load the compound->C1-C5 mapping. Uses yaml.safe_load (T-01-08)."""
    p = path or DEFAULT_COMPOUND_MAPPING_PATH
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("compound_mapping.yaml must be a mapping")
    return data


def _compound_letter(
    compound: str,
    year: int,
    round_number: int,
    mapping: dict[str, dict[str, str]],
) -> str:
    key = f"{year}-{round_number:02d}"
    return mapping.get(key, {}).get(str(compound).upper(), "")


def _weather_at(time: Any, weather: pd.DataFrame) -> tuple[float, float]:
    """Return (air_temp, track_temp) at the given time. Nearest-match lookup."""
    if weather.empty or "Time" not in weather.columns:
        return (float("nan"), float("nan"))
    if pd.isna(time):
        return (float("nan"), float("nan"))
    idx = (weather["Time"] - time).abs().idxmin()
    row = weather.loc[idx]
    air_raw = row.get("AirTemp", float("nan"))
    trk_raw = row.get("TrackTemp", float("nan"))
    air = float(air_raw) if pd.notna(air_raw) else float("nan")
    trk = float(trk_raw) if pd.notna(trk_raw) else float("nan")
    return (air, trk)


def _lap_overlaps_sc_vsc(
    lap_start: Any,
    lap_end: Any,
    track_status: pd.DataFrame,
) -> bool:
    if track_status.empty or "Status" not in track_status.columns:
        return False
    if pd.isna(lap_start) or pd.isna(lap_end):
        return False
    # Status values in FastF1 are strings of digits; coerce to int
    ts = track_status.copy()
    ts["Status"] = pd.to_numeric(ts["Status"], errors="coerce").fillna(1).astype(int)
    mask = (
        (ts["Time"] >= lap_start)
        & (ts["Time"] <= lap_end)
        & (ts["Status"].isin(SC_VSC_STATUS_CODES))
    )
    return bool(mask.any())


def annotate_stint(
    artifact: Any,
    year: int,
    round_number: int,
    mapping: dict[str, dict[str, str]] | None = None,
    quality: QualityReport | None = None,
) -> AnnotatedStint:
    """Produce per-lap annotation for a StintArtifact (DATA-06)."""
    mapping = mapping if mapping is not None else load_compound_mapping()
    laps_df: pd.DataFrame = artifact.laps

    annotated: list[AnnotatedLap] = []
    for _, row in laps_df.iterrows():
        lap_number_raw = row.get("LapNumber", 0)
        lap_number = int(lap_number_raw) if pd.notna(lap_number_raw) else 0
        compound = str(row.get("Compound", "") or "")
        letter = _compound_letter(compound, year, round_number, mapping)
        tire_age_raw = row.get("TyreLife", 0)
        tire_age = int(tire_age_raw) if pd.notna(tire_age_raw) else 0
        fresh_raw = row.get("FreshTyre", False)
        fresh = bool(fresh_raw) if pd.notna(fresh_raw) else False
        lap_time = row.get("LapTime", pd.NaT)
        lap_time_s = float("nan") if pd.isna(lap_time) else lap_time.total_seconds()
        fuel = max(0.0, FUEL_START_KG - FUEL_BURN_KG_PER_LAP * lap_number)
        lap_start = row.get("LapStartTime", row.get("Time"))
        lap_end = row.get("Time")
        air_t, trk_t = _weather_at(lap_end, artifact.weather)
        is_out_lap = bool(pd.notna(row.get("PitOutTime")))
        is_in_lap = bool(pd.notna(row.get("PitInTime")))
        is_sc_vsc = _lap_overlaps_sc_vsc(lap_start, lap_end, artifact.track_status)
        exclude = is_in_lap or is_out_lap or is_sc_vsc
        annotated.append(
            AnnotatedLap(
                lap_number=lap_number,
                compound=compound,
                compound_letter=letter,
                tire_age_laps=tire_age,
                fresh_tyre=fresh,
                lap_time_s=lap_time_s,
                fuel_estimate_kg=fuel,
                air_temp_c=air_t,
                track_temp_c=trk_t,
                is_in_lap=is_in_lap,
                is_out_lap=is_out_lap,
                is_sc_vsc=is_sc_vsc,
                exclude_from_degradation=exclude,
            )
        )

    return AnnotatedStint(key=artifact.key, laps=annotated, quality=quality)
