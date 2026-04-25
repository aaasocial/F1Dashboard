"""Shared fixtures for calibration tests."""
from __future__ import annotations
import sqlite3
from pathlib import Path

import numpy as np
import pytest


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    """Fresh SQLite DB file per test. Does NOT call initialize_schema — test chooses."""
    return tmp_path / "f1_test.db"


@pytest.fixture
def initialized_db(tmp_db_path: Path):
    """Yields an sqlite3.Connection with schema applied. Closes on teardown."""
    from f1_calibration.db import initialize_schema
    conn = sqlite3.connect(tmp_db_path)
    initialize_schema(conn)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def mini_compound_map() -> dict:
    """Subset of compound_map for unit tests that must not hit the full 66-race dict."""
    return {
        (2023, 1): {"SOFT": "C3", "MEDIUM": "C2", "HARD": "C1"},
        (2023, 2): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},
    }


@pytest.fixture
def synthetic_stint():
    """Small synthetic stint-like artifact for stage unit tests.

    Returns a dict with the minimum attributes stage fitters read. Real StintArtifact
    tests use packages/core fixtures; this is faster & deterministic for numerical tests.
    """
    n_laps = 25
    rng = np.random.default_rng(42)
    return {
        "lap_times_s": 90.0 + 0.05 * np.arange(n_laps) + rng.normal(0, 0.1, n_laps),
        "tire_ages": np.arange(n_laps, dtype=np.int64),
        "compound": "C3",
        "year": 2023,
        "round_num": 1,
        "driver": "VER",
        "n_laps": n_laps,
    }
