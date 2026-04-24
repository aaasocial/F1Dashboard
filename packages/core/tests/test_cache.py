"""DATA-02 tests: two-layer cache semantics (no network)."""

from __future__ import annotations

import gzip
import pickle
from pathlib import Path

import pandas as pd
import pytest
from f1_core.ingestion.cache import (
    PREPROCESSING_VERSION,
    StintArtifact,
    StintKey,
    load_or_fetch,
)


def _make_artifact(key: StintKey) -> StintArtifact:
    return StintArtifact(
        key=key,
        car_data=pd.DataFrame({"Speed": [0, 100, 200]}),
        pos_data=pd.DataFrame({"X": [0.0, 1.0], "Y": [0.0, 1.0]}),
        laps=pd.DataFrame({"LapNumber": [1, 2, 3]}),
        weather=pd.DataFrame(),
        track_status=pd.DataFrame(),
        race_control_messages=pd.DataFrame(),
        session_metadata={"event_name": "Test"},
        fastf1_version="3.8.2",
        preprocessing_version=PREPROCESSING_VERSION,
    )


def test_second_call_hits_cache(tmp_path: Path) -> None:
    key = StintKey(year=2023, round=1, driver_code="VER", stint_index=2)
    call_count = {"n": 0}

    def fetcher(k: StintKey) -> StintArtifact:
        call_count["n"] += 1
        return _make_artifact(k)

    a1 = load_or_fetch(key, tmp_path, fetcher)
    a2 = load_or_fetch(key, tmp_path, fetcher)

    assert call_count["n"] == 1, "fetcher must only be called once"
    assert a1.key == a2.key
    assert a2.car_data["Speed"].tolist() == [0, 100, 200]


def test_cache_key_includes_fastf1_version() -> None:
    import fastf1

    key = StintKey(year=2023, round=1, driver_code="VER", stint_index=2)
    fname = key.filename()
    assert fastf1.__version__ in fname
    assert f"prep-{PREPROCESSING_VERSION}" in fname
    assert "VER" in fname
    assert fname.endswith(".pkl.gz")


def test_cached_file_written_to_expected_path(tmp_path: Path) -> None:
    key = StintKey(year=2023, round=1, driver_code="VER", stint_index=2)

    def fetcher(k: StintKey) -> StintArtifact:
        return _make_artifact(k)

    load_or_fetch(key, tmp_path, fetcher)

    expected = key.path(tmp_path)
    assert expected.exists()
    # Verify it's a valid gzip pickle
    with gzip.open(expected, "rb") as f:
        artifact = pickle.load(f)
    assert isinstance(artifact, StintArtifact)


def test_atomic_write_never_leaves_partial(tmp_path: Path) -> None:
    key = StintKey(year=2023, round=1, driver_code="VER", stint_index=2)

    def bad_fetcher(k: StintKey) -> StintArtifact:
        raise RuntimeError("simulated fetch failure after partial write")

    with pytest.raises(RuntimeError):
        load_or_fetch(key, tmp_path, bad_fetcher)

    # Final path must not exist even if a tmp file was created
    assert not key.path(tmp_path).exists()
