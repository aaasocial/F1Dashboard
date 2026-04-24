"""FIXED physical constants (model_spec.md §Parameter registry FIXED table).

These are NOT calibrated — they are regulatory, geometric, or published
physical constants. Per CONTEXT.md D-04, these live as module-level
constants rather than fields on any params dataclass.
"""
from __future__ import annotations

# Vehicle mass & geometry — model_spec.md §Parameter registry FIXED
M_DRY: float = 798.0          # kg, minimum car mass incl. driver (FIA regulation)
WB: float = 3.6               # m, wheelbase
T_F: float = 1.60             # m, front track width
T_R: float = 1.60             # m, rear track width
R_0: float = 0.330            # m, tire nominal radius

# Tread half-widths — model_spec.md §D.2 (front narrower than rear)
B_TREAD_F: float = 0.15       # m
B_TREAD_R: float = 0.20       # m

# Environment — model_spec.md §B.4
RHO_AIR: float = 1.20         # kg/m³, nominal air density

# Rolling resistance — model_spec.md §E.6
C_RR: float = 0.012

# Gravitational acceleration
G: float = 9.81               # m/s²

# Total mass used for quick nominal load calculations (dry + nominal fuel).
# Module B will add time-varying fuel mass in Phase 3; for Phase 2 nominal
# we include ~50 kg mid-race fuel estimate.
M_FUEL_NOMINAL: float = 50.0  # kg
M_TOT: float = M_DRY + M_FUEL_NOMINAL  # kg

# Per-tire tread contact area — used by Module F convection term.
# Approximated as 2 * a_cp_nominal * b_tread with a_cp_nominal ~= 0.08 m.
A_TREAD_F: float = 2 * 0.08 * B_TREAD_F   # m² per front tire
A_TREAD_R: float = 2 * 0.08 * B_TREAD_R   # m² per rear tire
# Module F uses these as a per-tire (4,) array for convection.

# Forward Euler timestep — D-06 (locked at telemetry rate; RK4 deferred)
DT_THERMAL: float = 0.25      # s

# Reference temperature for Arrhenius aging — model_spec.md §G.2
T_REF_AGING: float = 80.0     # °C

# Carcass convection coefficient (lumped). model_spec.md §F.2 assumes a
# slower exchange than the tread surface; nominal h_carc=5 W/m²K.
H_CARC: float = 5.0           # W/m²K
A_CARC_F: float = 0.18        # m² per front tire, lumped sidewall area
A_CARC_R: float = 0.22        # m² per rear tire

__all__ = [
    "A_CARC_F", "A_CARC_R", "A_TREAD_F", "A_TREAD_R",
    "B_TREAD_F", "B_TREAD_R",
    "C_RR", "DT_THERMAL", "G", "H_CARC",
    "M_DRY", "M_FUEL_NOMINAL", "M_TOT",
    "RHO_AIR", "R_0",
    "T_F", "T_R", "T_REF_AGING", "WB",
]
