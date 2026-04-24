"""DATA-04: per-team gear-ratio inference from steady-speed segments.

Algorithm (model_spec section A.4):
  V_wheel = 2*pi*R_0 * RPM / (60 * combined_ratio)
  => combined_ratio = 2*pi*R_0 * RPM / (60 * V_wheel)

Selects samples with Throttle >= 99 (full-throttle, steady state) and V > 50 km/h
(avoid low-speed noise). Groups by gear; takes the median combined ratio per gear.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Fixed constants per model_spec.md
R_0_M = 0.330  # tire radius [m]

# Thresholds
THROTTLE_MIN = 99.0
SPEED_MIN_KMH = 50.0
MIN_SAMPLES_PER_GEAR = 20


def infer_gear_ratios(car_data: pd.DataFrame) -> dict[int, float]:
    """Return {gear: combined_ratio} for gears with enough steady-state samples.

    combined_ratio = G_gear * G_final (the product); the caller may split it
    using a published gearbox spec, but this function returns the product only.
    """
    required = {"Speed", "RPM", "Throttle", "nGear"}
    missing = required - set(car_data.columns)
    if missing:
        raise ValueError(f"car_data missing required columns: {missing}")

    df = car_data[["Speed", "RPM", "Throttle", "nGear"]].copy()
    df = df.dropna()
    df = df[(df["Throttle"] >= THROTTLE_MIN) & (df["Speed"] > SPEED_MIN_KMH)]

    ratios: dict[int, float] = {}
    for gear, gdf in df.groupby("nGear"):
        gear_i = int(gear)
        if gear_i <= 0 or gear_i > 8:
            continue
        if len(gdf) < MIN_SAMPLES_PER_GEAR:
            continue
        v_mps = gdf["Speed"].to_numpy(dtype=float) / 3.6  # km/h -> m/s
        rpm = gdf["RPM"].to_numpy(dtype=float)
        # Guard against zero speeds
        valid = (v_mps > 0) & (rpm > 0)
        if valid.sum() < MIN_SAMPLES_PER_GEAR:
            continue
        ratio = 2.0 * np.pi * R_0_M * rpm[valid] / (60.0 * v_mps[valid])
        ratios[gear_i] = float(np.median(ratio))
    return ratios
