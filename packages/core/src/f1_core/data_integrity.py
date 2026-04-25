"""DATA-05: per-stint quality scoring + verdict.

Counts throttle sentinels, NaN lap times, within-stint compound changes, missing
positions. Combines them into a score in [0, 1] + a categorical verdict.

Thresholds (A6 in research, flagged for later validation):
  OK      score >= 0.9
  WARN    0.7 <= score < 0.9
  EXCLUDE 0.4 <= score < 0.7
  REFUSE  score < 0.4
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from f1_core.contracts import QualityReport, QualityVerdict

SENTINEL_THROTTLE_THRESHOLD = 100  # any value > 100 is a sentinel (pitfall P2)

DEFAULT_KNOWN_ISSUES_PATH = Path(__file__).parent / "data" / "known_issues.yaml"


def load_known_issues(path: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    """Load the known-issues registry. Uses yaml.safe_load (T-01-08)."""
    p = path or DEFAULT_KNOWN_ISSUES_PATH
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"known_issues.yaml must be a mapping, got {type(data).__name__}")
    return data


def analyze(
    car_data: pd.DataFrame,
    laps: pd.DataFrame,
    pos_data: pd.DataFrame,
    year: int,
    round_number: int,
    known_issues: dict[str, list[dict[str, Any]]] | None = None,
) -> QualityReport:
    """Produce a QualityReport for a stint (DATA-05)."""
    if known_issues is None:
        known_issues = load_known_issues()

    issues: list[str] = []

    # Throttle sentinels (pitfall P2)
    if not car_data.empty and "Throttle" in car_data.columns:
        throttle_sentinels = int((car_data["Throttle"] > SENTINEL_THROTTLE_THRESHOLD).sum())
    else:
        throttle_sentinels = 0
    if throttle_sentinels > 0:
        issues.append(f"throttle_sentinels={throttle_sentinels}")

    # NaN lap times
    if not laps.empty and "LapTime" in laps.columns:
        nan_laps = int(laps["LapTime"].isna().sum())
    else:
        nan_laps = 0
    if nan_laps > 0:
        issues.append(f"nan_lap_times={nan_laps}")

    # Compound continuity within stint (pitfall P3)
    compound_mislabel = False
    if not laps.empty and {"Stint", "Compound"}.issubset(laps.columns):
        for stint_idx, stint_laps in laps.groupby("Stint"):
            uniques = stint_laps["Compound"].dropna().unique()
            if len(uniques) > 1:
                compound_mislabel = True
                issues.append(f"compound_changes_within_stint={stint_idx}")

    # Known-issues override
    key = f"{year}-{round_number:02d}"
    for issue in known_issues.get(key, []):
        tag = issue.get("tag", "unknown")
        issues.append(f"known_issue:{tag}")
        if tag == "compound_mislabel":
            compound_mislabel = True

    # Missing positions
    if not pos_data.empty and {"X", "Y"}.issubset(pos_data.columns):
        missing_pos_pct = float(pos_data[["X", "Y"]].isna().any(axis=1).mean())
    else:
        missing_pos_pct = 0.0
    if missing_pos_pct > 0:
        issues.append(f"missing_position_pct={missing_pos_pct:.3f}")

    # Score
    n_samples = max(len(car_data), 1)
    n_laps = max(len(laps), 1)
    score = 1.0
    score -= min(0.5, throttle_sentinels / n_samples)
    score -= min(0.3, nan_laps / n_laps)
    score -= 0.3 if compound_mislabel else 0.0
    score -= min(0.2, missing_pos_pct)
    score = max(0.0, score)

    if score >= 0.9:
        verdict = QualityVerdict.OK
    elif score >= 0.7:
        verdict = QualityVerdict.WARN
    elif score >= 0.4:
        verdict = QualityVerdict.EXCLUDE
    else:
        verdict = QualityVerdict.REFUSE

    return QualityReport(
        score=score,
        verdict=verdict,
        issues=issues,
        throttle_sentinel_count=throttle_sentinels,
        nan_lap_time_count=nan_laps,
        compound_mislabel=compound_mislabel,
        missing_position_pct=missing_pos_pct,
    )
