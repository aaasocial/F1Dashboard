"""API test fixtures — monkeypatch service layer to avoid Jolpica/FastF1 during tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from f1_api.app import create_app
from f1_api.services.stints import (
    DriverSummary,
    RaceSummary,
    StintSummary,
)
from fastapi.testclient import TestClient


@pytest.fixture
def fake_races() -> list[RaceSummary]:
    return [
        RaceSummary(
            year=2022, round=1, name="Bahrain Grand Prix", country="Bahrain", date=date(2022, 3, 20)
        ),
        RaceSummary(
            year=2022,
            round=2,
            name="Saudi Arabian Grand Prix",
            country="Saudi Arabia",
            date=date(2022, 3, 27),
        ),
        RaceSummary(
            year=2023, round=1, name="Bahrain Grand Prix", country="Bahrain", date=date(2023, 3, 5)
        ),
    ]


@pytest.fixture
def fake_drivers() -> list[DriverSummary]:
    return [
        DriverSummary(
            driver_code="VER", full_name="Max Verstappen", team="Red Bull Racing", stint_count=3
        ),
        DriverSummary(
            driver_code="PER", full_name="Sergio Perez", team="Red Bull Racing", stint_count=3
        ),
        DriverSummary(
            driver_code="HAM", full_name="Lewis Hamilton", team="Mercedes", stint_count=3
        ),
    ]


@pytest.fixture
def fake_stints_ver_bahrain_2023() -> list[StintSummary]:
    # Derived from the canonical fixture so "stint 2 MEDIUM ~23 laps" matches
    return [
        StintSummary(
            stint_index=1,
            compound="SOFT",
            compound_letter="C3",
            lap_count=15,
            start_lap=1,
            end_lap=15,
            pit_in_lap=15,
            pit_out_lap=1,
            tire_age_at_start=0,
            quality_score=0.98,
            quality_verdict="ok",
        ),
        StintSummary(
            stint_index=2,
            compound="MEDIUM",
            compound_letter="C2",
            lap_count=23,
            start_lap=16,
            end_lap=38,
            pit_in_lap=38,
            pit_out_lap=16,
            tire_age_at_start=0,
            quality_score=0.97,
            quality_verdict="ok",
        ),
        StintSummary(
            stint_index=3,
            compound="HARD",
            compound_letter="C1",
            lap_count=19,
            start_lap=39,
            end_lap=57,
            pit_in_lap=None,
            pit_out_lap=39,
            tire_age_at_start=0,
            quality_score=0.96,
            quality_verdict="ok",
        ),
    ]


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
    fake_races: list[RaceSummary],
    fake_drivers: list[DriverSummary],
    fake_stints_ver_bahrain_2023: list[StintSummary],
) -> Iterator[TestClient]:
    """TestClient with all service functions monkeypatched — no Jolpica calls."""
    # Patch at the site where routers look them up.
    from f1_api.routers import drivers as drivers_router_mod
    from f1_api.routers import races as races_router_mod
    from f1_api.routers import stints as stints_router_mod

    def _races(start_year: int = 2022, end_year: int | None = None) -> list[RaceSummary]:
        if end_year is None:
            end_year = 2025
        return [r for r in fake_races if start_year <= r.year <= end_year]

    def _drivers(race_id: str) -> list[DriverSummary]:
        if race_id != "2023-bahrain":
            raise ValueError(f"unknown race_id {race_id}")
        return fake_drivers

    def _stints(race_id: str, driver_code: str) -> list[StintSummary]:
        if race_id == "2023-bahrain" and driver_code == "VER":
            return fake_stints_ver_bahrain_2023
        raise ValueError(f"no stints for {race_id}/{driver_code}")

    monkeypatch.setattr(races_router_mod, "list_races", _races)
    monkeypatch.setattr(drivers_router_mod, "list_drivers_for_race", _drivers)
    monkeypatch.setattr(stints_router_mod, "list_stints_for_driver", _stints)

    app = create_app()
    with TestClient(app) as tc:
        yield tc


# ---------------------------------------------------------------------------
# Phase 4 fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def fixture_calibration(tmp_path_factory: pytest.TempPathFactory):
    """Session-scoped fixture: builds a minimal Stage-4 NetCDF + calibration_runs row.

    Yields:
        (netcdf_path, calibration_id, db_path) tuple.

    Teardown:
        Removes the NetCDF and stage5 CSV from WORKSPACE_ROOT/.data/posteriors/.
        The SQLite DB is under tmp_path (auto-cleaned by pytest).

    Security (T-4-W0-LEAK, T-4-W0-OVERWRITE):
        - NetCDF written under WORKSPACE_ROOT/.data/posteriors/, not tmp_path
        - db_path is under tmp_path, never DEFAULT_DB_PATH
    """
    from packages.api.tests.fixtures.calibration_fixture import build_fixture_posterior

    tmp = tmp_path_factory.mktemp("cal")
    netcdf_path, calibration_id, db_path = build_fixture_posterior(tmp, compound="C3")

    yield netcdf_path, calibration_id, db_path

    # Teardown: clear posterior lru_cache to release file handles before unlinking
    # (Windows holds file locks until the cache entry is evicted — T-4-W0-LOCK)
    try:
        from f1_api.services.posterior_store import get_posterior
        get_posterior.cache_clear()
    except ImportError:
        pass

    # Teardown: remove NetCDF and stage5 CSV from WORKSPACE_ROOT/.data/posteriors/
    if netcdf_path.exists():
        netcdf_path.unlink()

    # Also clean up any stage5 CSVs written alongside the NetCDF
    posteriors_dir = netcdf_path.parent
    for stray in list(posteriors_dir.glob("stage5_*.csv")):
        try:
            stray.unlink()
        except OSError:
            pass


@pytest.fixture
def fake_stint_artifact():
    """Build a minimal StintArtifact with ~100 samples — no FastF1 call.

    Used by tests that exercise run_simulation plumbing without live telemetry.
    Returns a StintArtifact with:
        - car_data: 100-row DataFrame (Speed, RPM, nGear, Throttle, Brake, DRS, Time)
        - pos_data: empty DataFrame
        - laps: 1-row DataFrame
        - weather: empty DataFrame
        - track_status / race_control_messages: empty DataFrames
    """
    from f1_core.ingestion.cache import StintArtifact, StintKey

    n = 100
    rng = np.random.default_rng(0)

    car_data = pd.DataFrame(
        {
            "Speed": rng.uniform(80, 320, n).astype("float32"),
            "RPM": rng.integers(4000, 12000, n).astype("int32"),
            "nGear": rng.integers(1, 8, n).astype("int8"),
            "Throttle": rng.uniform(0, 100, n).astype("float32"),
            "Brake": rng.choice([0, 1], n).astype("bool"),
            "DRS": rng.choice([0, 8, 10, 12, 14], n).astype("int8"),
            "Time": pd.to_timedelta(np.linspace(0, 90, n), unit="s"),
        }
    )

    laps = pd.DataFrame(
        {
            "LapNumber": [1],
            "LapTime": [pd.Timedelta(seconds=95.3)],
            "Compound": ["C3"],
            "TyreLife": [1],
        }
    )

    key = StintKey(year=2023, round=1, driver_code="VER", stint_index=2)

    return StintArtifact(
        key=key,
        car_data=car_data,
        pos_data=pd.DataFrame(),
        laps=laps,
        weather=pd.DataFrame(),
        track_status=pd.DataFrame(),
        race_control_messages=pd.DataFrame(),
        session_metadata={"EventName": "Bahrain Grand Prix", "Year": 2023},
    )


@pytest.fixture
def monkeypatched_run_simulation(monkeypatch: pytest.MonkeyPatch):
    """Patch f1_api.services.simulate.run_simulation to return a canned SimulationResult.

    Skips if the module does not exist yet (Plan 01 creates it).

    The canned result has:
        - per_timestep arrays of shape (100,) for time axis
        - per_lap list of 5 dicts (one per lap)

    Returns the monkeypatch object so callers can do further patching.
    """
    try:
        import f1_api.services.simulate as sim_mod  # noqa: F401
    except ImportError:
        pytest.skip("Plan 01 implements f1_api.services.simulate")

    n = 100

    class _FakeSimResult:
        """Minimal stand-in for SimulationResult."""

        t = np.linspace(0, 90, n)
        t_tread = np.full((n, 4), 95.0)  # shape (100, 4)
        e_tire = np.full((n, 4), 0.01)
        mu = np.full((n, 4), 1.1)
        f_z = np.full((n, 4), 3500.0)
        f_y = np.full((n, 4), 800.0)
        f_x = np.full((n, 4), 300.0)
        mu_0 = np.full(n, 1.2)
        per_lap = [
            {"lap": i + 1, "mean_mu": 1.1, "mean_t_tread": 95.0, "e_tire_total": 0.05}
            for i in range(5)
        ]

    monkeypatch.setattr(sim_mod, "run_simulation", lambda *a, **kw: _FakeSimResult())
    return monkeypatch


# Re-export install_simulate_stubs from the fixtures package so it is
# importable via ``packages.api.tests.fixtures.simulate_stubs`` (the
# fixtures/ directory has __init__.py and works under --import-mode=importlib).
from packages.api.tests.fixtures.simulate_stubs import install_simulate_stubs  # noqa: F401


@pytest.fixture(params=["slip", "bomb", "symlink", "non_zip", "valid"])
def malicious_zip(request: pytest.FixtureRequest) -> bytes:
    """Parametrised fixture: returns zip bytes for each security scenario.

    Params:
        slip     — path-traversal zip (zip slip)
        bomb     — decompression bomb (declared 600 MB)
        symlink  — POSIX symlink member
        non_zip  — plain bytes (not a zip at all)
        valid    — well-formed FastF1-shaped zip (happy path)

    Usage::

        @pytest.mark.parametrize("malicious_zip", ["slip", "bomb"], indirect=True)
        def test_rejects_bad_zip(client, malicious_zip):
            ...
    """
    from packages.api.tests.fixtures.zip_fixtures import (
        make_decompression_bomb,
        make_non_zip,
        make_symlink_zip,
        make_valid_zip,
        make_zip_slip,
    )

    _dispatch = {
        "slip": make_zip_slip,
        "bomb": make_decompression_bomb,
        "symlink": make_symlink_zip,
        "non_zip": make_non_zip,
        "valid": make_valid_zip,
    }
    return _dispatch[request.param]()
