"""Stage 2 — Friction baseline (CALIB-02).

Fits mu_0^fresh, p_bar_0, n via log-log regression on peak lateral grip samples
from laps 2-5 of each training stint.

Model (model_spec §D.3):  mu_eff(p_bar) = mu_0 * (p_bar_0 / p_bar)^(1-n)
Take logs:                ln mu_eff = ln mu_0 + (1-n)*ln p_bar_0 - (1-n)*ln p_bar
Linear form:              ln mu_eff = alpha + beta * ln p_bar
                            where beta = -(1-n) = n-1  ->  n = 1 + beta
                            and alpha = ln mu_0 + (1-n)*ln p_bar_0
Choose p_bar_0 = median(p_bar samples)  ->  mu_0 = exp(alpha + beta * ln p_bar_0).

Compound-agnostic per D-05.
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from f1_core.physics.params import FrictionParams
from f1_core.physics.defaults import make_nominal_params


def fit_stage2(
    mu_eff_samples: NDArray[np.float64],
    p_bar_samples: NDArray[np.float64],
) -> tuple[FrictionParams, dict[str, float | int]]:
    """Closed-form log-log regression. No iterative optimizer needed."""
    mu = np.asarray(mu_eff_samples, dtype=np.float64).ravel()
    p = np.asarray(p_bar_samples, dtype=np.float64).ravel()
    if mu.shape != p.shape:
        raise ValueError(f"shape mismatch: mu {mu.shape} vs p {p.shape}")
    if mu.size < 10:
        raise ValueError(f"need at least 10 samples, got {mu.size}")
    if np.any(mu <= 0.0) or np.any(p <= 0.0):
        raise ValueError("mu_eff and p_bar must be strictly positive (log requires)")

    log_mu = np.log(mu)
    log_p = np.log(p)
    slope, intercept = np.polyfit(log_p, log_mu, 1)

    # n = 1 + slope  (slope = -(1-n))
    n_fit = float(1.0 + slope)
    p_bar_0 = float(np.median(p))
    mu_0_fresh = float(np.exp(intercept + slope * np.log(p_bar_0)))

    # Diagnostics: R^2
    pred = intercept + slope * log_p
    ss_res = float(np.sum((log_mu - pred) ** 2))
    ss_tot = float(np.sum((log_mu - np.mean(log_mu)) ** 2))
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    nominal = make_nominal_params().friction
    params = FrictionParams(
        mu_0_fresh=mu_0_fresh,
        p_bar_0=p_bar_0,
        n=n_fit,
        c_py=nominal.c_py,       # semi-constrained — keep nominal
        K_rad=nominal.K_rad,     # semi-constrained — keep nominal
    )
    diagnostics: dict[str, float | int] = {
        "n_samples": int(mu.size),
        "r_squared": r_squared,
        "n_fit": n_fit,
    }
    return params, diagnostics


__all__ = ["fit_stage2"]
