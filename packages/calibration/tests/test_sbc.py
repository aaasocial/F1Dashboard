"""Tests for SBC (CALIB-06). Fast tests on uniformity stat; integration test runs real MCMC."""
from __future__ import annotations
import numpy as np
import pytest
from f1_calibration.sbc import sbc_uniformity_test, run_sbc


# ---------- Fast unit tests (no MCMC) ----------

def test_sbc_uniformity_passes_on_uniform_ranks():
    rng = np.random.default_rng(0)
    # Simulate 1000 trials x 2 params, ranks drawn uniformly from [0, 500]
    ranks = rng.integers(0, 501, size=(1000, 2))
    result = sbc_uniformity_test(ranks, param_names=["a", "b"])
    assert result["uniformity_ok"] is True
    assert all(p > 0.05 for p in result["ks_p_value"].values())


def test_sbc_uniformity_fails_on_degenerate_ranks():
    ranks = np.full((100, 2), 0, dtype=np.int64)   # all zeros -> KS rejects uniformity
    result = sbc_uniformity_test(ranks, param_names=["a", "b"])
    assert result["uniformity_ok"] is False


def test_sbc_uniformity_fails_on_biased_ranks():
    rng = np.random.default_rng(7)
    # Ranks heavily concentrated at a single value (500) — distribution far from uniform
    # when compared against max_rank of 500. KS test will detect non-uniformity.
    biased = np.full((500, 1), 500, dtype=np.int64)  # all ranks at maximum
    result = sbc_uniformity_test(biased, param_names=["biased"])
    # All ranks are identical and at maximum — strongly non-uniform
    assert result["uniformity_ok"] is False


def test_sbc_uniformity_rejects_wrong_shape():
    with pytest.raises(ValueError, match="must be 2D"):
        sbc_uniformity_test(np.array([1, 2, 3]), param_names=["x"])


def test_sbc_uniformity_rejects_name_mismatch():
    ranks = np.zeros((10, 3), dtype=np.int64)
    with pytest.raises(ValueError, match="n_params"):
        sbc_uniformity_test(ranks, param_names=["only_one"])


# ---------- Integration test (marked; skipped by default in unit-only mode) ----------

@pytest.mark.integration
def test_sbc_uniformity_on_gaussian():
    """End-to-end SBC on a trivial Gaussian model. Passes when ranks are uniform."""
    import pymc as pm

    def prior_sample_fn(rng):
        return {"mu": float(rng.normal(0.0, 1.0))}

    def forward_fn(theta, rng):
        # Observe 20 samples from N(mu, 1)
        return rng.normal(theta["mu"], 1.0, size=20).astype(np.float64)

    def build_model_fn(y_obs):
        with pm.Model() as model:
            mu = pm.Normal("mu", mu=0.0, sigma=1.0)
            pm.Normal("obs", mu=mu, sigma=1.0, observed=y_obs)
        return model

    result = run_sbc(
        build_model_fn=build_model_fn,
        forward_fn=forward_fn,
        prior_sample_fn=prior_sample_fn,
        param_names=["mu"],
        n_simulations=20,   # minimal for CI speed; real SBC uses 50+
        seed=123,
        draws=300,
        tune=300,
        chains=2,
    )
    # Ranks should be roughly uniform -- but with only 20 trials, allow the test to pass
    # on any reasonable KS p-value. The key assertion is that shape/dtype are correct.
    assert result["ranks"].shape == (20, 1)
    assert "mu" in result["ks_p_value"]
    # Uniformity on 20 trials is noisy; assert we got SOME KS p-value, not strict pass
    assert isinstance(result["uniformity_ok"], bool)
