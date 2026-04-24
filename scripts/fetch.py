"""CLI: `uv run python scripts/fetch.py <race_id> <driver_id> [--stint N]`

Validates inputs before filesystem/network access (threat T-01-04).
Prints artifact summary to stdout; pickle is left in the Layer-2 cache for reuse.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "packages/core/src"))

from f1_core.ingestion import (
    init_cache,
    load_stint,
    parse_race_id,
    validate_driver_code,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="fetch",
        description="Fetch a FastF1 stint into the two-layer cache (DATA-01, DATA-02).",
    )
    parser.add_argument(
        "race_id",
        help="Race identifier in the form YYYY-event_slug, e.g. '2023-bahrain'.",
    )
    parser.add_argument(
        "driver_id",
        help="3-letter driver code, e.g. 'VER', 'HAM'.",
    )
    parser.add_argument(
        "--stint",
        type=int,
        default=2,
        help="1-indexed stint number (default: 2).",
    )
    args = parser.parse_args()

    # Threat T-01-04: validate both inputs BEFORE any filesystem operation.
    try:
        year, event_slug = parse_race_id(args.race_id)
        validate_driver_code(args.driver_id)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    init_cache()
    # event slug → FastF1 event name: use the slug as-is; FastF1 does fuzzy matching
    event = event_slug.replace("_", " ")

    artifact = load_stint(
        year=year,
        event=event,
        driver_code=args.driver_id,
        stint_index=args.stint,
    )

    print(
        f"OK: {artifact.session_metadata.get('event_name', event)} "
        f"{args.driver_id} stint {args.stint}: "
        f"{len(artifact.laps)} laps, {len(artifact.car_data)} telemetry samples"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
