"""Service layer for POST /simulate (API-04).

Decisions: D-01..D-06 implemented at full fidelity. D-05 compliance: this
module does NOT import pymc, numpyro, or pytensor.
"""
from __future__ import annotations
import importlib.metadata
import logging
import re
import shutil
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
from f1_core.ingestion import init_cache, load_stint, parse_race_id
from f1_core.physics.defaults import make_nominal_params
from f1_core.physics.orchestrator import run_simulation, SimulationResult  # noqa: F401
from f1_core.physics.params import (
    AeroParams, DegradationParams, FrictionParams, PhysicsParams, ThermalParams,
)
from f1_core.stint_annotation import load_compound_mapping
from f1_calibration.common import WORKSPACE_ROOT
from f1_calibration.db import DEFAULT_DB_PATH, read_latest_parameter_set, validate_compound
from f1_api.services.sessions import SESSION_ROOT

from f1_api.cache.simulate_cache import SimulateCache, hash_overrides
from f1_api.schemas.simulate import (
    CIArray1D, CIArray2D, CIValue,
    ParameterOverrides, PerLapRow, PerStintSummary, PerTimestepBlock,
    SimulateRequest, SimulateResponse, SimulationMetadata,  # noqa: F401
)
from f1_api.services.posterior_store import (
    get_posterior, make_seed, read_latest_calibration_run, sample_stage4_draws,
)

log = logging.getLogger(__name__)
MODEL_SCHEMA_VERSION = "v1"
K_DRAWS = 100

# Compound letter pattern (C1-C5)
_COMPOUND_LETTER_RE = re.compile(r"^C[1-5]$", re.IGNORECASE)

# Session ID regex: 32 hex chars (uuid4().hex) — T-4-SESSION-ESCAPE defence-in-depth
_SESSION_ID_RE = re.compile(r"^[0-9a-f]{32}$")

# Module-level cache singleton, initialized on first use OR by app lifespan.
_cache: SimulateCache | None = None


def get_cache() -> SimulateCache:
    """Return (or lazily create) the module-level SimulateCache singleton."""
    global _cache
    if _cache is None:
        _cache = SimulateCache(DEFAULT_DB_PATH, max_entries=64)
    return _cache


def _merge_session_into_cache(session_id: str) -> None:
    """Pitfall 7 Option A: copy uploaded session contents into global FastF1
    cache so load_stint() finds data without a Jolpica round-trip.

    Security (T-4-SESSION-ESCAPE):
      - session_id regex-validated (defence-in-depth on top of Pydantic).
      - Resolved path must stay under SESSION_ROOT (symlink-escape guard).
    """
    from f1_api.services.sessions import SESSION_ROOT as _SESSION_ROOT
    if not _SESSION_ID_RE.match(session_id):
        raise ValueError(f"invalid session_id format: {session_id!r}")
    session_dir = _SESSION_ROOT / session_id
    if not session_dir.exists() or not session_dir.is_dir():
        raise ValueError(f"unknown session_id: {session_id}")
    # Defence-in-depth: ensure session_dir really resolves under SESSION_ROOT
    resolved = session_dir.resolve()
    if not resolved.is_relative_to(_SESSION_ROOT.resolve()):
        raise ValueError(f"session_id escapes SESSION_ROOT: {session_id}")
    fastf1_cache_root = init_cache()   # idempotent
    shutil.copytree(session_dir, fastf1_cache_root, dirs_exist_ok=True)


def run_simulation_with_uncertainty(
    race_id: str,
    driver_code: str,
    stint_index: int,
    overrides: ParameterOverrides | None = None,
    session_id: str | None = None,
) -> SimulateResponse:
    """Top-level /simulate service (D-01..D-06).

    D-01: three data levels in one response (per-timestep, per-lap, per-stint).
    D-02: mean/lo_95/hi_95 triplet at every level.
    D-03: metadata block with calibration_id, model_schema_version, fastf1_version.
    D-04: K=100 draws; overrides apply equally to all K.
    D-05: no PyMC at runtime (module-level guard below).
    D-06: two-layer LRU+SQLite cache.
    """
    # 0. Pitfall 7 Option A: merge session cache before load_stint so FastF1
    #    finds uploaded data locally and skips the Jolpica round-trip.
    if session_id is not None:
        _merge_session_into_cache(session_id)

    # 1. Load stint (triggers Phase 1 Layer-2 cache)
    year, slug = parse_race_id(race_id)
    artifact = load_stint(
        year=year, event=slug.replace("_", " "),
        driver_code=driver_code, stint_index=stint_index,
    )
    compound_letter = _derive_compound_letter(artifact)  # e.g. "C3"

    # 2. Latest calibration run for this compound
    cal_run = read_latest_calibration_run(DEFAULT_DB_PATH, compound_letter)
    if cal_run is None:
        raise ValueError(f"no calibration for compound={compound_letter}")
    calibration_id = int(cal_run["calibration_id"])

    # 3. Cache probe
    oh = hash_overrides(overrides.model_dump(exclude_none=True) if overrides else None)
    cached = get_cache().get(race_id, driver_code, stint_index, calibration_id, oh)
    if cached is not None:
        return SimulateResponse.model_validate_json(cached)

    # 4. K-draw posterior sampling
    idata = get_posterior(cal_run["netcdf_path"])
    seed = make_seed(race_id, driver_code, stint_index, calibration_id)
    draws = sample_stage4_draws(idata, K=K_DRAWS, seed=seed)

    # 5. Build K PhysicsParams (Stage 1-3 point estimates + Stage 4 samples + overrides)
    params_list = _build_params_list(compound_letter, draws, overrides)

    # 6. K sequential forward passes
    results: list[SimulationResult] = []
    for params_k in params_list:
        result_k = run_simulation(artifact, params_k)
        results.append(result_k)

    # 7. Aggregate mean + 95% CI; assemble response
    response = _assemble_response(
        results=results,
        compound=compound_letter,
        stint_index=stint_index,
        calibration_id=calibration_id,
        overrides_applied=overrides is not None,
    )

    # 8. Cache
    payload = response.model_dump_json().encode()
    get_cache().put(race_id, driver_code, stint_index, calibration_id, oh, payload)
    return response


def _derive_compound_letter(artifact: Any) -> str:
    """Derive C1-C5 compound letter from StintArtifact.

    If the laps DataFrame already has a C[1-5] value (e.g. fixture data),
    use it directly. Otherwise use the compound mapping YAML.
    """
    laps = artifact.laps
    if laps.empty or "Compound" not in laps.columns:
        raise ValueError("stint laps missing Compound column")

    raw_compound = str(laps["Compound"].iloc[0])

    # If already in C[1-5] format, validate and return.
    if _COMPOUND_LETTER_RE.match(raw_compound):
        return validate_compound(raw_compound.upper())

    # Otherwise look up via compound mapping YAML (year + round from artifact.key)
    mapping = load_compound_mapping()
    year = int(artifact.key.year)
    round_number = int(artifact.key.round)
    key = f"{year}-{round_number:02d}"
    letter = mapping.get(key, {}).get(raw_compound.upper(), "")

    if not letter:
        raise ValueError(
            f"Cannot map compound {raw_compound!r} for race {year}-round{round_number}. "
            f"Add an entry to the compound mapping YAML."
        )

    return validate_compound(letter)


def _build_params_list(
    compound: str,
    draws: dict[str, np.ndarray],
    overrides: ParameterOverrides | None,
) -> list[PhysicsParams]:
    """Build K PhysicsParams: Stage 1-3 point estimates + Stage 4 per-draw samples."""
    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    try:
        ps1 = read_latest_parameter_set(conn, compound, 1)
        ps2 = read_latest_parameter_set(conn, compound, 2)
        ps3 = read_latest_parameter_set(conn, compound, 3)
    finally:
        conn.close()

    # Fall back to nominal priors if no calibration data exists for stages 1-3
    nominal = make_nominal_params()

    if ps1 is None:
        log.warning("No Stage 1 params for compound=%s; using nominal priors", compound)
        aero = nominal.aero
    else:
        p = ps1["params"]
        aero = AeroParams(
            C_LA=float(p["C_LA"]),
            C_DA=float(p["C_DA"]),
            xi=float(p["xi"]),
            K_rf_split=float(p["K_rf_split"]),
            WD=float(p["WD"]),
            H_CG=float(p["H_CG"]),
            BB=float(p["BB"]),
        )

    if ps2 is None:
        log.warning("No Stage 2 params for compound=%s; using nominal priors", compound)
        friction = nominal.friction
    else:
        p = ps2["params"]
        friction = FrictionParams(
            mu_0_fresh=float(p["mu_0_fresh"]),
            p_bar_0=float(p["p_bar_0"]),
            n=float(p["n"]),
            c_py=float(p["c_py"]),
            K_rad=float(p["K_rad"]),
        )

    if ps3 is None:
        log.warning("No Stage 3 params for compound=%s; using nominal priors", compound)
        thermal = nominal.thermal
    else:
        p = ps3["params"]
        thermal = ThermalParams(
            T_opt=float(p["T_opt"]),
            sigma_T=float(p["sigma_T"]),
            C_tread=float(p["C_tread"]),
            C_carc=float(p["C_carc"]),
            C_gas=float(p["C_gas"]),
            R_tc=float(p["R_tc"]),
            R_cg=float(p["R_cg"]),
            h_0=float(p["h_0"]),
            h_1=float(p["h_1"]),
            alpha_p=float(p["alpha_p"]),
            delta_T_blanket=float(p["delta_T_blanket"]),
        )

    K = len(draws["beta_therm"])
    params_list: list[PhysicsParams] = []
    for k in range(K):
        degrad = DegradationParams(
            beta_therm=float(draws["beta_therm"][k]),
            T_act=float(draws["T_act"][k]),
            k_wear=float(draws["k_wear"][k]),
        )
        params_k = PhysicsParams(
            aero=aero, friction=friction, thermal=thermal, degradation=degrad
        )
        params_k = _apply_overrides(params_k, overrides)
        params_list.append(params_k)

    return params_list


def _apply_overrides(params: PhysicsParams, overrides: ParameterOverrides | None) -> PhysicsParams:
    """Return a new PhysicsParams with the relevant stage fields overridden."""
    if overrides is None:
        return params

    od = overrides.model_dump(exclude_none=True)
    if not od:
        return params

    # Aero overrides
    aero_fields = {"C_LA", "C_DA", "xi"}
    aero_overrides = {k: v for k, v in od.items() if k in aero_fields}
    aero = replace(params.aero, **aero_overrides) if aero_overrides else params.aero

    # Friction overrides
    friction_fields = {"mu_0_fresh", "p_bar_0", "n"}
    friction_overrides = {k: v for k, v in od.items() if k in friction_fields}
    friction = replace(params.friction, **friction_overrides) if friction_overrides else params.friction

    # Thermal overrides
    thermal_fields = {"T_opt", "sigma_T"}
    thermal_overrides = {k: v for k, v in od.items() if k in thermal_fields}
    thermal = replace(params.thermal, **thermal_overrides) if thermal_overrides else params.thermal

    # Degradation overrides
    degrad_fields = {"beta_therm", "T_act", "k_wear"}
    degrad_overrides = {k: v for k, v in od.items() if k in degrad_fields}
    degrad = replace(params.degradation, **degrad_overrides) if degrad_overrides else params.degradation

    return PhysicsParams(aero=aero, friction=friction, thermal=thermal, degradation=degrad)


def _aggregate_2d(stack: np.ndarray) -> CIArray2D:
    """(K, N, 4) → CIArray2D with mean/lo_95/hi_95. Pitfall 5: .tolist() conversion."""
    mean = stack.mean(axis=0)
    lo_95 = np.percentile(stack, 2.5, axis=0)
    hi_95 = np.percentile(stack, 97.5, axis=0)
    return CIArray2D(
        mean=mean.tolist(),
        lo_95=lo_95.tolist(),
        hi_95=hi_95.tolist(),
    )


def _aggregate_1d(stack: np.ndarray) -> CIArray1D:
    """(K, N) → CIArray1D with mean/lo_95/hi_95."""
    mean = stack.mean(axis=0)
    lo_95 = np.percentile(stack, 2.5, axis=0)
    hi_95 = np.percentile(stack, 97.5, axis=0)
    return CIArray1D(
        mean=mean.tolist(),
        lo_95=lo_95.tolist(),
        hi_95=hi_95.tolist(),
    )


def _aggregate_scalar(stack: np.ndarray) -> CIValue:
    """(K,) → CIValue with mean/lo_95/hi_95."""
    return CIValue(
        mean=float(stack.mean()),
        lo_95=float(np.percentile(stack, 2.5)),
        hi_95=float(np.percentile(stack, 97.5)),
    )


def _assemble_response(
    results: list[SimulationResult],
    compound: str,
    stint_index: int,
    calibration_id: int,
    overrides_applied: bool,
) -> SimulateResponse:
    """Stack K results and build SimulateResponse with all three data levels."""
    K = len(results)

    # --- Per-timestep block ---
    t_tread_stack = np.stack([r.t_tread for r in results])   # (K, N, 4)
    e_tire_stack = np.stack([r.e_tire for r in results])
    mu_stack = np.stack([r.mu for r in results])
    f_z_stack = np.stack([r.f_z for r in results])
    f_y_stack = np.stack([r.f_y for r in results])
    f_x_stack = np.stack([r.f_x for r in results])
    mu_0_stack = np.stack([r.mu_0 for r in results])         # (K, N)

    per_timestep = PerTimestepBlock(
        t=results[0].t.tolist(),                 # deterministic across draws
        t_tread=_aggregate_2d(t_tread_stack),
        e_tire=_aggregate_2d(e_tire_stack),
        mu=_aggregate_2d(mu_stack),
        f_z=_aggregate_2d(f_z_stack),
        f_y=_aggregate_2d(f_y_stack),
        f_x=_aggregate_2d(f_x_stack),
        mu_0=_aggregate_1d(mu_0_stack),
    )

    # --- Per-lap block ---
    # Collect K draws of per-lap dicts; assume same number of laps across draws.
    n_laps = len(results[0].per_lap)
    per_lap_rows: list[PerLapRow] = []

    for lap_idx in range(n_laps):
        lap_draws = [r.per_lap[lap_idx] for r in results if lap_idx < len(r.per_lap)]
        if not lap_draws:
            continue

        ref = lap_draws[0]

        def _scalar_ci(field_key: str, _draws=lap_draws) -> CIValue:
            vals = np.array([
                row[field_key] for row in _draws
                if isinstance(row.get(field_key), (int, float)) and _is_finite(row[field_key])
            ], dtype=np.float64)
            if len(vals) == 0:
                return CIValue(mean=0.0, lo_95=0.0, hi_95=0.0)
            return _aggregate_scalar(vals)

        # Observed lap time is deterministic (from telemetry, not sampled)
        obs_raw = ref.get("Obs_s", "")
        obs_s: float | None = None
        if isinstance(obs_raw, (int, float)) and _is_finite(obs_raw):
            obs_s = float(obs_raw)

        per_lap_rows.append(PerLapRow(
            lap=int(ref.get("Lap", lap_idx + 1)),
            compound=str(ref.get("Compound", compound)),
            age=int(ref.get("Age", 0)) if isinstance(ref.get("Age"), (int, float)) else 0,
            obs_s=obs_s,
            pred_s=_scalar_ci("Pred_s"),
            delta_s=_scalar_ci("Delta_s"),
            grip_pct=_scalar_ci("Grip_pct"),
            t_tread_max_c=_scalar_ci("T_tread_C"),
            e_tire_mj=_scalar_ci("E_tire_MJ"),
        ))

    # --- Per-stint summary ---
    # total predicted time = sum of per-lap pred_s per draw
    total_time_per_draw = np.array([
        sum(
            float(r.per_lap[l].get("Pred_s", 0))
            for l in range(n_laps)
            if l < len(r.per_lap) and isinstance(r.per_lap[l].get("Pred_s"), (int, float))
        )
        for r in results
    ])

    # stint-end grip = mu_0 at last timestep / mu_0_fresh (last draw's param)
    # We use mu_0 at t=-1 across all draws, relative to initial mu_0 (index 0)
    grip_at_end_per_draw = np.array([
        100.0 * r.mu_0[-1] / r.mu_0[0] if r.mu_0[0] > 0 else 0.0
        for r in results
    ])

    # peak tread temp across all timesteps per draw
    peak_t_tread_per_draw = np.array([
        float(np.max(r.t_tread))
        for r in results
    ])

    # total energy (J → MJ) = sum over last timestep across 4 tires per draw
    total_e_tire_per_draw = np.array([
        float(np.sum(r.e_tire[-1])) / 1e6
        for r in results
    ])

    per_stint = PerStintSummary(
        total_predicted_time_s=_aggregate_scalar(total_time_per_draw),
        stint_end_grip_pct=_aggregate_scalar(grip_at_end_per_draw),
        peak_t_tread_c=_aggregate_scalar(peak_t_tread_per_draw),
        total_e_tire_mj=_aggregate_scalar(total_e_tire_per_draw),
    )

    # --- Metadata ---
    metadata = SimulationMetadata(
        calibration_id=calibration_id,
        model_schema_version=MODEL_SCHEMA_VERSION,
        fastf1_version=importlib.metadata.version("fastf1"),
        compound=compound,
        stint_index=stint_index,
        overrides_applied=overrides_applied,
        k_draws=K_DRAWS,
    )

    return SimulateResponse(
        metadata=metadata,
        per_timestep=per_timestep,
        per_lap=per_lap_rows,
        per_stint=per_stint,
    )


def _is_finite(v: Any) -> bool:
    """Check if a value is a finite float/int."""
    try:
        return bool(np.isfinite(float(v)))
    except (TypeError, ValueError):
        return False


# Runtime guard: this module must never pull in pymc/numpyro/pytensor.
import sys as _sys
_forbidden = [m for m in _sys.modules if m.split(".")[0] in {"pymc", "numpyro", "pytensor"}]
if _forbidden:  # pragma: no cover — defence in depth
    raise ImportError(f"D-05 violation: forbidden MCMC modules imported: {_forbidden}")
