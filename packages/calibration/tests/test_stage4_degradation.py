"""Stage 4 tests: SBC gate, convergence, NetCDF round-trip (CALIB-04, CALIB-07)."""
from __future__ import annotations
import os
from pathlib import Path
import numpy as np
import pytest

# Mark: any test that actually samples is 'integration' (JAX compile + MCMC).
# Unit tests only verify imports / validation.


# ---------- Unit-fast tests ----------

def test_module_imports():
    import f1_calibration.stage4_degradation as m
    assert hasattr(m, "fit_stage4")
    assert hasattr(m, "build_stage4_model")
    assert hasattr(m, "persist_posterior")
    assert hasattr(m, "run_stage4_sbc")


def test_build_stage4_model_validates_compound():
    from f1_calibration.stage4_degradation import build_stage4_model
    with pytest.raises(ValueError, match=r"C\[1-5\]"):
        build_stage4_model(
            obs_lap_times=np.zeros(5),
            lap_boundary_idx=np.array([0, 10, 20, 30, 40, 50]),
            t_tread_traj=np.full((50, 4), 90.0),
            p_slide_traj=np.full((50, 4), 1000.0),
            mu_0_init=1.8,
            d_tread_init=np.full(4, 0.010),
            t_lap_ref=90.0,
            compound="X9",
        )


def test_persist_posterior_rejects_outside_workspace(tmp_path):
    """T-3-03: NetCDF write path must fail on paths outside workspace root."""
    from f1_calibration.stage4_degradation import persist_posterior
    import arviz as az
    # Create a minimal InferenceData stub — error must fire before write
    idata = az.InferenceData()
    outside = tmp_path / "evil"
    with pytest.raises(ValueError, match="outside workspace"):
        persist_posterior(idata, "C3", posteriors_dir=outside)


# ---------- Integration tests (require JAX + PyMC compile) ----------

def _detect_sampler() -> str:
    """Return 'numpyro' if available, else 'pymc' as fallback for tests."""
    try:
        import numpyro  # noqa: F401
        return "numpyro"
    except ImportError:
        return "pymc"


@pytest.mark.integration
def test_fit_stage4_smoke(initialized_db):
    """Run a small MCMC on synthetic data; assert r-hat and ESS meet relaxed smoke thresholds."""
    from f1_calibration.stage4_degradation import fit_stage4
    from f1_calibration.jax_model import simulate_mu_0

    # Ground truth theta*
    beta_true, T_act_true, k_wear_true = 1.5e-6, 25.0, 8e-13
    n_steps, n_laps = 60, 6
    boundaries = np.linspace(0, n_steps, n_laps + 1, dtype=np.int64)
    t_tread_traj = np.full((n_steps, 4), 95.0, dtype=np.float64)
    p_slide_traj = np.full((n_steps, 4), 2000.0, dtype=np.float64)
    mu_0_init = 1.8
    d_tread_init = np.full(4, 0.010, dtype=np.float64)
    t_lap_ref = 90.0

    mu_traj = np.asarray(simulate_mu_0(
        beta_true, T_act_true, k_wear_true,
        t_tread_traj=t_tread_traj, p_slide_traj=p_slide_traj,
        mu_0_init=mu_0_init, d_tread_init=d_tread_init,
    ))
    mu_end = mu_traj[boundaries[1:] - 1]
    pred = t_lap_ref + 0.5 * t_lap_ref * (mu_0_init - mu_end) / mu_0_init
    rng = np.random.default_rng(7)
    obs_lap_times = pred + rng.normal(0, 0.15, pred.shape)

    fixed = {
        "t_tread_traj": t_tread_traj,
        "p_slide_traj": p_slide_traj,
        "mu_0_init": mu_0_init,
        "d_tread_init": d_tread_init,
    }
    sampler = _detect_sampler()
    idata, param_set_id = fit_stage4(
        compound="C3",
        fixed_trajectories=fixed,
        obs_lap_times=obs_lap_times,
        lap_boundary_idx=boundaries,
        t_lap_ref=t_lap_ref,
        db_conn=initialized_db,
        chains=2,
        draws=500,
        tune=500,
        target_accept=0.85,
        random_seed=11,
        skip_sbc=True,
        nuts_sampler=sampler,
    )
    # Relaxed smoke-test thresholds (full pipeline enforces 1.01 / 400)
    import arviz as az
    summ = az.summary(idata, var_names=["beta_therm", "T_act", "k_wear"])
    assert summ["r_hat"].max() < 1.05
    assert summ["ess_bulk"].min() > 200
    assert param_set_id >= 1


@pytest.mark.integration
def test_netcdf_roundtrip():
    """CALIB-07: posterior.to_netcdf + az.from_netcdf preserves values."""
    from f1_calibration.stage4_degradation import persist_posterior, build_stage4_model
    import arviz as az
    import pymc as pm

    # Quick tiny model -> run a minimal sample -> persist -> reload
    n_steps, n_laps = 40, 4
    boundaries = np.linspace(0, n_steps, n_laps + 1, dtype=np.int64)
    t_tread_traj = np.full((n_steps, 4), 90.0, dtype=np.float64)
    p_slide_traj = np.full((n_steps, 4), 1500.0, dtype=np.float64)
    obs = np.array([90.0, 90.2, 90.5, 90.9], dtype=np.float64)
    model = build_stage4_model(
        obs_lap_times=obs,
        lap_boundary_idx=boundaries,
        t_tread_traj=t_tread_traj,
        p_slide_traj=p_slide_traj,
        mu_0_init=1.8,
        d_tread_init=np.full(4, 0.010),
        t_lap_ref=90.0,
        compound="C3",
    )
    sampler = _detect_sampler()
    with model:
        idata = pm.sample(
            draws=200,
            tune=200,
            chains=2,
            nuts_sampler=sampler,
            target_accept=0.80,
            random_seed=3,
            progressbar=False,
            idata_kwargs={"log_likelihood": False},
        )

    # Write to .data/posteriors (gitignored)
    from f1_calibration.common import DEFAULT_POSTERIORS_DIR
    path = persist_posterior(idata, "C3", posteriors_dir=DEFAULT_POSTERIORS_DIR)
    try:
        assert path.exists()
        reloaded = az.from_netcdf(str(path))
        # Compare posterior arrays exactly
        beta_orig = idata.posterior["beta_therm"].values
        beta_reloaded = reloaded.posterior["beta_therm"].values
        assert np.allclose(beta_orig, beta_reloaded, atol=1e-8)
    finally:
        # Clean up the test artifact
        try:
            path.unlink()
        except Exception:
            pass


@pytest.mark.integration
def test_stage4_refuses_on_sbc_failure(initialized_db, monkeypatch):
    """Pre-flight gate: if SBC uniformity fails, fit_stage4 must raise RuntimeError."""
    from f1_calibration import stage4_degradation
    from f1_calibration.sbc import SBCResult

    fake = SBCResult(
        ranks=np.zeros((10, 3), dtype=np.int64),
        param_names=["beta_therm", "T_act", "k_wear"],
        ks_p_value={"beta_therm": 0.0, "T_act": 0.0, "k_wear": 0.0},
        uniformity_ok=False,
    )
    monkeypatch.setattr(stage4_degradation, "run_stage4_sbc", lambda compound, **kw: fake)

    with pytest.raises(RuntimeError, match="SBC pre-flight failed"):
        stage4_degradation.fit_stage4(
            compound="C3",
            fixed_trajectories={
                "t_tread_traj": np.full((40, 4), 90.0),
                "p_slide_traj": np.full((40, 4), 1500.0),
                "mu_0_init": 1.8,
                "d_tread_init": np.full(4, 0.010),
            },
            obs_lap_times=np.array([90.0, 90.1, 90.2, 90.4]),
            lap_boundary_idx=np.array([0, 10, 20, 30, 40], dtype=np.int64),
            t_lap_ref=90.0,
            db_conn=initialized_db,
            skip_sbc=False,
        )
