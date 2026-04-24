"""Shared fixtures for physics tests (Phase 2).

fixtures:
  - nominal_params: make_nominal_params() baseline
  - canonical_stint_artifact: 2023 Bahrain VER Stint 2 loaded from disk fixture
  - synthetic_kinematic_state: short (N=100) KinematicState with realistic numbers
"""
from __future__ import annotations

import gzip
import pickle
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest

from f1_core.contracts import KinematicState
from f1_core.ingestion.cache import StintArtifact
from f1_core.physics import PhysicsParams, make_nominal_params

FIX_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def nominal_params() -> PhysicsParams:
    return make_nominal_params()


@pytest.fixture
def canonical_stint_artifact() -> Iterator[StintArtifact]:
    """2023 Bahrain GP, VER, Stint 2 — canonical fixture pickled in Phase 1."""
    p = FIX_DIR / "bahrain_2023_ver_stint2.pkl.gz"
    if not p.exists():
        pytest.skip("canonical fixture missing — run Phase 1 fixture generation")
    with gzip.open(p, "rb") as f:
        artifact = pickle.load(f)
    yield artifact


@pytest.fixture
def synthetic_kinematic_state() -> KinematicState:
    """Hand-built (N=100) kinematic state — steady 70 m/s, κ=0, no lateral accel.

    Useful for module unit tests that need shape-compatible input without
    requiring a real fixture.
    """
    n = 100
    t = np.arange(n) * 0.25
    v = np.full(n, 70.0)
    kappa = np.zeros(n)
    return KinematicState(
        t=t,
        v=v,
        a_lat=v * v * kappa,
        a_long=np.zeros(n),
        psi=np.zeros(n),
        v_sx_rear=np.zeros(n),
        kappa=kappa,
    )
