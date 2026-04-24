"""Physics parameter dataclasses (model_spec.md §Parameter registry LEARNED + SEMI-CONSTRAINED).

Per CONTEXT.md D-03: four nested dataclasses, one per calibration stage.
Each physics module receives only its own params dataclass.

NOTE: These are frozen=True to prevent accidental mutation during a simulation
run. A new PhysicsParams is built per simulation call.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AeroParams:
    """Stage 1 calibration target — model_spec.md §B.4 + §Calibration staging Stage 1.

    Fields:
        C_LA: lift coefficient * reference area [m²]  (C_L·A in model_spec)
        C_DA: drag coefficient * reference area [m²]  (C_D·A)
        xi:   aero balance, fraction of downforce on front axle [-] (ξ)
        K_rf_split: front roll-stiffness split K_rf / (K_rf + K_rr) [-]  (model_spec §B.3)
        WD:   static front weight distribution [-]  (semi-constrained, §B.1)
        H_CG: center-of-gravity height [m]  (semi-constrained)
        BB:   brake bias, fraction on front axle [-]  (semi-constrained, §C.3)
    """
    C_LA: float
    C_DA: float
    xi: float
    K_rf_split: float
    WD: float
    H_CG: float
    BB: float


@dataclass(frozen=True)
class FrictionParams:
    """Stage 2 calibration target — model_spec.md §D.3–§D.5 + §E.1.

    Fields:
        mu_0_fresh: reference friction of a fresh tire [-]  (§D.3, μ_0^fresh)
        p_bar_0:    reference contact pressure [Pa]          (§D.3, p̄_0)
        n:          load exponent, A_real ∝ p̄^n, typical 0.75–0.85 [-]
        c_py:       brush-model tread lateral stiffness [N/m³]  (§E.1, C_α = c_py·a_cp²)
        K_rad:      tire radial stiffness [N/m]  (semi-constrained, §D.1 δ = F_z/K_rad)
    """
    mu_0_fresh: float
    p_bar_0: float
    n: float
    c_py: float
    K_rad: float


@dataclass(frozen=True)
class ThermalParams:
    """Stage 3 calibration target — model_spec.md §D.4, §F.1–§F.6.

    Fields:
        T_opt:      optimal tread temperature [°C]   (§D.4)
        sigma_T:    Grosch bell half-width [°C]     (§D.4)
        C_tread:    tread thermal capacity [J/K]    (§F.1, per tire)
        C_carc:     carcass thermal capacity [J/K]  (§F.2, per tire)
        C_gas:      gas thermal capacity [J/K]      (§F.3, per tire)
        R_tc:       tread-carcass resistance [K/W]  (§F.1)
        R_cg:       carcass-gas resistance [K/W]    (§F.2)
        h_0:        convection base [W/m²K]         (§F.5)
        h_1:        convection V-coeff [W/m²K/(m/s)^0.5]  (§F.5)
        alpha_p:    heat partition fraction into tire [-]  (§F.4)
        delta_T_blanket: initial tread preheat above T_track [°C]  (§F.6, semi-constrained)
    """
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


@dataclass(frozen=True)
class DegradationParams:
    """Stage 4 calibration target — model_spec.md §G.2–§G.3.

    Fields:
        beta_therm: Arrhenius-aging rate coefficient [1/s]    (§G.2)
        T_act:      activation temperature scale [°C]         (§G.2)
        k_wear:     mechanical-wear rate per unit sliding power [m·W⁻¹·s⁻¹]  (§G.3)
    """
    beta_therm: float
    T_act: float
    k_wear: float


@dataclass(frozen=True)
class PhysicsParams:
    """Thin container grouping the four stage-specific param dataclasses.

    The orchestrator receives PhysicsParams and passes only the relevant
    inner params to each module — never the full container (D-03).
    """
    aero: AeroParams
    friction: FrictionParams
    thermal: ThermalParams
    degradation: DegradationParams


__all__ = [
    "AeroParams",
    "DegradationParams",
    "FrictionParams",
    "PhysicsParams",
    "ThermalParams",
]
