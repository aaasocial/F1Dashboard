"""Service layer for GET /calibration/{compound} (API-05, D-09).

D-05 compliant: no pymc/numpyro/pytensor imports.
"""
from __future__ import annotations
import logging
import sqlite3

import arviz as az
import numpy as np

from f1_calibration.db import (
    DEFAULT_DB_PATH, read_latest_parameter_set, validate_compound,
)
from f1_api.schemas.calibration import (
    CalibrationMetadata, CalibrationResponse, Stage1Summary, Stage2Summary,
    Stage3Summary, Stage4Summary, Stage4VarSummary, Stage5Summary,
)
from f1_api.services.posterior_store import get_posterior

log = logging.getLogger(__name__)
_STAGE4_VARS = ("beta_therm", "T_act", "k_wear")


def _read_calibration_run_direct(db_path, compound: str):
    """Read latest calibration_runs row for compound directly via sqlite3.

    Does NOT call resolve_db_path() — the DB path here is app-controlled
    (either DEFAULT_DB_PATH or a test monkeypatch), not user-supplied input.
    Parameterized SQL prevents injection (T-4-SQL). The compound whitelist
    is applied by the caller before this function is invoked.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(
            "SELECT calibration_id, compound, year_range, created_at, git_sha, "
            "heldout_rmse_s, baseline_rmse_s, r_hat_max, ess_bulk_min, netcdf_path "
            "FROM calibration_runs WHERE compound = :compound "
            "ORDER BY created_at DESC LIMIT 1",
            {"compound": compound},
        )
        row = cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))
    finally:
        conn.close()


def build_calibration_summary(compound: str) -> CalibrationResponse:
    """Compose a per-compound calibration summary across all 5 stages."""
    # 1. Whitelist validation BEFORE any DB touch (T-4-SQL)
    compound = validate_compound(compound)

    # 2. Latest calibration_runs row
    cal_run = _read_calibration_run_direct(DEFAULT_DB_PATH, compound)
    if cal_run is None:
        raise ValueError(f"no calibration for compound={compound}")

    # 3. Parameter sets for stages 1-4
    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    try:
        stage1 = read_latest_parameter_set(conn, compound, 1)
        stage2 = read_latest_parameter_set(conn, compound, 2)
        stage3 = read_latest_parameter_set(conn, compound, 3)
        stage4 = read_latest_parameter_set(conn, compound, 4)
    finally:
        conn.close()
    for name, row in [("stage1", stage1), ("stage2", stage2),
                      ("stage3", stage3), ("stage4", stage4)]:
        if row is None:
            raise ValueError(f"missing {name} parameter_set for compound={compound}")

    # 4. Stage 4 posterior summary from NetCDF
    idata = get_posterior(cal_run["netcdf_path"])
    stage4_block = _stage4_block(idata)

    # 5. Compose response
    return CalibrationResponse(
        metadata=CalibrationMetadata(
            calibration_id=int(cal_run["calibration_id"]),
            compound=compound,
            year_range=str(cal_run["year_range"]),
            created_at=str(cal_run["created_at"]),
            git_sha=str(cal_run["git_sha"]),
        ),
        stage1=Stage1Summary(
            **{k: float(stage1["params"][k]) for k in (
                "C_LA", "C_DA", "xi", "K_rf_split", "WD", "H_CG", "BB")},
            residual_rmse=_residual_rmse(stage1),
        ),
        stage2=Stage2Summary(
            **{k: float(stage2["params"][k]) for k in (
                "mu_0_fresh", "p_bar_0", "n", "c_py", "K_rad")},
            residual_rmse=_residual_rmse(stage2),
        ),
        stage3=Stage3Summary(
            **{k: float(stage3["params"][k]) for k in (
                "T_opt", "sigma_T", "C_tread", "C_carc", "C_gas",
                "R_tc", "R_cg", "h_0", "h_1", "alpha_p", "delta_T_blanket")},
            residual_rmse=_residual_rmse(stage3),
        ),
        stage4=stage4_block,
        stage5=Stage5Summary(
            heldout_rmse_s=float(cal_run["heldout_rmse_s"]),
            baseline_rmse_s=float(cal_run["baseline_rmse_s"]),
            beat_baseline=(float(cal_run["heldout_rmse_s"])
                           < float(cal_run["baseline_rmse_s"])),
        ),
    )


def _residual_rmse(row: dict) -> float | None:
    """Best-effort RMSE extraction from diagnostics dict."""
    diag = row.get("diagnostics") or {}
    for key in ("rmse", "residual_rmse", "heldout_rmse"):
        if key in diag and diag[key] is not None:
            return float(diag[key])
    return None


def _stage4_block(idata: az.InferenceData) -> Stage4Summary:
    """az.summary with hdi_prob=0.95 -> Stage4Summary."""
    df = az.summary(
        idata,
        var_names=list(_STAGE4_VARS),
        hdi_prob=0.95,
        stat_focus="mean",
    )
    # ArviZ column names at hdi_prob=0.95: mean, sd, hdi_2.5%, hdi_97.5%,
    # mcse_mean, mcse_sd, ess_bulk, ess_tail, r_hat
    return Stage4Summary(
        beta_therm=_stage4_var(df, "beta_therm"),
        T_act=_stage4_var(df, "T_act"),
        k_wear=_stage4_var(df, "k_wear"),
    )


def _stage4_var(df, var: str) -> Stage4VarSummary:
    # Resolve actual HDI column names (ArviZ may use "hdi_2.5%" or "hdi_2.50%")
    cols = df.columns.tolist()
    lo_col = next((c for c in cols if c.startswith("hdi_2.")), None)
    hi_col = next((c for c in cols if c.startswith("hdi_97.")), None)
    if lo_col is None or hi_col is None:
        raise ValueError(
            f"az.summary did not return expected HDI columns; got: {cols}"
        )
    return Stage4VarSummary(
        mean=float(df.loc[var, "mean"]),
        sd=float(df.loc[var, "sd"]),
        hdi_lo_95=float(df.loc[var, lo_col]),
        hdi_hi_95=float(df.loc[var, hi_col]),
        r_hat=float(df.loc[var, "r_hat"]),
        ess_bulk=float(df.loc[var, "ess_bulk"]),
    )


__all__ = ["build_calibration_summary"]

# Runtime guard: this module must never pull in pymc/numpyro/pytensor.
import sys as _sys  # noqa: E402
_forbidden = [m for m in _sys.modules if m.split(".")[0] in {"pymc", "numpyro", "pytensor"}]
if _forbidden:  # pragma: no cover — defence in depth
    raise ImportError(
        f"D-05 violation in services/calibration.py: {_forbidden}"
    )
