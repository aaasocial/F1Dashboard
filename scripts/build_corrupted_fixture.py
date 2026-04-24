"""Build packages/core/tests/fixtures/corrupted_stint.pkl.gz from the canonical fixture.

Injects: throttle=104 sentinels in 5% of rows, NaN LapTime for 3 laps, a within-stint
compound change (half the laps relabeled HARD). Used by DATA-05 negative tests.
"""

from __future__ import annotations

import gzip
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "packages/core/src"))

SRC = Path(__file__).parent.parent / "packages/core/tests/fixtures/bahrain_2023_ver_stint2.pkl.gz"
DST = Path(__file__).parent.parent / "packages/core/tests/fixtures/corrupted_stint.pkl.gz"


def main() -> int:
    if not SRC.exists():
        print(f"Source fixture missing: {SRC}", file=sys.stderr)
        return 2
    with gzip.open(SRC, "rb") as f:
        artifact = pickle.load(f)

    # Inject throttle sentinels (5% of samples)
    car = artifact.car_data.copy()
    rng = np.random.default_rng(42)
    n = len(car)
    idx = rng.choice(n, size=max(1, n // 20), replace=False)
    if "Throttle" in car.columns:
        car.loc[car.index[idx], "Throttle"] = 104
    artifact.car_data = car

    # Inject NaN LapTime in 3 laps + within-stint compound change
    laps = artifact.laps.copy()
    if len(laps) >= 3:
        laps.loc[laps.index[:3], "LapTime"] = pd.NaT

    if "Compound" in laps.columns and len(laps) > 4:
        half = len(laps) // 2
        laps.loc[laps.index[half:], "Compound"] = "HARD"
    artifact.laps = laps

    DST.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(DST, "wb") as f:
        pickle.dump(artifact, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"Wrote corrupted fixture: {DST} ({DST.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
