"""Pydantic v2 request/response schemas for POST /simulate (API-04).

Decisions honored: D-01 (three levels in one response), D-02 (mean/lo_95/hi_95 triplet),
D-03 (metadata block), D-04 (K=100 draws + overrides_applied flag).
"""
from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field


class CIValue(BaseModel):
    """Single scalar + 95% credible interval. D-02."""
    model_config = ConfigDict(frozen=True)
    mean: float
    lo_95: float
    hi_95: float


class CIArray1D(BaseModel):
    """(N,) array of mean/lo_95/hi_95 lists. D-02."""
    model_config = ConfigDict(frozen=True)
    mean: list[float]
    lo_95: list[float]
    hi_95: list[float]


class CIArray2D(BaseModel):
    """(N, 4) tire-indexed array of mean/lo_95/hi_95 lists. D-02."""
    model_config = ConfigDict(frozen=True)
    mean: list[list[float]]
    lo_95: list[list[float]]
    hi_95: list[list[float]]


class SimulationMetadata(BaseModel):
    """Provenance/diagnostics block in every response. D-03."""
    model_config = ConfigDict(frozen=True)
    calibration_id: int
    model_schema_version: str = "v1"
    fastf1_version: str
    compound: str
    stint_index: int
    overrides_applied: bool
    k_draws: int = 100


class PerTimestepBlock(BaseModel):
    """~4 Hz telemetry-rate arrays. D-01."""
    model_config = ConfigDict(frozen=True)
    t: list[float]                  # (N,) — time is deterministic
    t_tread: CIArray2D              # (N, 4)
    e_tire: CIArray2D
    mu: CIArray2D
    f_z: CIArray2D
    f_y: CIArray2D
    f_x: CIArray2D
    mu_0: CIArray1D                 # (N,)


class PerLapRow(BaseModel):
    """One row per race lap. D-01."""
    model_config = ConfigDict(frozen=True)
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
    model_config = ConfigDict(frozen=True)
    total_predicted_time_s: CIValue
    stint_end_grip_pct: CIValue
    peak_t_tread_c: CIValue
    total_e_tire_mj: CIValue


class SimulateResponse(BaseModel):
    """Top-level response envelope. D-01."""
    model_config = ConfigDict(frozen=True)
    metadata: SimulationMetadata
    per_timestep: PerTimestepBlock
    per_lap: list[PerLapRow]
    per_stint: PerStintSummary


class ParameterOverrides(BaseModel):
    """Optional physics-parameter overrides for forward pass.
    Every field has a physically-plausible range bound (T-4-OVERRIDE)."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    # Aero (Stage 1)
    C_LA: float | None = Field(default=None, gt=0, lt=20)
    C_DA: float | None = Field(default=None, gt=0, lt=10)
    xi: float | None = Field(default=None, ge=0, le=1)
    # Friction (Stage 2)
    mu_0_fresh: float | None = Field(default=None, gt=0, lt=3)
    p_bar_0: float | None = Field(default=None, gt=1e3, lt=1e7)
    n: float | None = Field(default=None, ge=0.5, le=1.2)
    # Thermal (Stage 3)
    T_opt: float | None = Field(default=None, ge=50, le=150)
    sigma_T: float | None = Field(default=None, gt=0, lt=100)
    # Degradation (Stage 4)
    beta_therm: float | None = Field(default=None, ge=0, lt=1)
    T_act: float | None = Field(default=None, gt=0, lt=500)
    k_wear: float | None = Field(default=None, ge=0, lt=1)


class SimulateRequest(BaseModel):
    """POST /simulate request body."""
    model_config = ConfigDict(extra="forbid")
    race_id: str = Field(pattern=r"^[0-9]{4}-[a-z0-9_]+$", min_length=6, max_length=48)
    driver_code: str = Field(pattern=r"^[A-Z]{3}$")
    stint_index: int = Field(ge=1, le=10)
    overrides: ParameterOverrides | None = None
    session_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")


__all__ = [
    "CIValue", "CIArray1D", "CIArray2D",
    "SimulationMetadata", "PerTimestepBlock", "PerLapRow", "PerStintSummary",
    "SimulateResponse", "ParameterOverrides", "SimulateRequest",
]
