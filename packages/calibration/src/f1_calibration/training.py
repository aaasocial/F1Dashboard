"""Training stint iterator. Wraps FastF1 load_stint across a year range.

Pull each race's drivers + stints once, apply compound filter via compound_map.
On any FastF1 load failure for a single stint, log + skip (do not abort).

Per D-04: 2022-2023 = training data; 2024 = validation holdout.
Per D-05: Stages 1-2 (compound=None) use all races; Stages 3-4 filter by compound.
"""
from __future__ import annotations
from collections.abc import Iterator

from f1_core.ingestion.cache import StintArtifact
from f1_core.ingestion.fastf1_client import load_stint
from f1_calibration.common import get_logger
from f1_calibration.compound_map import lookup, races_for_compound

_log = get_logger(__name__)

# Pragmatic subset of drivers for training iteration — avoids iterating the full
# 20-driver grid for every race, while covering both title contenders and midfield.
# Stages 1-2 are compound-agnostic so driver variance is averaged over the fleet.
_DEFAULT_DRIVERS = ("VER", "HAM", "LEC", "SAI", "RUS", "PER", "NOR", "ALO")


def iter_training_stints(
    *,
    years: tuple[int, ...],
    compound: str | None = None,
    drivers: tuple[str, ...] = _DEFAULT_DRIVERS,
    max_stint_index: int = 6,
) -> Iterator[StintArtifact]:
    """Yield StintArtifact instances for calibration training.

    If ``compound`` is None (Stages 1-2, compound-agnostic), yield all stints
    across ``years`` for the enumerated drivers.
    If ``compound`` is 'C1'..'C5' (Stages 3-4), yield only stints from races
    where that compound was assigned as SOFT, MEDIUM, or HARD.

    Stint enumeration is resilient: on any FastF1 / cache failure for a single
    stint, the error is logged at DEBUG level and the driver's remaining stints
    for that race are skipped (break). This prevents one bad race from aborting
    an entire multi-hour calibration run.

    Args:
        years: Season years to iterate (e.g. (2022, 2023) for training).
        compound: If given, filter to races where this Pirelli compound was used.
        drivers: Driver codes to iterate over per race.
        max_stint_index: Maximum stint index to attempt per driver (inclusive).

    Yields:
        StintArtifact instances (from Layer-2 cache or FastF1 network fetch).
    """
    if compound is None:
        # Stages 1-2: all rounds 1..24 for each year
        race_candidates: list[tuple[int, int]] = [
            (y, r) for y in years for r in range(1, 25)
        ]
    else:
        race_candidates = races_for_compound(compound, years)

    for year, round_num in race_candidates:
        for driver_code in drivers:
            for stint_index in range(1, max_stint_index + 1):
                try:
                    artifact = load_stint(
                        year=year,
                        event=str(round_num),
                        driver_code=driver_code,
                        stint_index=stint_index,
                    )
                except Exception as exc:  # noqa: BLE001 — iterator resilience
                    _log.debug(
                        "skip (%d, %d, %s, %d): %s",
                        year, round_num, driver_code, stint_index, exc,
                    )
                    break  # stop iterating this driver's stints for this race
                yield artifact


__all__ = ["iter_training_stints"]
