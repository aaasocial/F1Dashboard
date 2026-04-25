# Phase 3: Bayesian Calibration Pipeline - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3 delivers an offline CLI calibration pipeline. A calibration engineer runs `f1-calibrate run-all --compound C3` end-to-end against 2022–2024 FastF1 data and obtains versioned posterior parameter sets (ArviZ NetCDF) with passing convergence diagnostics (r̂ < 1.01, ESS > 400) and lower held-out RMSE than a linear baseline — completing the offline path that makes `/simulate` a pure forward pass.

Phase 3 does NOT include: the `/simulate` API endpoint (Phase 4), any frontend work, or online/web-triggered calibration.

Deliverable: a calibration engineer runs five sequential stages (aero → friction → thermal → degradation → validation) that persist fitted parameters into SQLite and ArviZ NetCDF, with a single `run-all` command that chains all stages in one shot.

</domain>

<decisions>
## Implementation Decisions

### CLI Structure
- **D-01:** Two entry point styles in `f1-calibrate`:
  - Stage subcommands: `f1-calibrate stage1 --compound C3`, `stage2`, `stage3`, `stage4`, `stage5`
  - Convenience command: `f1-calibrate run-all --compound C3` — chains stages 1→5 in sequence, detects already-completed stages in SQLite and skips them (resumable)
  - Each stage subcommand can be re-run independently to iterate without re-running prior stages
  - CLI entry point defined in `packages/calibration/pyproject.toml` as `f1-calibrate` console script (Typer-based, mirroring `f1-simulate` pattern from Phase 2)

- **D-02:** Inter-stage parameter handoff via SQLite only — each stage writes its fitted params as a row in the `parameter_sets` table and reads prior-stage params from that same table. No intermediate TOML/JSON checkpoint files. The `parameter_sets` table is CALIB-07's required schema; stages simply query it by `(compound, stage_number, is_latest=True)`.

### Training Data Scope
- **D-03:** Training window is 2022–2024 (three full seasons of the ground-effect era). 2025 data excluded at first calibration run — it may be partially available and introduces regulation-change noise. This is a constant in the pipeline, not a CLI flag (simplifies invocation; update it in a single config constant when 2025 is ready).

- **D-04:** Chronological 80/20 train/validation split: 2022–2023 = training set, 2024 = validation set (Stage 5 holdout). Avoids data leakage (shared circuit characteristics between a 2024 training race and a 2024 validation race). Tests generalization to a new season — the real-world use case.

- **D-05:** Compound-specific race filtering for friction/thermal/degradation stages:
  - Stages 3–4: train only on stints where the target compound was the assigned Pirelli spec (e.g., for C3, include only races where Pirelli mapped C3 as SOFT, MEDIUM, or HARD at that event)
  - Stages 1–2 (aero, friction baseline): train on all races from 2022–2023 regardless of compound — aero and load-sensitivity params are compound-agnostic

### Stage 4 JAX Strategy
- **D-06:** JAX-native rewrite of Modules F + G for Stage 4 MCMC only. Modules F (thermal ODE) and G (Arrhenius aging + Archard wear) are reimplemented in `jax.numpy` in `packages/calibration/src/f1_calibration/jax_model.py`. The production NumPy simulation in `packages/core/` is unchanged.
  - Why F + G together: thermal dynamics (Module F) feed directly into degradation aging (Module G's T_tread input). Separating them creates artificial fixed-temperature assumptions that bias the degradation posterior.
  - Stages 1–3 pre-compute T_tread trajectories and P_slide arrays from the full NumPy pipeline; these are passed as fixed arrays into the JAX log-likelihood for Stage 4. Stage 4 only samples over (β_therm, T_act, k_wear) — 3 parameters.

- **D-07:** Stage 4 sampler: PyMC 5.x model with `sample(nuts_sampler="numpyro")`. Full analytical gradients via JAX autodiff → NUTS convergence target: r̂ < 1.01 and ESS > 400 (CALIB-04). SBC and prior predictive checks (CALIB-06) run on synthetic data before real-data fitting.

### Compound Scope
- **D-08:** Per-compound independent calibration. Each `run-all --compound C3` run fits one Pirelli compound (C1–C5) from scratch against races where that compound was assigned. No hierarchical model across compounds in v1. The calibration spec identifies hierarchical priors as a future mitigation (Challenge 4) — not a v1 requirement.

### Claude's Discretion
- Specific Typer command structure (subcommand grouping, help text, flag names) — planner decides
- PyMC prior distributions for Stage 4 (log-normal vs half-normal vs truncated-normal) — researcher should propose based on physical bounds in model_calibration_strategy.html §F
- Stage 4 MCMC hyperparameters (chains=4, draws=1000, tune=1000 is a reasonable default — planner confirms against ESS target)
- SQLite schema exact DDL for `parameter_sets` and `calibration_runs` tables — researcher derives from CALIB-07 requirements
- Stage 5 RMSE output format (CSV filename convention, column names)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Calibration Specification
- `model_calibration_strategy.html` — Authoritative calibration spec. Part IV (§Stage 1–5 methods), Part V (data preparation checklist), Part VI (software stack), Part VII (challenges and mitigations). Read in full before planning any stage.

### Physics Model
- `model_spec.md` — Module F (thermal ODE equations) and Module G (Arrhenius aging, Archard wear equations). The JAX reimplementation (D-06) must match these exactly.
- `model_v1_complete.html` — Extended derivation detail for thermal and degradation modules.

### Requirements
- `.planning/REQUIREMENTS.md` §Calibration Pipeline — CALIB-01 through CALIB-08. These are the acceptance tests for Phase 3.
- `.planning/ROADMAP.md` §Phase 3 — Success criteria (5 items). Use as the acceptance checklist.

### Prior Phase Artifacts (Phase 3 builds on these)
- `packages/core/src/f1_core/physics/params.py` — AeroParams, FrictionParams, ThermalParams, DegradationParams, PhysicsParams. Stage 1–4 output must produce instances of these types so the calibrated posteriors can feed into `run_simulation()`.
- `packages/core/src/f1_core/physics/orchestrator.py` — `run_simulation(artifact, params)` — the forward pass Stages 1–3 call into for fitting; Stage 4 JAX model reimplements Modules F+G from this file's logic.
- `packages/core/src/f1_core/physics/defaults.py` — `make_nominal_params()` — starting point for calibration priors (Stage 4 PyMC priors should be centered near these values).
- `packages/core/src/f1_core/ingestion/fastf1_client.py` — `load_stint()` — how calibration loads training stints.

### Project Context
- `.planning/PROJECT.md` §Key Decisions — "Bayesian calibration for Stage 4 only; Stages 1–3 use scipy.optimize" and "SQLite for parameter versioning".
- `CLAUDE.md` §Bayesian Inference — PyMC + NumPyro guidance, JAX integration options (A/B/C). Decision D-06 selects Option A (JAX rewrite) for Modules F+G.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `f1_core.physics.params` — AeroParams, FrictionParams, ThermalParams, DegradationParams, PhysicsParams. Stage outputs must produce these frozen dataclass instances. Stage 4 posterior samples become multiple PhysicsParams instances.
- `f1_core.physics.orchestrator.run_simulation(artifact, params)` — Stages 1–3 call this to get model predictions for fitting. Stage 4 does NOT call this — it calls the JAX reimplementation instead.
- `f1_core.physics.defaults.make_nominal_params()` — Use as prior centers for Stage 4 PyMC priors.
- `f1_core.physics.module_f` and `f1_core.physics.module_g` — The NumPy implementations that the JAX rewrite must match equation-for-equation.
- `f1_core.ingestion.fastf1_client.load_stint()` — Training data loader. Calibration iterates this over all races in the training window.
- `packages/calibration/src/f1_calibration/__init__.py` — Empty (version string only). Phase 3 populates this package.

### Established Patterns
- `@dataclass(frozen=True)` for all param types — Stage outputs must produce these (D-08). No mutation.
- Typer-based CLI with named subcommands — `f1-simulate` pattern from Phase 2's `cli.py`. `f1-calibrate` follows the same `typer.Typer(invoke_without_command=True)` with subcommand groups.
- Console script in `packages/calibration/pyproject.toml`: `[project.scripts] f1-calibrate = "f1_calibration.cli:app"`.

### Integration Points
- `packages/calibration/` — All Phase 3 code lives here. Imports from `f1_core` (the core package). Does NOT import from `f1_api`.
- The `parameter_sets` and `calibration_runs` SQLite tables live on the same SQLite file as the Phase 1/2 app DB (`.data/f1.db` locally, `/data/f1.db` on Fly.io volume). Phase 4's `/simulate` endpoint queries this DB to load posteriors.
- ArviZ NetCDF files for Stage 4 posteriors live alongside the SQLite DB: `.data/posteriors/{compound}_{season}_{timestamp}.nc`.

</code_context>

<specifics>
## Specific Ideas

- **Stage 4 JAX model location:** `packages/calibration/src/f1_calibration/jax_model.py` — exports `log_likelihood_f_g(beta_therm, T_act, k_wear, *, t_tread_init, p_slide_arr, dt=0.25)` as a pure JAX function. The PyMC model in `stage4.py` wraps this.
- **Compound mapping table:** `packages/calibration/src/f1_calibration/compound_map.py` — a dict `{(year, round): {"SOFT": "C5", "MEDIUM": "C4", "HARD": "C3"}}` derived from Pirelli press releases. Required for D-05 compound-specific filtering.
- **run-all resumability:** `run-all` checks SQLite for a row in `parameter_sets` matching `(compound, stage_number, year_range="2022-2024")`. If found, skips that stage. Provides a `--force` flag to re-run all stages even if SQLite has prior results.
- **Stage 5 CSV artifact:** Written to `.data/validation/stage5_{compound}_{timestamp}_per_circuit.csv`. Columns: circuit, n_stints, rmse_s, mean_delta_s, worst_lap.

</specifics>

<deferred>
## Deferred Ideas

- **Hierarchical priors across compounds** — Calibration spec Challenge 4 mentions this as a mitigation. Deferred to v2; per-compound independent calibration is v1 (D-08).
- **Driver aggressiveness coefficient** — Calibration spec Challenge 5. A per-driver multiplier on degradation rate. Deferred to v2.
- **Track-specific aero corrections** — Challenge 3 in the calibration spec (C_LA varies by wing package). Deferred to v2; Stage 1 fits one C_LA per season.
- **2025+ training data** — Excluded in v1 (D-03). Add once the full season is available and stable.

</deferred>

---

*Phase: 03-bayesian-calibration-pipeline*
*Context gathered: 2026-04-23*
