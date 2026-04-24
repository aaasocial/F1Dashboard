"""Pydantic v2 request/response schemas for POST /simulate (API-04).

Decisions honored: D-01 (three levels in one response), D-02 (mean/lo_95/hi_95 triplet),
D-03 (metadata block), D-04 (K=100 draws + overrides_applied flag).
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "CIValue",
    "CIArray1D",
    "CIArray2D",
    "SimulationMetadata",
    "PerTimestepBlock",
    "PerLapRow",
    "PerStintSummary",
    "SimulateResponse",
    "ParameterOverrides",
    "SimulateRequest",
    "SimulateStreamRequest",
]


class CIValue(BaseModel):
    """Single scalar + 95% credible interval. D-02."""

    model_config = ConfigDict(extra="forbid")

    mean: float
    lo_95: float
    hi_95: float


class CIArray1D(BaseModel):
    """(N,) array of mean/lo_95/hi_95 lists. D-02."""

    model_config = ConfigDict(extra="forbid")

    mean: list[float]
    lo_95: list[float]
    hi_95: list[float]


class CIArray2D(BaseModel):
    """(N, 4) tire-indexed array of mean/lo_95/hi_95 lists. D-02."""

    model_config = ConfigDict(extra="forbid")

    mean: list[list[float]]
    lo_95: list[list[float]]
    hi_95: list[list[float]]


class SimulationMetadata(BaseModel):
    """Provenance/diagnostics block in every response. D-03."""

    model_config = ConfigDict(extra="forbid")

    calibration_id: int
    model_schema_version: str
    fastf1_version: str
    compound: str
    stint_index: int
    overrides_applied: bool
    k_draws: int


class PerTimestepBlock(BaseModel):
    """~4 Hz telemetry-rate arrays. D-01."""

    model_config = ConfigDict(extra="forbid")

    t: list[float]
    t_tread: CIArray2D
    e_tire: CIArray2D
    mu: CIArray2D
    f_z: CIArray2D
    f_y: CIArray2D
    f_x: CIArray2D
    mu_0: CIArray1D


class PerLapRow(BaseModel):
    """One row per race lap. D-01."""

    model_config = ConfigDict(extra="forbid")

    lap: int
    compound: str
    age: int
    obs_s: float | None
    pred_s: CIValue
    delta_s: CIValue
    grip_pct: CIValue
    t_tread_max_c: CIValue
    e_tire_mj: CIValue


class PerStintSummary(BaseModel):
    """Aggregates over the full stint. D-01."""

    model_config = ConfigDict(extra="forbid")

    total_predicted_time_s: CIValue
    stint_end_grip_pct: CIValue
    peak_t_tread_c: CIValue
    total_e_tire_mj: CIValue


class SimulateResponse(BaseModel):
    """Top-level response envelope. D-01."""

    model_config = ConfigDict(extra="forbid")

    metadata: SimulationMetadata
    per_timestep: PerTimestepBlock
    per_lap: list[PerLapRow]
    per_stint: PerStintSummary

    # Track geometry fields — set on /simulate/stream simulation_complete event;
    # None on sync /simulate (geometry is streaming-only in v1). D-01.
    track: list[list[float]] | None = Field(
        default=None,
        description=(
            "Circuit outline: normalized [0,1] X/Y coordinate pairs from FastF1 fastest-lap "
            "GPS telemetry. Savitzky-Golay smoothed (window=21, order=3). "
            "Set on /simulate/stream simulation_complete event; None on sync /simulate."
        ),
    )
    sector_bounds: list[list[int]] | None = Field(
        default=None,
        description=(
            "Index triplets into track[]: [[s1_start,s1_end],[s2_start,s2_end],[s3_start,s3_end]]. "
            "Set on /simulate/stream; None on sync /simulate."
        ),
    )
    turns: list[dict] | None = Field(
        default=None,
        description=(
            'Turn markers: [{"n": 1, "at": 0.13}, ...] where "at" is the fraction 0..1 '
            "around the circuit. Set on /simulate/stream; None on sync /simulate."
        ),
    )


class ParameterOverrides(BaseModel):
    """Optional physics-parameter overrides for forward pass.
    Every field has a physically-plausible range bound (T-4-OVERRIDE)."""

    model_config = ConfigDict(extra="forbid")

    C_LA: float | None = Field(default=None, ge=0.0, le=10.0)
    C_DA: float | None = Field(default=None, ge=0.0, le=5.0)
    xi: float | None = Field(default=None, ge=0.0, le=1.0)
    mu_0_fresh: float | None = Field(default=None, ge=0.5, le=3.0)
    p_bar_0: float | None = Field(default=None, ge=100_000.0, le=400_000.0)
    n: float | None = Field(default=None, ge=0.0, le=5.0)
    T_opt: float | None = Field(default=None, ge=50.0, le=150.0)
    sigma_T: float | None = Field(default=None, ge=1.0, le=50.0)
    beta_therm: float | None = Field(default=None, ge=0.0, le=1.0)
    T_act: float | None = Field(default=None, ge=1000.0, le=20_000.0)
    k_wear: float | None = Field(default=None, ge=0.0, le=1.0)


class SimulateRequest(BaseModel):
    """POST /simulate request body."""

    model_config = ConfigDict(extra="forbid")

    race_id: str = Field(pattern=r"^[0-9]{4}-[a-z0-9_]+$", min_length=6, max_length=48)
    driver_code: str = Field(pattern=r"^[A-Z]{3}$")
    stint_index: int = Field(ge=1, le=10)
    overrides: ParameterOverrides | None = None
    session_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")


class SimulateStreamRequest(BaseModel):
    """POST /simulate/stream request body — same constraints as SimulateRequest
    but omits overrides (streaming UI is point-estimate only in v1)."""

    model_config = ConfigDict(extra="forbid")

    race_id: str = Field(pattern=r"^[0-9]{4}-[a-z0-9_]+$", min_length=6, max_length=48)
    driver_code: str = Field(pattern=r"^[A-Z]{3}$")
    stint_index: int = Field(ge=1, le=10)
    session_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
