# Phase 3: Bayesian Calibration Pipeline — Research

**Researched:** 2026-04-23
**Domain:** Offline Bayesian calibration pipeline (PyMC + NumPyro + JAX, scipy.optimize, SQLite parameter versioning, ArviZ NetCDF)
**Confidence:** HIGH on stack + patterns; MEDIUM on exact MCMC hyperparameters and Pirelli compound-map construction

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**CLI Structure**
- **D-01:** Two entry point styles in `f1-calibrate`:
  - Stage subcommands: `f1-calibrate stage1 --compound C3`, `stage2`, `stage3`, `stage4`, `stage5`
  - Convenience command: `f1-calibrate run-all --compound C3` — chains stages 1→5, detects already-completed stages in SQLite and skips them (resumable)
  - Each stage subcommand can be re-run independently
  - CLI entry point defined in `packages/calibration/pyproject.toml` as `f1-calibrate` console script (Typer-based, mirroring `f1-simulate` pattern from Phase 2)
- **D-02:** Inter-stage parameter handoff via **SQLite only** — each stage writes its fitted params as a row in `parameter_sets` and reads prior-stage params from that same table. **No intermediate TOML/JSON checkpoint files.** Stages query by `(compound, stage_number, is_latest=True)`.

**Training Data Scope**
- **D-03:** Training window is **2022–2024** (three full seasons of the ground-effect era). 2025 excluded at first calibration run. This is a **constant** in the pipeline, not a CLI flag.
- **D-04:** Chronological 80/20 train/validation split: **2022–2023 = training**, **2024 = Stage 5 validation holdout**.
- **D-05:** Compound-specific race filtering:
  - Stages 3–4: train only on stints where the target compound was the assigned Pirelli spec
  - Stages 1–2: train on all races from 2022–2023 regardless of compound (aero + load sensitivity are compound-agnostic)

**Stage 4 JAX Strategy**
- **D-06:** **JAX-native rewrite of Modules F + G** for Stage 4 MCMC only. Reimplemented in `packages/calibration/src/f1_calibration/jax_model.py`. Production NumPy simulation in `packages/core/` is unchanged. F + G together (not F alone) because thermal feeds directly into degradation's `T_tread` input. Stages 1–3 pre-compute `T_tread` and `P_slide` from the full NumPy pipeline; those arrays are passed as **fixed inputs** to the JAX log-likelihood. Stage 4 only samples over 3 parameters: `(β_therm, T_act, k_wear)`.
- **D-07:** PyMC 5.x model with `sample(nuts_sampler="numpyro")`. Full analytical gradients via JAX autodiff. Convergence targets: **r̂ < 1.01 and ESS > 400** (CALIB-04). **SBC and prior predictive checks** run on synthetic data before real fitting.

**Compound Scope**
- **D-08:** **Per-compound independent calibration.** Each `run-all --compound C3` fits one Pirelli compound (C1–C5) from scratch against races where that compound was assigned. **No hierarchical model** across compounds in v1.

### Claude's Discretion

- Specific Typer subcommand grouping, help text, flag names
- PyMC prior distributions for Stage 4 (log-normal vs half-normal vs truncated-normal) — recommended below based on physical bounds
- Stage 4 MCMC hyperparameters (chains, draws, tune) — recommended below
- SQLite schema DDL for `parameter_sets` and `calibration_runs` tables — derived below
- Stage 5 RMSE output format (CSV filename convention, column names)

### Deferred Ideas (OUT OF SCOPE)

- **Hierarchical priors across compounds** (Challenge 4) — deferred to v2
- **Driver aggressiveness coefficient** (Challenge 5) — deferred to v2
- **Track-specific aero corrections** (Challenge 3) — Stage 1 fits one `C_LA` per season
- **2025+ training data** — excluded in v1 (D-03)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CALIB-01 | Stage 1 Aero: fit `C_LA, C_DA, ξ` via `scipy.optimize.least_squares`; ±10% / ±15% / joint-fit tolerance | §Stage 1 algorithm + §Standard Stack scipy.optimize guidance |
| CALIB-02 | Stage 2 Friction: fit `μ₀^fresh, p̄₀, n` from ln(μ_eff) vs ln(p̄) regression on laps 2–5; ±5% / ±0.05 | §Stage 2 algorithm + §Code Examples OLS on log-log scale |
| CALIB-03 | Stage 3 Thermal: fit `T_opt, σ_T, C_tread, C_carc, C_gas, R_tc, R_cg, h_0, h_1, α_p` via constrained optimization on warm-up curves; ±10°C / ±5°C | §Stage 3 algorithm + `least_squares` with bounds |
| CALIB-04 | Stage 4 Degradation: fit `β_therm, T_act, k_wear` via PyMC + NumPyro NUTS; r̂ < 1.01, ESS > 400 | §Stage 4 detailed design + JAX model + MCMC hyperparameter guidance |
| CALIB-05 | Stage 5 Cross-validation: per-lap time RMSE < 0.3s on calibrated compounds, per-circuit breakdown | §Stage 5 RMSE computation + CSV format |
| CALIB-06 | SBC + prior predictive checks run on synthetic data before real fitting | §SBC Implementation + simuk or hand-rolled |
| CALIB-07 | ArviZ NetCDF persistence + SQLite `parameter_sets`/`calibration_runs` versioning with git SHA | §SQLite Schema DDL + §ArviZ NetCDF serialization |
| CALIB-08 | Baseline linear model (lap time vs tire age per stint per compound); physics must beat it on held-out RMSE | §Baseline Linear Model (scikit-learn LinearRegression) |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

Actionable directives the plan MUST honor:

- **Python 3.12 only** (`requires-python = ">=3.12,<3.13"`). Do NOT use 3.13 — JAX GPU wheels + some Numba-dependent nutpie bits are inconsistent on 3.13.
- **Scientific stack pinned:** NumPy 2.1+, SciPy 1.17+, pandas 2.2+.
- **PyMC + NumPyro (JAX backend)** is the chosen sampler path. `sample(nuts_sampler="numpyro")` is the idiomatic call. JAX is CPU-only build (GPU not required for 15–20 params).
- **Do not use `scipy.integrate.odeint`** — SciPy recommends `solve_ivp` for all new code. (Stage 3 may use `solve_ivp` if the thermal warm-up fit needs explicit ODE integration; otherwise the existing `module_f.thermal_step` forward-Euler loop is sufficient and cheaper.)
- **Stan / CmdStanPy is rejected** — adds C++ toolchain to the Docker image for no ESS/s gain over NumPyro at this parameter count.
- **Calibration package imports from `f1_core`, NEVER from `f1_api`.**
- **All param dataclasses are `@dataclass(frozen=True)`** — no mutation. Stage outputs must produce instances of `AeroParams`, `FrictionParams`, `ThermalParams`, `DegradationParams` from `f1_core.physics.params`.
- **Typer-based CLI** mirroring `f1-simulate` — `typer.Typer(invoke_without_command=True)`, subcommand groups, `add_completion=False`, `no_args_is_help=True`.
- **Exception tracebacks at CLI boundary:** catch at boundary, print exception message only (no internal paths). Mirror pattern from `packages/core/src/f1_core/physics/cli.py`.
- **Tests live in `packages/calibration/tests/`** (directory must be created); discovered by root `pyproject.toml` `testpaths`. Uses `--import-mode=importlib` — set `__init__.py` appropriately.
- **GSD workflow:** changes go through planned phase execution.

---

## Summary

Phase 3 delivers a five-stage offline calibration pipeline that fits the Learned parameters of the physics model (roughly 17 parameters per compound) from public FastF1 telemetry. Stages 1–3 use `scipy.optimize.least_squares` with analytical residuals against observables extracted by running the existing NumPy forward model (`run_simulation`) on training stints. Stage 4 uses PyMC 5.x with the NumPyro JAX-NUTS sampler on a 3-parameter Bayesian posterior (`β_therm, T_act, k_wear`) built over a JAX-reimplementation of Modules F + G; Stages 1–3 feed it fixed `T_tread` and `P_slide` trajectories so Stage 4 sees a constrained, well-posed inference. Stage 5 cross-validates against 2024 races, comparing against a `LinearRegression` baseline.

All inter-stage handoff flows through one SQLite file (the same `.data/f1.db` that Phase 4's `/simulate` will read). ArviZ persists the posterior as NetCDF alongside the DB. A resumable `run-all` detects completed stages in SQLite and skips them; `--force` overrides.

**Primary recommendation:** Build a 9-file package (`stage1.py` … `stage5.py`, `jax_model.py`, `compound_map.py`, `db.py`, `baseline.py`, plus `cli.py` and `priors.py`) with a thin `common.py` for SQLite + NetCDF I/O. Pre-verify Stage 4 plumbing with SBC on a 50-draw synthetic dataset before running on real data — SBC catches prior/likelihood mismatch faster than chasing r̂ problems on real races.

---

## Standard Stack

### Core (new dependencies Phase 3 adds)

| Library | Version | Purpose | Why Standard | Source |
|---------|---------|---------|--------------|--------|
| **pymc** | 5.28.4 (latest 2026-04) | Model DSL + sampling orchestration | `sample(nuts_sampler="numpyro")` makes JAX-backed NUTS one keyword away. 5.x has stable PyTensor backend. | `[VERIFIED: pip index versions pymc]` |
| **numpyro** | 0.20.1 (latest 2026-04) | JAX-compiled NUTS sampler backend | ~2.9× ESS/s vs default PyMC on CPU; called automatically via `nuts_sampler="numpyro"`. | `[VERIFIED: pip index versions numpyro]` |
| **jax** | 0.10.0 (latest 2026-04) | Array + autodiff library; compile target for NumPyro | Provides full gradients for NUTS via `jax.grad`. CPU build is enough at 3 params. | `[VERIFIED: pip index versions jax]` |
| **jaxlib** | matches `jax` version | JAX compiled kernels | Required transitive dep of `jax`. | `[CITED: jax.readthedocs.io]` |
| **arviz** | 0.23.4 (stable; 1.0.0 just released) | `InferenceData` + NetCDF + diagnostics (r̂, ESS, rank plots) | Canonical PyMC output format. `to_netcdf()` / `from_netcdf()` is the persistence path. | `[VERIFIED: pip index versions arviz]` |
| **netcdf4** | 1.7.4 (latest) | NetCDF engine (ArviZ `InferenceData.to_netcdf` backend) | Required for NetCDF writing. Pure-Python alternative `h5netcdf` works too. | `[VERIFIED: pip index versions netcdf4]` |
| **scikit-learn** | 1.8.0 (latest 2026-04) | `LinearRegression` for CALIB-08 baseline + sanity regressions | Smallest hammer for the linear baseline. | `[VERIFIED: pip index versions scikit-learn]` |

**Pin versions in `packages/calibration/pyproject.toml`:**

```toml
[project]
name = "f1-calibration"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
    "f1-core",
    "pymc>=5.18,<6",            # NUTS via numpyro backend
    "numpyro>=0.16,<1",         # JAX NUTS
    "jax>=0.4,<1",              # CPU build; no GPU extras
    "arviz>=0.20,<1",           # InferenceData + NetCDF (0.20+ is API-stable)
    "netcdf4>=1.7,<2",          # NetCDF writer engine for to_netcdf()
    "scikit-learn>=1.5,<2",     # Linear baseline (CALIB-08)
    "typer>=0.24,<1",           # CLI (matches f1-core pin)
    "rich>=13",                 # tables/console (matches f1-core pattern)
]

[project.scripts]
f1-calibrate = "f1_calibration.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/f1_calibration"]

[tool.uv.sources]
f1-core = { workspace = true }
```

**Note on versions:** upper-bounds are deliberately generous (`<6`, `<1`, `<2`) because all four libs are still in active minor evolution. Pin floors at tested minimums.

### Supporting (already present in the workspace — reused)

| Library | Version | Purpose | Already pinned in |
|---------|---------|---------|-------------------|
| numpy | >=2.1,<3 | Array math for Stages 1–3 observables | `packages/core/pyproject.toml` |
| scipy | >=1.17,<2 | `scipy.optimize.least_squares` + `scipy.stats` | `packages/core/pyproject.toml` |
| pandas | >=2.2,<3 | FastF1 DataFrame manipulation | `packages/core/pyproject.toml` |
| fastf1 | ==3.8.2 | Training-data ingestion via `load_stint` | `packages/core/pyproject.toml` |
| typer | >=0.24,<1 | CLI | `packages/core/pyproject.toml` |

### Alternatives Considered

| Instead of | Could use | Tradeoff |
|------------|-----------|----------|
| PyMC + NumPyro (D-07) | **nutpie** (Rust NUTS, 0.16.8 latest) | nutpie can edge NumPyro on very small models (ESS/s), but you'd lose the PyMC model-spec DSL **if you called nutpie directly**; via `sample(nuts_sampler="nutpie")` it's a drop-in fallback. Keep as a one-line fallback if NumPyro has gradient issues. `[VERIFIED: pip index versions nutpie]` |
| PyMC + NumPyro | Raw NumPyro | Rejected: you'd rewrite priors in NumPyro syntax; PyMC's DSL is clearer for 17-param physics priors. |
| scipy.optimize.least_squares (Stages 1–3) | scipy.optimize.minimize | `least_squares` exposes Jacobian and returns residuals diagnostic; `minimize` wraps residual SoS into a scalar and loses this. Use `least_squares` for all residual-fit stages. |
| diffrax for Stage 4 thermal ODE | Hand-rolled forward Euler in JAX | **Hand-rolled preferred** because Module F's thermal ODE is already forward Euler at Δt=0.25 s (model_spec §F.7) and numerically stable at the time constants involved. Diffrax's adaptive solvers would add a transitive dep and compile time for no accuracy gain at 4 Hz stepping. Flag diffrax as the upgrade path if Phase 3's forward Euler proves unstable on synthetic data — but the Phase 2 NumPy version passed invariant tests, so this is unlikely. |
| `numpyro.infer.MCMC` directly | `pm.sample(nuts_sampler="numpyro")` | Direct NumPyro path would work for the 3-param posterior but forgoes PyMC's `InferenceData` output and prior-predictive plumbing. Keep the PyMC wrapper. |

**Installation (workspace-local):**
```bash
uv sync --package f1-calibration
```

**Version verification (run at plan-time):**
```bash
pip index versions pymc numpyro jax arviz scikit-learn netcdf4 nutpie
```
Latest captured on 2026-04-23 (from the research session):
- pymc 5.28.4, numpyro 0.20.1, jax 0.10.0, arviz 0.23.4 (1.0.0 released recently), scikit-learn 1.8.0, netcdf4 1.7.4, nutpie 0.16.8 `[VERIFIED: pip index versions ...]`

---

## Architecture Patterns

### Recommended Project Structure

```
packages/calibration/
├── pyproject.toml                               # already present; add deps
├── src/
│   └── f1_calibration/
│       ├── __init__.py                          # already present; keep version string
│       ├── cli.py                               # Typer app — f1-calibrate entry point
│       ├── common.py                            # shared: load_stint iteration, log setup
│       ├── db.py                                # SQLite: parameter_sets + calibration_runs DDL, reads, writes
│       ├── compound_map.py                      # static dict (year, round) -> {SOFT:C5, MED:C4, HARD:C3}
│       ├── training.py                          # iterate 2022–2023 races, build per-compound training sets
│       ├── priors.py                            # PyMC prior builder (derived from make_nominal_params)
│       ├── baseline.py                          # CALIB-08 linear model (sklearn LinearRegression)
│       ├── stage1_aero.py                       # fit C_LA, C_DA, ξ via least_squares
│       ├── stage2_friction.py                   # fit μ₀^fresh, p̄₀, n via log-log regression
│       ├── stage3_thermal.py                    # fit T_opt, σ_T, thermal caps via constrained least_squares
│       ├── jax_model.py                         # JAX-native Modules F + G (D-06) — pure function
│       ├── stage4_degradation.py                # PyMC model using jax_model.log_likelihood + NumPyro sampler
│       ├── sbc.py                               # SBC + prior predictive checks (CALIB-06)
│       ├── stage5_validation.py                 # held-out RMSE, per-circuit CSV, baseline comparison
│       └── run_all.py                           # resumable orchestrator for D-01 run-all command
└── tests/
    ├── __init__.py                              # empty, required for importlib import mode
    ├── conftest.py                              # shared fixtures (synthetic stint, db_path, compound_map_fixture)
    ├── test_db.py                               # DDL round-trip, latest-row query semantics
    ├── test_compound_map.py                     # known-race assertions (Bahrain 2023 = C1/C2/C3)
    ├── test_baseline.py                         # linear model fits known trend
    ├── test_stage1_aero.py                      # synthetic residuals → known C_LA
    ├── test_stage2_friction.py                  # synthetic → known μ₀^fresh, n
    ├── test_stage3_thermal.py                   # synthetic warm-up → known T_opt
    ├── test_jax_model.py                        # parity: jax_model == module_f+g within 1e-6 on sample stint
    ├── test_stage4_degradation.py               # SBC on synthetic → passes; r̂ < 1.01 on 2-chain smoke test
    ├── test_sbc.py                              # simuk or hand-rolled rank-plot uniformity test
    ├── test_stage5_validation.py                # fixture posterior → RMSE < 0.3 s
    ├── test_run_all.py                          # resumability: re-invoking with same (compound, years) no-ops
    └── test_cli.py                              # typer.CliRunner over each stage subcommand
```

### Pattern 1: Stage module signature (consistent across Stages 1–5)

**What:** Every stage exposes a single public function `fit_stageN(...)` that takes an input iterable of training stints and returns a populated stage-specific params dataclass. CLI wraps this.

**When to use:** Every Stage 1–4 module.

**Example:**

```python
# stage1_aero.py
# Source: pattern derived from packages/core/src/f1_core/physics/module_f.py
from __future__ import annotations

from collections.abc import Iterable
import numpy as np
from scipy.optimize import least_squares
from f1_core.physics.params import AeroParams
from f1_core.ingestion.cache import StintArtifact

def fit_stage1(
    stints: Iterable[StintArtifact],
    *,
    prior_mu_grip: float = 1.8,      # from make_nominal_params
) -> tuple[AeroParams, dict[str, float]]:
    """Fit C_LA, C_DA, ξ from max lateral-g at fast corners.

    Returns (fitted AeroParams, diagnostics dict with {rmse, n_corners, residual_max}).
    """
    # 1. Extract residuals per corner from each stint
    # 2. least_squares with bounds: C_LA in [3.0, 7.0], C_DA in [0.8, 1.8], xi in [0.40, 0.50]
    # 3. Pack into AeroParams (preserve K_rf_split, WD, H_CG, BB from nominal)
    ...
```

### Pattern 2: Stage 4 JAX model (D-06) — single pure function

**What:** `jax_model.py` exposes `log_likelihood_f_g(theta, *, fixed_inputs)` as a JAX-traceable pure function. PyMC's `pm.Potential` wraps it.

**When to use:** Stage 4 only.

**Key insight:** The JAX reimplementation of Modules F+G **must be a parity reimplementation** of `f1_core.physics.module_f.thermal_step` and `module_g.degradation_step`. Write a parity test (`test_jax_model.py`) that runs both on the Bahrain 2023 VER stint 2 fixture and asserts the scalar outputs (`mu_0(t)`, mean `T_tread(t)`) match to `1e-6` — this is the single most important correctness guard in Phase 3.

**Example:**

```python
# jax_model.py
# Source: parity with packages/core/src/f1_core/physics/module_f.py and module_g.py
from __future__ import annotations

import jax
import jax.numpy as jnp

# Shape-matching constants from f1_core.physics.constants
_A_TREAD = jnp.array([0.3, 0.3, 0.4, 0.4])   # front, front, rear, rear (m²)
_A_CARC  = jnp.array([0.4, 0.4, 0.5, 0.5])
_H_CARC  = 5.0                                 # W/m²K
_DT      = 0.25                                # s (matches DT_THERMAL)
_T_REF   = 80.0                                # °C (T_REF_AGING)

def _thermal_and_deg_step(
    state,                     # (t_tread, t_carc, t_gas, mu_0, d_tread, e_tire) — jnp arrays
    inputs,                    # (v, t_air, p_total, p_slide) — jnp scalars or (4,)
    thermal_params,            # ThermalParams-equivalent jnp array/tuple
    beta_therm, T_act, k_wear, # sampled
):
    t_tread, t_carc, t_gas, mu_0, d_tread, e_tire = state
    v, t_air, p_total, p_slide = inputs
    C_tread, C_carc, C_gas, R_tc, R_cg, h_0, h_1, alpha_p = thermal_params

    # Module F — thermal (equations §F.1–F.3, jnp-vectorized over 4 tires)
    h_air = h_0 + h_1 * jnp.sqrt(jnp.maximum(v, 0.0))
    q_heat = alpha_p * p_total
    q_conv_tread = h_air * _A_TREAD * (t_tread - t_air)
    q_tc = (t_tread - t_carc) / R_tc
    dT_tread = (q_heat - q_conv_tread - q_tc) / C_tread

    q_conv_carc = _H_CARC * _A_CARC * (t_carc - t_air)
    q_cg = (t_carc - t_gas) / R_cg
    dT_carc = (q_tc - q_conv_carc - q_cg) / C_carc
    dT_gas = q_cg / C_gas

    t_tread_n = t_tread + _DT * dT_tread
    t_carc_n  = t_carc  + _DT * dT_carc
    t_gas_n   = t_gas   + _DT * dT_gas

    # Module G — energy + aging + wear (§G.1–G.3)
    e_tire_n = e_tire + p_total * _DT
    t_tread_mean = jnp.mean(t_tread_n)
    arg = jnp.clip((t_tread_mean - _T_REF) / T_act, -20.0, 20.0)   # Pitfall 4 clamp
    d_mu_0_dt = -beta_therm * mu_0 * jnp.exp(arg)
    mu_0_n = jnp.maximum(mu_0 + _DT * d_mu_0_dt, 0.0)
    d_tread_n = jnp.maximum(d_tread - _DT * k_wear * p_slide, 0.0)

    return (t_tread_n, t_carc_n, t_gas_n, mu_0_n, d_tread_n, e_tire_n)

def simulate_mu_0(
    beta_therm: float,
    T_act: float,
    k_wear: float,
    *,
    t_tread_traj: jnp.ndarray,     # (N, 4) fixed from Stage 3 forward pass
    p_slide_traj: jnp.ndarray,     # (N, 4) fixed from Stage 3 forward pass
    p_total_traj: jnp.ndarray,     # (N, 4)
    mu_0_init: float,
    d_tread_init: jnp.ndarray,     # (4,)
) -> jnp.ndarray:
    """Return (N,) mu_0 trajectory by stepping only the Arrhenius and wear updates.

    Since T_tread is FIXED from Stages 1-3, we only need to step the scalar μ_0
    and per-tire d_tread. This is a 3-parameter scan — ideal for jax.lax.scan.
    """
    def step(carry, step_inputs):
        mu_0, d_tread = carry
        t_tread_row, p_total_row, p_slide_row = step_inputs
        arg = jnp.clip((jnp.mean(t_tread_row) - _T_REF) / T_act, -20.0, 20.0)
        mu_0 = jnp.maximum(mu_0 + _DT * (-beta_therm * mu_0 * jnp.exp(arg)), 0.0)
        d_tread = jnp.maximum(d_tread - _DT * k_wear * p_slide_row, 0.0)
        return (mu_0, d_tread), mu_0

    (_, _), mu_0_traj = jax.lax.scan(
        step, (mu_0_init, d_tread_init),
        (t_tread_traj, p_total_traj, p_slide_traj),
    )
    return mu_0_traj

def log_likelihood_f_g(
    beta_therm, T_act, k_wear,
    *,
    obs_lap_times: jnp.ndarray,    # (L,) observed lap times per-lap, per-stint (flattened)
    lap_boundary_idx: jnp.ndarray, # (L+1,) indices into the 4-Hz traj at lap starts
    t_tread_traj, p_slide_traj, p_total_traj,
    mu_0_init, d_tread_init,
    t_lap_ref, sigma_obs,
):
    """Per-lap Gaussian observation likelihood on delta_t_lap (model_spec §G.4)."""
    mu_0_traj = simulate_mu_0(
        beta_therm, T_act, k_wear,
        t_tread_traj=t_tread_traj, p_slide_traj=p_slide_traj,
        p_total_traj=p_total_traj,
        mu_0_init=mu_0_init, d_tread_init=d_tread_init,
    )
    # Take μ_0 at end of each lap → predicted lap time via G.4
    mu_0_end_of_lap = mu_0_traj[lap_boundary_idx[1:] - 1]
    pred_lap_times = t_lap_ref + 0.5 * t_lap_ref * (mu_0_init - mu_0_end_of_lap) / mu_0_init
    return jnp.sum(-0.5 * ((obs_lap_times - pred_lap_times) / sigma_obs) ** 2)
```

**Key JAX gotchas this pattern avoids:**
- `jax.lax.scan` for the 4-Hz loop — JAX-traceable; Python `for` over 5000+ steps would bloat the compile graph.
- `jnp.clip` on the Arrhenius exponent replicates `module_g.ARRHENIUS_EXP_CLAMP=20.0` (Pitfall 4 in `module_g.py`).
- No NumPy mixing inside the scan — breaks tracing.
- `simulate_mu_0` stepping only scalar `mu_0` + 4-element `d_tread` carries very small state → extremely fast (~ms) per sample.

### Pattern 3: PyMC wrapper (Stage 4)

**What:** PyMC Model block defines priors + deterministic forward pass + likelihood; NumPyro sampler invoked via `nuts_sampler="numpyro"`.

**When to use:** Stage 4 only.

**Example:**

```python
# stage4_degradation.py
# Source: https://www.pymc.io/projects/examples/en/latest/samplers/fast_sampling_with_jax_and_numba.html
from __future__ import annotations

import pymc as pm
import pytensor.tensor as pt
import arviz as az
import numpy as np
from f1_calibration.jax_model import log_likelihood_f_g
from f1_calibration.priors import degradation_prior_centers

def fit_stage4(
    *,
    compound: str,
    fixed_traj: dict,     # t_tread_traj, p_slide_traj, p_total_traj, mu_0_init, d_tread_init, lap_boundary_idx
    obs_lap_times: np.ndarray,
    t_lap_ref: float,
    chains: int = 4,
    draws: int = 1000,
    tune: int = 1000,
    target_accept: float = 0.90,
    random_seed: int = 42,
) -> az.InferenceData:
    centers = degradation_prior_centers(compound)    # from make_nominal_params

    with pm.Model() as model:
        # Priors — log-normal for strictly positive rates (see §Priors)
        beta_therm = pm.LogNormal("beta_therm", mu=np.log(centers["beta_therm"]), sigma=1.0)
        T_act      = pm.LogNormal("T_act",      mu=np.log(centers["T_act"]),      sigma=0.3)
        k_wear     = pm.LogNormal("k_wear",     mu=np.log(centers["k_wear"]),     sigma=1.0)
        sigma_obs  = pm.HalfNormal("sigma_obs", sigma=0.5)   # lap-time obs noise (s)

        # Likelihood — wrap JAX log-likelihood in pm.Potential
        # (for JAX autodiff we need pytensor→jax bridge; see note below)
        loglik = pm.Potential(
            "loglik",
            _wrap_jax_loglik(beta_therm, T_act, k_wear, sigma_obs,
                             obs_lap_times=obs_lap_times, t_lap_ref=t_lap_ref,
                             **fixed_traj),
        )

        idata = pm.sample(
            draws=draws, tune=tune, chains=chains,
            nuts_sampler="numpyro",
            target_accept=target_accept,
            random_seed=random_seed,
            idata_kwargs={"log_likelihood": True},
        )

    # Convergence diagnostics (CALIB-04)
    summary = az.summary(idata, var_names=["beta_therm", "T_act", "k_wear"])
    assert (summary["r_hat"] < 1.01).all(), f"r̂ failed: {summary['r_hat']}"
    assert (summary["ess_bulk"] > 400).all(), f"ESS failed: {summary['ess_bulk']}"
    return idata
```

**The PyTensor→JAX bridge:** For a pure-JAX likelihood to receive gradients via PyMC's NumPyro backend, you can either:
1. Use `pytensor.graph.op.Op` wrapping the JAX function (manual but explicit) — recommended for this project
2. Use `icomo.jax2pytensor` (https://discourse.pymc.io/t/new-package-transforming-jax-to-pytensor-for-odes-and-other-applications/16191) — adds a dep but is cleaner
3. Rewrite the likelihood in pure PyTensor — works but you lose your JAX re-implementation

**Recommendation:** Option 1 (explicit `Op` wrapper using `pytensor.link.jax.dispatch`). The 3-parameter likelihood is simple enough that a custom `Op` is ~40 lines. Keep `icomo` in back pocket if you want to revisit.

### Pattern 4: SQLite schema (CALIB-07, D-02)

**What:** Two tables — `parameter_sets` (every stage writes one row per compound per run) and `calibration_runs` (one row per `run-all` finish).

**When to use:** The schema is the single inter-stage handoff format (D-02).

**DDL:**

```sql
-- db.py: initialize_schema()

CREATE TABLE IF NOT EXISTS parameter_sets (
    parameter_set_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    compound            TEXT    NOT NULL,                    -- C1, C2, C3, C4, C5
    stage_number        INTEGER NOT NULL,                    -- 1, 2, 3, 4, 5
    year_range          TEXT    NOT NULL,                    -- "2022-2024" (D-03)
    created_at          TEXT    NOT NULL,                    -- ISO 8601 UTC
    git_sha             TEXT    NOT NULL,                    -- short sha at run time
    params_json         TEXT    NOT NULL,                    -- serialized AeroParams / FrictionParams / etc.
    is_latest           INTEGER NOT NULL DEFAULT 1,          -- 0/1; updated in a trigger
    diagnostics_json    TEXT,                                -- per-stage fit diagnostics (RMSE, residual max, ESS)
    UNIQUE (compound, stage_number, created_at)
);
CREATE INDEX IF NOT EXISTS ix_parameter_sets_latest
    ON parameter_sets (compound, stage_number, is_latest);

CREATE TABLE IF NOT EXISTS calibration_runs (
    calibration_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    compound              TEXT    NOT NULL,
    year_range            TEXT    NOT NULL,                 -- "2022-2024"
    train_window          TEXT    NOT NULL,                 -- "2022-2023"
    holdout_window        TEXT    NOT NULL,                 -- "2024"
    created_at            TEXT    NOT NULL,                 -- ISO 8601 UTC
    git_sha               TEXT    NOT NULL,
    heldout_rmse_s        REAL    NOT NULL,                 -- per-lap time RMSE on holdout
    baseline_rmse_s       REAL    NOT NULL,                 -- CALIB-08 comparison
    r_hat_max             REAL    NOT NULL,                 -- max across sampled params
    ess_bulk_min          REAL    NOT NULL,                 -- min across sampled params
    netcdf_path           TEXT    NOT NULL,                 -- posteriors/{compound}_2022-2024_{ts}.nc
    param_set_stage1      INTEGER REFERENCES parameter_sets(parameter_set_id),
    param_set_stage2      INTEGER REFERENCES parameter_sets(parameter_set_id),
    param_set_stage3      INTEGER REFERENCES parameter_sets(parameter_set_id),
    param_set_stage4      INTEGER REFERENCES parameter_sets(parameter_set_id),
    stage5_csv_path       TEXT    NOT NULL                  -- .data/validation/stage5_{compound}_{ts}_per_circuit.csv
);

-- Trigger: when a new parameter_sets row lands, demote older rows for same (compound, stage_number)
CREATE TRIGGER IF NOT EXISTS trg_parameter_sets_latest
AFTER INSERT ON parameter_sets
BEGIN
    UPDATE parameter_sets
       SET is_latest = 0
     WHERE compound = NEW.compound
       AND stage_number = NEW.stage_number
       AND parameter_set_id != NEW.parameter_set_id;
END;
```

**DB location:** `.data/f1.db` (local) / `/data/f1.db` (Fly.io). Same file as the Phase 1/2/4 app DB — there is no separate calibration DB (confirmed in CONTEXT.md §code_context).

**DB access pattern:** Use `sqlite3` stdlib — do NOT pull in SQLAlchemy/SQLModel/Alembic just for Phase 3. Alembic is pre-marked as HIGH-confidence in CLAUDE.md for the project, but at Phase 3 the two tables are static and the migrations are one-shot. Phase 4 can introduce Alembic when the same DB needs live API schema management.

### Pattern 5: Resumable run-all orchestrator

**What:** `f1-calibrate run-all --compound C3` walks stages 1→5 in sequence. Before each stage, it queries `parameter_sets` for `(compound, stage_number, year_range="2022-2024", is_latest=1)`. If a row exists and `--force` was not passed, skip that stage.

**Example:**

```python
# run_all.py
def run_all(compound: str, force: bool = False, db_path: Path = DEFAULT_DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        initialize_schema(conn)
        for stage_num, fit_fn in [(1, fit_stage1), (2, fit_stage2), (3, fit_stage3), (4, fit_stage4)]:
            if not force and has_stage_result(conn, compound, stage_num, "2022-2024"):
                log.info(f"Stage {stage_num} already complete for {compound}; skipping (use --force to re-run)")
                continue
            params, diag = fit_fn(...)                    # each stage loads its own training data
            write_parameter_set(conn, compound, stage_num, params, diag)
        # Stage 5 always runs — it's validation, not a fit
        stage5_validation.run(conn, compound)
```

### Anti-Patterns to Avoid

- **Don't re-implement Modules F + G in Python for Stage 4.** D-06 says JAX only. If you hand-roll Python residuals for Stage 4, you lose autodiff and NUTS falls back to slow finite differences.
- **Don't sample over `T_opt`, `σ_T`, `C_tread`, etc. in Stage 4.** Those are Stage 3's responsibility — Stage 4 assumes they are known. Only `β_therm, T_act, k_wear` are sampled (D-06).
- **Don't call `pm.sample(nuts_sampler="numpyro")` without `sample_kwargs={"random_seed": ...}`** in tests. Non-reproducible MCMC tests are flaky — always seed.
- **Don't write intermediate TOML/JSON handoff files** (D-02 forbids).
- **Don't use `scipy.optimize.minimize` for Stages 1–3 residual fits.** `least_squares` with `method='trf'` and explicit bounds is the right tool — it exposes the residual vector for diagnostics.
- **Don't load training data inside every stage.** Load once via `training.iter_training_stints(compound)` and reuse across Stages 2–4.
- **Don't commit ArviZ NetCDF posteriors to git.** Add `.data/posteriors/` to `.gitignore`. The SQLite DB stores the file path; the file itself is a build artifact.
- **Don't run real-data Stage 4 before SBC passes on synthetic data** (CALIB-06). SBC is the cheapest debugger for prior/likelihood mismatch.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| NUTS sampler | Custom MCMC/Metropolis-Hastings | `pm.sample(nuts_sampler="numpyro")` | NUTS with dual averaging and mass matrix adaptation is decades of research. NumPyro's JAX version is ~3× faster than default PyMC. |
| Posterior diagnostics (r̂, ESS) | Manual Gelman-Rubin or autocorrelation math | `arviz.summary` (returns both) | Gelman-Rubin has 3 variants, split vs non-split, rank-normalized vs not; ArviZ uses the 2021 Vehtari rank-normalized version. |
| NetCDF serialization | Manual xarray + netcdf4 plumbing | `idata.to_netcdf()` / `az.from_netcdf()` | One-liner; preserves groups. |
| JAX ODE solver | Manual RK4 for Module F in JAX | **Use forward Euler (matches module_f.thermal_step)** | Module F in NumPy is already forward Euler at Δt=0.25 s (§F.7); the JAX rewrite should match for parity. If accuracy becomes an issue, swap to `diffrax.diffeqsolve` — not before. |
| Linear regression (baseline) | Manual normal equations | `sklearn.linear_model.LinearRegression` | CALIB-08 needs one baseline per (compound, stint); LinearRegression handles multicollinearity, is batch-fittable, and returns RMSE straightforwardly. |
| SBC rank-plot computation | Manual histogram of rank statistics | `simuk` (PyPI) or `arviz.plot_rank` | simuk supports PyMC natively, returns diagnostic plots, and is the 2026-standard SBC tool (by ArviZ team). |
| Pirelli compound mapping from race name | Regex scraping Pirelli press releases | **Static dict committed in `compound_map.py`** | FastF1 does NOT expose C1–C5; the Compound column is only SOFT/MEDIUM/HARD. Build the (year, round) → {SOFT:C5, MED:C4, HARD:C3} mapping once from Pirelli press releases; commit it. See §Runtime State Inventory. `[CITED: github.com/theOehrly/Fast-F1/issues/332]` |
| SQLite migrations | Alembic | Plain `CREATE TABLE IF NOT EXISTS` + version constant | Two-table schema, one owner, no live migrations yet. Alembic is the right upgrade when Phase 4 adds API-facing schema. |

**Key insight:** The calibration spec document (`model_calibration_strategy.html` §Part VI) lists the exact libraries. Every choice in the Standard Stack table above is a direct mapping from that spec. Don't invent alternatives.

---

## Runtime State Inventory

Phase 3 is a **greenfield implementation** — there is no prior calibration state to migrate. However, the phase creates **new** runtime state that subsequent phases will depend on. Verify all five categories before planning:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | New: `.data/f1.db` gains `parameter_sets` + `calibration_runs` tables. New: `.data/posteriors/{compound}_2022-2024_{timestamp}.nc` ArviZ NetCDF files. New: `.data/validation/stage5_{compound}_{timestamp}_per_circuit.csv`. **FastF1 cache is existing** from Phase 1 (`.data/fastf1_cache/`) — Phase 3 iterates over it for 2022–2024 races. | Ship SQLite DDL in `db.py`. Add `.data/posteriors/` and `.data/validation/` to `.gitignore` (these are build artifacts, not source). Verify FastF1 cache is warm for all 2022–2024 races before first `run-all`. |
| **Live service config** | None. Phase 3 is an offline CLI — there is no deployed service at this stage. | None — verified by reviewing ROADMAP (deployment is Phase 7). |
| **OS-registered state** | None. No cron / Task Scheduler / systemd unit is created by Phase 3. | None. Calibration is manually invoked. (v2 may add a scheduled re-calibration job; deferred.) |
| **Secrets / env vars** | None *new*. `F1_CACHE_DIR` (existing from Phase 1) is honored for the FastF1 layer. `F1_DB_PATH` (new, optional) may point to an alternate SQLite file — default is `.data/f1.db`. | Document `F1_DB_PATH` in the CLI help if introduced; default to `.data/f1.db`. No secret material is created. |
| **Build artifacts / installed packages** | New install of `pymc`, `numpyro`, `jax`, `jaxlib`, `arviz`, `netcdf4`, `scikit-learn` into the uv workspace. Transitive deps (pytensor, xarray, filelock, cloudpickle) land automatically. `uv.lock` will change. **JAX compile cache** will appear at `~/.cache/jax/` on first Stage 4 run — harmless. | After adding deps, run `uv sync --package f1-calibration` to update `uv.lock`. First Stage 4 run is ~30s slower due to JAX compilation; document this in the CLI output. |

**Nothing found in OS-registered state / Live service config / Secrets categories — verified by reviewing ROADMAP.md (calibration is offline CLI; deployment is Phase 7) and absence of any cron/systemd/Task Scheduler trigger in the CONTEXT.md specs.**

---

## Common Pitfalls

### Pitfall 1: NumPyro compilation blocks first run for ~30 seconds
**What goes wrong:** Running `f1-calibrate stage4 --compound C3` for the first time on a machine, the user sees no output for 30–60 s while JAX traces and compiles the scan loop. Appears to hang.
**Why it happens:** JAX compiles the traced log-likelihood + NUTS gradient on first call. Subsequent calls on the same machine hit the JAX persistent compile cache.
**How to avoid:**
- Print an explicit "Compiling JAX model (one-time, ~30s)..." message before the first sample call.
- In tests, use a tiny synthetic stint (50 samples) so compilation is fast.
- Set `jax.config.update("jax_enable_x64", True)` explicitly — default is x32 which will *silently* diverge from the NumPy parity test.
**Warning signs:** Stage 4 parity test passes but r̂ blows up only on real data → check x64 is enabled.

### Pitfall 2: Stage 3's thermal ODE is stiff
**What goes wrong:** Fitting `C_tread`, `C_carc`, `C_gas`, `R_tc`, `R_cg` jointly can drive the optimizer into parameter combinations where the thermal time constant `τ = C·R` is very small, making forward Euler blow up.
**Why it happens:** `τ = C_tread · R_tc`. If the optimizer tries `C_tread = 500 J/K` (way below nominal 6000) and `R_tc = 0.001 K/W`, `τ = 0.5 s` — below the 0.25 s Δt. Forward Euler oscillates.
**How to avoid:**
- Use `least_squares` with **lower bounds** on thermal capacities: `C_tread >= 2000 J/K`, `C_carc >= 8000 J/K`, `C_gas >= 200 J/K`, `R_tc >= 0.005 K/W`.
- As a secondary safety, check `min(τ)` in the residual function and return a penalty if `τ < 2 · Δt = 0.5 s`.
- Stage 3 can optionally switch to `scipy.integrate.solve_ivp(method='Radau')` for the warm-up curve integration — BUT only if the residual function needs higher accuracy than the production forward-Euler loop. Start with Euler to match `module_f.thermal_step`; escalate only on measurable fit-quality problems.
**Warning signs:** Stage 3 residual NaN or T_tread > 10000°C at best-fit — tighten bounds.

### Pitfall 3: Parameter degeneracy in Stage 4 (from calibration spec Challenge 2)
**What goes wrong:** `β_therm` and `T_act` are partially degenerate — increasing both can match lap-time evolution. Posterior shows high correlation between them, wide credible intervals despite r̂ OK.
**Why it happens:** `dμ_0/dt = −β_therm · μ_0 · exp((T_tread − T_ref)/T_act)`. At a fixed observed degradation rate, `β_therm` and `T_act` are anti-correlated.
**How to avoid:**
- Use **informative priors** on both: `T_act ~ LogNormal(log(25), 0.3)` — tight, since model_spec says "≈ 25 °C".
- After sampling, check `arviz.plot_pair` — high rank correlation between `β_therm` and `T_act` is the signal. Report it in diagnostics.
- If degeneracy is severe, fix `T_act = 25` and sample only `β_therm, k_wear` (2-param posterior). Spec permits this.
**Warning signs:** r̂ < 1.01 BUT credible intervals on `β_therm` span 2 orders of magnitude.

### Pitfall 4: Stage 5 RMSE dominated by outlier laps (SC/VSC, traffic)
**What goes wrong:** A single safety-car lap adds 30–60 s to observed lap time; physics predicts the clean time; RMSE explodes.
**Why it happens:** Phase 1's `data_integrity.py` flags SC/VSC laps but the calibration engineer must *actually exclude them* from the Stage 5 RMSE computation.
**How to avoid:**
- Stage 5's lap iteration MUST apply the same lap-exclusion filter as Phase 1's calibration dataset builder (see `DATA-05` / `DATA-06`).
- After computing RMSE, **also report** MAD (median absolute deviation) — robust to outliers; if RMSE >> MAD, the quality filter is letting outliers through.
**Warning signs:** RMSE > 2 s but median lap-time error < 0.3 s.

### Pitfall 5: ArviZ NetCDF file grows huge if `idata_kwargs={"log_likelihood": True}` on a long stint
**What goes wrong:** Storing per-lap log-likelihood matrices for 20 training races × 4 stints × 30 laps × 4000 posterior draws → 100s of MB per compound.
**Why it happens:** Default NetCDF compression is gzip — sometimes it's compute-slow. Without it the file is O(draws × observations).
**How to avoid:**
- Use `idata.to_netcdf(path, compress=True)` (default).
- Include log-likelihood only if PSIS-LOO or WAIC is desired; otherwise skip: `idata_kwargs={"log_likelihood": False}`.
- For v1, **don't store log-likelihood in NetCDF** — compute it on-demand if WAIC is needed later.
**Warning signs:** NetCDF file > 100 MB per compound → drop log-likelihood group.

### Pitfall 6: Typer global `--compound` on `run-all` but per-stage subcommands take it as an argument
**What goes wrong:** Inconsistent flag vs arg forms across subcommands create confusion — `f1-calibrate stage1 C3` vs `f1-calibrate stage1 --compound C3`.
**How to avoid:** Pick one form and stick with it. Recommendation: **always a flag** — `--compound C3` everywhere. Phase 2's `f1-simulate` uses positional args because the input is naturally tuple-like (year, event, driver, stint); calibration's `--compound` is a categorical filter, not a positional.
**Warning signs:** Tests use one form, docs use another.

### Pitfall 7: SBC on synthetic data uses priors instead of full prior-predictive
**What goes wrong:** Rolling "synthetic data" by sampling priors and then sampling posteriors without running the forward model — SBC passes trivially because it's testing the prior against itself.
**Why it happens:** SBC requires synthetic data drawn from the *joint* (prior × likelihood), not the marginal prior.
**How to avoid:**
- Use `simuk` (PyPI) — it enforces the correct joint-sampling loop.
- If hand-rolling: for each of N trials, sample `θ ~ prior`, then generate `y | θ` through the *forward* model, then fit `θ | y` and record the rank of true θ in the posterior.
- A uniform rank distribution across trials is the test. Use ≥ 50 trials for reasonable power.
**Warning signs:** SBC rank plot is *too* uniform (near-perfect) on a toy model — likely bypassing the forward step.

---

## Code Examples

### Stage 1 — Aero fit (residual shape)

```python
# stage1_aero.py
# Source: scipy.optimize.least_squares — https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html
import numpy as np
from scipy.optimize import least_squares

def _residuals(
    theta: np.ndarray,               # (3,): C_LA, C_DA, xi
    obs_corner_lat_g: np.ndarray,    # (K,) observed max lat g at K corners
    v_at_corner: np.ndarray,         # (K,) speed through corner
    mu_grip_prior: float,            # 1.8, from model_spec §Stage 1
    M_total: float,                  # 798 + fuel estimate
    rho_air: float = 1.20,
) -> np.ndarray:
    C_LA, C_DA, xi = theta           # noqa: ARG001 — xi enters via Stage 3 joint fit
    F_aero = 0.5 * rho_air * C_LA * v_at_corner**2
    predicted_lat_g = mu_grip_prior * (9.81 * M_total + F_aero) / (9.81 * M_total)
    return obs_corner_lat_g - predicted_lat_g

def fit_stage1(obs_corner_lat_g, v_at_corner, M_total):
    x0 = np.array([4.5, 1.1, 0.45])          # from make_nominal_params()
    bounds = ([3.0, 0.8, 0.40], [7.0, 1.8, 0.50])
    result = least_squares(
        _residuals, x0, bounds=bounds, method='trf',
        args=(obs_corner_lat_g, v_at_corner, 1.8, M_total),
    )
    rmse = np.sqrt(np.mean(result.fun**2))
    return AeroParams(
        C_LA=float(result.x[0]), C_DA=float(result.x[1]), xi=float(result.x[2]),
        # Keep nominal for semi-constrained fields (not fit here)
        K_rf_split=0.55, WD=0.445, H_CG=0.28, BB=0.575,
    ), {"rmse": float(rmse), "n_corners": len(obs_corner_lat_g)}
```

### Stage 2 — Friction log-log regression

```python
# stage2_friction.py
# Source: model_calibration_strategy.html §Stage 2
import numpy as np
from f1_core.physics.params import FrictionParams

def fit_stage2(mu_eff_samples: np.ndarray, p_bar_samples: np.ndarray):
    """Regress ln(μ_eff) on ln(p̄). Slope = -(1-n), intercept gives μ₀ at p̄=1."""
    log_mu = np.log(mu_eff_samples)
    log_p = np.log(p_bar_samples)
    slope, intercept = np.polyfit(log_p, log_mu, 1)
    n_fit = 1.0 + slope                          # slope = -(1-n) => n = 1+slope
    p_bar_0_choice = float(np.median(p_bar_samples))
    mu_0_fresh = float(np.exp(intercept + slope * np.log(p_bar_0_choice)))
    return FrictionParams(
        mu_0_fresh=mu_0_fresh, p_bar_0=p_bar_0_choice, n=float(n_fit),
        c_py=1.0e8, K_rad=250_000.0,
    )
```

### Stage 4 — Full PyMC + NumPyro model

See Pattern 3 above. Full code with PyTensor JAX `Op` wrapper belongs in `stage4_degradation.py`.

### SBC loop (CALIB-06)

```python
# sbc.py
# Source: arviz-devs/simuk — https://github.com/arviz-devs/simuk
from simuk import SBC
import pymc as pm

def run_sbc(build_model_fn, *, n_simulations: int = 50, seed: int = 42) -> dict:
    """Run SBC and return diagnostics dict {uniformity_p: float, rank_array: np.ndarray}.

    build_model_fn is a zero-arg callable that returns a fresh pm.Model
    — simuk repeatedly samples priors + simulates + fits.
    """
    sbc = SBC(
        model=build_model_fn(),
        num_simulations=n_simulations,
        sample_kwargs={"draws": 500, "tune": 500, "chains": 2,
                       "nuts_sampler": "numpyro", "progressbar": False},
        random_seed=seed,
    )
    sbc.run_simulations()
    # simuk's plot_ecdf returns a matplotlib Figure; we just check uniformity
    ranks = sbc.simulations["rank"]        # (n_simulations, n_params)
    return {"ranks": ranks, "uniformity_ok": _check_uniform(ranks)}
```

### ArviZ NetCDF round-trip

```python
# Persist posterior
import arviz as az
idata.to_netcdf(".data/posteriors/C3_2022-2024_20260423T143500Z.nc", compress=True)

# Load later (Phase 4 usage)
idata = az.from_netcdf(".data/posteriors/C3_2022-2024_20260423T143500Z.nc")
posterior_mean = idata.posterior[["beta_therm", "T_act", "k_wear"]].mean()
```

### Baseline linear model (CALIB-08)

```python
# baseline.py
from sklearn.linear_model import LinearRegression
import numpy as np

def fit_baseline_per_stint(tire_ages: np.ndarray, lap_times_s: np.ndarray) -> dict:
    """Fit lap_time = a·age + b per stint. Return RMSE over all stints."""
    X = tire_ages.reshape(-1, 1)
    y = lap_times_s
    model = LinearRegression().fit(X, y)
    rmse = float(np.sqrt(np.mean((model.predict(X) - y) ** 2)))
    return {"slope_s_per_lap": float(model.coef_[0]),
            "intercept_s": float(model.intercept_), "rmse_s": rmse}
```

### SQLite writer

```python
# db.py
import json, sqlite3, subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(".data/f1.db")

def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=Path(__file__).parent).decode().strip()
    except Exception:
        return "unknown"

def write_parameter_set(conn, compound, stage_number, params_dc, diagnostics: dict,
                        year_range: str = "2022-2024") -> int:
    row = {
        "compound": compound, "stage_number": stage_number, "year_range": year_range,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": _git_sha(),
        "params_json": json.dumps(asdict(params_dc)),
        "is_latest": 1,
        "diagnostics_json": json.dumps(diagnostics),
    }
    cur = conn.execute(
        "INSERT INTO parameter_sets (compound, stage_number, year_range, created_at, "
        "git_sha, params_json, is_latest, diagnostics_json) VALUES "
        "(:compound, :stage_number, :year_range, :created_at, :git_sha, :params_json, "
        ":is_latest, :diagnostics_json)", row)
    conn.commit()
    return cur.lastrowid
```

---

## State of the Art

| Old Approach | Current (2026) Approach | When Changed | Impact |
|--------------|-------------------------|--------------|--------|
| `scipy.integrate.odeint` | `scipy.integrate.solve_ivp` | SciPy 1.0+ | odeint still works but explicitly legacy. solve_ivp has method='Radau' for stiff systems — useful for Stage 3 if warm-up ODE fit becomes stiff. |
| PyMC default CPU sampler | `pm.sample(nuts_sampler="numpyro")` | PyMC 5.0+ | ~2.9× ESS/s on CPU; 1-line opt-in. Standard for 2024+. |
| Custom Stan via CmdStanPy | PyMC+NumPyro | PyMC 5.x maturity | Removes C++ toolchain dep; comparable ESS/s at small param counts. |
| Pydantic v1 | Pydantic v2 | FastAPI 0.100+ | 5–50× validation speedup. Phase 4 uses v2; Phase 3 doesn't need Pydantic. |
| ArviZ 0.14 API | ArviZ 0.20+ (1.0 just released 2026-04) | 2024+ | 0.20's `InferenceData` API is stable; 1.0.0 is API-compat. Pin `arviz>=0.20,<1` initially; upgrade to `>=1,<2` after 1.0 shakes out. |

**Deprecated/outdated:**
- **`scipy.integrate.odeint`** — avoid for new code (CLAUDE.md explicit constraint).
- **`pm.fit(method="advi")`** — still present in PyMC 5.x, but variational inference gives less accurate uncertainty tails than NUTS. Keep as a fallback for Stage 4 only if NUTS exceeds patience budget. (CLAUDE.md mentions this as an escape hatch.)
- **`pymc3`** — predecessor to pymc 5.x. Incompatible API.

---

## Assumptions Log

> Claims the plan / discussion may need to confirm with the user before finalizing.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `icomo` / custom PyTensor `Op` wrapper is the right JAX-PyMC bridge for the 3-param likelihood | §Pattern 3 | `[ASSUMED]` — icomo is MEDIUM confidence (newer community package). Fallback: rewrite the likelihood in pure PyTensor (same ESS/s via numpyro backend, just loses the `jax_model.py` parity guarantee). |
| A2 | `chains=4, draws=1000, tune=1000, target_accept=0.90` hits r̂ < 1.01 and ESS > 400 for the 3-param posterior | §Pattern 3 | `[ASSUMED]` — this is *typical* for simple posteriors but parameter degeneracy (Pitfall 3) could force `target_accept=0.95` and `tune=2000`. Validate on SBC first; tune up if ESS is low. |
| A3 | The compound map can be constructed manually from Pirelli press releases for 2022–2024 (≈ 66 races) | §Runtime State + compound_map.py | `[ASSUMED: based on FastF1 github issue #332]` — confirmed FastF1 does not expose C1–C5. Manual construction is ~2 hours of work (Pirelli publishes a press release per race). Alternative source: motorsportstats.com or f1technical.net. If Pirelli changes naming mid-season, the dict needs a "valid_from_round" field. |
| A4 | Stage 4 log-likelihood is Gaussian on per-lap-time residuals with a HalfNormal prior on `sigma_obs` | §Pattern 3 | `[ASSUMED]` — alternatives: Student-t (robust to outliers), or the spec's own formulation if it differs. model_calibration_strategy.html §Stage 4 doesn't explicitly prescribe a likelihood form. The Gaussian choice should be validated via posterior-predictive check. |
| A5 | `run-all` detects completed stages by `(compound, stage_number, year_range="2022-2024")` uniqueness | §Pattern 5 | `[ASSUMED]` per D-02; confirm that "same year_range string" is the correct resumability key (vs. git_sha match — i.e., should a code change auto-invalidate?). Recommended: match on year_range only, print git_sha of stored row, let `--force` override. |
| A6 | First-call JAX compile latency is acceptable (~30s) even in `run-all` mode | §Pitfall 1 | `[ASSUMED]`. JAX persistent compile cache helps on subsequent runs. If compile time is unacceptable, switch to `nuts_sampler="nutpie"` (Rust, faster first-compile). |
| A7 | SBC with 50 simulations is statistically adequate for 3-parameter posterior | §Pitfall 7 + sbc.py | `[CITED: simuk readthedocs]` — simuk docs use 100 for full coverage but 50 is routine for pre-flight checks. Raise to 100 if any param shows non-uniform ranks. |
| A8 | Stage 4 only samples `β_therm, T_act, k_wear` (not also `σ_obs`) as "model parameters" | §D-06, §Pattern 3 | `[ASSUMED: per D-06]`. The code pattern samples `sigma_obs` as an auxiliary (nuisance) parameter; that's standard. If the project wants `sigma_obs` tracked in the InferenceData as a "learned" param reported to users, keep the pattern; if not, mark it as deterministic or fix it. |

**If this table has entries:** The planner / `/gsd-discuss-phase` round should surface these to the user before locking implementation decisions.

---

## Open Questions

1. **Should Stage 4 fix `T_act = 25` (from model_spec §G.2 "typical values") and sample only 2 params?**
   - What we know: model_spec explicitly says `T_act ≈ 25 °C` is typical; Pitfall 3 flags `β_therm ↔ T_act` degeneracy.
   - What's unclear: whether the v1 calibration *must* produce a data-driven `T_act` or accepts the literature prior.
   - Recommendation: start with all 3 sampled; if SBC flags non-identifiability, fix `T_act` for the release and document in the Assumptions Log.

2. **How do we handle compounds that appear in only 2–3 races per season (C1, C5 at the extremes)?**
   - What we know: Pirelli doesn't bring C1 or C5 to every race; some seasons they appear at 3–4 events.
   - What's unclear: whether the calibration aborts with a "too few training stints" error, or fits with a warning, or falls back to nominal priors.
   - Recommendation: emit a structured warning and a diagnostic "n_stints = K" field in `parameter_sets.diagnostics_json`. Abort only if K < 5.

3. **Does Stage 5's held-out RMSE comparison need to account for the baseline's free parameters too?**
   - What we know: CALIB-08 says "linear baseline (lap time vs tire age per stint per compound)" — per-stint intercept + slope. CALIB-05 says "physics must achieve meaningfully lower RMSE".
   - What's unclear: "meaningfully lower" — 10%? 20%? Statistical significance via bootstrap?
   - Recommendation: report both as absolute RMSE in seconds and relative improvement percentage. Leave "meaningful" to human review — Phase 3 verifier can eyeball it.

4. **Where does the Phase 3 code update the `calibration_runs` table when `run-all` is resumed mid-run?**
   - What we know: a `run-all` interrupted mid-Stage-4 leaves `parameter_sets` rows for stages 1–3 but no `calibration_runs` row (which needs `heldout_rmse_s` from Stage 5).
   - What's unclear: whether the re-invoked `run-all` can skip stages 1–3 using the saved rows and only run 4 + 5.
   - Recommendation: yes — resumability MUST work at stage granularity (D-02 implies this). Plan this in the `run_all.py` design.

---

## Environment Availability

> Phase 3 depends only on Python packages installable via `uv sync`. No external services.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Runtime | ✓ | 3.12.0 | — (3.11/3.13 NOT supported per CLAUDE.md) |
| uv | Workspace deps | ✓ | existing | — |
| git CLI | `_git_sha()` in `db.py` | ✓ | existing | "unknown" string literal fallback already in code pattern |
| FastF1 cache (warm) | Stage 1–4 training data | ✗ (likely cold for 2022–2024 range) | — | Phase 3 plan should include a "pre-warm cache" step before full run-all |
| SQLite 3 stdlib | DB | ✓ | ships with Python | — |
| Internet access to Jolpica/Pirelli | First cache warm + compound_map sanity check | required once | — | Pre-warm cache once, then fully offline |

**Missing dependencies with fallback:** None — all new Python deps install from PyPI.

**Missing dependencies with no fallback:** First-run Jolpica access to warm FastF1 cache for 2022–2024 races. Plan should include a "pre-calibration ingestion" task that fetches all training-window races (~66 sessions) in parallel.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8+ with pytest-cov 5+, hypothesis 6+ (root `pyproject.toml` `[dependency-groups].dev`) |
| Config file | root `pyproject.toml` `[tool.pytest.ini_options]` — already includes `packages/calibration/tests` in `testpaths` |
| Quick run command | `uv run pytest packages/calibration/tests -x --tb=short` |
| Full suite command | `uv run pytest` (root; covers core + api + calibration) |

**Wave 0 framework gap:** `packages/calibration/tests/` directory does not yet exist. Plan must create it with `__init__.py` + `conftest.py` before Stage 1 tests can run.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| CALIB-01 | Stage 1 fits C_LA within ±10 % on synthetic corner data | unit | `uv run pytest packages/calibration/tests/test_stage1_aero.py -x` | ❌ Wave 0 |
| CALIB-02 | Stage 2 fits μ₀^fresh within ±5 % on synthetic log-log data | unit | `uv run pytest packages/calibration/tests/test_stage2_friction.py -x` | ❌ Wave 0 |
| CALIB-03 | Stage 3 fits T_opt within ±10 °C on synthetic warm-up curve | unit | `uv run pytest packages/calibration/tests/test_stage3_thermal.py -x` | ❌ Wave 0 |
| CALIB-04 | Stage 4 MCMC r̂ < 1.01, ESS > 400 on SBC synthetic (smoke = 2 chains, 200 draws) | integration | `uv run pytest packages/calibration/tests/test_stage4_degradation.py -x -m integration` | ❌ Wave 0 |
| CALIB-04 | jax_model parity with module_f + module_g within 1e-6 | unit | `uv run pytest packages/calibration/tests/test_jax_model.py::test_parity -x` | ❌ Wave 0 |
| CALIB-05 | Stage 5 per-lap RMSE reported; per-circuit CSV written | integration | `uv run pytest packages/calibration/tests/test_stage5_validation.py -x` | ❌ Wave 0 |
| CALIB-06 | SBC rank uniformity test passes on 50 synthetic trials | integration | `uv run pytest packages/calibration/tests/test_sbc.py -x -m integration` | ❌ Wave 0 |
| CALIB-07 | SQLite DDL round-trip: write params, read latest, match | unit | `uv run pytest packages/calibration/tests/test_db.py -x` | ❌ Wave 0 |
| CALIB-07 | NetCDF round-trip: posterior → file → load → same values | unit | `uv run pytest packages/calibration/tests/test_stage4_degradation.py::test_netcdf_roundtrip -x` | ❌ Wave 0 |
| CALIB-08 | Linear baseline fits synthetic line; RMSE > physics on synthetic stint | unit | `uv run pytest packages/calibration/tests/test_baseline.py -x` | ❌ Wave 0 |
| — | CLI: `f1-calibrate stage1 --compound C3` via typer.CliRunner on tiny fixture | integration | `uv run pytest packages/calibration/tests/test_cli.py -x` | ❌ Wave 0 |
| — | run-all resumability: second invocation with same args no-ops except Stage 5 | integration | `uv run pytest packages/calibration/tests/test_run_all.py::test_resumability -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest packages/calibration/tests -x --tb=short -m "not integration"` (unit tests only — subsecond feedback)
- **Per wave merge:** `uv run pytest packages/calibration/tests -x` (full suite including integration)
- **Phase gate:** `uv run pytest` (root — covers regressions in core + api)

### Wave 0 Gaps

- [ ] `packages/calibration/tests/__init__.py` — required for `--import-mode=importlib`
- [ ] `packages/calibration/tests/conftest.py` — shared fixtures:
    - `synthetic_stint` — 50-sample artifact with known ground-truth params
    - `tmp_db_path` — fresh SQLite file per test
    - `mini_compound_map` — subset dict for tests
- [ ] `packages/calibration/src/f1_calibration/__init__.py` — already present, keep
- [ ] Dependencies install: update `packages/calibration/pyproject.toml` per §Standard Stack, then `uv sync --package f1-calibration`
- [ ] JAX compile cache warm-up step for CI — first Stage 4 test will be ~30 s

**Pytest markers to configure:**
```toml
[tool.pytest.ini_options]
markers = [
    "integration: marks slow integration tests requiring full MCMC (deselect with '-m \"not integration\"')",
]
```

---

## Security Domain

Phase 3 is an offline CLI writing to the local workspace; attack surface is narrow but non-zero.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | — (no users; single-user CLI) |
| V3 Session Management | no | — |
| V4 Access Control | no | — (local filesystem only) |
| V5 Input Validation | **yes** | `--compound` must match `^C[1-5]$`; path arguments constrained to `.data/**` |
| V6 Cryptography | no | — (no secrets; git SHA is public) |
| V10 Malicious Code | **yes** | ArviZ NetCDF load is deserialization — use `az.from_netcdf(path)` on **trusted files only** (files this codebase wrote) |
| V12 File & Resource | **yes** | SQLite path + NetCDF path both must be inside `.data/` — no arbitrary filesystem writes |
| V14 Configuration | **yes** | `F1_DB_PATH` env var, if introduced, must resolve under the workspace root |

### Known Threat Patterns for offline-Python-CLI

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Argument injection into `compound` arg → SQL injection | Tampering | Always use parameterized queries (`conn.execute(sql, dict)`, never f-strings); validate `compound` matches `^C[1-5]$` before first DB op |
| Pickle / NetCDF deserialization of untrusted file | Tampering + Code Exec | Only load NetCDFs whose paths are returned by `calibration_runs.netcdf_path` — never user-supplied |
| Path traversal via `F1_DB_PATH` env var | Tampering | Resolve to absolute path, assert it's inside the workspace root, reject symlinks to `/` |
| Accidental commit of NetCDF posterior (large binary in git) | Information Disclosure + Repo Bloat | Add `.data/posteriors/*.nc` to `.gitignore` as part of the foundation plan for Phase 3 |
| Exception traceback leaks filesystem paths | Information Disclosure | Match Phase 2 CLI pattern: catch at CLI boundary, print `str(exc)` only, no `traceback.print_exc()` |
| Git SHA leak via `_git_sha()` calling `subprocess` with tainted PATH | Tampering | `subprocess.check_output(["git", ...], cwd=known_path)` — no shell=True, no string interpolation |

**No new secrets are introduced by Phase 3.** The git SHA stored in `calibration_runs` is public repository metadata.

---

## Sources

### Primary (HIGH confidence)

- `packages/core/src/f1_core/physics/params.py` — frozen dataclass definitions (must be produced by stages)
- `packages/core/src/f1_core/physics/defaults.py` — `make_nominal_params()` prior centers for Stage 4
- `packages/core/src/f1_core/physics/module_f.py` — canonical NumPy Module F (parity target for `jax_model.py`)
- `packages/core/src/f1_core/physics/module_g.py` — canonical NumPy Module G (parity target)
- `packages/core/src/f1_core/physics/cli.py` — Typer pattern to mirror
- `model_calibration_strategy.html` — Authoritative Stage 1–5 methods, challenges, software stack
- `model_spec.md` §Module F, §Module G, §G.4 (lap-time penalty)
- `CLAUDE.md` — pinned versions, rejected libraries, PyMC+NumPyro guidance
- `.planning/phases/03-bayesian-calibration-pipeline/03-CONTEXT.md` — decisions D-01 through D-08
- `.planning/REQUIREMENTS.md` §CALIB-01 through §CALIB-08 — acceptance criteria
- PyPI registry (verified 2026-04-23 via `pip index versions`) for latest package versions

### Secondary (MEDIUM confidence — official docs via WebSearch)

- [pymc.sampling.jax.sample_numpyro_nuts — PyMC docs](https://www.pymc.io/projects/docs/en/stable/api/generated/pymc.sampling.jax.sample_numpyro_nuts.html) — NumPyro backend kwargs
- [Faster Sampling with JAX and Numba — PyMC example gallery](https://www.pymc.io/projects/examples/en/latest/samplers/fast_sampling_with_jax_and_numba.html) — `nuts_sampler="numpyro"` idiom
- [simuk (ArviZ-devs) — SBC for PyMC](https://github.com/arviz-devs/simuk) — canonical SBC implementation for CALIB-06
- [arviz.InferenceData.to_netcdf docs](https://python.arviz.org/en/stable/api/generated/arviz.InferenceData.to_netcdf.html) — NetCDF round-trip API
- [arviz.from_netcdf docs](https://python.arviz.org/en/stable/api/generated/arviz.from_netcdf.html)
- [SciPy `solve_ivp` reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html) — Stage 3 fallback if forward Euler stiffs out
- [SciPy `least_squares` reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html) — Stage 1–3 fitter
- [Diffrax docs](https://docs.kidger.site/diffrax/) — alternative ODE solver in JAX (deferred)

### Tertiary (LOW confidence — community, needs validation)

- [FastF1 issue #332 — underlying compound info](https://github.com/theOehrly/Fast-F1/issues/332) — confirms FastF1 does not expose C1–C5 (supports manual `compound_map.py`)
- [PyMC-Labs: ODE Solvers, Neural Networks & Custom Ops](https://www.pymc-labs.com/blog-posts/jax-functions-in-pymc-3-quick-examples) — patterns for JAX-in-PyMC
- [icomo — jax2pytensor bridge](https://discourse.pymc.io/t/new-package-transforming-jax-to-pytensor-for-odes-and-other-applications/16191) — optional convenience; MEDIUM-LOW community confidence

---

## Metadata

**Confidence breakdown:**

- **Standard stack:** HIGH — every library version verified via live `pip index versions` on 2026-04-23; every choice traces to CLAUDE.md or `model_calibration_strategy.html` §Part VI
- **Architecture (SQLite schema, file layout, stage pattern):** HIGH — derived directly from CONTEXT.md D-01 through D-08 and CALIB-07 requirements; matches Phase 2's established Typer + frozen-dataclass patterns
- **JAX model pattern (Pattern 2):** MEDIUM-HIGH — parity with NumPy `module_f` and `module_g` is mechanical; the `pytensor ↔ jax` bridge has MEDIUM confidence (alternative paths A/B/C in CLAUDE.md all viable)
- **MCMC hyperparameters (chains/draws/tune/target_accept):** MEDIUM — `4/1000/1000/0.90` is standard for 3-param posteriors but MAY need tuning if parameter degeneracy (Pitfall 3) forces higher target_accept
- **SBC implementation:** MEDIUM — `simuk` is the right tool (by ArviZ team) but is newer; a hand-rolled fallback is documented
- **Compound map:** MEDIUM — manual construction from Pirelli press releases is straightforward but tedious; risk of mid-season compound reshuffle (A3)
- **Pitfalls:** HIGH — grounded in CLAUDE.md explicit warnings (odeint deprecation, Pydantic v2, Three.js note scope) + calibration spec Part VII challenges

**Research date:** 2026-04-23
**Valid until:** 2026-05-23 (30 days — pymc + numpyro + arviz minor versions tick faster than the stable APIs, but the sampling idiom `nuts_sampler="numpyro"` is stable across 5.x)
