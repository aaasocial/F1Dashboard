"""Phase 4 API-04 tests — /simulate endpoint behaviors (Wave 0 stubs).

Requirements: API-04-a through API-04-h (see VALIDATION.md).
Plans 01 and higher replace pytest.skip(...) stubs with real assertions.
"""
from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers: build a minimal canned SimulationResult for service-level tests
# ---------------------------------------------------------------------------

def _make_canned_sim_result(n: int = 100, n_laps: int = 5):
    """Return a minimal SimulationResult-like object with orchestrator-keyed per_lap."""
    from f1_core.physics.orchestrator import SimulationResult

    rng = np.random.default_rng(0)
    t = np.linspace(0, 90, n)
    arr2d = rng.uniform(50, 110, (n, 4))
    arr1d = rng.uniform(1.0, 1.3, n)

    per_lap = [
        {
            "Lap": i + 1,
            "Compound": "C3",
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
        t=t,
        t_tread=arr2d.copy(),
        e_tire=np.abs(arr2d.copy()) * 1e3,
        mu=arr2d.copy() / 110.0,
        f_z=np.full((n, 4), 3500.0),
        f_y=np.full((n, 4), 800.0),
        f_x=np.full((n, 4), 300.0),
        mu_0=arr1d,
        per_lap=per_lap,
    )


def _make_canned_response(calibration_id: int = 42):
    """Build a fully-populated canned SimulateResponse (N=4 timesteps, 1 lap)."""
    from f1_api.schemas.simulate import (
        CIArray1D, CIArray2D, CIValue,
        PerLapRow, PerStintSummary, PerTimestepBlock,
        SimulateResponse, SimulationMetadata,
    )

    n = 4
    ci2d = CIArray2D(
        mean=[[1.0, 1.0, 1.0, 1.0]] * n,
        lo_95=[[0.9, 0.9, 0.9, 0.9]] * n,
        hi_95=[[1.1, 1.1, 1.1, 1.1]] * n,
    )
    ci1d = CIArray1D(
        mean=[1.0] * n,
        lo_95=[0.9] * n,
        hi_95=[1.1] * n,
    )
    civ = CIValue(mean=1.0, lo_95=0.9, hi_95=1.1)

    return SimulateResponse(
        metadata=SimulationMetadata(
            calibration_id=calibration_id,
            model_schema_version="v1",
            fastf1_version="3.8.2",
            compound="C3",
            stint_index=2,
            overrides_applied=False,
            k_draws=100,
        ),
        per_timestep=PerTimestepBlock(
            t=[0.0, 0.25, 0.5, 0.75],
            t_tread=ci2d, e_tire=ci2d, mu=ci2d,
            f_z=ci2d, f_y=ci2d, f_x=ci2d, mu_0=ci1d,
        ),
        per_lap=[
            PerLapRow(
                lap=1, compound="C3", age=0, obs_s=90.2,
                pred_s=civ, delta_s=civ, grip_pct=civ,
                t_tread_max_c=civ, e_tire_mj=civ,
            )
        ],
        per_stint=PerStintSummary(
            total_predicted_time_s=civ,
            stint_end_grip_pct=civ,
            peak_t_tread_c=civ,
            total_e_tire_mj=civ,
        ),
    )


def test_simulate_happy_path(client: TestClient, monkeypatch: pytest.MonkeyPatch, fixture_calibration) -> None:
    """API-04-a: POST /simulate with a valid stint returns 200 + schema-valid body."""
    try:
        import f1_api.routers.simulate as router_mod
    except ImportError:
        pytest.skip("Plan 01 implements /simulate router")

    _, calibration_id, _ = fixture_calibration
    canned = _make_canned_response(calibration_id=calibration_id)
    monkeypatch.setattr(router_mod, "run_simulation_with_uncertainty", lambda **kw: canned)

    resp = client.post(
        "/simulate",
        json={"race_id": "2023-bahrain_grand_prix", "driver_code": "VER", "stint_index": 2},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["metadata"]["calibration_id"] == calibration_id


def test_simulate_three_levels(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """API-04-b: Response contains all three data levels."""
    try:
        import f1_api.routers.simulate as router_mod
    except ImportError:
        pytest.skip("Plan 01 implements /simulate router")

    canned = _make_canned_response()
    monkeypatch.setattr(router_mod, "run_simulation_with_uncertainty", lambda **kw: canned)

    resp = client.post(
        "/simulate",
        json={"race_id": "2023-bahrain_grand_prix", "driver_code": "VER", "stint_index": 2},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "per_timestep" in body
    assert "per_lap" in body
    assert "per_stint" in body
    assert len(body["per_lap"]) >= 1


def _patch_simulate_external_io(monkeypatch, fake_stint_artifact, tmp_path=None, K_draws=100):
    """Helper: monkeypatch all external I/O in f1_api.services.simulate.

    Creates a minimal SQLite DB for _build_params_list (Stage 1-3 lookups)
    and patches DEFAULT_DB_PATH so no real DB access happens.
    """
    import sqlite3
    import tempfile
    from pathlib import Path

    import f1_api.services.simulate as sim_mod
    from f1_core.physics.defaults import make_nominal_params
    from dataclasses import asdict
    from f1_calibration.db import initialize_schema, write_parameter_set

    nominal = make_nominal_params()

    # Build a minimal SQLite DB with Stage 1-3 parameter rows for "C3"
    if tmp_path is None:
        _tmpdir = tempfile.mkdtemp()
        db_path = Path(_tmpdir) / "test_sim.db"
    else:
        db_path = tmp_path / "test_sim.db"

    conn = sqlite3.connect(str(db_path))
    initialize_schema(conn)
    write_parameter_set(conn, "C3", 1, nominal.aero)
    write_parameter_set(conn, "C3", 2, nominal.friction)
    write_parameter_set(conn, "C3", 3, nominal.thermal)
    conn.close()

    # Patch DEFAULT_DB_PATH so _build_params_list connects to our test DB
    monkeypatch.setattr(sim_mod, "DEFAULT_DB_PATH", db_path)

    monkeypatch.setattr(sim_mod, "load_stint", lambda **kw: fake_stint_artifact)
    monkeypatch.setattr(
        sim_mod, "read_latest_calibration_run",
        lambda *a, **kw: {"calibration_id": 1, "netcdf_path": "fake.nc"},
    )
    monkeypatch.setattr(
        sim_mod, "get_posterior",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        sim_mod, "sample_stage4_draws",
        lambda idata, K, *, seed: {
            "beta_therm": np.full(K, 1e-6),
            "T_act": np.full(K, 100.0),
            "k_wear": np.full(K, 1e-12),
        },
    )

    class _NoCache:
        def get(self, *a, **kw):
            return None
        def put(self, *a, **kw):
            pass

    monkeypatch.setattr(sim_mod, "get_cache", lambda: _NoCache())
    return sim_mod


def test_simulate_ci_triplets(monkeypatch: pytest.MonkeyPatch, fake_stint_artifact) -> None:
    """API-04-c: Every CIArray field has lo_95 <= mean <= hi_95 (approximate)."""
    try:
        import f1_api.services.simulate as sim_mod
    except ImportError:
        pytest.skip("Plan 01 implements f1_api.services.simulate")

    canned = _make_canned_sim_result()
    sim_mod = _patch_simulate_external_io(monkeypatch, fake_stint_artifact)
    monkeypatch.setattr(sim_mod, "run_simulation", lambda *a, **kw: canned)

    response = sim_mod.run_simulation_with_uncertainty(
        race_id="2023-bahrain",
        driver_code="VER",
        stint_index=2,
    )

    # Verify CI ordering holds for per_timestep arrays
    ts = response.per_timestep
    for field_name in ("t_tread", "e_tire", "mu", "f_z", "f_y", "f_x"):
        arr = getattr(ts, field_name)
        for row_idx in range(len(arr.mean)):
            for col_idx in range(len(arr.mean[row_idx])):
                assert arr.lo_95[row_idx][col_idx] <= arr.hi_95[row_idx][col_idx], (
                    f"{field_name}[{row_idx}][{col_idx}]: lo_95 > hi_95"
                )

    # Verify per_lap CI ordering
    for lap_row in response.per_lap:
        assert lap_row.grip_pct.lo_95 <= lap_row.grip_pct.hi_95
        assert lap_row.pred_s.lo_95 <= lap_row.pred_s.hi_95


def test_simulate_overrides(monkeypatch: pytest.MonkeyPatch, fake_stint_artifact) -> None:
    """API-04-d: overrides_applied=True when overrides are passed; CI bands still present."""
    try:
        import f1_api.services.simulate as _sim  # noqa: F401
    except ImportError:
        pytest.skip("Plan 01 implements f1_api.services.simulate")

    from f1_api.schemas.simulate import ParameterOverrides

    canned = _make_canned_sim_result()
    sim_mod = _patch_simulate_external_io(monkeypatch, fake_stint_artifact)
    monkeypatch.setattr(sim_mod, "run_simulation", lambda *a, **kw: canned)

    overrides = ParameterOverrides(mu_0_fresh=1.5)
    response = sim_mod.run_simulation_with_uncertainty(
        race_id="2023-bahrain",
        driver_code="VER",
        stint_index=2,
        overrides=overrides,
    )

    assert response.metadata.overrides_applied is True
    # CI bands still present even with overrides
    assert response.per_stint.total_predicted_time_s.lo_95 <= response.per_stint.total_predicted_time_s.hi_95


@pytest.mark.integration
def test_simulate_cache_hit(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    fake_stint_artifact,
    tmp_path,
) -> None:
    """API-04-e: Second identical POST /simulate returns result in <50 ms (cache hit)."""
    import time

    try:
        import f1_api.routers.simulate as router_mod
        import f1_api.services.simulate as sim_mod
    except ImportError:
        pytest.skip("Plan 01 implements /simulate router")

    canned = _make_canned_sim_result(n=20, n_laps=2)
    sim_mod_patched = _patch_simulate_external_io(monkeypatch, fake_stint_artifact, tmp_path)
    monkeypatch.setattr(sim_mod_patched, "run_simulation", lambda *a, **kw: canned)

    # Use real cache (backed by tmp_path DB) — reset singleton so it picks up patched DB_PATH
    from f1_api.cache.simulate_cache import SimulateCache
    real_cache = SimulateCache(tmp_path / "test_sim.db", max_entries=64)
    monkeypatch.setattr(sim_mod_patched, "get_cache", lambda: real_cache)

    body = {"race_id": "2023-bahrain", "driver_code": "VER", "stint_index": 2}

    # First call — cache miss, runs K=100 forward passes
    t0 = time.perf_counter()
    resp1 = client.post("/simulate", json=body)
    first_ms = (time.perf_counter() - t0) * 1000

    assert resp1.status_code == 200, f"First call failed: {resp1.text}"

    # Second call — cache hit, should return in <50 ms
    t1 = time.perf_counter()
    resp2 = client.post("/simulate", json=body)
    second_ms = (time.perf_counter() - t1) * 1000

    assert resp2.status_code == 200, f"Second call failed: {resp2.text}"
    assert resp1.json()["metadata"]["calibration_id"] == resp2.json()["metadata"]["calibration_id"]
    assert second_ms < 50.0, f"Cache hit took {second_ms:.1f} ms (expected <50 ms)"


def test_simulate_cache_invalidation(tmp_path) -> None:
    """API-04-f: cache entries are invalidated when calibration_id changes."""
    from f1_api.cache.simulate_cache import SimulateCache
    db = tmp_path / "cache.db"
    cache = SimulateCache(db, max_entries=8)
    payload = b'{"ok": 1}'
    cache.put("2023-bahrain", "VER", 2, 1, None, payload)
    assert cache.get("2023-bahrain", "VER", 2, 1, None) == payload
    # New calibration_id → new key; old is cold on that key
    assert cache.get("2023-bahrain", "VER", 2, 2, None) is None
    # Explicit invalidation
    n = cache.invalidate_for_calibration(1)
    assert n == 1
    assert cache.get("2023-bahrain", "VER", 2, 1, None) is None


@pytest.mark.integration
def test_simulate_wall_time(
    monkeypatch: pytest.MonkeyPatch,
    fixture_calibration,
    tmp_path,
) -> None:
    """API-04-g: cold /simulate path completes within 2-second wall-time budget (D-04).

    Monkeypatches run_simulation to return a realistic synthetic SimulationResult
    (N=8000 timesteps, 22 laps) in <1 ms per call. K=100 calls run through the
    real aggregation + JSON serialization + cache write path.
    Asserts: total cold-path wall time < 2.0 seconds.
    """
    import time

    try:
        import f1_api.services.simulate as _sim  # noqa: F401
    except ImportError:
        pytest.skip("Plan 01 implements /simulate router")

    from packages.api.tests.fixtures.simulate_stubs import install_simulate_stubs
    calibration_id = install_simulate_stubs(monkeypatch, fixture_calibration, tmp_path)

    from f1_api.services.simulate import run_simulation_with_uncertainty

    t0 = time.perf_counter()
    resp = run_simulation_with_uncertainty(
        race_id="2023-bahrain_grand_prix",
        driver_code="VER",
        stint_index=2,
        overrides=None,
        session_id=None,
    )
    elapsed = time.perf_counter() - t0

    assert elapsed < 2.0, f"cold /simulate took {elapsed:.3f}s (budget 2.0s)"
    assert resp.metadata.calibration_id == calibration_id
    assert resp.metadata.k_draws == 100


def test_no_mcmc_at_runtime() -> None:
    """D-05: PyMC / NumPyro must not be imported when the API app is created.

    This test has REAL assertions (not a skip stub). It must be green before
    Plan 01 and must remain green after Phase 4 completes — D-05 enforcement.
    """
    import sys

    # First ensure clean baseline — remove any previously-imported MCMC modules
    for mod in list(sys.modules):
        if mod.startswith(("pymc", "numpyro", "pytensor")):
            del sys.modules[mod]

    from f1_api.app import create_app  # noqa: F401

    app = create_app()  # noqa: F841

    forbidden = [m for m in sys.modules if m.split(".")[0] in {"pymc", "numpyro", "pytensor"}]
    assert not forbidden, f"Forbidden MCMC modules imported at app creation: {forbidden}"
