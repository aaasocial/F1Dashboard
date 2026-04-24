"""Resumable run-all orchestrator for Phase 3 (CONTEXT D-01, RESEARCH §Pattern 5).

Before each stage, query parameter_sets for (compound, stage_number, year_range);
if a row exists and --force is not passed, skip the stage. Stage 5 ALWAYS runs
(it's validation, not a fit — fresh RMSE is required each run).

At end of every successful run_all: write a calibration_runs row tying the
four parameter_set_ids + Stage 5 CSV + NetCDF path together (CALIB-07).
"""
from __future__ import annotations

import sqlite3
from typing import Any

from f1_calibration.common import YEAR_RANGE, get_logger
from f1_calibration.db import (
    has_stage_result,
    read_latest_parameter_set,
    validate_compound,
    write_calibration_run,
)
from f1_calibration.stage5_validation import fit_stage5

_log = get_logger(__name__)


def _run_stage_dispatch(
    stage_num: int,
    compound: str,
    conn: sqlite3.Connection,
    console: Any,
) -> None:
    """Dispatch to the CLI _stageN_core helper for the given stage.

    Reuses the Typer command bodies via the extracted `_stageN_core` helpers in
    cli.py. This avoids duplicating training-data extraction logic. Uses a lazy
    import to avoid circular initialisation.
    """
    from f1_calibration import cli as cli_mod

    if stage_num == 1:
        cli_mod._stage1_core(compound, conn, console)  # type: ignore[attr-defined]
    elif stage_num == 2:
        cli_mod._stage2_core(compound, conn, console)  # type: ignore[attr-defined]
    elif stage_num == 3:
        cli_mod._stage3_core(compound, conn, console)  # type: ignore[attr-defined]
    elif stage_num == 4:
        cli_mod._stage4_core(compound, conn, console)  # type: ignore[attr-defined]
    else:
        raise ValueError(f"unknown stage_num {stage_num}")


def run_all(
    *,
    compound: str,
    conn: sqlite3.Connection,
    force: bool = False,
    console: Any | None = None,
) -> dict[str, Any]:
    """Chain stages 1→5 with SQLite resumability (D-01).

    Before each stage, checks `has_stage_result(conn, compound, stage_num)`. If a
    completed row already exists and `force` is False, the stage is skipped. Stage 5
    always runs because it writes the `calibration_runs` provenance row.

    Args:
        compound: Pirelli compound code (e.g. 'C3'). Validated at entry (T-3-01).
        conn: Open sqlite3.Connection with schema applied.
        force: If True, re-run all stages even if parameter_sets rows exist.
        console: Optional Rich Console for progress output. Falls back to a default.

    Returns:
        Summary dict with keys: compound, stages_run, stages_skipped,
        physics_rmse_s, baseline_rmse_s, calibration_id.

    Raises:
        ValueError: If compound fails validation (T-3-01).
        RuntimeError: If any stage fails or required rows are missing after run.
    """
    compound = validate_compound(compound)

    if console is None:
        from rich.console import Console
        console = Console()

    stages_run: list[int] = []
    stages_skipped: list[int] = []

    for stage_num in (1, 2, 3, 4):
        if not force and has_stage_result(conn, compound, stage_num):
            console.print(
                f"[dim]Stage {stage_num} already complete for {compound}; "
                f"skipping (use --force to re-run)[/dim]"
            )
            stages_skipped.append(stage_num)
            continue

        console.print(f"[bold]Running stage {stage_num} for {compound}...[/bold]")
        _run_stage_dispatch(stage_num, compound, conn, console)
        stages_run.append(stage_num)

    # Stage 5 ALWAYS runs — produces the calibration_runs row.
    console.print(f"[bold]Running stage 5 (validation) for {compound}...[/bold]")
    stage5 = fit_stage5(compound, conn)

    # Collect stage 1-4 parameter_set_ids + stage 4 diagnostics
    ids: dict[int, int] = {}
    stage4_diag: dict[str, Any] = {}
    for s in (1, 2, 3, 4):
        row = read_latest_parameter_set(conn, compound, s)
        if row is None:
            raise RuntimeError(
                f"cannot write calibration_runs: stage {s} missing after run_all"
            )
        ids[s] = int(row["parameter_set_id"])
        if s == 4:
            stage4_diag = row.get("diagnostics") or {}

    # NaN-safe baseline_rmse_s
    baseline_rmse = float(stage5["baseline_rmse_s"])
    if baseline_rmse != baseline_rmse:  # NaN check
        baseline_rmse = 0.0

    calibration_id = write_calibration_run(
        conn,
        compound=compound,
        heldout_rmse_s=float(stage5["physics_rmse_s"]),
        baseline_rmse_s=baseline_rmse,
        r_hat_max=float(stage4_diag.get("r_hat_max", 0.0)),
        ess_bulk_min=float(stage4_diag.get("ess_bulk_min", 0.0)),
        netcdf_path=str(stage4_diag.get("netcdf_path", "")),
        param_set_stage1=ids[1],
        param_set_stage2=ids[2],
        param_set_stage3=ids[3],
        param_set_stage4=ids[4],
        stage5_csv_path=str(stage5.get("csv_path") or ""),
    )

    console.print(
        f"[green]run-all complete:[/green] calibration_id={calibration_id} "
        f"physics_rmse={stage5['physics_rmse_s']:.4f}s "
        f"baseline_rmse={stage5['baseline_rmse_s']:.4f}s"
    )

    return {
        "compound": compound,
        "stages_run": stages_run,
        "stages_skipped": stages_skipped,
        "physics_rmse_s": float(stage5["physics_rmse_s"]),
        "baseline_rmse_s": float(stage5["baseline_rmse_s"]),
        "calibration_id": calibration_id,
    }


__all__ = ["run_all"]
