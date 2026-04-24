"""Tests for SQLite schema round-trip (CALIB-07) and security validators."""
from __future__ import annotations
import json
import sqlite3

import pytest
from f1_core.physics.params import AeroParams
from f1_calibration.db import (
    DEFAULT_DB_PATH,
    initialize_schema,
    validate_compound,
    resolve_db_path,
    write_parameter_set,
    read_latest_parameter_set,
    has_stage_result,
    write_calibration_run,
)


def test_validate_compound_accepts_valid():
    assert validate_compound("C3") == "C3"
    assert validate_compound("c3") == "C3"
    assert validate_compound(" C1 ") == "C1"


@pytest.mark.parametrize("bad", ["X9", "C0", "C6", "", "'; DROP TABLE --", "C3; SELECT 1"])
def test_validate_compound_rejects_invalid(bad):
    with pytest.raises(ValueError):
        validate_compound(bad)


def test_resolve_db_path_default_inside_workspace():
    p = resolve_db_path(None)
    assert p.name == "f1.db"


def test_resolve_db_path_rejects_outside_workspace(tmp_path, monkeypatch):
    # tmp_path on many systems is outside the repo
    outside = tmp_path / "leaked.db"
    outside.parent.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ValueError, match="outside workspace"):
        resolve_db_path(outside)


def test_initialize_schema_idempotent(tmp_db_path):
    conn = sqlite3.connect(tmp_db_path)
    try:
        initialize_schema(conn)
        initialize_schema(conn)  # second call must not raise
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
            "('parameter_sets','calibration_runs')"
        )
        names = {r[0] for r in cur.fetchall()}
        assert names == {"parameter_sets", "calibration_runs"}
    finally:
        conn.close()


def test_parameter_set_roundtrip(initialized_db):
    conn = initialized_db
    aero = AeroParams(C_LA=4.5, C_DA=1.1, xi=0.45, K_rf_split=0.55, WD=0.445, H_CG=0.28, BB=0.575)
    pid = write_parameter_set(conn, "C3", 1, aero, {"rmse": 0.5})
    assert pid >= 1
    row = read_latest_parameter_set(conn, "C3", 1)
    assert row is not None
    assert row["compound"] == "C3"
    assert row["stage_number"] == 1
    assert row["is_latest"] == 1
    assert row["params"]["C_LA"] == 4.5
    assert row["diagnostics"]["rmse"] == 0.5


def test_is_latest_trigger_demotes_prior_rows(initialized_db):
    conn = initialized_db
    aero_v1 = AeroParams(C_LA=4.5, C_DA=1.1, xi=0.45, K_rf_split=0.55, WD=0.445, H_CG=0.28, BB=0.575)
    pid1 = write_parameter_set(conn, "C3", 1, aero_v1)
    # Force different created_at by using a direct insert for determinism:
    conn.execute(
        "INSERT INTO parameter_sets (compound, stage_number, year_range, created_at, git_sha, "
        "params_json, is_latest, diagnostics_json) VALUES "
        "('C3', 1, '2022-2024', '2099-01-01T00:00:00+00:00', 'deadbee', ?, 1, '{}')",
        (json.dumps({"C_LA": 5.5}),),
    )
    conn.commit()
    # pid1 row must now be is_latest=0
    cur = conn.execute(
        "SELECT is_latest FROM parameter_sets WHERE parameter_set_id = ?", (pid1,)
    )
    assert cur.fetchone()[0] == 0
    # Latest query must return the newer row
    row = read_latest_parameter_set(conn, "C3", 1)
    assert row["params"]["C_LA"] == 5.5


def test_has_stage_result(initialized_db):
    conn = initialized_db
    assert not has_stage_result(conn, "C3", 1)
    aero = AeroParams(C_LA=4.5, C_DA=1.1, xi=0.45, K_rf_split=0.55, WD=0.445, H_CG=0.28, BB=0.575)
    write_parameter_set(conn, "C3", 1, aero)
    assert has_stage_result(conn, "C3", 1)
    assert not has_stage_result(conn, "C4", 1)


def test_write_calibration_run(initialized_db):
    conn = initialized_db
    aero = AeroParams(C_LA=4.5, C_DA=1.1, xi=0.45, K_rf_split=0.55, WD=0.445, H_CG=0.28, BB=0.575)
    ids = [write_parameter_set(conn, "C3", s, aero) for s in (1, 2, 3, 4)]
    cid = write_calibration_run(
        conn, compound="C3", heldout_rmse_s=0.25, baseline_rmse_s=0.45,
        r_hat_max=1.005, ess_bulk_min=800.0,
        netcdf_path=".data/posteriors/C3_2022-2024_x.nc",
        param_set_stage1=ids[0], param_set_stage2=ids[1],
        param_set_stage3=ids[2], param_set_stage4=ids[3],
        stage5_csv_path=".data/validation/stage5_C3_x.csv",
    )
    cur = conn.execute(
        "SELECT compound, heldout_rmse_s FROM calibration_runs WHERE calibration_id=?", (cid,)
    )
    row = cur.fetchone()
    assert row == ("C3", 0.25)
