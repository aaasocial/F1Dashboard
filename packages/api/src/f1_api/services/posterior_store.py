"""Posterior NetCDF loader + deterministic K-draw sampler for /simulate.

D-05: Reads NetCDF via ArviZ only. Does NOT import pymc, numpyro, or pytensor.
"""
from __future__ import annotations
import logging
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any

import arviz as az
import numpy as np

from f1_calibration.common import WORKSPACE_ROOT
from f1_calibration.db import resolve_db_path, validate_compound

log = logging.getLogger(__name__)

_STAGE4_VAR_NAMES = ("beta_therm", "T_act", "k_wear")


@lru_cache(maxsize=8)
def get_posterior(netcdf_path: str) -> az.InferenceData:
    """Load a NetCDF posterior. Cached per absolute path, per-worker."""
    path = Path(netcdf_path)
    if not path.is_absolute():
        path = WORKSPACE_ROOT / path
    resolve_db_path(path)  # Pitfall 6 + T-3-02/T-3-03: workspace containment
    return az.from_netcdf(str(path))


def sample_stage4_draws(
    idata: az.InferenceData,
    K: int = 100,
    *,
    seed: int,
) -> dict[str, np.ndarray]:
    """Return {var_name: (K,) array} for the three Stage-4 parameters.

    Uses az.extract with fixed rng for determinism per cache key (Pitfall 8).
    """
    rng = np.random.default_rng(seed)
    ext = az.extract(
        idata,
        var_names=list(_STAGE4_VAR_NAMES),
        num_samples=K,
        rng=rng,
    )
    return {name: np.asarray(ext[name].values) for name in _STAGE4_VAR_NAMES}


def read_latest_calibration_run(
    db_path: str | Path,
    compound: str,
) -> dict[str, Any] | None:
    """SELECT latest calibration_runs row for compound. Parameterized SQL."""
    compound = validate_compound(compound)   # T-4-SQL whitelist guard
    resolved = resolve_db_path(db_path)
    conn = sqlite3.connect(str(resolved))
    try:
        cur = conn.execute(
            "SELECT calibration_id, compound, year_range, created_at, git_sha, "
            "heldout_rmse_s, baseline_rmse_s, r_hat_max, ess_bulk_min, netcdf_path, "
            "param_set_stage1, param_set_stage2, param_set_stage3, param_set_stage4, "
            "stage5_csv_path "
            "FROM calibration_runs WHERE compound = :compound "
            "ORDER BY created_at DESC LIMIT 1",
            {"compound": compound},
        )
        row = cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))
    except sqlite3.OperationalError:
        # Table doesn't exist yet (Phase 3 calibration not yet run) — treat as no data.
        return None
    finally:
        conn.close()


def prime_posterior(db_path: str | Path, compound: str) -> None:
    """Warm the get_posterior cache for a compound (called from app lifespan)."""
    run = read_latest_calibration_run(db_path, compound)
    if run is None:
        log.warning("No calibration_runs row for compound=%s; posterior not primed", compound)
        return
    get_posterior(run["netcdf_path"])


def make_seed(race_id: str, driver_code: str, stint_index: int, calibration_id: int) -> int:
    """Deterministic seed for K-draw sampling per cache key (Pitfall 8)."""
    import hashlib
    key = f"{race_id}|{driver_code}|{stint_index}|{calibration_id}"
    digest = hashlib.sha256(key.encode()).digest()
    # Convert first 4 bytes to an int in [0, 2**32)
    return int.from_bytes(digest[:4], "big")


__all__ = [
    "get_posterior",
    "sample_stage4_draws",
    "read_latest_calibration_run",
    "prime_posterior",
    "make_seed",
]
