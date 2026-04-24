"""Phase 4 cross-endpoint integration test.

Exercises /sessions/upload -> /simulate -> /calibration/{compound} in one flow
to catch regressions in the 3-endpoint interaction surface.

Requirements: API-04, API-05, API-06 (combined cross-endpoint behaviour).
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_e2e_upload_simulate_calibration(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fixture_calibration,
) -> None:
    """End-to-end: POST /sessions/upload -> POST /simulate -> GET /calibration/C3.

    1. Seeds DB + NetCDF via fixture_calibration.
    2. Installs simulate-service stubs (no real physics, no Jolpica, no MCMC).
    3. Uploads a valid FastF1-shaped zip via POST /sessions/upload.
    4. Runs POST /simulate with the returned session_id.
    5. GETs GET /calibration/C3 with the fixture calibration DB.
    6. Cross-checks: /simulate metadata.calibration_id == /calibration metadata.calibration_id.
    """
    # 1. Install simulate stubs (stubs run_simulation, load_stint, _build_params_list,
    #    _derive_compound_letter, get_posterior, sample_stage4_draws,
    #    read_latest_calibration_run, DEFAULT_DB_PATH, get_cache, _cache).
    from packages.api.tests.fixtures.simulate_stubs import install_simulate_stubs

    calibration_id = install_simulate_stubs(monkeypatch, fixture_calibration, tmp_path)

    # 2. Patch SESSION_ROOT in both sessions and simulate services so upload +
    #    _merge_session_into_cache both use tmp_path/sessions.
    sessions_root = tmp_path / "sessions"
    sessions_root.mkdir(parents=True, exist_ok=True)

    import f1_api.services.sessions as sessions_svc
    import f1_api.services.simulate as sim_mod

    monkeypatch.setattr(sessions_svc, "SESSION_ROOT", sessions_root)
    monkeypatch.setattr(sim_mod, "SESSION_ROOT", sessions_root)

    # Patch init_cache so _merge_session_into_cache copies to a tmp dir (not real cache)
    fastf1_root = tmp_path / "fastf1_cache"
    fastf1_root.mkdir(parents=True)
    monkeypatch.setattr(sim_mod, "init_cache", lambda: fastf1_root)

    # 3. Patch calibration service DEFAULT_DB_PATH to use fixture DB.
    _, _, db_path = fixture_calibration
    import f1_api.services.calibration as cal_svc
    monkeypatch.setattr(cal_svc, "DEFAULT_DB_PATH", db_path)

    # Clear lru_cache on get_posterior so fixture NetCDF is loaded fresh.
    import f1_api.services.posterior_store as ps_mod
    ps_mod.get_posterior.cache_clear()

    # 4. Build valid zip bytes and POST to /sessions/upload.
    from packages.api.tests.fixtures.zip_fixtures import make_valid_zip

    zip_bytes = make_valid_zip()
    upload_resp = client.post(
        "/sessions/upload",
        files={"file": ("cache.zip", zip_bytes, "application/zip")},
    )
    assert upload_resp.status_code == 200, (
        f"POST /sessions/upload expected 200, got {upload_resp.status_code}: {upload_resp.text}"
    )
    upload_body = upload_resp.json()
    assert "session_id" in upload_body, f"missing session_id in upload response: {upload_body}"
    session_id = upload_body["session_id"]

    # 5. POST /simulate with the returned session_id.
    sim_resp = client.post(
        "/simulate",
        json={
            "race_id": "2023-bahrain_grand_prix",
            "driver_code": "VER",
            "stint_index": 2,
            "session_id": session_id,
        },
    )
    assert sim_resp.status_code == 200, (
        f"POST /simulate expected 200, got {sim_resp.status_code}: {sim_resp.text}"
    )
    sim_body = sim_resp.json()

    # Verify three-level structure.
    assert "metadata" in sim_body, "simulate response missing 'metadata'"
    assert "per_timestep" in sim_body, "simulate response missing 'per_timestep'"
    assert "per_lap" in sim_body, "simulate response missing 'per_lap'"
    assert "per_stint" in sim_body, "simulate response missing 'per_stint'"

    # Verify calibration_id is the fixture's calibration_id.
    assert sim_body["metadata"]["calibration_id"] == calibration_id, (
        f"simulate calibration_id {sim_body['metadata']['calibration_id']} "
        f"!= fixture calibration_id {calibration_id}"
    )

    # 6. GET /calibration/C3.
    cal_resp = client.get("/calibration/C3")
    assert cal_resp.status_code == 200, (
        f"GET /calibration/C3 expected 200, got {cal_resp.status_code}: {cal_resp.text}"
    )
    cal_body = cal_resp.json()

    # 7. Cross-check: both endpoints report the same calibration_id.
    assert cal_body["metadata"]["calibration_id"] == sim_body["metadata"]["calibration_id"], (
        f"/calibration calibration_id {cal_body['metadata']['calibration_id']} "
        f"!= /simulate calibration_id {sim_body['metadata']['calibration_id']}"
    )
