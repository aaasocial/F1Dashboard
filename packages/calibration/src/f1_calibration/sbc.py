"""Simulation-based calibration (CALIB-06, Pitfall 7 mitigation).

The correct SBC loop per Talts et al. 2018:
  1. Sample theta* ~ prior
  2. Simulate y* = forward_model(theta*, noise)    <- MANDATORY joint step
  3. Fit posterior p(theta | y*) via MCMC
  4. Compute rank of theta* in posterior draws
Uniformity of ranks across n_simulations trials -> correct inference.

Pitfall 7: skipping step 2 (using only the prior) passes SBC trivially because
it tests the prior against itself. The `forward_fn` argument is NOT optional.

We roll our own rather than use simuk (MEDIUM confidence community package) --
our 3-parameter model is simple enough that a ~40-line SBC harness is cleaner.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypedDict

import numpy as np
from numpy.typing import NDArray
from scipy.stats import kstest, uniform

from f1_calibration.common import get_logger

_log = get_logger(__name__)


class SBCResult(TypedDict):
    ranks: NDArray[np.int64]           # (n_simulations, n_params)
    param_names: list[str]
    ks_p_value: dict[str, float]
    uniformity_ok: bool


def sbc_uniformity_test(
    ranks: NDArray[np.int64],
    *,
    param_names: list[str] | None = None,
    alpha: float = 0.05,
    n_posterior_draws: int | None = None,
) -> dict[str, Any]:
    """KS test: are rank statistics uniformly distributed?

    ranks: (n_simulations, n_params) integer array with values in [0, n_posterior_draws]

    Args:
        ranks: 2D integer array of shape (n_simulations, n_params).
        param_names: Names for each parameter column.
        alpha: KS test significance level.
        n_posterior_draws: The known upper bound of the rank distribution
            (= draws * chains). When supplied, normalization uses this fixed
            value instead of the empirical max, preventing false KS rejections
            when the empirical max happens to be less than the true upper bound.
            If None, falls back to ranks.max() + 1 (conservative estimate that
            includes the upper boundary).
    """
    ranks = np.asarray(ranks, dtype=np.int64)
    if ranks.ndim != 2:
        raise ValueError(f"ranks must be 2D (n_simulations, n_params), got shape {ranks.shape}")
    n_sim, n_params = ranks.shape
    if param_names is None:
        param_names = [f"param_{i}" for i in range(n_params)]
    if len(param_names) != n_params:
        raise ValueError(f"len(param_names)={len(param_names)} != n_params={n_params}")

    # Use the known maximum (n_posterior_draws) if supplied; fall back to
    # ranks.max() + 1 as a conservative estimate that includes the upper boundary.
    # Using the empirical max (old behaviour) was biased: when all theta* values
    # happen to fall below the largest posterior draw, max_rank < n_posterior_draws
    # and the KS test against Uniform(0,1) rejects a well-calibrated model.
    if n_posterior_draws is not None:
        normalizer = float(n_posterior_draws)
    else:
        normalizer = float(ranks.max() + 1) if ranks.size > 0 else 1.0

    ks_p: dict[str, float] = {}
    for i, name in enumerate(param_names):
        # Normalize ranks to [0, 1] and KS-test against Uniform(0, 1)
        normalized = ranks[:, i].astype(np.float64) / max(normalizer, 1.0)
        stat, p_value = kstest(normalized, uniform.cdf)
        ks_p[name] = float(p_value)

    uniformity_ok = bool(all(p > alpha for p in ks_p.values()))
    return {"ks_p_value": ks_p, "uniformity_ok": uniformity_ok}


def run_sbc(
    build_model_fn: Callable[[NDArray[np.float64]], Any],
    forward_fn: Callable[[dict[str, float], np.random.Generator], NDArray[np.float64]],
    prior_sample_fn: Callable[[np.random.Generator], dict[str, float]],
    *,
    param_names: list[str],
    n_simulations: int = 50,
    seed: int = 42,
    draws: int = 500,
    tune: int = 500,
    chains: int = 2,
    nuts_sampler: str = "numpyro",
) -> SBCResult:
    """Run SBC with correct joint sampling (Pitfall 7).

    Args:
        build_model_fn: y_observed -> pm.Model (fresh model per trial, conditioned on y)
        forward_fn: (theta_dict, rng) -> y_observed array  [MANDATORY -- enforces Pitfall 7]
        prior_sample_fn: rng -> theta_dict  (prior draws)
        param_names: names of sampled parameters (must be keys in theta_dict and pm.Model vars)
        n_simulations: number of SBC trials (50 for pre-flight; 100 for full coverage)

    Returns SBCResult with per-param ranks + KS p-values + uniformity_ok flag.
    """
    import pymc as pm   # local import; arviz + pymc add ~3s to module-import

    rng_master = np.random.default_rng(seed)
    ranks = np.full((n_simulations, len(param_names)), -1, dtype=np.int64)

    for sim_idx in range(n_simulations):
        sub_rng = np.random.default_rng(rng_master.integers(0, 2**31 - 1))
        # Step 1: sample theta* from prior
        theta_true = prior_sample_fn(sub_rng)
        # Step 2: simulate y* from forward model (Pitfall 7 -- this is the mandatory step)
        y_obs = forward_fn(theta_true, sub_rng)
        # Step 3: fit posterior via MCMC
        model = build_model_fn(y_obs)
        with model:
            idata = pm.sample(
                draws=draws, tune=tune, chains=chains,
                nuts_sampler=nuts_sampler,
                random_seed=int(sub_rng.integers(0, 2**31 - 1)),
                progressbar=False,
                idata_kwargs={"log_likelihood": False},
            )
        # Step 4: for each param, count how many posterior draws are below theta*
        for p_idx, name in enumerate(param_names):
            posterior_samples = idata.posterior[name].values.ravel()
            rank = int(np.sum(posterior_samples < theta_true[name]))
            ranks[sim_idx, p_idx] = rank
        if (sim_idx + 1) % 10 == 0:
            _log.info("SBC progress: %d / %d trials", sim_idx + 1, n_simulations)

    diag = sbc_uniformity_test(ranks, param_names=param_names, n_posterior_draws=draws * chains)
    return SBCResult(
        ranks=ranks,
        param_names=list(param_names),
        ks_p_value=diag["ks_p_value"],
        uniformity_ok=diag["uniformity_ok"],
    )


__all__ = ["SBCResult", "run_sbc", "sbc_uniformity_test"]
