"""SQLite schema + writers for parameter_sets and calibration_runs (CALIB-07, D-02).

Security (T-3-01..T-3-06):
  - validate_compound: whitelist ^C[1-5]$ before any SQL op
  - Parameterized queries via sqlite3.execute(sql, dict) — never f-string SQL
  - resolve_db_path: assert inside workspace root, no symlink escapes
  - _git_sha: subprocess with explicit cwd + shell=False, catches every Exception → "unknown"
"""
from __future__ import annotations

import json
import re
import sqlite3
import subprocess
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from f1_calibration.common import WORKSPACE_ROOT, YEAR_RANGE

DEFAULT_DB_PATH: Path = WORKSPACE_ROOT / ".data" / "f1.db"
_COMPOUND_RE = re.compile(r"^C[1-5]$")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS parameter_sets (
    parameter_set_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    compound            TEXT    NOT NULL,
    stage_number        INTEGER NOT NULL,
    year_range          TEXT    NOT NULL,
    created_at          TEXT    NOT NULL,
    git_sha             TEXT    NOT NULL,
    params_json         TEXT    NOT NULL,
    is_latest           INTEGER NOT NULL DEFAULT 1,
    diagnostics_json    TEXT,
    UNIQUE (compound, stage_number, created_at)
);
CREATE INDEX IF NOT EXISTS ix_parameter_sets_latest
    ON parameter_sets (compound, stage_number, is_latest);
CREATE TABLE IF NOT EXISTS calibration_runs (
    calibration_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    compound              TEXT    NOT NULL,
    year_range            TEXT    NOT NULL,
    train_window          TEXT    NOT NULL,
    holdout_window        TEXT    NOT NULL,
    created_at            TEXT    NOT NULL,
    git_sha               TEXT    NOT NULL,
    heldout_rmse_s        REAL    NOT NULL,
    baseline_rmse_s       REAL    NOT NULL,
    r_hat_max             REAL    NOT NULL,
    ess_bulk_min          REAL    NOT NULL,
    netcdf_path           TEXT    NOT NULL,
    param_set_stage1      INTEGER REFERENCES parameter_sets(parameter_set_id),
    param_set_stage2      INTEGER REFERENCES parameter_sets(parameter_set_id),
    param_set_stage3      INTEGER REFERENCES parameter_sets(parameter_set_id),
    param_set_stage4      INTEGER REFERENCES parameter_sets(parameter_set_id),
    stage5_csv_path       TEXT    NOT NULL
);
CREATE TRIGGER IF NOT EXISTS trg_parameter_sets_latest
AFTER INSERT ON parameter_sets
BEGIN
    UPDATE parameter_sets
       SET is_latest = 0
     WHERE compound = NEW.compound
       AND stage_number = NEW.stage_number
       AND parameter_set_id != NEW.parameter_set_id;
END;
"""


def validate_compound(compound: str) -> str:
    """Whitelist-validate compound. Mitigation for T-3-01 (arg injection -> SQL).

    Args:
        compound: Compound code to validate. Accepts mixed case with surrounding
                  whitespace (e.g. ' c3 ' -> 'C3').

    Returns:
        Normalized uppercase compound code (e.g. 'C3').

    Raises:
        ValueError: If compound does not match ^C[1-5]$ after normalization.
    """
    if not isinstance(compound, str):
        raise ValueError(f"compound must be str, got {type(compound).__name__}")
    normalized = compound.strip().upper()
    if not _COMPOUND_RE.match(normalized):
        raise ValueError(f"compound must match ^C[1-5]$, got {compound!r}")
    return normalized


def resolve_db_path(db_path: str | Path | None) -> Path:
    """Resolve db_path to absolute; assert inside workspace root. T-3-03 mitigation.

    Args:
        db_path: Filesystem path to the SQLite database, or None for default.

    Returns:
        Resolved absolute Path inside workspace root.

    Raises:
        ValueError: If the resolved path falls outside WORKSPACE_ROOT or is a symlink.
    """
    if db_path is None:
        resolved = DEFAULT_DB_PATH.resolve()
    else:
        resolved = Path(db_path).expanduser().resolve()
    try:
        resolved.relative_to(WORKSPACE_ROOT.resolve())
    except ValueError:
        raise ValueError(
            f"db_path {resolved} is outside workspace root {WORKSPACE_ROOT}"
        )
    if resolved.is_symlink():
        raise ValueError(f"db_path {resolved} must not be a symlink")
    return resolved


def _git_sha() -> str:
    """Short git SHA of current HEAD. T-3-06: cwd explicit, shell=False, exceptions swallowed.

    Returns:
        Short SHA string (e.g. 'abc1234') or 'unknown' on any subprocess failure.
    """
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(WORKSPACE_ROOT),
            shell=False,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return out.decode("utf-8", errors="replace").strip() or "unknown"
    except Exception:  # noqa: BLE001 — T-3-06: any failure returns sentinel
        return "unknown"


def initialize_schema(conn: sqlite3.Connection) -> None:
    """Create all tables, trigger, and indexes. Idempotent (uses IF NOT EXISTS).

    Args:
        conn: Open sqlite3 connection. The caller retains ownership.
    """
    conn.executescript(_SCHEMA_SQL)
    conn.commit()


def _serialize_params(params: Any) -> str:
    """Serialize a frozen dataclass (AeroParams | FrictionParams | ...) to JSON string."""
    if is_dataclass(params):
        return json.dumps(asdict(params), sort_keys=True)
    if isinstance(params, dict):
        return json.dumps(params, sort_keys=True)
    raise TypeError(f"cannot serialize params of type {type(params).__name__}")


def write_parameter_set(
    conn: sqlite3.Connection,
    compound: str,
    stage_number: int,
    params: Any,
    diagnostics: dict[str, Any] | None = None,
    *,
    year_range: str = YEAR_RANGE,
) -> int:
    """Insert a parameter set row. Triggers is_latest demotion on prior (compound, stage) rows.

    Args:
        conn: Open sqlite3 connection with schema applied.
        compound: Pirelli compound code (e.g. 'C3'). Validated before SQL.
        stage_number: Pipeline stage (1-5).
        params: Frozen dataclass (AeroParams etc.) or dict to serialize to JSON.
        diagnostics: Optional dict of calibration diagnostics (e.g. {'rmse': 0.5}).
        year_range: Training window identifier. Defaults to '2022-2024'.

    Returns:
        Inserted parameter_set_id (>= 1).

    Raises:
        ValueError: If compound or stage_number are invalid.
    """
    compound = validate_compound(compound)
    if stage_number not in (1, 2, 3, 4, 5):
        raise ValueError(f"stage_number must be 1..5, got {stage_number}")
    row = {
        "compound": compound,
        "stage_number": stage_number,
        "year_range": year_range,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "git_sha": _git_sha(),
        "params_json": _serialize_params(params),
        "is_latest": 1,
        "diagnostics_json": json.dumps(diagnostics or {}, sort_keys=True),
    }
    cur = conn.execute(
        "INSERT INTO parameter_sets (compound, stage_number, year_range, created_at, "
        "git_sha, params_json, is_latest, diagnostics_json) VALUES "
        "(:compound, :stage_number, :year_range, :created_at, :git_sha, :params_json, "
        ":is_latest, :diagnostics_json)",
        row,
    )
    conn.commit()
    if cur.lastrowid is None:
        raise RuntimeError("INSERT did not return a lastrowid — database may be read-only")
    return cur.lastrowid


def read_latest_parameter_set(
    conn: sqlite3.Connection,
    compound: str,
    stage_number: int,
    *,
    year_range: str = YEAR_RANGE,
) -> dict[str, Any] | None:
    """Read the most recent is_latest=1 parameter set for (compound, stage_number).

    Args:
        conn: Open sqlite3 connection with schema applied.
        compound: Pirelli compound code. Validated before SQL.
        stage_number: Pipeline stage (1-5).
        year_range: Training window filter. Defaults to '2022-2024'.

    Returns:
        Dict with decoded 'params' (dict from JSON) and 'diagnostics' (dict),
        plus all column values. None if no matching row exists.
    """
    compound = validate_compound(compound)
    cur = conn.execute(
        "SELECT parameter_set_id, compound, stage_number, year_range, created_at, "
        "git_sha, params_json, is_latest, diagnostics_json "
        "FROM parameter_sets "
        "WHERE compound = :compound AND stage_number = :stage_number "
        "  AND year_range = :year_range AND is_latest = 1 "
        "ORDER BY created_at DESC LIMIT 1",
        {"compound": compound, "stage_number": stage_number, "year_range": year_range},
    )
    row = cur.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in cur.description]
    out = dict(zip(cols, row))
    out["params"] = json.loads(out.pop("params_json"))
    out["diagnostics"] = json.loads(out.pop("diagnostics_json") or "{}")
    return out


def has_stage_result(
    conn: sqlite3.Connection,
    compound: str,
    stage_number: int,
    *,
    year_range: str = YEAR_RANGE,
) -> bool:
    """Return True if a is_latest=1 row exists for (compound, stage_number, year_range).

    Used by run-all to detect already-completed stages (D-01 resumable pipeline).
    """
    return read_latest_parameter_set(conn, compound, stage_number, year_range=year_range) is not None


def _validate_stored_path(raw: str, field: str) -> str:
    """Resolve raw path (absolute or relative-to-workspace) and assert it stays inside workspace.

    T-3-02/T-3-03: Both absolute and relative paths must be validated before storage in
    the DB. A relative path such as '../../outside/evil.nc' would bypass a check that
    only tests `is_absolute()`. We resolve relative paths against WORKSPACE_ROOT first.

    Args:
        raw: The raw path string supplied by the caller.
        field: Field name for diagnostic messages.

    Returns:
        The original raw string (stored as-is; only the resolved form is validated).

    Raises:
        ValueError: If the resolved path falls outside WORKSPACE_ROOT or is a symlink.
    """
    p = Path(raw)
    if not p.is_absolute():
        p = WORKSPACE_ROOT / p
    resolve_db_path(p)   # raises ValueError if outside workspace or is a symlink
    return raw  # store the original string, not the resolved absolute form


def write_calibration_run(
    conn: sqlite3.Connection,
    *,
    compound: str,
    heldout_rmse_s: float,
    baseline_rmse_s: float,
    r_hat_max: float,
    ess_bulk_min: float,
    netcdf_path: str,
    param_set_stage1: int,
    param_set_stage2: int,
    param_set_stage3: int,
    param_set_stage4: int,
    stage5_csv_path: str,
) -> int:
    """Insert a completed calibration run row.

    Args:
        conn: Open sqlite3 connection with schema applied.
        compound: Pirelli compound code. Validated before SQL.
        heldout_rmse_s: Per-lap RMSE on 2024 holdout (seconds).
        baseline_rmse_s: Baseline linear model RMSE on same holdout (seconds).
        r_hat_max: Maximum r-hat across all Stage 4 MCMC parameters.
        ess_bulk_min: Minimum bulk ESS across all Stage 4 MCMC parameters.
        netcdf_path: Path to ArviZ NetCDF posterior file (relative or absolute).
        param_set_stage1..4: Foreign keys into parameter_sets.
        stage5_csv_path: Path to Stage 5 per-circuit RMSE CSV.

    Returns:
        Inserted calibration_id (>= 1).

    Raises:
        ValueError: If compound is invalid or either path escapes workspace (T-3-02/T-3-03).
    """
    compound = validate_compound(compound)
    # Validate both paths unconditionally — relative paths like '../../evil.nc' must
    # also be caught. _validate_stored_path resolves against WORKSPACE_ROOT first.
    netcdf_path = _validate_stored_path(netcdf_path, "netcdf_path")
    stage5_csv_path = _validate_stored_path(stage5_csv_path, "stage5_csv_path")
    row = {
        "compound": compound,
        "year_range": YEAR_RANGE,
        "train_window": "2022-2023",
        "holdout_window": "2024",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "git_sha": _git_sha(),
        "heldout_rmse_s": float(heldout_rmse_s),
        "baseline_rmse_s": float(baseline_rmse_s),
        "r_hat_max": float(r_hat_max),
        "ess_bulk_min": float(ess_bulk_min),
        "netcdf_path": str(netcdf_path),
        "param_set_stage1": int(param_set_stage1),
        "param_set_stage2": int(param_set_stage2),
        "param_set_stage3": int(param_set_stage3),
        "param_set_stage4": int(param_set_stage4),
        "stage5_csv_path": str(stage5_csv_path),
    }
    cur = conn.execute(
        "INSERT INTO calibration_runs (compound, year_range, train_window, holdout_window, "
        "created_at, git_sha, heldout_rmse_s, baseline_rmse_s, r_hat_max, ess_bulk_min, "
        "netcdf_path, param_set_stage1, param_set_stage2, param_set_stage3, param_set_stage4, "
        "stage5_csv_path) VALUES "
        "(:compound, :year_range, :train_window, :holdout_window, :created_at, :git_sha, "
        ":heldout_rmse_s, :baseline_rmse_s, :r_hat_max, :ess_bulk_min, :netcdf_path, "
        ":param_set_stage1, :param_set_stage2, :param_set_stage3, :param_set_stage4, "
        ":stage5_csv_path)",
        row,
    )
    conn.commit()
    if cur.lastrowid is None:
        raise RuntimeError("INSERT did not return a lastrowid — database may be read-only")
    return cur.lastrowid


__all__ = [
    "DEFAULT_DB_PATH",
    "initialize_schema",
    "validate_compound",
    "resolve_db_path",
    "write_parameter_set",
    "read_latest_parameter_set",
    "has_stage_result",
    "write_calibration_run",
]
