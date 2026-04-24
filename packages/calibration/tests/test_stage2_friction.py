"""Stage 2 friction fit accuracy on synthetic data (CALIB-02: ±5% mu_0, ±0.05 n)."""
from __future__ import annotations
import numpy as np
import pytest
from f1_calibration.stage2_friction import fit_stage2


def _synthetic_friction_data(mu_0_true: float, n_true: float, p_bar_0_true: float,
                             n_samples: int = 100, seed: int = 0):
    """Generate mu_eff samples from the log-log friction law with Gaussian log-noise.

    Pressure range [0.5x, 1.5x] is symmetric around p_bar_0_true so that
    median(p) ≈ p_bar_0_true — this ensures fit_stage2's mu_0_fresh evaluation
    at the data median matches the true mu_0 to within ±5% (CALIB-02).
    """
    rng = np.random.default_rng(seed)
    # Pressure samples spanning a plausible physical range (symmetric around p_bar_0)
    p = rng.uniform(0.5 * p_bar_0_true, 1.5 * p_bar_0_true, n_samples)
    mu_clean = mu_0_true * (p_bar_0_true / p) ** (1.0 - n_true)
    log_noise = rng.normal(0, 0.01, n_samples)   # ~1% log-space jitter -> R² > 0.95
    mu = mu_clean * np.exp(log_noise)
    return mu, p


def test_stage2_recovers_synthetic_mu_0():
    mu_0_true, n_true, p0_true = 1.9, 0.78, 1.5e5
    mu, p = _synthetic_friction_data(mu_0_true, n_true, p0_true, n_samples=500, seed=42)
    params, diag = fit_stage2(mu, p)
    rel_err_mu = abs(params.mu_0_fresh - mu_0_true) / mu_0_true
    assert rel_err_mu < 0.05, f"mu_0 {params.mu_0_fresh:.3f} off from {mu_0_true} by {rel_err_mu:.1%}"
    assert abs(params.n - n_true) < 0.05, f"n {params.n:.3f} off from {n_true} by {abs(params.n - n_true):.3f}"
    assert diag["r_squared"] > 0.95


def test_stage2_preserves_nominal_semi_constrained():
    mu, p = _synthetic_friction_data(1.8, 0.8, 1.5e5, n_samples=100)
    params, _ = fit_stage2(mu, p)
    assert params.c_py == 1.0e8
    assert params.K_rad == 250_000.0


def test_stage2_rejects_nonpositive_samples():
    with pytest.raises(ValueError, match="strictly positive"):
        fit_stage2(np.array([1.5, -0.1] + [1.8] * 10), np.array([1.5e5] * 12))


def test_stage2_rejects_too_few_samples():
    mu, p = _synthetic_friction_data(1.8, 0.8, 1.5e5, n_samples=8)
    with pytest.raises(ValueError, match="at least 10"):
        fit_stage2(mu, p)


def test_stage2_rejects_shape_mismatch():
    with pytest.raises(ValueError, match="shape mismatch"):
        fit_stage2(np.ones(50), np.ones(40))


def test_stage2_p_bar_0_is_median_of_samples():
    mu, p = _synthetic_friction_data(1.8, 0.8, 1.5e5, n_samples=100, seed=7)
    params, _ = fit_stage2(mu, p)
    # p_bar_0 equals the median of the input pressure samples
    assert params.p_bar_0 == pytest.approx(float(np.median(p)))
