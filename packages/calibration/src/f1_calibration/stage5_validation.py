"""Stage 5 — Cross-validation + linear baseline comparison (CALIB-05, CALIB-08).

Reads posterior means for stages 1-4 from SQLite, assembles a PhysicsParams,
runs production forward simulation on the 2024 validation set, reports
per-lap-time RMSE + per-circuit breakdown, and compares against a linear
baseline on the same stints.

Pitfall 4: SC/VSC/pit laps are excluded from the RMSE computation. If the
underlying stint artifact does not expose a 'normal racing' flag, fall back
to MAD-based outlier filtering (|resid| > 3·MAD).

Security:
  T-3-01: validate_compound at entry
  T-3-03: resolve_db_path on csv output directory
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, TypedDict

import numpy as np
from numpy.typing import NDArray

from f1_core.physics.orchestrator import run_simulation
from f1_core.physics.params import (
    AeroParams,
    DegradationParams,
    FrictionParams,
    PhysicsParams,
    ThermalParams,
)

from f1_calibration.baseline import fit_baseline_batch, rmse_per_lap
from f1_calibration.common import DEFAULT_VALIDATION_DIR, VALIDATION_YEARS, get_logger
from f1_calibration.db import read_latest_parameter_set, resolve_db_path, validate_compound

_log = get_logger(__name__)


class CircuitRow(TypedDict):
    circuit: str
    n_stints: int
    rmse_s: float
    mean_delta_s: float
    worst_lap: float


def _assemble_params(db_conn: Any, compound: str) -> PhysicsParams:
    """Read stages 1-4 posterior-mean params from SQLite. Raise if any missing."""
    stages: dict[int, dict] = {}
    for stage_num in (1, 2, 3, 4):
        row = read_latest_parameter_set(db_conn, compound, stage_num)
        if row is None:
            raise RuntimeError(
                f"missing stage {stage_num} params for compound {compound}; "
                f"run `f1-calibrate stage{stage_num} --compound {compound}` first"
            )
        stages[stage_num] = row["params"]
    return PhysicsParams(
        aero=AeroParams(**stages[1]),
        friction=FrictionParams(**stages[2]),
        thermal=ThermalParams(**stages[3]),
        degradation=DegradationParams(**stages[4]),
    )


def _mad_filter(residuals: NDArray[np.float64], threshold: float = 3.0) -> NDArray[np.bool_]:
    """MAD-based outlier mask; True = keep.

    Pitfall 4 mitigation: excludes laps where |obs - pred| > 3·MAD of residuals,
    which catches SC/VSC/pit-in/pit-out laps that inflate lap times by 20-40s.
    """
    if residuals.size < 3:
        return np.ones_like(residuals, dtype=bool)
    med = np.median(residuals)
    mad = np.median(np.abs(residuals - med))
    if mad == 0.0:
        return np.ones_like(residuals, dtype=bool)
    return np.abs(residuals - med) < threshold * mad


def _clean_laps_from_stint(stint_result: Any) -> dict[str, NDArray[np.float64]]:
    """Extract (pred, obs, ages, circuit) + apply Pitfall 4 filter.

    The orchestrator's SimulationResult exposes per_lap_rows() — we read:
      (Lap, Compound, Age, Pred_s, Obs_s, Delta_s, ...)
    If a 'is_normal_racing_lap' flag exists on the underlying stint, use it;
    else fall back to MAD-based filter on (pred - obs) residuals.
    """
    rows = list(stint_result.per_lap_rows())
    if not rows:
        return {
            "pred": np.array([], dtype=np.float64),
            "obs": np.array([], dtype=np.float64),
            "ages": np.array([], dtype=np.float64),
            "circuit": np.array([], dtype=object),
        }

    # Columns: Lap(0), Compound(1), Age(2), Pred_s(3), Obs_s(4), Delta_s(5), ...
    ages_raw = [r[2] for r in rows]
    pred_raw = [r[3] for r in rows]
    obs_raw = [r[4] for r in rows]

    # Filter out rows with non-finite obs (e.g. empty string from per_lap_rows for missing LapTime)
    valid_indices = []
    for idx in range(len(rows)):
        try:
            obs_val = float(obs_raw[idx]) if obs_raw[idx] != "" else float("nan")
        except (TypeError, ValueError):
            obs_val = float("nan")
        if np.isfinite(obs_val):
            valid_indices.append(idx)

    if not valid_indices:
        return {
            "pred": np.array([], dtype=np.float64),
            "obs": np.array([], dtype=np.float64),
            "ages": np.array([], dtype=np.float64),
            "circuit": np.array([], dtype=object),
        }

    ages = np.array([float(ages_raw[i]) if ages_raw[i] != "" else 0.0 for i in valid_indices], dtype=np.float64)
    pred = np.array([float(pred_raw[i]) for i in valid_indices], dtype=np.float64)
    obs = np.array([float(obs_raw[i]) for i in valid_indices], dtype=np.float64)
    resid = pred - obs

    # Primary filter: try to read is_normal_racing_lap from stint if present
    normal_mask: NDArray[np.bool_] | None = None
    stint = getattr(stint_result, "stint", None)
    if stint is not None and hasattr(stint, "is_normal_racing_lap"):
        raw_mask = np.asarray(stint.is_normal_racing_lap, dtype=bool)
        if raw_mask.size == resid.size:
            normal_mask = raw_mask

    if normal_mask is None:
        normal_mask = _mad_filter(resid, threshold=3.0)

    circuit = str(getattr(stint_result, "circuit", "unknown"))
    n_clean = int(normal_mask.sum())
    return {
        "pred": pred[normal_mask],
        "obs": obs[normal_mask],
        "ages": ages[normal_mask],
        "circuit": np.array([circuit] * n_clean, dtype=object),
    }


def fit_stage5(
    compound: str,
    db_conn: Any,
    *,
    validation_stints: Iterable[Any] | None = None,
    validation_dir: Path | None = None,
    skip_baseline: bool = False,
    skip_csv: bool = False,
) -> dict[str, Any]:
    """Run Stage 5 cross-validation: physics RMSE vs linear baseline on 2024 holdout.

    Args:
        compound: Pirelli compound code (e.g. 'C3'). Validated at entry (T-3-01).
        db_conn: Open sqlite3.Connection with schema applied. Must contain
            is_latest=1 rows for stages 1-4 for the given compound.
        validation_stints: Optional override for the validation stint list.
            If None, calls iter_training_stints(years=VALIDATION_YEARS, compound=compound).
            Tests inject _FakeStintResult instances here.
        validation_dir: Output directory for the per-circuit CSV.
            Defaults to DEFAULT_VALIDATION_DIR (.data/validation/).
            Must be inside workspace root (T-3-03 enforced by resolve_db_path).
        skip_baseline: If True, skip linear baseline fitting (baseline_rmse_s = NaN).
        skip_csv: If True, skip CSV writing (csv_path = None).

    Returns:
        dict with keys:
          physics_rmse_s: float — per-lap RMSE across all clean validation laps
          baseline_rmse_s: float | NaN — linear baseline RMSE on same laps
          per_circuit: list[CircuitRow] — per-circuit breakdown, sorted by rmse_s desc
          n_stints: int — number of stints contributing at least one clean lap
          n_laps: int — total clean lap count
          csv_path: str | None — path to per-circuit CSV, or None if skip_csv
          compound: str — normalized compound code

    Raises:
        ValueError: If compound is invalid (T-3-01) or CSV dir is outside workspace (T-3-03).
        RuntimeError: If any of stages 1-4 are missing from SQLite, or all laps filtered.
    """
    compound = validate_compound(compound)
    params = _assemble_params(db_conn, compound)

    if validation_stints is None:
        from f1_calibration.training import iter_training_stints
        validation_stints = list(iter_training_stints(
            years=VALIDATION_YEARS, compound=compound,
        ))
    else:
        validation_stints = list(validation_stints)

    if not validation_stints:
        raise RuntimeError(
            f"no validation stints for compound {compound} in {VALIDATION_YEARS}"
        )

    all_pred: list[NDArray[np.float64]] = []
    all_obs: list[NDArray[np.float64]] = []
    baseline_stints: list[dict[str, Any]] = []
    per_circuit_data: dict[str, list[dict[str, NDArray[np.float64]]]] = {}
    n_stints = 0
    n_laps = 0

    for stint in validation_stints:
        result = run_simulation(stint, params)
        clean = _clean_laps_from_stint(result)
        if clean["pred"].size == 0:
            continue
        n_stints += 1
        n_laps += int(clean["pred"].size)
        all_pred.append(clean["pred"])
        all_obs.append(clean["obs"])
        circuit_key = str(clean["circuit"][0]) if clean["circuit"].size > 0 else "unknown"
        per_circuit_data.setdefault(circuit_key, []).append({
            "pred": clean["pred"],
            "obs": clean["obs"],
        })
        baseline_stints.append({
            "tire_ages": clean["ages"],
            "lap_times_s": clean["obs"],
            "compound": compound,
        })

    if n_laps == 0:
        raise RuntimeError(
            f"all validation laps were filtered out for {compound}"
        )

    pred_all = np.concatenate(all_pred)
    obs_all = np.concatenate(all_obs)
    physics_rmse = rmse_per_lap(obs_all, pred_all)

    baseline_rmse: float = float("nan")
    if not skip_baseline and baseline_stints:
        b_result = fit_baseline_batch(baseline_stints)
        baseline_rmse = float(b_result["combined_rmse_s"])

    per_circuit_rows: list[CircuitRow] = []
    for circuit, entries in per_circuit_data.items():
        c_pred = np.concatenate([e["pred"] for e in entries])
        c_obs = np.concatenate([e["obs"] for e in entries])
        c_delta = c_pred - c_obs
        per_circuit_rows.append(
            CircuitRow(
                circuit=circuit,
                n_stints=len(entries),
                rmse_s=rmse_per_lap(c_obs, c_pred),
                mean_delta_s=float(np.mean(c_delta)),
                worst_lap=float(np.max(np.abs(c_delta))),
            )
        )
    per_circuit_rows.sort(key=lambda r: r["rmse_s"], reverse=True)

    csv_path: Path | None = None
    if not skip_csv:
        dir_ = validation_dir if validation_dir is not None else DEFAULT_VALIDATION_DIR
        dir_.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        csv_filename = f"stage5_{compound}_{ts}_per_circuit.csv"
        csv_path_candidate = dir_ / csv_filename
        # T-3-03: workspace containment check before opening the file handle
        csv_path_abs = resolve_db_path(csv_path_candidate)
        with open(csv_path_abs, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=["circuit", "n_stints", "rmse_s", "mean_delta_s", "worst_lap"],
            )
            writer.writeheader()
            for row in per_circuit_rows:
                writer.writerow(row)
        csv_path = csv_path_abs
        _log.info("Wrote Stage 5 per-circuit CSV: %s", csv_path)

    return {
        "physics_rmse_s": physics_rmse,
        "baseline_rmse_s": baseline_rmse,
        "per_circuit": per_circuit_rows,
        "n_stints": n_stints,
        "n_laps": n_laps,
        "csv_path": str(csv_path) if csv_path is not None else None,
        "compound": compound,
    }


__all__ = ["CircuitRow", "fit_stage5"]
