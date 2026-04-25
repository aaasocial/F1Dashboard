"""Criterion 2 — <200 ms forward simulation on canonical fixture.

Two tiers per RESEARCH.md Pitfall 7:
  - `physics_pipeline_dev_laptop`: <200 ms (runs locally; M1/Ryzen baseline)
  - `physics_pipeline_ci`:         <600 ms (shared GitHub Actions runners)

CI runs only the `physics_pipeline_ci` group via .github/workflows/benchmark.yml
to avoid flaky dev-threshold failures on low-spec hardware.
"""
from __future__ import annotations

import numpy as np
import pytest

from f1_core.physics.defaults import make_nominal_params
from f1_core.physics.orchestrator import run_simulation

pytestmark = [pytest.mark.benchmark]


@pytest.mark.benchmark(group="physics_pipeline_dev_laptop", min_rounds=5)
def test_full_stint_under_200ms_dev_laptop(benchmark, canonical_stint_artifact):
    """<200 ms budget for developer laptop (Criterion 2 authoritative threshold)."""
    params = make_nominal_params()
    result = benchmark(run_simulation, canonical_stint_artifact, params)
    # Sanity: the pipeline produced valid output
    assert len(result.per_lap) > 0
    assert np.all(np.isfinite(result.mu_0))
    # Hard wall-clock assertion (only when benchmark.stats is available;
    # skipped when run under --benchmark-disable which sets stats=None)
    if benchmark.stats is not None:
        mean_s = benchmark.stats["mean"]
        assert mean_s < 0.200, (
            f"Full stint simulation took {mean_s * 1000:.1f} ms; budget is 200 ms "
            f"(see Pitfall 7 for why CI has a relaxed threshold)."
        )


@pytest.mark.benchmark(group="physics_pipeline_ci", min_rounds=5)
def test_full_stint_under_600ms_ci(benchmark, canonical_stint_artifact):
    """Relaxed CI threshold per RESEARCH.md Pitfall 7 (shared runner variance)."""
    params = make_nominal_params()
    result = benchmark(run_simulation, canonical_stint_artifact, params)
    assert len(result.per_lap) > 0
    if benchmark.stats is not None:
        mean_s = benchmark.stats["mean"]
        assert mean_s < 0.600, (
            f"CI simulation took {mean_s * 1000:.1f} ms; CI budget is 600 ms. "
            f"If this consistently fails, consider pytest-codspeed (Pitfall 7)."
        )
