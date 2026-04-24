"""DATA-01 + config tests: input validation + canonical fixture loader (no network)."""

from __future__ import annotations

import gzip
import pickle
from pathlib import Path

import pytest
from f1_core.ingestion.cache import StintArtifact
from f1_core.ingestion.config import (
    parse_race_id,
    validate_driver_code,
    validate_race_id,
)


@pytest.mark.parametrize(
    "rid",
    ["2023-bahrain", "2024-monza", "2022-saudi_arabia", "2025-mexico_city"],
)
def test_validate_race_id_accepts_valid(rid: str) -> None:
    assert validate_race_id(rid) == rid


@pytest.mark.parametrize(
    "rid",
    [
        "../etc/passwd",
        "2023-../evil",
        "2023/bahrain",
        "2023-Bahrain",  # uppercase rejected
        "23-bahrain",  # 2-digit year rejected
        "2023_bahrain",  # underscore separator rejected
        "",
    ],
)
def test_validate_race_id_rejects_invalid(rid: str) -> None:
    with pytest.raises(ValueError):
        validate_race_id(rid)


@pytest.mark.parametrize("dc", ["VER", "HAM", "LEC", "NOR"])
def test_validate_driver_code_accepts_valid(dc: str) -> None:
    assert validate_driver_code(dc) == dc


@pytest.mark.parametrize("dc", ["ver", "VERS", "VE", "../", "", "ver1", "V3R"])
def test_validate_driver_code_rejects_invalid(dc: str) -> None:
    with pytest.raises(ValueError):
        validate_driver_code(dc)


def test_parse_race_id_splits_year_and_slug() -> None:
    year, slug = parse_race_id("2023-bahrain")
    assert year == 2023
    assert slug == "bahrain"


def _fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "bahrain_2023_ver_stint2.pkl.gz"


def test_fetch_canonical_fixture_smoke() -> None:
    """D-06: the committed canonical fixture is loadable and has expected shape."""
    p = _fixture_path()
    if not p.exists():
        pytest.skip(
            f"Canonical fixture not yet built at {p}. "
            "Run `uv run python scripts/build_canonical_fixture.py` once."
        )
    with gzip.open(p, "rb") as f:
        artifact = pickle.load(f)
    assert isinstance(artifact, StintArtifact)
    # Bahrain 2023 VER stint 2 is MEDIUM, laps 16-38 (~23 laps)
    assert len(artifact.laps) >= 15, f"expected ~23 laps, got {len(artifact.laps)}"
    assert len(artifact.laps) <= 30
    assert not artifact.car_data.empty, "car_data must be non-empty"
    assert artifact.key.driver_code == "VER"
    assert artifact.key.stint_index == 2
    assert artifact.key.year == 2023


def test_fetch_canonical_fixture(tmp_path: Path) -> None:
    """DATA-01: load_stint wrapper round-trip via the committed fixture + mock fetch.

    We cannot hit Jolpica in CI, so this test verifies that once the fixture is on
    disk at the cache path, load_or_fetch returns it without invoking the fetcher.
    """
    from f1_core.ingestion.cache import StintKey, load_or_fetch

    fixture = _fixture_path()
    if not fixture.exists():
        pytest.skip("Canonical fixture not yet built.")

    # Load the fixture, extract its key, write it into a cache-shaped tmp dir
    with gzip.open(fixture, "rb") as f:
        artifact = pickle.load(f)
    key = artifact.key
    dst = key.path(tmp_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(dst, "wb") as f:
        pickle.dump(artifact, f)

    called = {"n": 0}

    def should_not_be_called(k: StintKey) -> StintArtifact:
        called["n"] += 1
        raise AssertionError("fetcher should not run — cache hit expected")

    loaded = load_or_fetch(key, tmp_path, should_not_be_called)
    assert called["n"] == 0
    assert loaded.key == key
