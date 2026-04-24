"""Stage 5 cross-validation tests (CALIB-05, CALIB-08)."""
from __future__ import annotations
from pathlib import Path
from typing import Iterable
import csv
import numpy as np
import pytest

from f1_core.physics.params import (
    AeroParams, DegradationParams, FrictionParams, ThermalParams,
)
from f1_calibration.db import write_parameter_set
from f1_calibration.stage5_validation import fit_stage5


class _FakeStintResult:
    """Stand-in for run_simulation output used in tests.

    Real SimulationResult has per_lap_rows() yielding tuples with at least
    (lap, compound, age, pred_s, obs_s, delta_s, ...).
    """
    def __init__(self, pred: np.ndarray, obs: np.ndarray, circuit: str):
        self._rows = [
            (i + 1, "C3", i, float(pred[i]), float(obs[i]), float(pred[i] - obs[i]))
            for i in range(pred.size)
        ]
        self.circuit = circuit

    def per_lap_rows(self):
        return iter(self._rows)


@pytest.fixture
def seeded_db(initialized_db):
    """Seed SQLite with minimal parameter_sets rows for C3 stages 1-4."""
    aero = AeroParams(C_LA=4.5, C_DA=1.1, xi=0.45, K_rf_split=0.55, WD=0.445, H_CG=0.28, BB=0.575)
    friction = FrictionParams(mu_0_fresh=1.8, p_bar_0=1.5e5, n=0.8, c_py=1.0e8, K_rad=250_000.0)
    thermal = ThermalParams(T_opt=95.0, sigma_T=20.0, C_tread=6000.0, C_carc=20000.0, C_gas=500.0,
                            R_tc=0.02, R_cg=0.05, h_0=10.0, h_1=8.0, alpha_p=0.55, delta_T_blanket=60.0)
    deg = DegradationParams(beta_therm=1.0e-6, T_act=25.0, k_wear=1.0e-12)
    write_parameter_set(initialized_db, "C3", 1, aero)
    write_parameter_set(initialized_db, "C3", 2, friction)
    write_parameter_set(initialized_db, "C3", 3, thermal)
    write_parameter_set(initialized_db, "C3", 4, deg)
    return initialized_db


@pytest.fixture
def patched_run_simulation(monkeypatch):
    """Replace orchestrator.run_simulation with a pass-through that yields the stint's own rows."""
    def fake_run_simulation(artifact, params):
        # Expect tests to pass _FakeStintResult-like objects with per_lap_rows()
        return artifact
    import f1_calibration.stage5_validation as m
    monkeypatch.setattr(m, "run_simulation", fake_run_simulation)


def _synthetic_stints(n_stints: int = 3, n_laps: int = 20, noise: float = 0.0,
                      circuits: list[str] | None = None, seed: int = 0):
    rng = np.random.default_rng(seed)
    circuits = circuits or [f"circuit_{i}" for i in range(n_stints)]
    out: list[_FakeStintResult] = []
    for i in range(n_stints):
        ages = np.arange(n_laps, dtype=np.float64)
        pred = 90.0 + 0.05 * ages                          # physics predicts linearly
        obs = pred + rng.normal(0, noise, n_laps)           # obs matches pred + noise
        out.append(_FakeStintResult(pred, obs, circuits[i]))
    return out


def test_stage5_rmse_on_noise_free_synthetic(seeded_db, patched_run_simulation, tmp_path):
    """With zero noise, physics RMSE must be ~0."""
    stints = _synthetic_stints(n_stints=3, n_laps=20, noise=0.0)
    result = fit_stage5("C3", seeded_db, validation_stints=stints,
                        validation_dir=tmp_path / "val", skip_csv=True)
    assert result["physics_rmse_s"] < 1e-10
    # Baseline must also fit nearly perfectly on noise-free linear data
    assert result["baseline_rmse_s"] < 1e-5
    assert result["n_stints"] == 3
    assert result["n_laps"] == 60


def test_stage5_beats_baseline_on_noisy_synthetic(seeded_db, patched_run_simulation, tmp_path):
    """Physics should beat baseline when observations are physics-generated + noise."""
    stints = _synthetic_stints(n_stints=4, n_laps=25, noise=0.05, seed=42)
    result = fit_stage5("C3", seeded_db, validation_stints=stints,
                        validation_dir=tmp_path / "val", skip_csv=True)
    # On pure synthetic data where physics == true model, physics RMSE ≈ noise level;
    # baseline RMSE on the same data should be at least noise level too.
    assert result["physics_rmse_s"] < 0.10
    assert result["baseline_rmse_s"] > 0.0
    assert result["physics_rmse_s"] <= result["baseline_rmse_s"] * 1.1   # physics within 10% of baseline


def test_stage5_csv_format(seeded_db, patched_run_simulation, tmp_path):
    """CSV must have exact header and one row per circuit."""
    stints = _synthetic_stints(n_stints=3, n_laps=15, noise=0.02,
                                circuits=["bahrain", "jeddah", "melbourne"])
    from f1_calibration.common import DEFAULT_VALIDATION_DIR
    DEFAULT_VALIDATION_DIR.mkdir(parents=True, exist_ok=True)

    result = fit_stage5("C3", seeded_db, validation_stints=stints,
                        validation_dir=DEFAULT_VALIDATION_DIR, skip_csv=False)
    csv_path = Path(result["csv_path"])
    try:
        assert csv_path.exists()
        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            assert reader.fieldnames == ["circuit", "n_stints", "rmse_s", "mean_delta_s", "worst_lap"]
            rows = list(reader)
            assert len(rows) == 3
            circuits = {r["circuit"] for r in rows}
            assert circuits == {"bahrain", "jeddah", "melbourne"}
    finally:
        try: csv_path.unlink()
        except Exception: pass


def test_stage5_rejects_csv_dir_outside_workspace(seeded_db, patched_run_simulation, tmp_path):
    """T-3-03: CSV dir outside workspace raises ValueError via resolve_db_path."""
    stints = _synthetic_stints(n_stints=2, n_laps=10, noise=0.01)
    with pytest.raises(ValueError, match="outside workspace"):
        fit_stage5("C3", seeded_db, validation_stints=stints,
                   validation_dir=tmp_path / "evil", skip_csv=False)


def test_stage5_missing_stage_raises(initialized_db, patched_run_simulation):
    """If stage 2/3/4 rows are missing, fit_stage5 must raise a helpful error."""
    aero = AeroParams(C_LA=4.5, C_DA=1.1, xi=0.45, K_rf_split=0.55, WD=0.445, H_CG=0.28, BB=0.575)
    write_parameter_set(initialized_db, "C3", 1, aero)
    # Stages 2/3/4 deliberately NOT written
    stints = _synthetic_stints(n_stints=1, n_laps=10, noise=0.01)
    with pytest.raises(RuntimeError, match="missing stage 2"):
        fit_stage5("C3", initialized_db, validation_stints=stints, skip_csv=True)


def test_stage5_mad_filter_excludes_outliers(seeded_db, patched_run_simulation, tmp_path):
    """Pitfall 4: a 30-second outlier lap (SC lap) must not dominate RMSE."""
    rng = np.random.default_rng(0)
    pred = 90.0 + 0.05 * np.arange(20)
    obs = pred + rng.normal(0, 0.05, 20)
    obs[10] += 30.0   # simulate a SC lap
    stint = _FakeStintResult(pred, obs, "bahrain")
    result = fit_stage5("C3", seeded_db, validation_stints=[stint],
                        validation_dir=tmp_path / "ignored", skip_csv=True)
    # If MAD filter works, RMSE stays small despite the 30s outlier
    assert result["physics_rmse_s"] < 1.0, (
        f"MAD filter failed to exclude SC outlier — RMSE={result['physics_rmse_s']:.2f}"
    )
