"""run_all resumability tests (D-01)."""
from __future__ import annotations
import sqlite3
import pytest
from unittest.mock import MagicMock

from f1_core.physics.params import AeroParams, FrictionParams, ThermalParams, DegradationParams
from f1_calibration.db import write_parameter_set
from f1_calibration.run_all import run_all


@pytest.fixture
def patch_stage_cores(monkeypatch):
    """Replace _stageN_core with mocks that write dummy parameter_sets rows."""
    from f1_calibration import cli as cli_mod
    from f1_calibration import run_all as run_all_mod
    aero = AeroParams(C_LA=4.5, C_DA=1.1, xi=0.45, K_rf_split=0.55, WD=0.445, H_CG=0.28, BB=0.575)
    friction = FrictionParams(mu_0_fresh=1.8, p_bar_0=1.5e5, n=0.8, c_py=1.0e8, K_rad=250_000.0)
    thermal = ThermalParams(T_opt=95.0, sigma_T=20.0, C_tread=6000.0, C_carc=20000.0, C_gas=500.0,
                            R_tc=0.02, R_cg=0.05, h_0=10.0, h_1=8.0, alpha_p=0.55, delta_T_blanket=60.0)
    deg = DegradationParams(beta_therm=1e-6, T_act=25.0, k_wear=1e-12)
    call_log: list[int] = []
    def fake_stage1(compound, conn, console):
        call_log.append(1); write_parameter_set(conn, compound, 1, aero, {"rmse": 0.1})
    def fake_stage2(compound, conn, console):
        call_log.append(2); write_parameter_set(conn, compound, 2, friction, {"r_squared": 0.99})
    def fake_stage3(compound, conn, console):
        call_log.append(3); write_parameter_set(conn, compound, 3, thermal, {"rmse_C": 2.0})
    def fake_stage4(compound, conn, console, **kw):
        call_log.append(4); write_parameter_set(conn, compound, 4, deg,
            {"r_hat_max": 1.003, "ess_bulk_min": 800.0,
             "netcdf_path": ".data/posteriors/C3_2022-2024_x.nc"})
    monkeypatch.setattr(cli_mod, "_stage1_core", fake_stage1, raising=False)
    monkeypatch.setattr(cli_mod, "_stage2_core", fake_stage2, raising=False)
    monkeypatch.setattr(cli_mod, "_stage3_core", fake_stage3, raising=False)
    monkeypatch.setattr(cli_mod, "_stage4_core", fake_stage4, raising=False)

    # Also mock fit_stage5 to avoid real run_simulation dependency
    def fake_stage5(compound, conn, **kw):
        return {
            "physics_rmse_s": 0.25, "baseline_rmse_s": 0.40,
            "per_circuit": [], "n_stints": 2, "n_laps": 40,
            "csv_path": ".data/validation/stage5_C3_x_per_circuit.csv",
            "compound": compound,
        }
    monkeypatch.setattr(run_all_mod, "fit_stage5", fake_stage5, raising=False)
    # Also patch the symbol imported inside run_all itself
    import f1_calibration.stage5_validation as s5
    monkeypatch.setattr(s5, "fit_stage5", fake_stage5, raising=False)

    return call_log


def test_run_all_first_invocation_runs_all_stages(initialized_db, patch_stage_cores):
    result = run_all(compound="C3", conn=initialized_db, force=False)
    assert set(patch_stage_cores) == {1, 2, 3, 4}
    assert result["stages_run"] == [1, 2, 3, 4]
    assert result["stages_skipped"] == []
    assert result["physics_rmse_s"] == 0.25
    assert result["baseline_rmse_s"] == 0.40
    assert result["calibration_id"] >= 1


def test_run_all_resumability(initialized_db, patch_stage_cores):
    """Second invocation with same args must skip every stage (stage 5 always runs)."""
    run_all(compound="C3", conn=initialized_db, force=False)
    patch_stage_cores.clear()
    result = run_all(compound="C3", conn=initialized_db, force=False)
    # No fit stage re-invoked
    assert patch_stage_cores == []
    assert result["stages_run"] == []
    assert set(result["stages_skipped"]) == {1, 2, 3, 4}


def test_run_all_force_reruns_all_stages(initialized_db, patch_stage_cores):
    """--force disables skip logic even if rows exist."""
    run_all(compound="C3", conn=initialized_db, force=False)
    patch_stage_cores.clear()
    run_all(compound="C3", conn=initialized_db, force=True)
    assert set(patch_stage_cores) == {1, 2, 3, 4}


def test_run_all_partial_resume(initialized_db, patch_stage_cores):
    """Pre-seed stages 1-2 only → run_all invokes only stages 3-4 + stage 5."""
    aero = AeroParams(C_LA=4.5, C_DA=1.1, xi=0.45, K_rf_split=0.55, WD=0.445, H_CG=0.28, BB=0.575)
    friction = FrictionParams(mu_0_fresh=1.8, p_bar_0=1.5e5, n=0.8, c_py=1.0e8, K_rad=250_000.0)
    write_parameter_set(initialized_db, "C3", 1, aero)
    write_parameter_set(initialized_db, "C3", 2, friction)
    run_all(compound="C3", conn=initialized_db, force=False)
    assert set(patch_stage_cores) == {3, 4}   # stages 1, 2 skipped


def test_run_all_validates_compound(initialized_db, patch_stage_cores):
    with pytest.raises(ValueError, match="C\\[1-5\\]"):
        run_all(compound="X9", conn=initialized_db)
