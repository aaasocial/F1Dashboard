"""Phase 4 API-05 tests — /calibration endpoint behaviors.

Requirements: API-05-a through API-05-e (see VALIDATION.md).
Plan 02 replaces pytest.skip(...) stubs with real assertions.
"""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient


def test_calibration_happy_path(client: TestClient, monkeypatch, fixture_calibration) -> None:
    """API-05-a: GET /calibration/{compound} returns 200 + schema-valid diagnostics body."""
    netcdf_path, calibration_id, db_path = fixture_calibration

    import f1_api.services.calibration as cal_svc
    monkeypatch.setattr(cal_svc, "DEFAULT_DB_PATH", db_path)

    # Also patch DEFAULT_DB_PATH in posterior_store (read_latest_calibration_run uses it
    # indirectly via the db_path argument, but calibration service passes DEFAULT_DB_PATH)
    import f1_api.services.posterior_store as ps_mod
    # clear lru_cache so fixture NetCDF is loaded fresh
    ps_mod.get_posterior.cache_clear()

    resp = client.get("/calibration/C3")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    body = resp.json()
    assert set(body.keys()) == {"metadata", "stage1", "stage2", "stage3", "stage4", "stage5"}

    meta = body["metadata"]
    assert meta["calibration_id"] == calibration_id
    assert meta["compound"] == "C3"


def test_calibration_invalid_compound(client: TestClient) -> None:
    """API-05-b: GET /calibration/{compound} with invalid compound returns 422.

    Tests SQL-injection-looking and out-of-range inputs.
    Note: empty string "" produces a URL with no path segment (404 at routing
    level — FastAPI never reaches the endpoint handler), so we test other
    invalid forms instead.
    """
    # (bad_compound, expected_status)
    cases = [
        ("X9", 422),      # wrong letter
        ("c0", 422),      # C0 out of range (only C1-C5 valid)
        ("C6", 422),      # C6 out of range
        ("C11", 422),     # too long
        ("C1;DROP", 422), # SQL-injection attempt
        ("C", 422),       # too short
    ]

    for bad, expected in cases:
        resp = client.get(f"/calibration/{bad}")
        assert resp.status_code == expected, (
            f"Expected {expected} for compound={bad!r}, got {resp.status_code}: {resp.text}"
        )


def test_calibration_no_data(client: TestClient, monkeypatch, tmp_path) -> None:
    """API-05-c: GET /calibration/{compound} when no calibration row exists returns 404."""
    # Create an empty schema-initialized DB (no rows)
    empty_db = tmp_path / "empty.db"
    conn = sqlite3.connect(str(empty_db))
    from f1_calibration.db import initialize_schema
    initialize_schema(conn)
    conn.close()

    import f1_api.services.calibration as cal_svc
    monkeypatch.setattr(cal_svc, "DEFAULT_DB_PATH", empty_db)

    import f1_api.services.posterior_store as ps_mod
    ps_mod.get_posterior.cache_clear()

    resp = client.get("/calibration/C3")
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert "no calibration" in body["detail"].lower()


def test_calibration_all_stages(client: TestClient, monkeypatch, fixture_calibration) -> None:
    """API-05-d: Response includes parameter summaries for all four calibration stages."""
    netcdf_path, calibration_id, db_path = fixture_calibration

    import f1_api.services.calibration as cal_svc
    monkeypatch.setattr(cal_svc, "DEFAULT_DB_PATH", db_path)

    import f1_api.services.posterior_store as ps_mod
    ps_mod.get_posterior.cache_clear()

    resp = client.get("/calibration/C3")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    body = resp.json()

    # Stage 1 (aero) keys
    stage1_keys = {"C_LA", "C_DA", "xi", "K_rf_split", "WD", "H_CG", "BB"}
    assert stage1_keys.issubset(body["stage1"].keys()), (
        f"stage1 missing keys: {stage1_keys - set(body['stage1'].keys())}"
    )

    # Stage 2 (friction) keys
    stage2_keys = {"mu_0_fresh", "p_bar_0", "n", "c_py", "K_rad"}
    assert stage2_keys.issubset(body["stage2"].keys()), (
        f"stage2 missing keys: {stage2_keys - set(body['stage2'].keys())}"
    )

    # Stage 3 (thermal) keys
    stage3_keys = {
        "T_opt", "sigma_T", "C_tread", "C_carc", "C_gas",
        "R_tc", "R_cg", "h_0", "h_1", "alpha_p", "delta_T_blanket",
    }
    assert stage3_keys.issubset(body["stage3"].keys()), (
        f"stage3 missing keys: {stage3_keys - set(body['stage3'].keys())}"
    )

    # Stage 5 validation metrics
    stage5_keys = {"heldout_rmse_s", "baseline_rmse_s", "beat_baseline"}
    assert stage5_keys.issubset(body["stage5"].keys()), (
        f"stage5 missing keys: {stage5_keys - set(body['stage5'].keys())}"
    )


def test_calibration_stage4_diagnostics(
    client: TestClient, monkeypatch, fixture_calibration
) -> None:
    """API-05-e: Stage 4 response includes full posterior summary with HDI + diagnostics."""
    netcdf_path, calibration_id, db_path = fixture_calibration

    import f1_api.services.calibration as cal_svc
    monkeypatch.setattr(cal_svc, "DEFAULT_DB_PATH", db_path)

    import f1_api.services.posterior_store as ps_mod
    ps_mod.get_posterior.cache_clear()

    resp = client.get("/calibration/C3")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    body = resp.json()
    stage4 = body["stage4"]

    # Check all three Stage-4 variables are present
    assert set(stage4.keys()) == {"beta_therm", "T_act", "k_wear"}

    # Check each variable has the required diagnostic fields
    required_fields = {"mean", "sd", "hdi_lo_95", "hdi_hi_95", "r_hat", "ess_bulk"}
    for var_name in ("beta_therm", "T_act", "k_wear"):
        var_summary = stage4[var_name]
        assert required_fields.issubset(var_summary.keys()), (
            f"{var_name} missing fields: {required_fields - set(var_summary.keys())}"
        )
        # All values should be floats
        for field in required_fields:
            assert isinstance(var_summary[field], (int, float)), (
                f"{var_name}.{field} should be float, got {type(var_summary[field])}"
            )
        # HDI bounds should bracket the mean
        assert var_summary["hdi_lo_95"] <= var_summary["mean"] <= var_summary["hdi_hi_95"], (
            f"{var_name}: hdi_lo_95={var_summary['hdi_lo_95']} <= "
            f"mean={var_summary['mean']} <= hdi_hi_95={var_summary['hdi_hi_95']} violated"
        )
