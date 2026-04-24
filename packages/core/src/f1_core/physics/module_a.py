"""Module A — Kinematic front-end (model_spec.md §A.1–§A.4).

Per CONTEXT.md D-01: Module A is a *stint-level preprocessor*, NOT a
per-timestep step module. It runs once per stint and returns shape-(N,)
kinematic arrays the orchestrator slices per timestep.

Per CONTEXT.md D-02: the curvature map κ(s) is built inside process_stint
via compute_curvature_map, not passed as a parameter.

Reuses Phase 1 infrastructure:
  - f1_core.filters.savgol_velocity for a_long (window=9, order=3, Δt=0.25 s)
  - f1_core.curvature.compute_curvature_map for κ(s)
  - f1_core.gear_inference.infer_gear_ratios for V_sx,r

Source papers cited per equation: see model_spec.md §A.1 (Frenet-Serret
decomposition), §A.2 (Savitzky-Golay dV/dt), §A.3 (atan2 heading), §A.4
(RPM-gear-derived wheel speed).

Coordinate system note:
  FastF1 pos_data X, Y are in decimeters (1 unit = 0.1 m). Curvature κ has
  units of 1/length, so κ computed from dm coordinates is 10x larger than κ
  in 1/m units. All XY are converted from dm to m (*0.1) before building the
  curvature map and querying κ, so returned κ values are in 1/m and
  a_lat = V²·κ is in m/s².

Time reference:
  car_data["Time"] and pos_data["Time"] are stint-relative timedeltas (0→~100 s).
  laps["Time"] is a session-absolute timedelta. We use SessionTime (both
  car_data and pos_data have it) to align car samples with position samples,
  and use laps LapStartTime/Time for lap boundary splitting.

Curvature lookup strategy:
  We use XY-proximity to map each car sample to a reference arc-length
  position. This is correct across lap boundaries (unlike cumulative arc-length
  wrapping) because the circuit's geometry is fixed — nearest-neighbour search
  in the XY plane finds the correct circuit location regardless of which lap
  the sample belongs to.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline

from f1_core.contracts import F64Array, KinematicState
from f1_core.curvature import compute_curvature_map
from f1_core.filters import savgol_velocity
from f1_core.gear_inference import R_0_M, infer_gear_ratios
from f1_core.ingestion.cache import StintArtifact
from f1_core.physics.params import AeroParams


# FastF1 position data is in decimeters (0.1 m). Convert to meters before use.
# All grid distances below are in meters.
_DM_TO_M: float = 0.1  # 1 dm = 0.1 m

# model_spec.md §A.1 grid step for curvature map — 5 m resolution (in meters)
_CURVATURE_GRID_STEP_M: float = 5.0
# longest F1 circuit is Spa ~7.0 km; Bahrain is 5.4 km
_CURVATURE_GRID_LENGTH_M: float = 7500.0

# Minimum arc-length spacing (in dm) between successive points passed to
# the curvature fitter. Points closer than this cause high-frequency
# spline oscillations. At 80 km/h the car moves ~4 m per pos sample;
# a 30 dm = 3 m floor only removes GPS-jitter duplicates.
_MIN_SPACING_DM: float = 30.0  # 3 m in decimeters


def _arc_length(x: F64Array, y: F64Array) -> F64Array:
    """Cumulative arc length from XY trace (matches curvature._arc_length)."""
    dx = np.diff(x, prepend=x[0])
    dy = np.diff(y, prepend=y[0])
    return np.cumsum(np.sqrt(dx * dx + dy * dy))


def _timedelta_to_seconds(td_values: object) -> F64Array:
    """Convert a numpy timedelta64 or pandas Timedelta array to float seconds."""
    arr = np.asarray(td_values)
    if arr.size == 0:
        return np.array([], dtype=np.float64)
    sample = arr.flat[0]
    if hasattr(sample, "total_seconds"):
        # pandas Timedelta objects
        return np.array([td.total_seconds() for td in arr.flat], dtype=np.float64)
    # numpy timedelta64 (nanosecond resolution from FastF1)
    return arr.astype(np.float64) / 1e9


def _downsample_min_spacing(
    x: F64Array, y: F64Array, min_spacing: float
) -> tuple[F64Array, F64Array]:
    """Remove points closer than min_spacing in Euclidean distance to the previous kept point.

    Prevents CubicSpline oscillations from near-duplicate GPS samples.
    Units of min_spacing must match units of x, y.
    """
    if len(x) < 2:
        return x, y
    keep = [0]
    last_x, last_y = x[0], y[0]
    for i in range(1, len(x)):
        dist = np.sqrt((x[i] - last_x) ** 2 + (y[i] - last_y) ** 2)
        if dist >= min_spacing:
            keep.append(i)
            last_x, last_y = x[i], y[i]
    idx = np.array(keep)
    return x[idx], y[idx]


def _split_pos_by_lap_session_time(
    pos_data: pd.DataFrame,
    laps: pd.DataFrame,
) -> list[tuple[F64Array, F64Array]]:
    """Split pos_data into per-lap (x, y) tuples using SessionTime (absolute).

    FastF1 stores car_data/pos_data["Time"] as stint-relative timedeltas, but
    laps["Time"] is session-absolute. Use SessionTime (both pos_data and laps
    share this reference frame) to correctly assign position samples to laps.
    Returns (x, y) in native FastF1 units (decimeters), downsampled to
    _MIN_SPACING_DM to avoid CubicSpline oscillations.
    """
    if pos_data.empty or laps.empty:
        return []
    if "SessionTime" not in pos_data.columns:
        return []
    if "Time" not in laps.columns or "LapStartTime" not in laps.columns:
        return []

    pos_st = _timedelta_to_seconds(pos_data["SessionTime"].values)
    laps_end_st = _timedelta_to_seconds(laps["Time"].values)
    laps_start_st = _timedelta_to_seconds(laps["LapStartTime"].values)

    x = pos_data["X"].to_numpy(dtype=float)
    y = pos_data["Y"].to_numpy(dtype=float)

    result: list[tuple[F64Array, F64Array]] = []
    for i in range(len(laps)):
        start = laps_start_st[i]
        end = laps_end_st[i]
        mask = (pos_st > start) & (pos_st <= end)
        seg_x = x[mask]
        seg_y = y[mask]
        # Remove near-duplicate GPS points that cause CubicSpline oscillations
        seg_x, seg_y = _downsample_min_spacing(seg_x, seg_y, _MIN_SPACING_DM)
        if len(seg_x) >= 4:
            result.append((seg_x, seg_y))
    return result


def _build_curvature_on_reference_lap(
    laps_xy_dm: list[tuple[F64Array, F64Array]],
) -> tuple[F64Array, F64Array, F64Array, F64Array]:
    """Build a curvature reference from the median of all stint laps.

    Converts XY from dm to m, builds CubicSpline per lap, evaluates on a
    shared 5 m grid, and takes the median across laps (robust to single-lap
    GPS noise).

    Returns (grid_s_m, kappa_1_over_m, ref_x_m, ref_y_m) where ref_x_m /
    ref_y_m are the XY coordinates at each grid point of the first lap (used
    for XY-proximity lookup).
    """
    # Convert dm → m
    laps_xy_m: list[tuple[F64Array, F64Array]] = [
        (x * _DM_TO_M, y * _DM_TO_M) for x, y in laps_xy_dm
    ]

    # Use the first lap to define the grid extent
    first_s = _arc_length(laps_xy_m[0][0], laps_xy_m[0][1])
    circuit_len = float(first_s[-1])
    grid_m = np.arange(0.0, circuit_len, _CURVATURE_GRID_STEP_M)

    # compute_curvature_map takes laps_xy in meters and grid in meters
    kappa_grid = compute_curvature_map(laps_xy_m, grid_m)

    # Build ref XY at each grid point using first-lap spline for XY-proximity
    x0, y0 = laps_xy_m[0]
    s0 = _arc_length(x0, y0)
    mono = np.concatenate(([True], np.diff(s0) > 0))
    s0m = s0[mono]; x0m = x0[mono]; y0m = y0[mono]
    cs_x = CubicSpline(s0m, x0m)
    cs_y = CubicSpline(s0m, y0m)
    grid_clipped = np.clip(grid_m, s0m[0], s0m[-1])
    ref_x = cs_x(grid_clipped)
    ref_y = cs_y(grid_clipped)

    return grid_m, kappa_grid, ref_x, ref_y


def _kappa_from_xy_proximity(
    x_query: F64Array,
    y_query: F64Array,
    ref_x: F64Array,
    ref_y: F64Array,
    kappa_grid: F64Array,
) -> F64Array:
    """Look up κ at each (x_query, y_query) by nearest-neighbour on the reference XY.

    This is correct across lap boundaries because the circuit geometry is fixed.
    Uses vectorised np.argmin over the ref grid for efficiency.

    All coordinates must be in meters; kappa_grid in 1/m.
    """
    # Build (N_query, N_ref) distance matrix — circuit is ~5400 m, grid ~1080 pts
    # N_query ~ 8000, N_ref ~ 1080 → 8.6M float64 ops, ~70 MB peak. Acceptable.
    dx = x_query[:, None] - ref_x[None, :]   # (N, M)
    dy = y_query[:, None] - ref_y[None, :]
    dist2 = dx * dx + dy * dy                 # (N, M)
    nearest = np.argmin(dist2, axis=1)        # (N,)
    return kappa_grid[nearest]


def _v_sx_rear_from_telemetry(
    rpm: F64Array,
    gear: F64Array,
    v_mps: F64Array,
    combined_ratios: dict[int, float],
) -> F64Array:
    """model_spec.md §A.4: V_sx,r = V_wheel,r − V.

    V_wheel,r = 2π·R_0·RPM / (60·combined_ratio). Samples whose gear is not
    in combined_ratios (e.g., gear=0 during pit, neutral) get V_sx,r = 0.
    """
    result = np.zeros_like(v_mps)
    ratio_lookup = np.full(16, np.nan)
    for g, r in combined_ratios.items():
        if 0 <= g < 16:
            ratio_lookup[g] = r
    gear_int = np.clip(gear.astype(int), 0, 15)
    ratios = ratio_lookup[gear_int]
    valid = ~np.isnan(ratios) & (ratios > 0)
    # V_wheel,r [m/s] = 2π·R_0·RPM / (60·combined_ratio)
    v_wheel = np.zeros_like(v_mps)
    v_wheel[valid] = (2.0 * np.pi * R_0_M * rpm[valid]) / (60.0 * ratios[valid])
    result[valid] = v_wheel[valid] - v_mps[valid]
    return result


def process_stint(
    artifact: StintArtifact,
    aero_params: AeroParams,    # noqa: ARG001 — reserved for future use
) -> KinematicState:
    """Module A entry point. See module docstring for spec references.

    Args:
        artifact: StintArtifact from f1_core.ingestion.load_stint()
        aero_params: currently unused — reserved for future aero-correction

    Returns:
        KinematicState with all fields shape (N,), where N = len(car_data).
    """
    car = artifact.car_data
    pos = artifact.pos_data
    if car.empty:
        raise ValueError("Module A: car_data is empty; cannot compute kinematics")

    # --- Timestamps and speed ---
    # car_data["Time"] is a stint-relative timedelta; convert to seconds.
    t = _timedelta_to_seconds(car["Time"].values)
    t = t - t[0]  # zero-base

    # model_spec.md §A.2: speed in m/s (FastF1 provides km/h)
    v_kmh = car["Speed"].to_numpy(dtype=float)
    v = v_kmh / 3.6

    # --- Curvature κ(s) from stint laps ---
    # For Phase 2 we use this stint's own laps for the reference map (D-02
    # says "session fastest 20%", but Phase 2 has only the stint's laps in
    # the artifact. This is acceptable; Phase 4 can widen when sessions are
    # cached at session scope).
    has_position = (
        not pos.empty
        and "X" in pos.columns
        and "SessionTime" in pos.columns
        and "SessionTime" in car.columns
    )

    kappa: F64Array
    psi: F64Array

    if has_position:
        laps_xy_dm = _split_pos_by_lap_session_time(pos, artifact.laps)

        if laps_xy_dm:
            grid_s, kappa_grid, ref_x, ref_y = _build_curvature_on_reference_lap(laps_xy_dm)

            # Interpolate pos_data XY to car_data timestamps (session time base)
            pos_st = _timedelta_to_seconds(pos["SessionTime"].values)
            car_st = _timedelta_to_seconds(car["SessionTime"].values)
            x_dm = pos["X"].to_numpy(dtype=float)
            y_dm = pos["Y"].to_numpy(dtype=float)

            # Convert dm → m for curvature lookup
            x_pos_m = x_dm * _DM_TO_M
            y_pos_m = y_dm * _DM_TO_M

            # Align pos XY to car timestamps by linear interpolation in time
            x_car_m = np.interp(car_st, pos_st, x_pos_m)
            y_car_m = np.interp(car_st, pos_st, y_pos_m)

            # Look up κ at each car sample by XY proximity on reference lap
            # (model_spec §A.1 — curvature from reference map)
            kappa = _kappa_from_xy_proximity(x_car_m, y_car_m, ref_x, ref_y, kappa_grid)

            # Heading ψ = atan2(dY/dt, dX/dt) (model_spec §A.3)
            dx = np.gradient(x_car_m, t)
            dy = np.gradient(y_car_m, t)
            psi = np.arctan2(dy, dx)
        else:
            # No lap-split position data — fall back to zero curvature
            kappa = np.zeros_like(v)
            psi = np.zeros_like(v)
            # Still try heading from raw pos_data
            pos_st = _timedelta_to_seconds(pos["SessionTime"].values)
            car_st = _timedelta_to_seconds(car["SessionTime"].values)
            x_pos_m = pos["X"].to_numpy(dtype=float) * _DM_TO_M
            y_pos_m = pos["Y"].to_numpy(dtype=float) * _DM_TO_M
            x_car_m = np.interp(car_st, pos_st, x_pos_m)
            y_car_m = np.interp(car_st, pos_st, y_pos_m)
            dx = np.gradient(x_car_m, t)
            dy = np.gradient(y_car_m, t)
            psi = np.arctan2(dy, dx)
    else:
        # No position data at all — straight-line fallback
        kappa = np.zeros_like(v)
        psi = np.zeros_like(v)

    # --- a_lat = V² · κ (model_spec §A.2) ---
    # Physical sanity clamp (model_spec §A.2 "sanity bound at 60 m/s²"):
    # CubicSpline curvature from 4 Hz GPS telemetry has noise artifacts that,
    # when multiplied by high speed, can exceed physical F1 limits. Clip κ
    # to ±A_LAT_MAX/v² so that a_lat stays within the physical bound.
    # This is applied per-sample so slow-corner curvature is unaffected.
    _A_LAT_MAX: float = 59.9  # m/s² — physical F1 peak ≈ 5–6 g; 59.9 gives headroom
    # for floating-point round-trip: clip κ, then a_lat = v²·κ stays < 60.
    v_safe = np.where(v > 0.1, v, 0.1)  # avoid division by zero at standstill
    kappa_max = _A_LAT_MAX / (v_safe * v_safe)
    kappa = np.clip(kappa, -kappa_max, kappa_max)
    a_lat = v * v * kappa

    # --- a_long = dV/dt via Savitzky-Golay (model_spec §A.2, CONTEXT D-01) ---
    # Savgol delta = median dt; the Phase 1 helper locks 0.25 s but honors overrides.
    if len(t) >= 2:
        dt_median = float(np.median(np.diff(t)))
        if dt_median <= 0 or not np.isfinite(dt_median):
            dt_median = 0.25
    else:
        dt_median = 0.25
    a_long = savgol_velocity(v, window=9, order=3, delta=dt_median)

    # --- V_sx,r from RPM + gear ratios (model_spec §A.4) ---
    rpm = car["RPM"].to_numpy(dtype=float)
    gear = car["nGear"].to_numpy(dtype=float)
    try:
        combined_ratios = infer_gear_ratios(car)
    except ValueError:
        # Missing columns or too few samples; zeros fallback
        combined_ratios = {}
    v_sx_rear = _v_sx_rear_from_telemetry(rpm, gear, v, combined_ratios)

    return KinematicState(
        t=t,
        v=v,
        a_lat=a_lat.astype(np.float64),
        a_long=np.asarray(a_long, dtype=np.float64),
        psi=psi.astype(np.float64),
        v_sx_rear=v_sx_rear.astype(np.float64),
        kappa=kappa.astype(np.float64),
    )


__all__ = ["process_stint"]
