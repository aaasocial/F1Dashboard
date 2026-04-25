"""DATA-05 tests: quality scoring on clean, corrupted, and synthetic inputs."""

from __future__ import annotations

import gzip
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from f1_core.contracts import QualityVerdict
from f1_core.data_integrity import analyze

FIX_DIR = Path(__file__).parent / "fixtures"


def _load(name: str):
    p = FIX_DIR / name
    if not p.exists():
        pytest.skip(f"Fixture missing: {p}")
    with gzip.open(p, "rb") as f:
        return pickle.load(f)


def test_clean_fixture_ok() -> None:
    a = _load("bahrain_2023_ver_stint2.pkl.gz")
    report = analyze(a.car_data, a.laps, a.pos_data, year=2023, round_number=a.key.round)
    assert report.verdict == QualityVerdict.OK, (
        f"canonical fixture must score OK; got verdict={report.verdict} "
        f"score={report.score:.3f} issues={report.issues}"
    )
    assert report.score >= 0.9


def test_corrupted_fixture_excluded() -> None:
    a = _load("corrupted_stint.pkl.gz")
    report = analyze(a.car_data, a.laps, a.pos_data, year=2023, round_number=a.key.round)
    assert report.verdict in {
        QualityVerdict.EXCLUDE,
        QualityVerdict.REFUSE,
        QualityVerdict.WARN,
    }, f"corrupted fixture must downgrade; got {report.verdict}"
    assert report.score < 0.9


def test_throttle_sentinel_detection() -> None:
    car = pd.DataFrame({"Throttle": [50, 60, 104, 104, 70, 104, 80, 104, 90, 104, 104, 100]})
    laps = pd.DataFrame(
        {
            "LapTime": [pd.Timedelta(seconds=90)],
            "Stint": [1],
            "Compound": ["MEDIUM"],
        }
    )
    pos = pd.DataFrame({"X": [0.0], "Y": [0.0]})
    report = analyze(car, laps, pos, year=2023, round_number=1)
    assert report.throttle_sentinel_count == 6


def test_nan_lap_time_counted() -> None:
    car = pd.DataFrame({"Throttle": [50, 60]})
    laps = pd.DataFrame(
        {
            "LapTime": [
                pd.Timedelta(seconds=90),
                pd.NaT,
                pd.NaT,
                pd.Timedelta(seconds=91),
            ],
            "Stint": [1, 1, 1, 1],
            "Compound": ["MEDIUM"] * 4,
        }
    )
    pos = pd.DataFrame({"X": [0.0], "Y": [0.0]})
    report = analyze(car, laps, pos, year=2023, round_number=1)
    assert report.nan_lap_time_count == 2


def test_compound_mislabel_within_stint() -> None:
    car = pd.DataFrame({"Throttle": [50]})
    laps = pd.DataFrame(
        {
            "LapTime": [pd.Timedelta(seconds=90)] * 4,
            "Stint": [1, 1, 1, 1],
            "Compound": ["MEDIUM", "MEDIUM", "HARD", "HARD"],
        }
    )
    pos = pd.DataFrame({"X": [0.0], "Y": [0.0]})
    report = analyze(car, laps, pos, year=2023, round_number=1)
    assert report.compound_mislabel is True


def test_missing_position_pct() -> None:
    car = pd.DataFrame({"Throttle": [50]})
    laps = pd.DataFrame(
        {
            "LapTime": [pd.Timedelta(seconds=90)],
            "Stint": [1],
            "Compound": ["MEDIUM"],
        }
    )
    pos = pd.DataFrame({"X": [0.0, np.nan, 2.0, np.nan], "Y": [0.0, 1.0, 2.0, 3.0]})
    report = analyze(car, laps, pos, year=2023, round_number=1)
    assert report.missing_position_pct == pytest.approx(0.5)


def test_known_issues_override_downgrades_verdict() -> None:
    car = pd.DataFrame({"Throttle": [50]})
    laps = pd.DataFrame(
        {
            "LapTime": [pd.Timedelta(seconds=90)],
            "Stint": [1],
            "Compound": ["MEDIUM"],
        }
    )
    pos = pd.DataFrame({"X": [0.0], "Y": [0.0]})
    known = {"2023-99": [{"tag": "compound_mislabel", "description": "test"}]}
    report = analyze(car, laps, pos, year=2023, round_number=99, known_issues=known)
    assert report.compound_mislabel is True
    assert "known_issue:compound_mislabel" in report.issues
