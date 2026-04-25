"""Shared pytest fixtures for f1-core tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def temp_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point F1_CACHE_DIR at a pytest tmp_path so tests never touch repo .data/."""
    cache_dir = tmp_path / "fastf1_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("F1_CACHE_DIR", str(cache_dir))
    yield cache_dir


@pytest.fixture
def fixtures_dir() -> Path:
    """Absolute path to packages/core/tests/fixtures/."""
    return Path(__file__).parent / "fixtures"
