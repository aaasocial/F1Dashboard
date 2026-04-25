# F1 Tire Degradation Model — Mathematical Specification

**Purpose:** This document is the single source of truth for the physics model that forms the backend algorithm. It is written for implementation in Python. Every equation includes its source paper for traceability.

**Architecture:** Seven modules, executed in sequence at each telemetry timestep. The thermal state from the previous timestep feeds into the friction model at the current timestep — this is the only feedback loop, handled causally through time without inner iteration.

---

## Module A — Kinematic front-end

Derives accelerations and slip-relevant quantities from the raw FastF1 telemetry (speed, XY position, RPM).

### A.1 Path curvature from XY position

Fit a smoothing cubic spline to the trajectory `(X(s), Y(s))` parameterized by arc length `s`. Compute curvature:

$$\kappa(s) = X'(s) \cdot Y''(s) - Y'(s) \cdot X''(s)$$

Since `s` is arc length, the denominator `(X'² + Y'²)^(3/2) = 1` by construction.

**Implementation note:** Build a reference curvature map `κ_ref(s)` once per circuit from aggregated fast laps. Cache it. For every subsequent lap, look up `κ` by cumulative distance `s(X, Y)` rather than re-differentiating noisy per-lap position data.

### A.2 Lateral and longitudinal acceleration

From Frenet-Serret decomposition:

$$a_{lat}(t) = V(t)^2 \cdot \kappa(s(t))$$

$$a_{long}(t) = \frac{dV}{dt}$$

Compute `dV/dt` with a Savitzky-Golay filter on the speed channel (window 7–11 samples, polynomial order 2–3) to suppress noise while preserving peaks.

### A.3 Heading angle (velocity vector direction)

$$\psi(t) = \text{atan2}\left(\frac{dY}{dt},\ \frac{dX}{dt}\right)$$

This is the direction the car's center of gravity is actually moving. The car's chassis heading differs by body sideslip `β` which is small (1–3°) and ignored in this model.

### A.4 Longitudinal slip velocity

Assuming rear-wheel drive with gear ratio `G_ratio(gear)` and final drive `G_final`:

$$V_{wheel,r}(t) = \frac{2\pi \cdot RPM(t)}{60 \cdot G_{ratio}(gear) \cdot G_{final}} \cdot R_0$$

$$V_{sx,r}(t) = V_{wheel,r}(t) - V(t)$$

For front tires (undriven in RWD), set `V_sx,f = 0` except during braking. Since FastF1's Brake channel is boolean, approximate by putting all longitudinal braking force on the fronts proportionally to brake bias and all accelerating force on the rears.

---

## Module B — Vertical load per tire

**Source:** Castellano et al. (2021), Eqs. 1–9, with simplifications for public data.

### B.1 Static loads

$$SL_F = \frac{M_{tot} \cdot WD}{2}, \qquad SL_R = \frac{M_{tot} \cdot (1 - WD)}{2}$$

where `WD` is the fraction of static weight on the front axle.

### B.2 Longitudinal load transfer

$$\Delta F_{z,long} = \frac{M_{tot} \cdot a_{long} \cdot H_{CG}}{WB}$$

Sign convention: `a_long > 0` means acceleration, which loads the rear (positive `ΔF_z,long` adds to rear, subtracts from front).

### B.3 Lateral load transfer (simplified from Castellano)

Castellano's full equation requires roll angle `θ` from suspension displacement sensors, which are unavailable. Use the elastic approximation:

$$\Delta F_{z,lat,f} = \frac{M_{tot} \cdot a_{lat} \cdot H_{CG}}{T_f} \cdot \frac{K_{rf}}{K_{rf} + K_{rr}}$$

$$\Delta F_{z,lat,r} = \frac{M_{tot} \cdot a_{lat} \cdot H_{CG}}{T_r} \cdot \frac{K_{rr}}{K_{rf} + K_{rr}}$$

Sign convention: `a_lat > 0` means right turn, which loads the left side.

### B.4 Aerodynamic downforce

$$F_{z,aero}(V) = \tfrac{1}{2} \rho \cdot C_L A \cdot V^2$$

Split front/rear by aero balance `ξ`:

$$F_{z,aero,f} = \xi \cdot F_{z,aero}, \qquad F_{z,aero,r} = (1 - \xi) \cdot F_{z,aero}$$

Within each axle, split left/right equally.

### B.5 Per-tire vertical load

For a right turn (`a_lat > 0`):

$$F_{z,FL} = SL_F - \Delta F_{z,long} + \Delta F_{z,lat,f} + \tfrac{1}{2} F_{z,aero,f}$$

$$F_{z,FR} = SL_F - \Delta F_{z,long} - \Delta F_{z,lat,f} + \tfrac{1}{2} F_{z,aero,f}$$

$$F_{z,RL} = SL_R + \Delta F_{z,long} + \Delta F_{z,lat,r} + \tfrac{1}{2} F_{z,aero,r}$$

$$F_{z,RR} = SL_R + \Delta F_{z,long} - \Delta F_{z,lat,r} + \tfrac{1}{2} F_{z,aero,r}$$

For left turns, swap the lateral transfer signs so the outside (right) tires are loaded.

**Floor:** Clip each `F_z,i` to a minimum of 50 N to prevent division-by-zero in downstream modules when vertical curvature produces near-zero loads at crests.

---

## Module C — Force distribution

**Source:** Castellano et al. (2021), Eqs. 10–27.

### C.1 Total forces from Newton's second law

$$F_{y,G}(t) = M_{tot} \cdot a_{lat}(t)$$

$$F_{x,G}(t) = M_{tot} \cdot a_{long}(t) - F_{drag}(V)$$

where `F_drag = ½ ρ C_D A V²`.

### C.2 Load-proportional lateral force distribution

Compute load fractions:

$$F_{z,i,\%} = \frac{F_{z,i}}{F_{z,FL} + F_{z,FR} + F_{z,RL} + F_{z,RR}}$$

Each tire's lateral force:

$$F_{y,i} = F_{y,G} \cdot F_{z,i,\%}$$

### C.3 Longitudinal force distribution

Brake component (active when `F_x,G < 0`), scaled by brake bias `BB`:

$$F_{x,i}^{brake} = \min(F_{x,G} \cdot F_{z,i,\%},\ 0) \cdot \begin{cases} BB & i \in \{FL, FR\} \\ 1 - BB & i \in \{RL, RR\} \end{cases}$$

Power component (active when `F_x,G > 0`), zero on fronts for RWD:

$$F_{x,FL}^{power} = F_{x,FR}^{power} = 0$$

$$F_{x,RL}^{power} = \max(F_{x,G} \cdot (F_{z,RL,\%} + F_{z,FL,\%}),\ 0)$$

$$F_{x,RR}^{power} = \max(F_{x,G} \cdot (F_{z,RR,\%} + F_{z,FR,\%}),\ 0)$$

Total: `F_x,i = F_x,i^brake + F_x,i^power`.

---

## Module D — Hertzian contact and friction

### D.1 Contact patch geometry

**Source:** Gim (1988), via Ozerem & Morrey (2019).

Radial deflection under load:

$$\delta_i = \frac{F_{z,i}}{K_{rad}}$$

Contact patch half-length:

$$a_{cp,i} = \sqrt{2 R_0 \delta_i} = \sqrt{\frac{2 R_0 F_{z,i}}{K_{rad}}}$$

This scales as `F_z^(1/2)`.

### D.2 Mean Hertzian contact pressure

$$\bar{p}_i = \frac{F_{z,i}}{4 \cdot a_{cp,i} \cdot b_{tread}}$$

### D.3 Load-dependent friction (Greenwood-Williamson)

**Source:** Greenwood & Williamson (1966); derivation in `rubber_friction_first_principles.html`.

The real contact area scales sub-linearly with load: `A_real ∝ p̄^n` with `n ≈ 0.75–0.85`. Since `F_adhesion = τ_s · A_real` and `μ = F/F_z`:

$$\mu^{pressure}(\bar{p}) = \mu_0 \cdot \left(\frac{\bar{p}_0}{\bar{p}}\right)^{1-n}$$

`μ_0` is the reference friction at the reference pressure `p̄_0`. All material constants (`τ_s`, `κ_GW`, `E*`) are absorbed into these two calibration parameters.

### D.4 Temperature-dependent friction (Grosch bell curve)

**Source:** Grosch (1963), Williams–Landel–Ferry (1955).

Adhesion + hysteretic friction combined produce a bell-shaped temperature dependence peaked at `T_opt`:

$$g(T) = \exp\left(-\frac{(T - T_{opt})^2}{2\sigma_T^2}\right)$$

### D.5 Complete friction coefficient

$$\mu_i(T_{tread,i}, \bar{p}_i) = \mu_0(t) \cdot \left(\frac{\bar{p}_0}{\bar{p}_i}\right)^{1-n} \cdot \exp\left(-\frac{(T_{tread,i} - T_{opt})^2}{2\sigma_T^2}\right)$$

`μ_0(t)` is the slowly-decaying reference friction from Module G. At `t = 0` of a fresh stint, `μ_0(0) = μ_0^fresh`. `T_tread,i` is from the previous timestep's thermal state (Module F).

---

## Module E — Slip inversion and sliding power

### E.1 Cornering stiffness

**Source:** Pacejka (2012), Ch. 3.

$$C_{\alpha,i} = c_{py} \cdot a_{cp,i}^2$$

### E.2 Brush model inversion

Given observed `F_y,i` and known `μ_i`, `F_z,i`, solve for the normalized slip parameter `Θ`:

$$\Theta_i = 1 - \left(1 - \frac{|F_{y,i}|}{\mu_i \cdot F_{z,i}}\right)^{1/3}$$

**Validity check:** If `|F_y,i| > μ_i · F_z,i`, clip `Θ_i = 1` (tire beyond full sliding — implies the demand exceeds grip, which can happen due to parameter error). Log these events for diagnostic purposes.

### E.3 Slip angle

$$\alpha_i = \text{sgn}(F_{y,i}) \cdot \arctan\left(\frac{3 \mu_i F_{z,i}}{C_{\alpha,i}} \cdot \Theta_i\right)$$

### E.4 Lateral slip velocity

$$V_{sy,i} = V \cdot \sin(\alpha_i)$$

### E.5 Sliding power per tire

**Source:** Kobayashi et al. (2019); Castellano et al. (2021).

$$P_{slide,i}(t) = |F_{y,i}| \cdot |V_{sy,i}| + |F_{x,i}| \cdot |V_{sx,i}|$$

### E.6 Rolling resistance

$$P_{rr,i}(t) = C_{rr} \cdot F_{z,i} \cdot V$$

with `C_rr ≈ 0.012`. Small compared to `P_slide` in corners, provides baseline heating on straights.

### E.7 Total dissipated power

$$P_{total,i}(t) = P_{slide,i}(t) + P_{rr,i}(t)$$

---

## Module F — Thermal ODE

**Source:** Sorniotti (2009); Farroni et al. (2015); Kenins et al. (2019).

Three-node lumped thermal model: tread, carcass, gas. Per tire:

### F.1 Tread temperature

$$C_{tread} \frac{dT_{tread,i}}{dt} = \alpha_p P_{total,i} - h_{air}(V) A_{tread}(T_{tread,i} - T_{air}) - \frac{T_{tread,i} - T_{carc,i}}{R_{tc}}$$

### F.2 Carcass temperature

$$C_{carc} \frac{dT_{carc,i}}{dt} = \frac{T_{tread,i} - T_{carc,i}}{R_{tc}} - h_{carc} A_{carc}(T_{carc,i} - T_{air}) - \frac{T_{carc,i} - T_{gas,i}}{R_{cg}}$$

### F.3 Gas temperature

$$C_{gas} \frac{dT_{gas,i}}{dt} = \frac{T_{carc,i} - T_{gas,i}}{R_{cg}}$$

### F.4 Heat partition coefficient

**Source:** Farroni et al. (2015).

Fraction of sliding power entering the tire (rest heats the road):

$$\alpha_p = \frac{e_{rubber}}{e_{rubber} + e_{road}}, \quad e = \sqrt{k \rho c_p}$$

Approximate `α_p ≈ 0.55` for racing slicks on asphalt.

### F.5 Speed-dependent convection

Forced-convection flat-plate correlation (Reynolds analogy):

$$h_{air}(V) = h_0 + h_1 \sqrt{V}$$

Typical values: `h_0 ≈ 10 W/m²K`, `h_1 ≈ 8 W/m²K/(m/s)^0.5`.

### F.6 Initial conditions

At start of stint (out of the pit lane):

$$T_{tread,i}(0) = T_{carc,i}(0) = T_{gas,i}(0) = T_{track} + \Delta T_{blanket}$$

with `ΔT_blanket ≈ 60°C` for current FIA-regulated pre-heated tires. Note: FIA tire blanket rules change over time; verify the regulation for the season being simulated.

### F.7 Numerical integration

At 4 Hz telemetry (`Δt = 0.25 s`), forward Euler is stable since all thermal time constants exceed 5 seconds:

$$T(t + \Delta t) = T(t) + \dot{T}(t) \cdot \Delta t$$

For higher accuracy, upgrade to RK4 with the same `Δt`.

---

## Module G — Cumulative energy and degradation

### G.1 Cumulative tire energy

**Source:** Todd et al. (2025); Castellano (2021).

$$E_{tire,i}(t + \Delta t) = E_{tire,i}(t) + P_{total,i}(t) \cdot \Delta t$$

### G.2 Thermal aging of reference friction

Rubber degrades permanently under sustained high temperature (reversion of vulcanization, oxidation). Model `μ_0` as a slowly-decaying state with Arrhenius-like temperature sensitivity:

$$\frac{d\mu_0}{dt} = -\beta_{therm} \cdot \mu_0 \cdot \exp\left(\frac{T_{tread,i} - T_{ref}}{T_{act}}\right)$$

Typical values: `T_ref = 80°C`, `T_act ≈ 25°C` (every 25°C above `T_ref` doubles the degradation rate).

### G.3 Mechanical wear

$$\frac{d \, d_{tread}}{dt} = -k_{wear} \cdot P_{slide,i}$$

Updates tread thickness. Downstream effects: `R_tc` decreases as the tread thins, accelerating thermal response.

### G.4 Lap-time penalty from grip loss

Corner speed scales as `V ∝ √μ`, so time through a corner scales as `1/√μ`. First-order expansion:

$$\Delta t_{lap}(t) \approx \frac{t_{lap}^{ref}}{2} \cdot \frac{\mu_0^{fresh} - \mu_0(t)}{\mu_0^{fresh}}$$

---

## Execution order at each timestep

At every telemetry sample (4 Hz nominal), execute in strict sequence:

1. **Read** raw telemetry: `V, X, Y, Z, RPM, throttle, brake, gear, T_track, T_air`.
2. **Module A:** compute `a_lat, a_long, ψ, V_sx,r`.
3. **Module B:** compute `F_z,i` per tire using `a_lat, a_long, V`.
4. **Module C:** compute `F_y,i, F_x,i` per tire using `F_z,i`.
5. **Module D:** compute `a_cp,i, p̄_i`, then `μ_i` using the previous timestep's `T_tread,i` and current `μ_0(t)`.
6. **Module E:** invert brush model to recover `Θ_i, α_i, V_sy,i`. Compute `P_slide,i, P_total,i`.
7. **Module F:** integrate thermal ODEs forward by `Δt` using current `P_total,i`. Update `T_tread,i, T_carc,i, T_gas,i`.
8. **Module G:** integrate `E_tire,i` forward. Update `μ_0` via G.2. Update `d_tread` via G.3.
9. Advance `t → t + Δt`. Repeat from step 1.

No iteration is required within a timestep. The feedback between friction and temperature is handled causally through time — friction at time `t` uses temperature from time `t - Δt`, which is physically correct.

---

## Parameter registry

Parameters classified by calibration status. Full table in `model_calibration_strategy.html`.

### FIXED (known from physics, regulations, or published specs)

| Symbol | Meaning | Value |
|--------|---------|-------|
| `M_dry` | Minimum car mass incl. driver | 798 kg |
| `WB` | Wheelbase | 3.6 m |
| `T_f, T_r` | Track widths | 1.60 m |
| `R_0` | Tire radius | 0.330 m |
| `b_tread` | Tread half-width | 0.15 m (front), 0.20 m (rear) |
| `ρ` | Air density | ~1.20 kg/m³ (from weather) |
| `C_rr` | Rolling resistance coeff | 0.012 |

### SEMI-CONSTRAINED (estimable with moderate uncertainty)

| Symbol | Meaning | Typical range |
|--------|---------|---------------|
| `M_fuel(t)` | Fuel mass at time t | ~110 kg at start, -1 kg/lap |
| `WD` | Front weight fraction | 0.43–0.46 |
| `H_CG` | CG height | 0.26–0.30 m |
| `K_rad` | Tire radial stiffness | 200–300 kN/m |
| `ΔT_blanket` | Blanket pre-heat above ambient | 50–70°C |
| `BB` | Brake bias (front fraction) | 0.55–0.60 |
| `G_ratio, G_final` | Gear ratios | Inferable from RPM vs V |

### LEARNED (must be calibrated from data)

**Per car/track:**
- `C_L A, C_D A, ξ` — aerodynamic coefficients and balance
- `K_rf/(K_rf+K_rr)` — roll stiffness split

**Per compound:**
- `μ_0^fresh, p̄_0, n` — friction baseline and load sensitivity
- `T_opt, σ_T` — temperature window
- `c_py` — brush model tread stiffness
- `C_tread, C_carc, C_gas, R_tc, R_cg, h_0, h_1, α_p` — thermal parameters
- `β_therm, T_act, k_wear` — degradation rates

Expect ~15–20 effective calibration dimensions per compound after physical priors constrain the rest.

---

## Calibration staging

Calibrate parameters sequentially to exploit observational independence. See `model_calibration_strategy.html` for full details.

### Stage 1 — Aero

**Observables:** max lateral g in aero-limited corners (Copse, Pouhon, 130R, T1 Monza).
**Fit:** `C_L A, C_D A, ξ`.
**Method:** `g_lat,max = μ·(g + F_aero/M)/g`, invert for `C_L A` assuming prior `μ ≈ 1.8`. `C_D A` from terminal straight-line speed.

### Stage 2 — Friction baseline

**Observables:** peak lateral g in laps 2–5 of each stint (warmed but not degraded).
**Fit:** `μ_0^fresh, p̄_0, n`.
**Method:** plot `ln(μ_eff)` vs `ln(p̄)` across many corners and speeds. Slope gives `-(1-n)`.

### Stage 3 — Thermal parameters

**Observables:** out-lap times (cold tire), warm-up rate (laps 1–5), peak performance temperature.
**Fit:** `T_opt, σ_T, C_tread, C_carc, R_tc, R_cg, h_0, h_1, α_p`.
**Method:** constrained optimization matching observed warm-up curves. Use informative priors from literature.

### Stage 4 — Degradation rates

**Observables:** lap-time evolution across mid-to-late stint.
**Fit:** `β_therm, T_act, k_wear`.
**Method:** Bayesian (MCMC or variational) against observed lap-time-vs-age curves. Hold out 20% of races for validation.

---

## Outputs

For each simulated stint, return:

**Per timestep (~4 Hz):**
- `F_z,i, F_y,i, F_x,i` — forces per tire (4 × 3 = 12 channels)
- `p̄_i, a_cp,i` — contact mechanics (4 × 2 = 8 channels)
- `μ_i, α_i, Θ_i` — friction and slip state (4 × 3 = 12 channels)
- `P_slide,i, P_total,i` — dissipated power (4 × 2 = 8 channels)
- `T_tread,i, T_carc,i, T_gas,i` — thermal state (4 × 3 = 12 channels)
- `E_tire,i` — cumulative energy per tire (4 channels)
- `μ_0(t)` — current reference friction (1 channel)

**Per lap:**
- Predicted lap time
- Observed lap time (for comparison)
- Peak per-tire temperature during lap
- Integrated per-tire energy during lap
- Tire age (laps on current set)

**Per stint:**
- Total integrated energy per tire
- Final `μ_0` at stint end
- Predicted remaining stint capability
- RMSE of predicted vs. observed lap times

**Confidence intervals:** Every scalar output includes 95% credible intervals from the Bayesian parameter posterior.

---

## Implementation guidance for Claude Code

### Architecture

- Each module is a Python class with a clear input/output contract. Modules compose: the thermal module can be swapped for a higher-fidelity version without touching kinematics.
- State flows explicitly through function returns, not globals. Simulation state (temperatures, cumulative energy, `μ_0`) is carried in a state object that updates each timestep.
- Separate physics from ML. The physics modules (A–F) are deterministic given parameters. Module G's degradation includes stochastic components only at the calibration boundary.

### Numerical

- Use NumPy for vectorized per-tire computation. Per-timestep work should be ~1 ms on a laptop.
- Use SciPy for ODE integration (`scipy.integrate.solve_ivp` with RK4 for thermal module) or explicit Euler at 4 Hz (adequate for the time constants involved).
- Use SciPy smoothing splines or cubic B-splines for track curvature fits.
- For calibration, use `numpyro` or `pymc` for Bayesian inference. For faster pointwise fits, use `scipy.optimize.least_squares` with trust-region-reflective.

### Testing

- Each module has unit tests that verify physical limits:
  - Module B: sum of four `F_z,i` equals total weight + downforce
  - Module C: sum of four `F_y,i` equals `M·a_lat` exactly
  - Module D: `μ(T_opt, p̄_0) = μ_0` exactly
  - Module E: when `|F_y| = μ·F_z`, `Θ = 1` exactly
  - Module F: at steady state, `dT/dt = 0` yields expected equilibrium temperatures
  - Module G: `E_tire` is monotonically non-decreasing
- Integration tests: run a known stint, verify lap-time prediction RMSE is below 0.3 seconds on calibrated compounds.

### Caching

- FastF1 telemetry fetching is the slow step (5–30 seconds per session). Cache on disk keyed by (race, driver, session).
- Model simulations are fast (~100 ms per stint). Don't over-cache; recompute on parameter changes.
- Track reference curvature maps are computed once per circuit per year (aero regulations change). Cache aggressively.

### Documentation

- Every equation in code has a docstring citing the source paper (Pacejka 2012 Ch. 3, Castellano 2021 Eq. 12, Sorniotti 2009, etc.)
- Each module has a module-level docstring explaining its role in the pipeline.
- A Jupyter notebook alongside the code runs each module in isolation with a toy input, showing users how the physics works.

### API surface (for frontend to consume)

```
GET  /races                            → list of (year, round, name)
GET  /races/{race_id}/drivers          → drivers who ran that race
GET  /stints/{race_id}/{driver_id}     → stints (compound, laps, pit info)
POST /simulate                          → run model with optional overrides
POST /what_if                           → run model with scenario params
GET  /calibration/{compound}            → current fitted parameters for compound
POST /calibrate                         → trigger new calibration run (admin)
```

`POST /simulate` payload:
```json
{
  "race_id": "2024-silverstone",
  "driver_id": "HAM",
  "stint_number": 2,
  "overrides": {
    "C_L_A": 5.8,
    "T_opt": 105,
    "mu_0_fresh": 1.85
  }
}
```

Response includes full per-timestep, per-lap, and per-stint outputs as described above, plus model version and calibration timestamp for reproducibility.
