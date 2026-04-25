"""Shared simulate-service stub installer for Phase 4 integration tests.

``install_simulate_stubs`` monkeypatches all external I/O in
``f1_api.services.simulate`` so tests run without Jolpica calls, FastF1
cache access, SQLite writes to production DB, or MCMC sampling.

Importable via ``packages.api.tests.fixtures.simulate_stubs`` regardless
of pytest's --import-mode (importlib or prepend).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def install_simulate_stubs(
    monkeypatch: pytest.MonkeyPatch,
    fixture_calibration: tuple,
    tmp_path: Path,
) -> int:
    """Install all external-I/O stubs needed by simulate integration tests.

    Stubs applied to ``f1_api.services.simulate``:
      - ``run_simulation``          → returns synthetic SimulationResult (N=8000, 22 laps)
      - ``load_stint``              → returns minimal StintArtifact (4 car rows, 22 lap rows)
      - ``_build_params_list``      → returns K=100 nominal PhysicsParams
      - ``_derive_compound_letter`` → always returns "C3"
      - ``get_posterior``           → returns None
      - ``sample_stage4_draws``     → returns deterministic draws dict
      - ``read_latest_calibration_run`` → returns fixture calibration_id + netcdf_path
      - ``get_cache``               → returns _NoCache (always miss)
      - ``DEFAULT_DB_PATH``         → tmp_path / "stub_cache.db" (schema-initialised)
      - ``_cache``                  → reset to None

    Security (T-4-E2E-LEAK):
      - All DB paths monkeypatched to tmp_path — never touches production DEFAULT_DB_PATH.
      - No real Jolpica or FastF1 network calls made.

    Returns:
        calibration_id (int) from fixture_calibration, for assertion in tests.
    """
    import f1_api.services.simulate as sim_mod
    from f1_calibration.db import initialize_schema, write_parameter_set
    from f1_core.ingestion.cache import StintArtifact, StintKey
    from f1_core.physics.defaults import make_nominal_params
    from f1_core.physics.orchestrator import SimulationResult

    netcdf_path, calibration_id, _fixture_db = fixture_calibration

    N = 8000
    n_laps = 22
    rng = np.random.default_rng(42)

    # ------------------------------------------------------------------
    # Fake run_simulation: realistic shape, fast (in-memory, <1 ms)
    # ------------------------------------------------------------------
    def _fake_run_simulation(artifact, params):
        t = np.linspace(0, 2000, N)
        f_z = np.full((N, 4), 3500.0)
        f_y = np.full((N, 4), 800.0)
        f_x = np.full((N, 4), 300.0)
        t_tread = rng.uniform(60.0, 130.0, (N, 4))
        e_tire = np.abs(rng.uniform(0.0, 1e3, (N, 4)))
        mu = rng.uniform(0.8, 1.3, (N, 4))
        mu_0 = np.linspace(1.2, 1.0, N)
        per_lap = [
            {
                "Lap": i + 1,
                "Compound": "MEDIUM",
                "Age": i,
                "Pred_s": float(90.0 + i * 0.1),
                "Obs_s": float(90.2 + i * 0.1),
                "Delta_s": float(-0.2),
                "Grip_pct": float(100.0 - i * 0.5),
                "T_tread_C": float(95.0 + i * 0.2),
                "E_tire_MJ": float(0.05 + i * 0.01),
            }
            for i in range(n_laps)
        ]
        return SimulationResult(
            t=t, f_z=f_z, f_y=f_y, f_x=f_x, mu=mu,
            t_tread=t_tread, e_tire=e_tire, mu_0=mu_0,
            per_lap=per_lap,
        )

    # ------------------------------------------------------------------
    # Fake load_stint: minimal StintArtifact, no FastF1/Jolpica call
    # ------------------------------------------------------------------
    def _fake_load_stint(**kw):
        car_data = pd.DataFrame({
            "Speed": np.linspace(100, 300, 4).astype("float32"),
            "RPM": np.array([8000, 9000, 10000, 11000], dtype="int32"),
            "nGear": np.array([3, 5, 6, 7], dtype="int8"),
            "Throttle": np.array([50, 80, 100, 100], dtype="float32"),
            "Brake": np.array([False, False, False, False]),
            "DRS": np.array([0, 0, 10, 10], dtype="int8"),
            "Time": pd.to_timedelta([0, 30, 60, 90], unit="s"),
        })
        laps = pd.DataFrame({
            "LapNumber": list(range(1, n_laps + 1)),
            "LapTime": [pd.Timedelta(seconds=90.0 + i * 0.1) for i in range(n_laps)],
            "Compound": ["MEDIUM"] * n_laps,
            "TyreLife": list(range(1, n_laps + 1)),
        })
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

    # ------------------------------------------------------------------
    # Fake _build_params_list: K nominal PhysicsParams, no DB read
    # ------------------------------------------------------------------
    def _fake_build_params_list(compound, draws, overrides):
        return [make_nominal_params() for _ in range(100)]

    # ------------------------------------------------------------------
    # Fake _derive_compound_letter: MEDIUM -> C3
    # ------------------------------------------------------------------
    def _fake_derive_compound_letter(artifact):
        return "C3"

    # ------------------------------------------------------------------
    # Fake sample_stage4_draws: deterministic draws
    # ------------------------------------------------------------------
    def _fake_sample_stage4_draws(idata, K, *, seed):
        return {
            "beta_therm": np.ones(K) * 1e-6,
            "T_act": np.ones(K) * 100.0,
            "k_wear": np.ones(K) * 1e-10,
        }

    # ------------------------------------------------------------------
    # Fake read_latest_calibration_run: returns fixture calibration row
    # ------------------------------------------------------------------
    def _fake_read_latest_calibration_run(db, compound):
        return {
            "calibration_id": calibration_id,
            "netcdf_path": str(netcdf_path),
        }

    # ------------------------------------------------------------------
    # Fake get_posterior: no NetCDF file access
    # ------------------------------------------------------------------
    def _fake_get_posterior(netcdf_path_str):
        return None

    # ------------------------------------------------------------------
    # No-op cache: always misses so cold path is exercised
    # ------------------------------------------------------------------
    class _NoCache:
        def get(self, *a, **kw):
            return None

        def put(self, *a, **kw):
            pass

    # ------------------------------------------------------------------
    # Build a minimal parameter DB for DEFAULT_DB_PATH
    # ------------------------------------------------------------------
    db_path = tmp_path / "stub_cache.db"
    conn = sqlite3.connect(str(db_path))
    initialize_schema(conn)
    nominal = make_nominal_params()
    write_parameter_set(conn, "C3", 1, nominal.aero)
    write_parameter_set(conn, "C3", 2, nominal.friction)
    write_parameter_set(conn, "C3", 3, nominal.thermal)
    conn.close()

    # Apply monkeypatches
    monkeypatch.setattr(sim_mod, "run_simulation", _fake_run_simulation)
    monkeypatch.setattr(sim_mod, "load_stint", _fake_load_stint)
    monkeypatch.setattr(sim_mod, "_build_params_list", _fake_build_params_list)
    monkeypatch.setattr(sim_mod, "_derive_compound_letter", _fake_derive_compound_letter)
    monkeypatch.setattr(sim_mod, "sample_stage4_draws", _fake_sample_stage4_draws)
    monkeypatch.setattr(sim_mod, "read_latest_calibration_run", _fake_read_latest_calibration_run)
    monkeypatch.setattr(sim_mod, "get_posterior", _fake_get_posterior)
    monkeypatch.setattr(sim_mod, "get_cache", lambda: _NoCache())
    monkeypatch.setattr(sim_mod, "DEFAULT_DB_PATH", db_path)
    # Reset the module-level cache singleton so it re-initialises against tmp DB
    monkeypatch.setattr(sim_mod, "_cache", None)

    return calibration_id


__all__ = ["install_simulate_stubs"]
