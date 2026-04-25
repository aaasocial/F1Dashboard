"""Stage 4 -- Bayesian degradation calibration (CALIB-04, CALIB-07).

Samples (beta_therm, T_act, k_wear, sigma_obs) via PyMC 5.x + NumPyro NUTS. Priors are
LogNormal centered on make_nominal_params() values (D-06). Informative prior on
T_act (Pitfall 3) prevents beta_therm <-> T_act degeneracy. Likelihood wraps the JAX
simulate_mu_0 chain from jax_model.py through a pytensor Op with JAX dispatch.

SBC pre-flight (CALIB-06) runs on synthetic data before every real-data fit.
Posterior is persisted to ArviZ NetCDF; path + diagnostics are mirrored into
the SQLite parameter_sets table (CALIB-07).

Security:
  T-3-01: validate_compound called at all public entry points
  T-3-02: NetCDF load path only from calibration_runs.netcdf_path (read side in Plan 08 CLI)
  T-3-03: resolve_db_path asserts NetCDF write target is inside workspace
  T-3-05: .data/posteriors/*.nc is covered by repo-level .gitignore (.data/)
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

import arviz as az
import jax
import jax.numpy as jnp
import pymc as pm
import pytensor.tensor as pt
from pytensor.graph.op import Op

from f1_core.physics.params import DegradationParams

from f1_calibration.common import DEFAULT_POSTERIORS_DIR, YEAR_RANGE, get_logger
from f1_calibration.db import (
    resolve_db_path,
    validate_compound,
    write_parameter_set,
)
from f1_calibration.jax_model import log_likelihood_f_g, simulate_mu_0
from f1_calibration.priors import degradation_prior_centers
from f1_calibration.sbc import SBCResult, run_sbc

_log = get_logger(__name__)

# ---- JAX jit-ed kernels (compiled on first call -- Pitfall 1) ----


def _make_jit_loglik(fixed: dict[str, Any]):
    """Return a jax.jit-ed scalar log-likelihood closing over fixed trajectory inputs."""

    @jax.jit
    def _loglik(theta: jnp.ndarray) -> jnp.ndarray:
        beta_therm, T_act, k_wear, sigma_obs = theta[0], theta[1], theta[2], theta[3]
        return log_likelihood_f_g(
            beta_therm,
            T_act,
            k_wear,
            sigma_obs,
            obs_lap_times=jnp.asarray(fixed["obs_lap_times"]),
            lap_boundary_idx=jnp.asarray(fixed["lap_boundary_idx"]),
            t_tread_traj=jnp.asarray(fixed["t_tread_traj"]),
            p_slide_traj=jnp.asarray(fixed["p_slide_traj"]),
            mu_0_init=float(fixed["mu_0_init"]),
            d_tread_init=jnp.asarray(fixed["d_tread_init"]),
            t_lap_ref=float(fixed["t_lap_ref"]),
        )

    _loglik_grad = jax.jit(jax.grad(_loglik))
    return _loglik, _loglik_grad


# ---- pytensor Op bridging PyMC -> JAX (RESEARCH §Pattern 3 Option 1) ----


class _JaxLogLikGradOp(Op):
    """Pytensor Op that returns the gradient of the JAX log-likelihood."""

    itypes = [pt.dvector]
    otypes = [pt.dvector]

    def __init__(self, grad_fn: Any) -> None:
        super().__init__()
        self._grad = grad_fn

    def perform(self, node: Any, inputs: list, outputs_storage: list) -> None:
        theta_np = np.asarray(inputs[0], dtype=np.float64)
        outputs_storage[0][0] = np.asarray(self._grad(theta_np), dtype=np.float64)


class _JaxLogLikOp(Op):
    """Pytensor Op wrapping a jit-compiled JAX log-likelihood + gradient.

    PyMC uses NumPyro's JAX lowering for NUTS, so `perform` is only exercised in
    CPU-fallback paths. The `grad` method returns gradients via a companion Op so
    PyTensor's symbolic diff machinery works correctly.
    """

    itypes = [pt.dvector]  # theta shape (4,)
    otypes = [pt.dscalar]

    def __init__(self, loglik_fn: Any, grad_fn: Any) -> None:
        super().__init__()
        self._loglik = loglik_fn
        self._grad = grad_fn

    def perform(self, node: Any, inputs: list, outputs_storage: list) -> None:
        theta_np = np.asarray(inputs[0], dtype=np.float64)
        # Must be a 0-d numpy array (shape=()), not a Python float or np.float64 scalar
        outputs_storage[0][0] = np.array(float(self._loglik(theta_np)), dtype=np.float64)

    def grad(self, inputs: list, output_grads: list) -> list:
        (theta,) = inputs
        grad_op = _JaxLogLikGradOp(self._grad)
        return [output_grads[0] * grad_op(theta)]


# ---- Model builder ----


def build_stage4_model(
    *,
    obs_lap_times: NDArray[np.float64],
    lap_boundary_idx: NDArray[np.int64],
    t_tread_traj: NDArray[np.float64],
    p_slide_traj: NDArray[np.float64],
    mu_0_init: float,
    d_tread_init: NDArray[np.float64],
    t_lap_ref: float,
    compound: str,
) -> pm.Model:
    """Construct a fresh PyMC 5.x model for Stage 4 MCMC.

    Returns a pm.Model conditioned on the fixed trajectories from Stages 1-3.
    Priors: LogNormal on (beta_therm, T_act, k_wear) + HalfNormal on sigma_obs.
    T_act uses an informative sigma=0.3 to prevent beta_therm<->T_act degeneracy
    (Pitfall 3).

    Args:
        obs_lap_times: Observed per-lap times (L,) [s].
        lap_boundary_idx: Lap boundary indices (L+1,) into the trajectory.
        t_tread_traj: Fixed tread temperature trajectory (N, 4) from Stage 3 [deg C].
        p_slide_traj: Fixed sliding power trajectory (N, 4) from Stage 3 [W].
        mu_0_init: Initial tire friction coefficient [-].
        d_tread_init: Initial per-tire tread depth (4,) [m].
        t_lap_ref: Reference lap time [s] (fastest lap with fresh tires).
        compound: Pirelli compound code e.g. 'C3'. Validated before use (T-3-01).

    Returns:
        A fresh pm.Model with priors and Potential log-likelihood defined.
    """
    compound = validate_compound(compound)
    centers = degradation_prior_centers(compound)

    fixed: dict[str, Any] = {
        "obs_lap_times": np.asarray(obs_lap_times, dtype=np.float64),
        "lap_boundary_idx": np.asarray(lap_boundary_idx, dtype=np.int64),
        "t_tread_traj": np.asarray(t_tread_traj, dtype=np.float64),
        "p_slide_traj": np.asarray(p_slide_traj, dtype=np.float64),
        "mu_0_init": float(mu_0_init),
        "d_tread_init": np.asarray(d_tread_init, dtype=np.float64),
        "t_lap_ref": float(t_lap_ref),
    }
    loglik_fn, grad_fn = _make_jit_loglik(fixed)
    jax_op = _JaxLogLikOp(loglik_fn, grad_fn)

    with pm.Model() as model:
        # Priors -- LogNormal for strictly-positive rates (D-06 design)
        beta_therm = pm.LogNormal("beta_therm", mu=np.log(centers["beta_therm"]), sigma=1.0)
        # Pitfall 3: informative prior on T_act prevents beta_therm <-> T_act degeneracy
        T_act = pm.LogNormal("T_act", mu=np.log(centers["T_act"]), sigma=0.3)
        k_wear = pm.LogNormal("k_wear", mu=np.log(centers["k_wear"]), sigma=1.0)
        sigma_obs = pm.HalfNormal("sigma_obs", sigma=0.5)

        theta = pt.stack([beta_therm, T_act, k_wear, sigma_obs])
        pm.Potential("loglik", jax_op(theta))

    return model


# ---- SBC pre-flight ----


def run_stage4_sbc(
    compound: str,
    *,
    n_simulations: int = 30,
    random_seed: int = 42,
    nuts_sampler: str = "numpyro",
) -> SBCResult:
    """Run SBC on a synthetic mini-dataset before attempting real-data fit.

    Uses a 50-step trajectory and 5 synthetic laps -- small enough for CI (<60s
    after JAX compile). Returns SBCResult; caller checks uniformity_ok.

    Args:
        compound: Pirelli compound code (validated internally).
        n_simulations: Number of SBC trials (30 for pre-flight).
        random_seed: Master RNG seed for reproducibility.
        nuts_sampler: NUTS sampler backend ('numpyro', 'pymc', etc.).

    Returns:
        SBCResult with ranks, KS p-values, and uniformity_ok flag.
    """
    compound = validate_compound(compound)
    centers = degradation_prior_centers(compound)

    n_steps, n_laps = 50, 5
    boundaries = np.linspace(0, n_steps, n_laps + 1, dtype=np.int64)
    t_tread_traj = np.full((n_steps, 4), 90.0, dtype=np.float64)
    p_slide_traj = np.full((n_steps, 4), 2000.0, dtype=np.float64)
    mu_0_init = 1.8
    d_tread_init = np.full(4, 0.010, dtype=np.float64)
    t_lap_ref = 90.0

    def prior_sample_fn(rng: np.random.Generator) -> dict[str, float]:
        return {
            "beta_therm": float(
                np.exp(np.log(centers["beta_therm"]) + rng.normal(0, 1.0))
            ),
            "T_act": float(np.exp(np.log(centers["T_act"]) + rng.normal(0, 0.3))),
            "k_wear": float(np.exp(np.log(centers["k_wear"]) + rng.normal(0, 1.0))),
        }

    def forward_fn(
        theta: dict[str, float], rng: np.random.Generator
    ) -> NDArray[np.float64]:
        # Pitfall 7: actually simulate from the forward model, not just resample prior
        mu_traj = np.asarray(
            simulate_mu_0(
                theta["beta_therm"],
                theta["T_act"],
                theta["k_wear"],
                t_tread_traj=t_tread_traj,
                p_slide_traj=p_slide_traj,
                mu_0_init=mu_0_init,
                d_tread_init=d_tread_init,
            )
        )
        mu_end = mu_traj[boundaries[1:] - 1]
        pred_lap_times = (
            t_lap_ref + 0.5 * t_lap_ref * (mu_0_init - mu_end) / mu_0_init
        )
        return (pred_lap_times + rng.normal(0, 0.2, pred_lap_times.shape)).astype(
            np.float64
        )

    def build_model_fn(y_obs: NDArray[np.float64]) -> pm.Model:
        return build_stage4_model(
            obs_lap_times=y_obs,
            lap_boundary_idx=boundaries,
            t_tread_traj=t_tread_traj,
            p_slide_traj=p_slide_traj,
            mu_0_init=mu_0_init,
            d_tread_init=d_tread_init,
            t_lap_ref=t_lap_ref,
            compound=compound,
        )

    _log.info("Running SBC pre-flight (%d trials, sampler=%s)...", n_simulations, nuts_sampler)
    return run_sbc(
        build_model_fn=build_model_fn,
        forward_fn=forward_fn,
        prior_sample_fn=prior_sample_fn,
        param_names=["beta_therm", "T_act", "k_wear"],
        n_simulations=n_simulations,
        seed=random_seed,
        draws=400,
        tune=400,
        chains=2,
        nuts_sampler=nuts_sampler,
    )


# ---- NetCDF persistence ----


def persist_posterior(
    idata: az.InferenceData,
    compound: str,
    *,
    posteriors_dir: Path | None = None,
) -> Path:
    """Write posterior to NetCDF. Enforces workspace-root containment (T-3-03).

    Args:
        idata: ArviZ InferenceData object with posterior group.
        compound: Pirelli compound code (validated internally, T-3-01).
        posteriors_dir: Directory for NetCDF output. Defaults to DEFAULT_POSTERIORS_DIR.
            Must be inside WORKSPACE_ROOT (T-3-03).

    Returns:
        Absolute Path to the written .nc file.

    Raises:
        ValueError: If compound is invalid (T-3-01) or path escapes workspace (T-3-03).
    """
    compound = validate_compound(compound)
    dir_ = posteriors_dir or DEFAULT_POSTERIORS_DIR
    dir_.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = dir_ / f"{compound}_{YEAR_RANGE}_{ts}.nc"
    # Validate path is inside workspace before writing (T-3-03)
    path_abs = resolve_db_path(path)
    # Pitfall 5: do NOT store log_likelihood group (large; compute on demand if WAIC needed)
    idata.to_netcdf(str(path_abs), compress=True)
    _log.info("Wrote posterior to %s", path_abs)
    return path_abs


# ---- Main fit orchestration ----


def fit_stage4(
    *,
    compound: str,
    fixed_trajectories: dict[str, Any],
    obs_lap_times: NDArray[np.float64],
    lap_boundary_idx: NDArray[np.int64],
    t_lap_ref: float,
    db_conn: Any,  # sqlite3.Connection -- not imported at module level for test speed
    chains: int = 4,
    draws: int = 1000,
    tune: int = 1000,
    target_accept: float = 0.90,
    random_seed: int = 42,
    skip_sbc: bool = False,
    nuts_sampler: str = "numpyro",
) -> tuple[az.InferenceData, int]:
    """Full Stage 4 pipeline: SBC -> MCMC -> diagnostics -> NetCDF -> SQLite.

    Validates compound (T-3-01), optionally runs SBC pre-flight on synthetic data,
    builds PyMC model, samples via NumPyro NUTS, asserts convergence diagnostics
    (r_hat < 1.01, ess_bulk > 400), persists posterior to NetCDF, and writes a
    parameter_sets row with stage_number=4 holding posterior MEAN as DegradationParams.

    Args:
        compound: Pirelli compound code (e.g. 'C3'). Validated at entry (T-3-01).
        fixed_trajectories: Dict with keys t_tread_traj (N,4), p_slide_traj (N,4),
            mu_0_init (float), d_tread_init (4,) from Stages 1-3.
        obs_lap_times: Observed per-lap times (L,) [s].
        lap_boundary_idx: Lap boundary indices (L+1,).
        t_lap_ref: Reference lap time [s].
        db_conn: Open sqlite3.Connection with schema applied.
        chains: Number of MCMC chains. Default 4 (D-07).
        draws: Posterior draws per chain. Default 1000 (D-07).
        tune: Tuning steps per chain. Default 1000 (D-07).
        target_accept: NUTS target acceptance probability. Default 0.90 (D-07).
        random_seed: Master RNG seed.
        skip_sbc: If True, skip SBC pre-flight (for testing/debugging only).
        nuts_sampler: NUTS backend. Default 'numpyro' (production).

    Returns:
        Tuple of (InferenceData, parameter_set_id) where parameter_set_id is the
        row inserted into parameter_sets.

    Raises:
        RuntimeError: If SBC pre-flight fails uniformity check (when skip_sbc=False).
        RuntimeError: If r_hat >= 1.01 or ess_bulk <= 400 after sampling.
    """
    compound = validate_compound(compound)

    if not skip_sbc:
        sbc_result = run_stage4_sbc(compound, nuts_sampler=nuts_sampler)
        if not sbc_result["uniformity_ok"]:
            raise RuntimeError(
                f"SBC pre-flight failed for {compound}: "
                f"ks_p_values={sbc_result['ks_p_value']}. "
                "Refusing to fit real data -- investigate prior/likelihood mismatch."
            )
        _log.info("SBC pre-flight passed: %s", sbc_result["ks_p_value"])

    model = build_stage4_model(
        obs_lap_times=obs_lap_times,
        lap_boundary_idx=lap_boundary_idx,
        t_tread_traj=fixed_trajectories["t_tread_traj"],
        p_slide_traj=fixed_trajectories["p_slide_traj"],
        mu_0_init=fixed_trajectories["mu_0_init"],
        d_tread_init=fixed_trajectories["d_tread_init"],
        t_lap_ref=t_lap_ref,
        compound=compound,
    )

    _log.info("Compiling JAX model (one-time, ~30s)...")  # Pitfall 1 UX
    with model:
        idata = pm.sample(
            draws=draws,
            tune=tune,
            chains=chains,
            nuts_sampler=nuts_sampler,
            target_accept=target_accept,
            random_seed=random_seed,
            progressbar=False,
            idata_kwargs={"log_likelihood": False},  # Pitfall 5: no log_likelihood group
        )

    summary = az.summary(idata, var_names=["beta_therm", "T_act", "k_wear"])
    r_hat_max = float(summary["r_hat"].max())
    ess_bulk_min = float(summary["ess_bulk"].min())
    n_div = (
        int(idata.sample_stats.diverging.values.sum())
        if hasattr(idata, "sample_stats") and "diverging" in idata.sample_stats
        else 0
    )

    if r_hat_max >= 1.01:
        raise RuntimeError(
            f"r_hat convergence failed: max r_hat={r_hat_max:.4f} (threshold 1.01)"
        )
    if ess_bulk_min <= 400:
        raise RuntimeError(
            f"ESS threshold failed: min ess_bulk={ess_bulk_min:.1f} (threshold 400)"
        )

    netcdf_path = persist_posterior(idata, compound)

    # Write posterior MEAN as DegradationParams for inter-stage handoff (D-02)
    post = idata.posterior
    mean_params = DegradationParams(
        beta_therm=float(post["beta_therm"].mean()),
        T_act=float(post["T_act"].mean()),
        k_wear=float(post["k_wear"].mean()),
    )
    diagnostics = {
        "r_hat_max": r_hat_max,
        "ess_bulk_min": ess_bulk_min,
        "n_divergences": n_div,
        "netcdf_path": str(netcdf_path),
        "chains": chains,
        "draws": draws,
        "tune": tune,
        "nuts_sampler": nuts_sampler,
    }
    param_set_id = write_parameter_set(db_conn, compound, 4, mean_params, diagnostics)
    return idata, param_set_id


__all__ = [
    "build_stage4_model",
    "fit_stage4",
    "persist_posterior",
    "run_stage4_sbc",
]
