"""Deterministic fixture builder for Stage-4 NetCDF posterior + calibration_runs SQLite row.

Provides ``build_fixture_posterior`` — used by conftest.py ``fixture_calibration`` session
fixture and any test that needs a pre-seeded posterior without running real MCMC.

Security (T-4-W0-LEAK, T-4-W0-OVERWRITE):
  - NetCDF written under WORKSPACE_ROOT/.data/posteriors/fixture_<uuid4>.nc
  - SQLite DB written under caller-supplied tmp_path (never DEFAULT_DB_PATH)
  - Both paths registered for teardown cleanup via the returned metadata
"""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

import arviz as az
import numpy as np
import xarray as xr

from f1_calibration.common import WORKSPACE_ROOT
from f1_calibration.db import (
    DEFAULT_DB_PATH,
    initialize_schema,
    write_calibration_run,
    write_parameter_set,
)
from f1_core.physics.params import AeroParams, DegradationParams, FrictionParams, ThermalParams

# Default dummy parameter values — physically plausible, not calibrated
_DEFAULT_AERO = AeroParams(
    C_LA=3.5,
    C_DA=1.2,
    xi=0.45,
    K_rf_split=0.55,
    WD=0.47,
    H_CG=0.3,
    BB=0.58,
)
_DEFAULT_FRICTION = FrictionParams(
    mu_0_fresh=1.2,
    p_bar_0=2.0e5,
    n=0.8,
    c_py=1.0e6,
    K_rad=1.5e6,
)
_DEFAULT_THERMAL = ThermalParams(
    T_opt=100.0,
    sigma_T=20.0,
    C_tread=2000.0,
    C_carc=3000.0,
    C_gas=500.0,
    R_tc=0.05,
    R_cg=0.1,
    h_0=10.0,
    h_1=2.0,
    alpha_p=0.1,
    delta_T_blanket=20.0,
)


def build_fixture_posterior(
    tmp_path: Path,
    *,
    compound: str = "C3",
    chains: int = 2,
    draws: int = 50,
    seed: int = 42,
) -> tuple[Path, int, Path]:
    """Build a minimal Stage-4 NetCDF + seed a calibration_runs row.

    Args:
        tmp_path: Directory for the SQLite database (must be pytest tmp_path or similar).
                  The NetCDF is written under WORKSPACE_ROOT/.data/posteriors/ (T-4-W0-LEAK).
        compound: Pirelli compound code (default "C3").
        chains: Number of MCMC chains in fake posterior (default 2).
        draws: Number of draws per chain (default 50).
        seed: RNG seed for deterministic sample generation (default 42).

    Returns:
        Tuple of (netcdf_path, calibration_id, db_path).

    Security:
        - db_path is under tmp_path, never DEFAULT_DB_PATH (T-4-W0-OVERWRITE)
        - netcdf_path is under WORKSPACE_ROOT/.data/posteriors/ (T-4-W0-LEAK)
        - Caller must register finalizer to delete netcdf_path (and stage5 CSV) on teardown
    """
    rng = np.random.default_rng(seed)

    # 1. Build fake posterior samples (physically plausible ranges)
    beta_therm = rng.uniform(1e-6, 1e-5, size=(chains, draws))
    T_act = rng.uniform(80.0, 120.0, size=(chains, draws))
    k_wear = rng.uniform(1e-10, 1e-9, size=(chains, draws))

    # 2. Wrap in xarray.Dataset with dims (chain, draw) matching ArviZ convention
    ds = xr.Dataset(
        {
            "beta_therm": (["chain", "draw"], beta_therm),
            "T_act": (["chain", "draw"], T_act),
            "k_wear": (["chain", "draw"], k_wear),
        },
        coords={
            "chain": np.arange(chains),
            "draw": np.arange(draws),
        },
    )

    # 3. Wrap in ArviZ InferenceData
    idata = az.from_dict(posterior={"beta_therm": beta_therm, "T_act": T_act, "k_wear": k_wear})

    # 4. Write NetCDF under WORKSPACE_ROOT/.data/posteriors/ (T-4-W0-LEAK)
    posteriors_dir = WORKSPACE_ROOT / ".data" / "posteriors"
    posteriors_dir.mkdir(parents=True, exist_ok=True)
    netcdf_filename = f"fixture_{compound}_{uuid.uuid4().hex}.nc"
    netcdf_path = posteriors_dir / netcdf_filename
    az.to_netcdf(idata, str(netcdf_path))

    # 5. Build SQLite DB under tmp_path (never DEFAULT_DB_PATH — T-4-W0-OVERWRITE)
    db_path = tmp_path / "f1.db"
    assert db_path != DEFAULT_DB_PATH, (
        f"Fixture must not write to DEFAULT_DB_PATH {DEFAULT_DB_PATH}. "
        f"Received tmp_path={tmp_path}"
    )

    conn = sqlite3.connect(str(db_path))
    initialize_schema(conn)

    # 6. Write parameter sets for stages 1–4
    ps1 = write_parameter_set(conn, compound, 1, _DEFAULT_AERO)
    ps2 = write_parameter_set(conn, compound, 2, _DEFAULT_FRICTION)
    ps3 = write_parameter_set(conn, compound, 3, _DEFAULT_THERMAL)

    mean_params = DegradationParams(
        beta_therm=float(beta_therm.mean()),
        T_act=float(T_act.mean()),
        k_wear=float(k_wear.mean()),
    )
    ps4 = write_parameter_set(
        conn,
        compound,
        4,
        mean_params,
        diagnostics={"r_hat_max": 1.005, "ess_bulk_min": 450.0, "n_divergences": 0},
    )

    # 7. Create a minimal stage5 CSV under WORKSPACE_ROOT/.data so path validation passes
    stage5_csv_path = WORKSPACE_ROOT / ".data" / "posteriors" / f"stage5_{uuid.uuid4().hex}.csv"
    stage5_csv_path.write_text("circuit,rmse_s\nbahrain,0.2\n")

    # 8. Write calibration_runs row
    calibration_id = write_calibration_run(
        conn,
        compound=compound,
        heldout_rmse_s=0.25,
        baseline_rmse_s=0.45,
        r_hat_max=1.005,
        ess_bulk_min=450.0,
        netcdf_path=str(netcdf_path),
        param_set_stage1=ps1,
        param_set_stage2=ps2,
        param_set_stage3=ps3,
        param_set_stage4=ps4,
        stage5_csv_path=str(stage5_csv_path),
    )
    conn.close()

    return netcdf_path, calibration_id, db_path


__all__ = ["build_fixture_posterior"]
