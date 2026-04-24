"""Pydantic v2 response schemas for GET /calibration/{compound} (API-05, D-09)."""
from __future__ import annotations
from pydantic import BaseModel, ConfigDict


class Stage1Summary(BaseModel):
    """Stage 1 (aero): point estimates + residual uncertainty."""
    model_config = ConfigDict(frozen=True)
    C_LA: float
    C_DA: float
    xi: float
    K_rf_split: float
    WD: float
    H_CG: float
    BB: float
    residual_rmse: float | None = None


class Stage2Summary(BaseModel):
    """Stage 2 (friction): point estimates + residual uncertainty."""
    model_config = ConfigDict(frozen=True)
    mu_0_fresh: float
    p_bar_0: float
    n: float
    c_py: float
    K_rad: float
    residual_rmse: float | None = None


class Stage3Summary(BaseModel):
    """Stage 3 (thermal): 8 ODE params + T_opt/sigma_T (held fixed at nominal)."""
    model_config = ConfigDict(frozen=True)
    T_opt: float
    sigma_T: float
    C_tread: float
    C_carc: float
    C_gas: float
    R_tc: float
    R_cg: float
    h_0: float
    h_1: float
    alpha_p: float
    delta_T_blanket: float
    residual_rmse: float | None = None
    t_opt_fixed: bool = True
    sigma_t_fixed: bool = True


class Stage4VarSummary(BaseModel):
    """Posterior summary for a single Stage-4 variable."""
    model_config = ConfigDict(frozen=True)
    mean: float
    sd: float
    hdi_lo_95: float
    hdi_hi_95: float
    r_hat: float
    ess_bulk: float


class Stage4Summary(BaseModel):
    """Stage 4 (Bayesian degradation): full posterior summary per variable."""
    model_config = ConfigDict(frozen=True)
    beta_therm: Stage4VarSummary
    T_act: Stage4VarSummary
    k_wear: Stage4VarSummary


class Stage5Summary(BaseModel):
    """Stage 5 validation metrics."""
    model_config = ConfigDict(frozen=True)
    heldout_rmse_s: float
    baseline_rmse_s: float
    beat_baseline: bool


class CalibrationMetadata(BaseModel):
    """calibration_runs row metadata echoed in the response."""
    model_config = ConfigDict(frozen=True)
    calibration_id: int
    compound: str
    year_range: str
    created_at: str
    git_sha: str


class CalibrationResponse(BaseModel):
    """Top-level response for GET /calibration/{compound}."""
    model_config = ConfigDict(frozen=True)
    metadata: CalibrationMetadata
    stage1: Stage1Summary
    stage2: Stage2Summary
    stage3: Stage3Summary
    stage4: Stage4Summary
    stage5: Stage5Summary


__all__ = [
    "Stage1Summary", "Stage2Summary", "Stage3Summary", "Stage4VarSummary",
    "Stage4Summary", "Stage5Summary", "CalibrationMetadata", "CalibrationResponse",
]
