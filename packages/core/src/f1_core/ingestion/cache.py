"""Layer-2 cache: versioned gzip-pickle artifact store (DATA-02).

Keyed by (fastf1_version, preprocessing_version, year, round, driver_code, stint_index)
so a FastF1 or preprocessing bump auto-invalidates stale pickles (pitfall P6).

Security note (T-01-05): Pickles are WRITTEN by our code at paths we control
(under F1_CACHE_DIR). Never load a pickle from a user-supplied path.
"""

from __future__ import annotations

import gzip
import os
import pickle
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fastf1
import pandas as pd

# Bump when ingestion logic changes (new columns, different dtype, etc.).
PREPROCESSING_VERSION = "v1"


@dataclass(frozen=True)
class StintKey:
    """Unique key for a stint artifact in the Layer-2 cache."""

    year: int
    round: int  # 1-indexed round within the season
    driver_code: str  # 3-letter, e.g. "VER"
    stint_index: int  # 1-indexed

    def filename(self) -> str:
        fastf1_ver = fastf1.__version__
        return (
            f"{self.year}_{self.round:02d}_{self.driver_code}_stint{self.stint_index}"
            f"__ff1-{fastf1_ver}__prep-{PREPROCESSING_VERSION}.pkl.gz"
        )

    def path(self, root: Path) -> Path:
        return root / "stints" / self.filename()


@dataclass
class StintArtifact:
    """What we store in Layer-2. Plain-data, FastF1-version-agnostic."""

    key: StintKey
    car_data: pd.DataFrame
    pos_data: pd.DataFrame
    laps: pd.DataFrame
    weather: pd.DataFrame
    track_status: pd.DataFrame
    race_control_messages: pd.DataFrame
    session_metadata: dict[str, Any] = field(default_factory=dict)
    fastf1_version: str = ""
    preprocessing_version: str = PREPROCESSING_VERSION


def load_or_fetch(
    key: StintKey,
    root: Path,
    fetcher: Callable[[StintKey], StintArtifact],
) -> StintArtifact:
    """Layer-2 cache. If pickle exists, unpickle; else call fetcher and write atomically."""
    p = key.path(root)
    if p.exists():
        with gzip.open(p, "rb") as f:
            artifact = pickle.load(f)
        if not isinstance(artifact, StintArtifact) or artifact.key != key:
            # Key mismatch or wrong type — stale file from older preprocessing_version,
            # a renamed file, or an OS-level rename collision. Treat as cache miss.
            artifact = fetcher(key)
            _atomic_write(artifact, p)
        return artifact
    artifact = fetcher(key)
    _atomic_write(artifact, p)
    return artifact


def _atomic_write(artifact: StintArtifact, final_path: Path) -> None:
    """Write to temp file, fsync, then os.replace — prevents partial reads (T-01-07)."""
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = final_path.with_suffix(final_path.suffix + ".tmp")
    with open(tmp, "wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb") as gz:
            pickle.dump(artifact, gz, protocol=pickle.HIGHEST_PROTOCOL)
        # fsync the underlying file descriptor before rename so that a crash between
        # close and os.replace cannot leave a valid directory entry pointing to
        # incomplete data blocks (ext4/XFS crash consistency).
        raw.flush()
        os.fsync(raw.fileno())
    os.replace(tmp, final_path)
