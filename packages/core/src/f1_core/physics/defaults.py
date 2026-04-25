"""Nominal parameter priors — model_spec.md §Parameter registry typical values.

Per CONTEXT.md D-04: single source of default initialization for all
Phase 2 forward simulations. These values are INTENTIONALLY approximate;
Phase 3 calibration replaces them with fitted posteriors.

Citation convention: every value below cites the model_spec.md table or
section it came from. If you change a default, update the citation.
"""
from __future__ import annotations

from f1_core.physics.params import (
    AeroParams,
    DegradationParams,
    FrictionParams,
    PhysicsParams,
    ThermalParams,
)


def make_nominal_params() -> PhysicsParams:
    """Return a PhysicsParams populated with mid-range nominal priors.

    Phase 2 uses this for CLI invocations and as the pytest fixture
    baseline. Phase 3 calibration replaces every LEARNED value.
    """
    aero = AeroParams(
        # LEARNED — model_spec.md §Parameter registry LEARNED "C_L A" typical F1 2023+
        C_LA=4.5,          # m², mid-range downforce setup
        C_DA=1.1,          # m², mid-range drag
        # LEARNED — §B.4 aero balance ξ
        xi=0.45,           # 45% front downforce (typical race setup)
        # LEARNED — §B.3 roll-stiffness split
        K_rf_split=0.55,   # K_rf / (K_rf + K_rr) — front-biased roll stiffness
        # SEMI-CONSTRAINED — §B.1 WD 0.43–0.46
        WD=0.445,
        # SEMI-CONSTRAINED — §B range 0.26–0.30 m
        H_CG=0.28,
        # SEMI-CONSTRAINED — §C.3 brake bias 0.55–0.60
        BB=0.575,
    )
    friction = FrictionParams(
        # LEARNED — §D.3 μ_0^fresh typical 1.6–2.0 for F1 slick
        mu_0_fresh=1.8,
        # LEARNED — §D.3 reference pressure 1.5 bar ≈ 1.5e5 Pa
        p_bar_0=1.5e5,
        # LEARNED — §D.3 load exponent typical 0.75–0.85
        n=0.8,
        # LEARNED — §E.1 brush tread stiffness, typical 1e8 N/m³ for racing slick
        c_py=1.0e8,
        # SEMI-CONSTRAINED — §D.1 K_rad 200–300 kN/m
        K_rad=250_000.0,   # N/m
    )
    thermal = ThermalParams(
        # LEARNED — §D.4 T_opt typical 90–105 °C for modern F1 slicks
        T_opt=95.0,
        # LEARNED — §D.4 σ_T typical 18–22 °C
        sigma_T=20.0,
        # LEARNED — §F.1 tread thermal capacity lumped ≈ 6000 J/K per tire
        C_tread=6000.0,
        # LEARNED — §F.2 carcass capacity ≈ 20000 J/K
        C_carc=20000.0,
        # LEARNED — §F.3 gas capacity ≈ 500 J/K
        C_gas=500.0,
        # LEARNED — §F.1 R_tc typical 0.02 K/W (conductive path through rubber)
        R_tc=0.02,
        # LEARNED — §F.2 R_cg typical 0.05 K/W (across inner liner)
        R_cg=0.05,
        # LEARNED — §F.5 typical h_0=10 W/m²K
        h_0=10.0,
        # LEARNED — §F.5 typical h_1=8 W/m²K/(m/s)^0.5
        h_1=8.0,
        # LEARNED — §F.4 α_p ≈ 0.55 for slicks on asphalt
        alpha_p=0.55,
        # SEMI-CONSTRAINED — §F.6 ΔT_blanket 50–70 °C
        delta_T_blanket=60.0,
    )
    degradation = DegradationParams(
        # LEARNED — §G.2 β_therm typical 1e-6 /s (slow aging)
        beta_therm=1.0e-6,
        # LEARNED — §G.2 "every 25°C above T_ref doubles rate"
        T_act=25.0,
        # LEARNED — §G.3 k_wear typical 1e-12 m/(W·s) for slicks
        k_wear=1.0e-12,
    )
    return PhysicsParams(aero=aero, friction=friction, thermal=thermal, degradation=degradation)


__all__ = ["make_nominal_params"]
