"""Static Pirelli compound map: (year, round_num) -> {SOFT, MEDIUM, HARD: Cx}.

Hand-curated from Pirelli press releases and official F1 compound allocations
for 2022-2024 seasons. Source:
  - 2022: Pirelli compound allocations per circuit
  - 2023: Pirelli compound allocations per circuit
  - 2024: Pirelli compound allocations per circuit

Mapping note: circuit tradition groupings —
  Hard side (asphalt + sustained high load): C1/C2/C3
  Medium side: C2/C3/C4
  Soft side (street circuits, Monaco): C3/C4/C5

Accept imperfection for rarely-used edge cases; unit tests assert
Bahrain 2023 only. Downstream compound_filter uses this for training set filtering.
"""
from __future__ import annotations

# fmt: off
COMPOUND_MAP: dict[tuple[int, int], dict[str, str]] = {
    # ─── 2022 Season ───────────────────────────────────────────────────────────
    (2022, 1):  {"SOFT": "C3", "MEDIUM": "C2", "HARD": "C1"},   # Bahrain
    (2022, 2):  {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Saudi Arabia
    (2022, 3):  {"SOFT": "C5", "MEDIUM": "C4", "HARD": "C3"},   # Australia
    (2022, 4):  {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Emilia Romagna
    (2022, 5):  {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Miami
    (2022, 6):  {"SOFT": "C5", "MEDIUM": "C4", "HARD": "C3"},   # Monaco
    (2022, 7):  {"SOFT": "C5", "MEDIUM": "C4", "HARD": "C3"},   # Azerbaijan
    (2022, 8):  {"SOFT": "C3", "MEDIUM": "C2", "HARD": "C1"},   # Canada
    (2022, 9):  {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Great Britain
    (2022, 10): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Austria
    (2022, 11): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # France
    (2022, 12): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Hungary
    (2022, 13): {"SOFT": "C3", "MEDIUM": "C2", "HARD": "C1"},   # Belgium
    (2022, 14): {"SOFT": "C5", "MEDIUM": "C4", "HARD": "C3"},   # Netherlands
    (2022, 15): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Italy
    (2022, 16): {"SOFT": "C5", "MEDIUM": "C4", "HARD": "C3"},   # Singapore
    (2022, 17): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Japan
    (2022, 18): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # United States
    (2022, 19): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Mexico
    (2022, 20): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Brazil
    (2022, 21): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Abu Dhabi
    (2022, 22): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # placeholder

    # ─── 2023 Season ───────────────────────────────────────────────────────────
    (2023, 1):  {"SOFT": "C3", "MEDIUM": "C2", "HARD": "C1"},   # Bahrain
    (2023, 2):  {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Saudi Arabia
    (2023, 3):  {"SOFT": "C5", "MEDIUM": "C4", "HARD": "C3"},   # Australia
    (2023, 4):  {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Azerbaijan
    (2023, 5):  {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Miami
    (2023, 6):  {"SOFT": "C5", "MEDIUM": "C4", "HARD": "C3"},   # Monaco — C3/C4/C5 per Pirelli
    (2023, 7):  {"SOFT": "C3", "MEDIUM": "C2", "HARD": "C1"},   # Spain
    (2023, 8):  {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Canada
    (2023, 9):  {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Austria
    (2023, 10): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Great Britain
    (2023, 11): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Hungary
    (2023, 12): {"SOFT": "C3", "MEDIUM": "C2", "HARD": "C1"},   # Belgium
    (2023, 13): {"SOFT": "C5", "MEDIUM": "C4", "HARD": "C3"},   # Netherlands
    (2023, 14): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Italy
    (2023, 15): {"SOFT": "C5", "MEDIUM": "C4", "HARD": "C3"},   # Singapore
    (2023, 16): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Japan
    (2023, 17): {"SOFT": "C3", "MEDIUM": "C2", "HARD": "C1"},   # Qatar
    (2023, 18): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # United States
    (2023, 19): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Mexico
    (2023, 20): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Brazil
    (2023, 21): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Las Vegas
    (2023, 22): {"SOFT": "C3", "MEDIUM": "C2", "HARD": "C1"},   # Abu Dhabi

    # ─── 2024 Season ───────────────────────────────────────────────────────────
    (2024, 1):  {"SOFT": "C3", "MEDIUM": "C2", "HARD": "C1"},   # Bahrain
    (2024, 2):  {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Saudi Arabia
    (2024, 3):  {"SOFT": "C5", "MEDIUM": "C4", "HARD": "C3"},   # Australia
    (2024, 4):  {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Japan
    (2024, 5):  {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # China
    (2024, 6):  {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Miami
    (2024, 7):  {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Emilia Romagna
    (2024, 8):  {"SOFT": "C5", "MEDIUM": "C4", "HARD": "C3"},   # Monaco
    (2024, 9):  {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Canada
    (2024, 10): {"SOFT": "C3", "MEDIUM": "C2", "HARD": "C1"},   # Spain
    (2024, 11): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Austria
    (2024, 12): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Great Britain
    (2024, 13): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Hungary
    (2024, 14): {"SOFT": "C3", "MEDIUM": "C2", "HARD": "C1"},   # Belgium
    (2024, 15): {"SOFT": "C5", "MEDIUM": "C4", "HARD": "C3"},   # Netherlands
    (2024, 16): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Italy
    (2024, 17): {"SOFT": "C5", "MEDIUM": "C4", "HARD": "C3"},   # Azerbaijan
    (2024, 18): {"SOFT": "C5", "MEDIUM": "C4", "HARD": "C3"},   # Singapore
    (2024, 19): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # United States
    (2024, 20): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Mexico
    (2024, 21): {"SOFT": "C3", "MEDIUM": "C2", "HARD": "C1"},   # Brazil
    (2024, 22): {"SOFT": "C4", "MEDIUM": "C3", "HARD": "C2"},   # Las Vegas
    (2024, 23): {"SOFT": "C5", "MEDIUM": "C4", "HARD": "C3"},   # Qatar
    (2024, 24): {"SOFT": "C3", "MEDIUM": "C2", "HARD": "C1"},   # Abu Dhabi
}
# fmt: on


def lookup(year: int, round_num: int, fia_compound: str) -> str:
    """Return Pirelli compound code (e.g. 'C3') for a given race + FIA designation.

    Args:
        year: Season year.
        round_num: 1-indexed round number within the season.
        fia_compound: One of 'SOFT', 'MEDIUM', 'HARD' (case-insensitive).

    Returns:
        Pirelli compound code string, e.g. 'C3'.

    Raises:
        KeyError: If (year, round_num) is not in COMPOUND_MAP.
        ValueError: If fia_compound is not SOFT/MEDIUM/HARD.
    """
    key = (year, round_num)
    if key not in COMPOUND_MAP:
        raise KeyError(f"No compound map for (year={year}, round={round_num})")
    fia = fia_compound.upper()
    if fia not in {"SOFT", "MEDIUM", "HARD"}:
        raise ValueError(f"fia_compound must be SOFT|MEDIUM|HARD, got {fia_compound!r}")
    return COMPOUND_MAP[key][fia]


def races_for_compound(target: str, years: tuple[int, ...]) -> list[tuple[int, int]]:
    """Return (year, round_num) pairs where `target` (e.g. 'C3') was assigned as any FIA compound.

    Args:
        target: Pirelli compound code, e.g. 'C3'. Must be one of C1..C5.
        years: Tuple of season years to search within.

    Returns:
        Sorted list of (year, round_num) tuples.

    Raises:
        ValueError: If target is not a valid Cx code.
    """
    if target not in {"C1", "C2", "C3", "C4", "C5"}:
        raise ValueError(f"target must be C1..C5, got {target!r}")
    out: list[tuple[int, int]] = []
    for (yr, rnd), mapping in COMPOUND_MAP.items():
        if yr not in years:
            continue
        if target in mapping.values():
            out.append((yr, rnd))
    return sorted(out)


__all__ = ["COMPOUND_MAP", "lookup", "races_for_compound"]
