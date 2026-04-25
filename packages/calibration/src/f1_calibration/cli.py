"""f1-calibrate Typer CLI (CONTEXT.md D-01, RESEARCH.md §Pitfall 6).

Subcommands (all use `--compound` flag per Pitfall 6):
  stage1   — Aero fit (CALIB-01)
  stage2   — Friction fit (CALIB-02)
  stage3   — Thermal fit (CALIB-03)
  stage4   — Degradation MCMC (CALIB-04, CALIB-06, CALIB-07)
  stage5   — Cross-validation + baseline comparison (CALIB-05, CALIB-08)
  run-all  — Chain stages 1→5 with SQLite resumability (D-01)

Exit codes (T-3-04 — no traceback leak at any boundary):
  0 success
  1 validation error (bad compound, bad path)
  2 calibration/convergence error (r̂ failed, stage missing)
  3 unexpected internal error
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from f1_calibration.common import TRAINING_YEARS, YEAR_RANGE, get_logger
from f1_calibration.db import (
    DEFAULT_DB_PATH,
    initialize_schema,
    resolve_db_path,
    validate_compound,
    write_parameter_set,
)

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="f1-calibrate -- Offline Bayesian calibration pipeline (Phase 3).",
)
console = Console()
_log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _handle_exit(exc: Exception) -> typer.Exit:
    """Map exception type → exit code + message without traceback (T-3-04)."""
    if isinstance(exc, ValueError):
        console.print(f"[red]Invalid input:[/red] {exc}")
        return typer.Exit(code=1)
    if isinstance(exc, RuntimeError):
        console.print(f"[red]Calibration failed:[/red] {exc}")
        return typer.Exit(code=2)
    console.print(f"[red]Internal error:[/red] {exc}")
    return typer.Exit(code=3)


def _open_db(db_path: str | None) -> sqlite3.Connection:
    """Open SQLite + initialize schema. Workspace containment check via resolve_db_path."""
    path = resolve_db_path(db_path if db_path else str(DEFAULT_DB_PATH))
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    initialize_schema(conn)
    return conn


# ---------------------------------------------------------------------------
# Stage 1 core
# ---------------------------------------------------------------------------

def _stage1_core(compound: str, conn: sqlite3.Connection, con: Any) -> None:
    """Fit aero params from corner lat-g. Compound-agnostic (D-05)."""
    import numpy as np
    from f1_calibration.stage1_aero import fit_stage1
    from f1_calibration.training import iter_training_stints

    lat_g_list: list[float] = []
    v_list: list[float] = []
    n_stints_used = 0

    for stint in iter_training_stints(years=TRAINING_YEARS, compound=None):
        tel = getattr(stint, "telemetry", None)
        if tel is None:
            continue
        try:
            v_col = np.asarray(tel["V_mps"], dtype=np.float64)
            a_lat = np.asarray(tel["a_lat_mps2"], dtype=np.float64) / 9.81
        except Exception:
            continue
        mask = (v_col > 30.0) & (v_col < 90.0) & (np.abs(a_lat) > 2.0)
        if mask.any():
            lat_g_list.extend(np.abs(a_lat[mask]).tolist())
            v_list.extend(v_col[mask].tolist())
            n_stints_used += 1

    if len(lat_g_list) < 3:
        raise RuntimeError(
            f"insufficient corner samples for stage 1: got {len(lat_g_list)}, need >=3"
        )

    params, diag = fit_stage1(np.asarray(lat_g_list), np.asarray(v_list))
    pid = write_parameter_set(conn, compound, 1, params, diag)

    table = Table(title=f"Stage 1 — Aero fit ({compound})")
    for col in ("Parameter", "Value"):
        table.add_column(col)
    for k, v in {"C_LA": params.C_LA, "C_DA": params.C_DA, "xi": params.xi}.items():
        table.add_row(k, f"{v:.4f}")
    con.print(table)
    con.print(f"[green]Wrote parameter_set_id={pid}[/green]")


# ---------------------------------------------------------------------------
# Stage 2 core
# ---------------------------------------------------------------------------

def _stage2_core(compound: str, conn: sqlite3.Connection, con: Any) -> None:
    """Fit friction baseline. Compound-agnostic (D-05)."""
    import numpy as np
    from f1_calibration.stage2_friction import fit_stage2
    from f1_calibration.training import iter_training_stints

    mu_eff: list[float] = []
    p_bar: list[float] = []

    for stint in iter_training_stints(years=TRAINING_YEARS, compound=None):
        samples = getattr(stint, "friction_samples", None)
        if samples is None:
            continue
        mu_s = samples.get("mu_eff")
        p_s = samples.get("p_bar")
        if mu_s is None or p_s is None:
            continue
        mu_eff.extend(np.asarray(mu_s).tolist())
        p_bar.extend(np.asarray(p_s).tolist())

    if len(mu_eff) < 10:
        raise RuntimeError(
            f"insufficient friction samples: got {len(mu_eff)}, need >=10"
        )

    params, diag = fit_stage2(np.asarray(mu_eff), np.asarray(p_bar))
    pid = write_parameter_set(conn, compound, 2, params, diag)

    table = Table(title=f"Stage 2 — Friction fit ({compound})")
    for col in ("Parameter", "Value"):
        table.add_column(col)
    for k, v in {
        "mu_0_fresh": params.mu_0_fresh,
        "p_bar_0": params.p_bar_0,
        "n": params.n,
    }.items():
        table.add_row(k, f"{v:.4g}")
    con.print(table)
    con.print(f"[green]Wrote parameter_set_id={pid}[/green]")


# ---------------------------------------------------------------------------
# Stage 3 core
# ---------------------------------------------------------------------------

def _stage3_core(compound: str, conn: sqlite3.Connection, con: Any) -> None:
    """Fit thermal ODE params from warm-up curves. Compound-specific (D-05)."""
    import numpy as np
    from f1_calibration.stage3_thermal import WarmupCurve, fit_stage3
    from f1_calibration.training import iter_training_stints

    warmup_curves: list[WarmupCurve] = []

    for stint in iter_training_stints(years=TRAINING_YEARS, compound=compound):
        wc = getattr(stint, "warmup_curve", None)
        if wc is None:
            continue
        warmup_curves.append(wc)

    if len(warmup_curves) < 2:
        raise RuntimeError(
            f"insufficient warm-up curves for stage 3 ({compound}): "
            f"got {len(warmup_curves)}, need >=2"
        )

    params, diag = fit_stage3(warmup_curves, compound=compound)
    pid = write_parameter_set(conn, compound, 3, params, diag)

    table = Table(title=f"Stage 3 — Thermal fit ({compound})")
    for col in ("Parameter", "Value"):
        table.add_column(col)
    for k, v in {
        "C_tread": params.C_tread,
        "C_carc": params.C_carc,
        "C_gas": params.C_gas,
        "R_tc": params.R_tc,
        "R_cg": params.R_cg,
        "h_0": params.h_0,
        "h_1": params.h_1,
        "alpha_p": params.alpha_p,
    }.items():
        table.add_row(k, f"{v:.4g}")
    con.print(table)
    con.print(f"[green]Wrote parameter_set_id={pid}[/green]")


# ---------------------------------------------------------------------------
# Stage 4 core
# ---------------------------------------------------------------------------

def _stage4_core(
    compound: str,
    conn: sqlite3.Connection,
    con: Any,
    *,
    skip_sbc: bool = False,
    chains: int = 4,
    draws: int = 1000,
    tune: int = 1000,
) -> None:
    """Bayesian degradation fit via PyMC + NumPyro NUTS. Compound-specific (D-05)."""
    import numpy as np
    from f1_calibration.stage4_degradation import fit_stage4
    from f1_calibration.training import iter_training_stints

    # Collect fixed trajectories + lap times across training stints
    all_lap_times: list[float] = []
    lap_boundary_idx: list[int] = []
    fixed_trajectories: list[dict] = []
    lap_cursor = 0

    for stint in iter_training_stints(years=TRAINING_YEARS, compound=compound):
        lap_ts = getattr(stint, "lap_times_s", None)
        traj = getattr(stint, "fixed_trajectories", None)
        if lap_ts is None or traj is None:
            continue
        lap_times_arr = np.asarray(lap_ts, dtype=np.float64)
        n = len(lap_times_arr)
        all_lap_times.extend(lap_times_arr.tolist())
        lap_cursor += n
        lap_boundary_idx.append(lap_cursor)
        fixed_trajectories.append(traj)

    if len(all_lap_times) < 10:
        raise RuntimeError(
            f"insufficient lap time data for stage 4 ({compound}): "
            f"got {len(all_lap_times)} laps, need >=10"
        )

    t_lap_ref = float(np.median(all_lap_times))

    # fit_stage4 returns (InferenceData, parameter_set_id)
    idata, pid = fit_stage4(
        compound=compound,
        fixed_trajectories=fixed_trajectories,
        obs_lap_times=np.asarray(all_lap_times),
        lap_boundary_idx=np.asarray(lap_boundary_idx, dtype=np.int64),
        t_lap_ref=t_lap_ref,
        db_conn=conn,
        chains=chains,
        draws=draws,
        tune=tune,
        skip_sbc=skip_sbc,
    )

    import arviz as az
    rhat = az.summary(idata)["r_hat"].max()
    con.print(
        f"[green]Stage 4 complete: parameter_set_id={pid}, r̂_max={rhat:.4f}[/green]"
    )


# ---------------------------------------------------------------------------
# Stage 5 core
# ---------------------------------------------------------------------------

def _stage5_core(compound: str, conn: sqlite3.Connection, con: Any) -> dict:
    """Cross-validation + baseline comparison. Writes calibration_runs row."""
    from f1_calibration.stage5_validation import fit_stage5

    results = fit_stage5(compound, conn)

    table = Table(title=f"Stage 5 — Validation ({compound})")
    for col in ("Metric", "Value"):
        table.add_column(col)
    table.add_row("Physics RMSE (s)", f"{results['physics_rmse_s']:.4f}")
    table.add_row("Baseline RMSE (s)", f"{results['baseline_rmse_s']:.4f}")
    table.add_row("N stints", str(results.get("n_stints", "?")))
    con.print(table)
    return results


# ---------------------------------------------------------------------------
# Typer subcommands
# ---------------------------------------------------------------------------

@app.command()
def stage1(
    compound: str = typer.Option(..., "--compound", help="Target compound C1..C5"),
    db_path: str | None = typer.Option(None, "--db", help="SQLite path (default .data/f1.db)"),
) -> None:
    """Fit aero params (C_LA, C_DA, xi) -- CALIB-01. Compound-agnostic; stored under target key."""
    try:
        compound = validate_compound(compound)
        conn = _open_db(db_path)
        try:
            _stage1_core(compound, conn, console)
        finally:
            conn.close()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — CLI boundary (T-3-04)
        raise _handle_exit(exc)


@app.command()
def stage2(
    compound: str = typer.Option(..., "--compound", help="Target compound C1..C5"),
    db_path: str | None = typer.Option(None, "--db", help="SQLite path (default .data/f1.db)"),
) -> None:
    """Fit friction baseline (μ₀^fresh, p̄₀, n) — CALIB-02. Compound-agnostic."""
    try:
        compound = validate_compound(compound)
        conn = _open_db(db_path)
        try:
            _stage2_core(compound, conn, console)
        finally:
            conn.close()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — CLI boundary (T-3-04)
        raise _handle_exit(exc)


@app.command()
def stage3(
    compound: str = typer.Option(..., "--compound", help="Target compound C1..C5"),
    db_path: str | None = typer.Option(None, "--db", help="SQLite path (default .data/f1.db)"),
) -> None:
    """Fit thermal ODE params (C_tread, R_tc, h_0, …) — CALIB-03. Compound-specific."""
    try:
        compound = validate_compound(compound)
        conn = _open_db(db_path)
        try:
            _stage3_core(compound, conn, console)
        finally:
            conn.close()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — CLI boundary (T-3-04)
        raise _handle_exit(exc)


@app.command()
def stage4(
    compound: str = typer.Option(..., "--compound", help="Target compound C1..C5"),
    db_path: str | None = typer.Option(None, "--db", help="SQLite path (default .data/f1.db)"),
    skip_sbc: bool = typer.Option(False, "--skip-sbc", help="Skip SBC pre-flight (CALIB-06)"),
    chains: int = typer.Option(4, "--chains", help="MCMC chains"),
    draws: int = typer.Option(1000, "--draws", help="Posterior draws per chain"),
    tune: int = typer.Option(1000, "--tune", help="Tuning steps per chain"),
) -> None:
    """Bayesian degradation MCMC (β_therm, T_act, k_wear) — CALIB-04/06/07. Compound-specific."""
    try:
        compound = validate_compound(compound)
        conn = _open_db(db_path)
        try:
            _stage4_core(
                compound, conn, console,
                skip_sbc=skip_sbc, chains=chains, draws=draws, tune=tune,
            )
        finally:
            conn.close()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — CLI boundary (T-3-04)
        raise _handle_exit(exc)


@app.command()
def stage5(
    compound: str = typer.Option(..., "--compound", help="Target compound C1..C5"),
    db_path: str | None = typer.Option(None, "--db", help="SQLite path (default .data/f1.db)"),
) -> None:
    """Cross-validation + baseline comparison — CALIB-05/08. Reads stages 1-4 from SQLite."""
    try:
        compound = validate_compound(compound)
        conn = _open_db(db_path)
        try:
            _stage5_core(compound, conn, console)
        finally:
            conn.close()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — CLI boundary (T-3-04)
        raise _handle_exit(exc)


@app.command("run-all")
def run_all_cmd(
    compound: str = typer.Option(..., "--compound", help="Target compound C1..C5"),
    db_path: str | None = typer.Option(None, "--db", help="SQLite path (default .data/f1.db)"),
    force: bool = typer.Option(False, "--force", help="Re-run all stages even if already complete"),
) -> None:
    """Chain stages 1→5 with SQLite resumability — D-01. Skips completed stages unless --force."""
    try:
        compound = validate_compound(compound)
        conn = _open_db(db_path)
        try:
            from f1_calibration.run_all import run_all
            result = run_all(compound=compound, conn=conn, force=force, console=console)
            console.print(
                f"[green]run-all complete:[/green] calibration_id={result['calibration_id']} "
                f"physics_rmse={result['physics_rmse_s']:.4f}s "
                f"baseline_rmse={result['baseline_rmse_s']:.4f}s"
            )
        finally:
            conn.close()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — CLI boundary (T-3-04)
        raise _handle_exit(exc)


if __name__ == "__main__":
    app()


__all__ = [
    "app",
    "_stage1_core",
    "_stage2_core",
    "_stage3_core",
    "_stage4_core",
    "_stage5_core",
]
