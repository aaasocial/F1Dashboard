"""One-shot: fetch Bahrain 2023 VER stint 2 from FastF1 and commit the artifact.

Run once per maintainer; the output is committed to git at
`packages/core/tests/fixtures/bahrain_2023_ver_stint2.pkl.gz` so CI runs offline.

Per D-06, this is the canonical fixture for all 7 phases.
"""

from __future__ import annotations

import gzip
import pickle
import sys
from pathlib import Path

# Allow `uv run python scripts/build_canonical_fixture.py` without install
sys.path.insert(0, str(Path(__file__).parent.parent / "packages/core/src"))

from f1_core.ingestion import init_cache, load_stint


def main() -> int:
    init_cache()
    print("Fetching Bahrain 2023 VER stint 2 (MEDIUM, laps ~16-38)...")
    artifact = load_stint(
        year=2023,
        event="Bahrain",
        session_type="R",
        driver_code="VER",
        stint_index=2,
    )
    out = (
        Path(__file__).parent.parent / "packages/core/tests/fixtures/bahrain_2023_ver_stint2.pkl.gz"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out, "wb") as f:
        pickle.dump(artifact, f, protocol=pickle.HIGHEST_PROTOCOL)
    size_kb = out.stat().st_size / 1024
    print(f"Wrote canonical fixture: {out} ({size_kb:.1f} KB)")
    print(f"  laps: {len(artifact.laps)}")
    print(f"  car_data samples: {len(artifact.car_data)}")
    print(f"  fastf1 version: {artifact.fastf1_version}")
    print(f"  preprocessing version: {artifact.preprocessing_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
