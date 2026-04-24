# Phase 3: Bayesian Calibration Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 03-bayesian-calibration-pipeline
**Areas discussed:** CLI structure, Training data scope, Stage 4 JAX strategy, Compound scope

---

## CLI Structure

**Q1: How should the calibrate CLI be structured?**

| Option | Description | Selected |
|--------|-------------|----------|
| Stage subcommands + run-all | `f1-calibrate stage1`…`stage5` + `f1-calibrate run-all --compound C3`. Each stage writes to SQLite so any stage can be re-run independently. run-all chains 1→5, detects and skips completed stages. | ✓ |
| Stage subcommands only | Per-stage subcommands, no run-all shortcut. Matches success criteria text literally. | |
| Single compound command | `f1-calibrate compound C3 --year 2024` always runs all 5 stages. Simpler UX but can't re-run Stage 4 alone. | |

**User's choice:** Stage subcommands + run-all

---

**Q2: When a stage subcommand runs, where does it write its results so the next stage can pick them up?**

| Option | Description | Selected |
|--------|-------------|----------|
| SQLite only | Each stage reads/writes the `parameter_sets` SQLite table (already required by CALIB-07). Persistent, inspectable, run-all can skip completed stages. No extra file formats. | ✓ |
| SQLite + TOML checkpoint files | Each stage also writes a human-readable TOML alongside the SQLite row for manual inspection/editing. | |
| In-memory only | Stages pass params in-memory; only Stage 4/5 result persists. Means stage subcommands can't read prior stage results independently. | |

**User's choice:** SQLite only

---

## Training Data Scope

**Q3: Which seasons does the calibration pipeline train on?**

| Option | Description | Selected |
|--------|-------------|----------|
| 2022–2024 | Three seasons of ground-effect era data. Consistent regulation window. Excludes 2025 which may be incomplete at first run. | ✓ |
| All available (2022–present) | Automatic: use all cached races from 2022 onwards. More data but longer first run. | |
| User-specified --year range | `--year-start`/`--year-end` flags. Most flexible but adds CLI complexity. | |

**User's choice:** 2022–2024 (Recommended)

---

**Q4: How is the 80/20 train/validation split (Stage 5) defined?**

| Option | Description | Selected |
|--------|-------------|----------|
| Chronological split | Train on 2022–2023, validate on 2024. Avoids data leakage, tests generalization to a new season. | ✓ |
| Random 20% holdout | Randomly hold out 20% of races across all seasons. Higher average training data but risks data leakage. | |
| Per-circuit holdout | Hold out most recent appearance of each circuit. Tests generalization across different track conditions. Complex to implement. | |

**User's choice:** Chronological split (Recommended)

---

## Stage 4 JAX Strategy

**Q5: How should the Stage 4 MCMC likelihood be implemented?**

| Option | Description | Selected |
|--------|-------------|----------|
| JAX-native hot path | Rewrite degradation forward pass (Arrhenius + thermal ODE) in JAX for Stage 4. Full analytical gradients → NumPyro NUTS ~3x faster per ESS. NumPy simulation unchanged for production. | ✓ |
| Black-box PyMC likelihood | Wrap run_simulation() as PyMC Potential/CustomDist. Switch to Metropolis (gradient-free). Simpler but slower mixing. | |
| pure_callback bridge | Keep NumPy forward pass, wrap via jax.pure_callback so NumPyro sees it as JAX-differentiable. Middle ground. | |

**User's choice:** JAX-native hot path (Recommended)

---

**Q6: Which modules get the JAX rewrite for Stage 4 calibration?**

| Option | Description | Selected |
|--------|-------------|----------|
| Module G only | Only Arrhenius aging and Archard wear (3 equations). T_tread trajectory from NumPy as fixed input. Minimal JAX surface. | |
| Modules F + G | Thermal ODE (Module F) + degradation (Module G). Correct physical coupling — T_tread uncertainty propagates into degradation posterior. 5x more JAX code but physically rigorous. | ✓ |
| Full pipeline A–G | All 7 modules in JAX. Correct end-to-end gradient flow but 40+ JAX equations to maintain. Deferred to v2. | |

**User's choice:** Modules F + G

---

## Compound Scope

**Q7: How should parameters be calibrated across compounds?**

| Option | Description | Selected |
|--------|-------------|----------|
| Per-compound independent | Each `run-all --compound C3` fits one compound from scratch. Simple, parallelizable, matches CLI design. Hierarchical priors are a future mitigation (calibration spec Challenge 4). | ✓ |
| Hierarchical across compounds | Joint PyMC model with compound-level priors drawn from population hyperpriors. More statistically correct but one massive Stage 4 model. | |
| Per-compound with cross-compound priors | Per-compound runs with Stage 4 priors tuned by known compound relationships. Same simple CLI, better priors. | |

**User's choice:** Per-compound independent (Recommended)

---

**Q8: When `calibrate run-all --compound C3` runs, what races does it include?**

| Option | Description | Selected |
|--------|-------------|----------|
| Only races where C3 was assigned | Stages 3–4 train on stints where target compound was the Pirelli spec. Stages 1–2 (aero) train on all races. | ✓ |
| All races, compound as covariate | All races train aero; compound filters stints for friction/thermal/degradation. More aero data but pipeline must filter internally. | |

**User's choice:** Only races where C3 was assigned (Recommended)

---

## Claude's Discretion

- Typer command structure (subcommand grouping, help text, flag names)
- PyMC prior distributions for Stage 4 (log-normal vs half-normal vs truncated-normal)
- Stage 4 MCMC hyperparameters (chains, draws, tune steps)
- SQLite schema exact DDL for `parameter_sets` and `calibration_runs` tables
- Stage 5 RMSE output filename convention and column names

## Deferred Ideas

- Hierarchical priors across compounds — calibration spec Challenge 4; defer to v2
- Driver aggressiveness coefficient — calibration spec Challenge 5; defer to v2
- Track-specific aero corrections — calibration spec Challenge 3; defer to v2
- 2025+ training data — add once full season is stable
