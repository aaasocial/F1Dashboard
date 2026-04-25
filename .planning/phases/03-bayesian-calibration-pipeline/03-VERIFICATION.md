---
phase: 03-bayesian-calibration-pipeline
verified: 2026-04-23T12:00:00Z
status: human_needed
score: 5/5 roadmap success criteria verified at implementation level
overrides_applied: 0
human_verification:
  - test: "Run `uv run pytest packages/calibration/tests -x -m 'not integration'` and confirm all 79 fast tests pass"
    expected: "79 passed, 4 deselected"
    why_human: "Cannot execute test runner in this environment; summaries report 79/79 but cannot verify the current state post all commits"
  - test: "Run `uv run f1-calibrate --help` and confirm all 6 subcommands (stage1, stage2, stage3, stage4, stage5, run-all) appear"
    expected: "Exit code 0; help output lists all 6 subcommands"
    why_human: "CLI invocation requires running the installed package; cannot confirm without executing the binary"
  - test: "Run `uv run f1-calibrate stage1 --compound X9` and confirm exit code 1 with 'Invalid input' in output and no 'Traceback' present"
    expected: "Exit code 1; 'Invalid input: compound must match ^C[1-5]$' printed; no Python traceback"
    why_human: "T-3-04 traceback suppression requires live invocation to confirm"
  - test: "Run the integration MCMC test: `uv run pytest packages/calibration/tests/test_stage4_degradation.py -x -m integration` and confirm the NetCDF roundtrip and smoke MCMC pass"
    expected: "3 integration tests pass; posterior values preserved to 1e-8 on NetCDF round-trip; r_hat < 1.05 on smoke run"
    why_human: "Integration tests require JAX compilation and PyMC sampling (~3 min); cannot run inline"
  - test: "Stage 3 T_opt/sigma_T deviation: confirm the CALIB-03 tolerance (±10 deg C T_opt, ±5 deg C sigma_T) is still met despite T_opt/sigma_T being held fixed rather than fitted"
    expected: "Because T_opt and sigma_T are passed through from nominal (95.0, 20.0) unchanged, the test asserts exact equality fit.T_opt == 95.0 -- the tolerance acceptance criterion in CALIB-03 is technically satisfied by passing through the nominal. Verify this is intentional and documented for calibration users."
    why_human: "Design decision: T_opt/sigma_T are non-identifiable from thermal residuals; they will be refined in Stage 4 MCMC. Human needs to confirm this phased approach is acceptable as Phase 3 CALIB-03 closure."
---

# Phase 3: Bayesian Calibration Pipeline Verification Report

**Phase Goal:** A calibration engineer can run `f1-calibrate run-all --compound C3` end-to-end and obtain versioned posterior parameter sets (NetCDF) with passing convergence diagnostics (r_hat < 1.01, ESS > 400) and lower held-out RMSE than a linear baseline — completing the offline path that makes `/simulate` a pure forward pass.

**Verified:** 2026-04-23T12:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Stage 1 fits C_LA within ±10%, C_DA within ±15%; Stage 2 fits mu_0_fresh within ±5%, n within ±0.05; Stage 3 fits T_opt within ±10 deg C, sigma_T within ±5 deg C | VERIFIED (with note) | stage1_aero.py uses scipy.optimize.least_squares with trf bounds; fit_stage1 test asserts C_LA recovery < 10%. stage2_friction.py uses np.polyfit log-log regression; test asserts mu_0 within 5%, n within 0.05. Stage 3 DEVIATION: T_opt/sigma_T held at nominal (95.0/20.0) — non-identifiable from thermal residuals; passed through unchanged. Test asserts exact equality (not tolerance). Documented in 03-04-SUMMARY.md. |
| 2 | Stage 4 MCMC achieves r_hat < 1.01 and ESS > 400; SBC on synthetic data passes before real-data fitting | VERIFIED (implementation) | stage4_degradation.py: PyMC 5.x + nuts_sampler="numpyro"; r_hat >= 1.01 raises RuntimeError; ess_bulk <= 400 raises RuntimeError; run_stage4_sbc() pre-flight gate blocks on uniformity_ok=False. sbc.py implements correct Talts joint-sampling loop (Pitfall 7). Integration test smoke run uses relaxed thresholds (r_hat < 1.05, ESS > 200). Full production thresholds enforced in fit_stage4. |
| 3 | Physics model achieves meaningfully lower per-lap RMSE than linear baseline on 20% held-out set | VERIFIED (implementation) | baseline.py implements fit_baseline_batch via sklearn LinearRegression. stage5_validation.py runs both physics (run_simulation) and baseline on same validation stints; returns both physics_rmse_s and baseline_rmse_s; CLI warns when physics fails to beat baseline (CALIB-08). Test asserts physics within 10% of baseline on synthetic data. |
| 4 | Stage 5 cross-validation reports per-lap RMSE < 0.3 s with per-circuit CSV artifact | VERIFIED (implementation) | stage5_validation.py: runs run_simulation on VALIDATION_YEARS=(2024,) stints; MAD filter excludes SC/VSC laps; csv.DictWriter emits circuit,n_stints,rmse_s,mean_delta_s,worst_lap. Test asserts RMSE < 1e-10 on noise-free data; CSV format verified with 3 circuits. Real-data RMSE target requires FastF1 data (human/integration). |
| 5 | Posteriors persisted as ArviZ NetCDF; calibration_runs table records provenance; calibration_id traceable | VERIFIED | idata.to_netcdf(compress=True) in persist_posterior(); resolve_db_path enforces workspace containment (T-3-03). calibration_runs table has columns: compound, year_range, heldout_rmse_s, baseline_rmse_s, r_hat_max, ess_bulk_min, netcdf_path, param_set_stage1..4, stage5_csv_path, git_sha, created_at. write_calibration_run called in run_all.py after Stage 5. NetCDF round-trip test verifies values preserved to 1e-8 (integration). |

**Score:** 5/5 roadmap truths verified at implementation level (human needed to confirm test execution and CALIB-03 T_opt/sigma_T design decision).

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `packages/calibration/pyproject.toml` | calibration dependencies + f1-calibrate entry point | VERIFIED | Contains pymc>=5.18, numpyro>=0.16, jax>=0.4, arviz, netcdf4, scikit-learn, typer, rich; f1-calibrate = "f1_calibration.cli:app" |
| `packages/calibration/src/f1_calibration/db.py` | SQLite DDL, writers, readers, validate_compound | VERIFIED | initialize_schema, trg_parameter_sets_latest trigger, write_parameter_set, read_latest_parameter_set, has_stage_result, write_calibration_run, validate_compound, resolve_db_path, _git_sha with shell=False |
| `packages/calibration/src/f1_calibration/compound_map.py` | Static compound map 2022-2024 + lookup helper | VERIFIED | COMPOUND_MAP covers 2022-2024 (68 rounds); lookup() with case-insensitive FIA compound; races_for_compound() reverse lookup; Bahrain 2023 = C1/C2/C3 confirmed |
| `packages/calibration/src/f1_calibration/common.py` | TRAINING_YEARS, VALIDATION_YEARS, YEAR_RANGE, get_logger | VERIFIED | TRAINING_YEARS=(2022,2023); VALIDATION_YEARS=(2024,); YEAR_RANGE="2022-2024" |
| `packages/calibration/src/f1_calibration/training.py` | iter_training_stints generator | VERIFIED | Compound=None iterates all rounds 1-24; compound-specific uses races_for_compound; on failure, logs+breaks (resilience) |
| `packages/calibration/src/f1_calibration/priors.py` | degradation_prior_centers from make_nominal_params | VERIFIED | Returns beta_therm=1e-6, T_act=25.0, k_wear=1e-12 from make_nominal_params().degradation |
| `packages/calibration/src/f1_calibration/stage1_aero.py` | fit_stage1 — scipy least_squares aero fit | VERIFIED | Uses least_squares(method='trf', bounds=...); returns AeroParams frozen dataclass; compound-agnostic |
| `packages/calibration/src/f1_calibration/stage2_friction.py` | fit_stage2 — log-log regression | VERIFIED | np.polyfit(log_p, log_mu, 1); returns FrictionParams; compound-agnostic |
| `packages/calibration/src/f1_calibration/baseline.py` | Linear baseline per stint (CALIB-08) | VERIFIED | sklearn LinearRegression; fit_baseline_per_stint, fit_baseline_batch, rmse_per_lap all present |
| `packages/calibration/src/f1_calibration/sbc.py` | SBC harness (CALIB-06) | VERIFIED | run_sbc with mandatory forward_fn (Pitfall 7); sbc_uniformity_test using scipy.stats.kstest |
| `packages/calibration/src/f1_calibration/stage3_thermal.py` | fit_stage3 — thermal calibration | VERIFIED | Uses production thermal_step (D-06); 8 free params (T_opt/sigma_T held fixed — deviation); _BOUNDS_LOWER with C_tread>=2000 and R_tc>=0.005 (Pitfall 2) |
| `packages/calibration/src/f1_calibration/jax_model.py` | JAX parity copy of Modules F+G | VERIFIED | jax.config.update("jax_enable_x64", True); lax.scan in simulate_mu_0 and thermal_scan; ARRHENIUS_EXP_CLAMP=20.0; T_REF_AGING=80.0; log_likelihood_f_g |
| `packages/calibration/src/f1_calibration/stage4_degradation.py` | PyMC MCMC + SBC gate + NetCDF | VERIFIED | build_stage4_model, fit_stage4, persist_posterior, run_stage4_sbc; nuts_sampler="numpyro"; T_act informative prior sigma=0.3; r_hat<1.01 and ESS>400 enforced; idata_kwargs={"log_likelihood":False}; Compiling JAX message |
| `packages/calibration/src/f1_calibration/stage5_validation.py` | fit_stage5 + MAD filter + CSV | VERIFIED | run_simulation + fit_baseline_batch; _mad_filter(threshold=3.0); csv.DictWriter with 5-column schema; resolve_db_path on output dir |
| `packages/calibration/src/f1_calibration/cli.py` | Typer app with 6 subcommands | VERIFIED | app=typer.Typer(no_args_is_help=True); 6 @app.command decorators; _handle_exit maps ValueError->1, RuntimeError->2, Exception->3; _stageN_core helpers; --compound flag on all subcommands |
| `packages/calibration/src/f1_calibration/run_all.py` | Resumable run-all orchestrator | VERIFIED | run_all(); has_stage_result skip gate; for stage_num in (1,2,3,4); Stage 5 always runs; write_calibration_run at end |
| `packages/calibration/tests/conftest.py` | tmp_db_path, initialized_db, mini_compound_map, synthetic_stint | VERIFIED | All 4 fixtures present |
| `packages/calibration/tests/test_db.py` | SQLite schema + security validator tests | VERIFIED | test_validate_compound_rejects_invalid, test_resolve_db_path_rejects_outside_workspace, test_initialize_schema_idempotent, test_is_latest_trigger_demotes_prior_rows |
| `packages/calibration/tests/test_compound_map.py` | Compound map unit tests | VERIFIED | 7 tests; test_bahrain_2023_mapping, test_unknown_race_raises, test_compound_map_covers_2022_2024 |
| `packages/calibration/tests/test_stage1_aero.py` | Stage 1 accuracy tests | VERIFIED | test_stage1_recovers_synthetic_c_la present |
| `packages/calibration/tests/test_stage2_friction.py` | Stage 2 accuracy tests | VERIFIED | test_stage2_recovers_synthetic_mu_0 present |
| `packages/calibration/tests/test_baseline.py` | Baseline linear model tests | VERIFIED | test_baseline_fits_linear_trend present; 7 tests |
| `packages/calibration/tests/test_sbc.py` | SBC uniformity tests | VERIFIED | test_sbc_uniformity_on_gaussian (integration marked); 5 fast tests |
| `packages/calibration/tests/test_stage3_thermal.py` | Stage 3 warm-up recovery tests | VERIFIED | test_stage3_recovers_synthetic_t_opt present (modified: asserts exact pass-through) |
| `packages/calibration/tests/test_jax_model.py` | JAX parity tests | VERIFIED | test_parity_with_numpy_module_g present (200-step <1e-6 tolerance) |
| `packages/calibration/tests/test_stage4_degradation.py` | MCMC smoke + NetCDF round-trip + SBC gate | VERIFIED | test_netcdf_roundtrip, test_stage4_refuses_on_sbc_failure, test_persist_posterior_rejects_outside_workspace |
| `packages/calibration/tests/test_stage5_validation.py` | Stage 5 RMSE + CSV + MAD tests | VERIFIED | test_stage5_rmse_on_noise_free_synthetic, test_stage5_mad_filter_excludes_outliers |
| `packages/calibration/tests/test_cli.py` | CLI subcommand + compound validation tests | VERIFIED | test_cli_help_lists_all_subcommands, test_stage1_rejects_invalid_compound |
| `packages/calibration/tests/test_run_all.py` | run-all resumability tests | VERIFIED | test_run_all_resumability, test_run_all_force_reruns_all_stages |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `packages/calibration/pyproject.toml` | `f1_calibration.cli:app` | [project.scripts] f1-calibrate entry point | VERIFIED | `f1-calibrate = "f1_calibration.cli:app"` confirmed |
| `db.py` | `.data/f1.db` | sqlite3.connect(DEFAULT_DB_PATH) | VERIFIED | DEFAULT_DB_PATH = WORKSPACE_ROOT / ".data" / "f1.db"; subprocess.check_output with shell=False |
| `stage1_aero.py` | `f1_core.physics.params.AeroParams` | dataclass instantiation | VERIFIED | `from f1_core.physics.params import AeroParams`; `return AeroParams(...)` confirmed |
| `stage2_friction.py` | `f1_core.physics.params.FrictionParams` | dataclass instantiation | VERIFIED | `from f1_core.physics.params import FrictionParams`; returns FrictionParams |
| `stage3_thermal.py` | `f1_core.physics.module_f.thermal_step` | forward integration | VERIFIED | `from f1_core.physics.module_f import thermal_step`; called in _forward_curve loop |
| `jax_model.py` | `f1_core.physics.module_g` | equation-for-equation parity | VERIFIED | lax.scan pattern matches degradation_step; ARRHENIUS_EXP_CLAMP and T_REF_AGING match production |
| `stage4_degradation.py` | `f1_calibration.jax_model.log_likelihood_f_g` | pytensor Op wrapping jax.jit | VERIFIED | `from f1_calibration.jax_model import log_likelihood_f_g`; _JaxLogLikOp.perform() calls jit-compiled function |
| `stage4_degradation.py` | `.data/posteriors/*.nc` | idata.to_netcdf(path, compress=True) | VERIFIED | `idata.to_netcdf(str(path_abs), compress=True)` in persist_posterior() |
| `stage5_validation.py` | `f1_core.physics.orchestrator.run_simulation` | forward pass using assembled PhysicsParams | VERIFIED | `from f1_core.physics.orchestrator import run_simulation`; called per validation stint |
| `stage5_validation.py` | `f1_calibration.baseline.fit_baseline_batch` | side-by-side RMSE comparison | VERIFIED | `from f1_calibration.baseline import fit_baseline_batch, rmse_per_lap`; called in fit_stage5 |
| `cli.py` | `packages/calibration/pyproject.toml [project.scripts]` | console script entry point | VERIFIED | `app` exported; entry point definition confirmed in pyproject.toml |
| `run_all.py` | `f1_calibration.stage{1..5}` | has_stage_result skip gate | VERIFIED | has_stage_result imported and called for stage_num in (1,2,3,4); _run_stage_dispatch dispatches to _stageN_core |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `stage4_degradation.py` | idata.posterior | pm.sample(..., nuts_sampler="numpyro") | Yes — real MCMC draws from PyMC model | FLOWING (per integration test) |
| `stage4_degradation.py` | netcdf_path | persist_posterior() -> idata.to_netcdf() | Yes — written to .data/posteriors/ | FLOWING |
| `stage5_validation.py` | physics_rmse_s | run_simulation() -> _clean_laps_from_stint() -> rmse_per_lap() | Yes — computed from per_lap_rows() | FLOWING |
| `stage5_validation.py` | baseline_rmse_s | fit_baseline_batch() -> combined_rmse_s | Yes — real sklearn LinearRegression fit | FLOWING |
| `run_all.py` | calibration_id | write_calibration_run() after Stage 5 | Yes — SQLite lastrowid | FLOWING |
| `stage3_thermal.py` | T_opt, sigma_T | Passed through from nominal (not from optimizer) | Nominal values, not fitted data | NOTE: Intentional deviation; see CALIB-03 note below |

---

### Behavioral Spot-Checks

Step 7b: SKIPPED for integration paths (JAX compilation, PyMC sampling, FastF1 network access). Fast unit tests pass per SUMMARY reports.

---

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|---------------|-------------|--------|----------|
| CALIB-01 | 03-02, 03-08 | Stage 1 aero calibration via scipy.optimize.least_squares | SATISFIED | stage1_aero.py: fit_stage1 with trf bounds; test_stage1_aero.py: C_LA recovery ±10% on synthetic; CLI stage1 subcommand exists |
| CALIB-02 | 03-02, 03-08 | Stage 2 friction baseline via log-log regression | SATISFIED | stage2_friction.py: np.polyfit(log_p, log_mu, 1); test_stage2_friction.py: mu_0 ±5%, n ±0.05; CLI stage2 subcommand exists |
| CALIB-03 | 03-04, 03-08 | Stage 3 thermal parameter calibration | PARTIAL — NOTE | stage3_thermal.py: fits 8 ODE params (C_tread, C_carc, C_gas, R_tc, R_cg, h_0, h_1, alpha_p) via least_squares trf; T_opt and sigma_T held at nominal (non-identifiable from thermal residuals — documented deviation); CALIB-03 tolerance met by pass-through; CLI stage3 subcommand exists |
| CALIB-04 | 03-05, 03-06, 03-08 | Stage 4 Bayesian degradation MCMC | SATISFIED | jax_model.py: JAX parity to 1e-6; stage4_degradation.py: PyMC+NumPyro NUTS, r_hat<1.01, ESS>400 enforced; integration tests exist; CLI stage4 subcommand; production default nuts_sampler="numpyro" (test fallback to "pymc" due to JAX version mismatch noted in summary) |
| CALIB-05 | 03-07, 03-08 | Stage 5 cross-validation, per-lap RMSE < 0.3s | SATISFIED (implementation) | stage5_validation.py: run_simulation on VALIDATION_YEARS; MAD filter (Pitfall 4); per-circuit CSV; RMSE < 0.3s target requires real FastF1 data (human needed) |
| CALIB-06 | 03-03, 03-06 | SBC pre-flight on synthetic data before Stage 4 | SATISFIED | sbc.py: run_sbc with mandatory forward_fn (Pitfall 7); run_stage4_sbc() blocks on uniformity_ok=False; test_sbc.py fast tests pass; integration test exists |
| CALIB-07 | 03-01, 03-06, 03-08 | ArviZ NetCDF + SQLite calibration_runs provenance | SATISFIED | db.py: parameter_sets + calibration_runs tables + trg_parameter_sets_latest trigger; persist_posterior writes NetCDF; write_calibration_run ties all together; git_sha recorded |
| CALIB-08 | 03-03, 03-07, 03-08 | Linear baseline sanity check; physics must beat baseline | SATISFIED | baseline.py: sklearn LinearRegression per-stint; fit_stage5 computes both physics_rmse_s and baseline_rmse_s; CLI warns when physics fails to beat baseline |

**Orphaned requirements check:** All CALIB-01..CALIB-08 are claimed by phase plans. No orphaned requirements detected.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `stage3_thermal.py` | ~199-201 | T_opt=nominal.T_opt, sigma_T=nominal.sigma_T passed through without fitting | INFO | Intentional design decision; physically motivated; documented in SUMMARY and code comments. Not a bug. |
| `stage4_degradation.py` | ~192 | nuts_sampler="numpyro" default but numpyro broken in current environment (JAX 0.10 vs numpyro expecting xla_pmap_p) | WARNING | Tests fall back to "pymc" via _detect_sampler(). Production deployment requires JAX upgrade to 0.4.x + compatible numpyro. Documented in 03-06-SUMMARY. |
| `run_all.py` | ~751-756 | _run_stage_dispatch calls cli_mod._stageN_core via lazy import | INFO | Required to avoid circular imports; established pattern per SUMMARY. Functions are real implementations, not stubs. |

---

### Human Verification Required

#### 1. Full Fast Test Suite Execution

**Test:** Run `uv run pytest packages/calibration/tests -x -m "not integration"` from the repo root.
**Expected:** 79 passed, 4 deselected (integration tests skipped). Zero failures or errors.
**Why human:** Cannot execute test runner in this verification environment. SUMMARYs report 79/79 but this needs confirmation on the current committed state.

#### 2. CLI Invocation and Help Output

**Test:** Run `PYTHONUTF8=1 uv run f1-calibrate --help` from the repo root.
**Expected:** Exit code 0; help output lists all 6 subcommands: stage1, stage2, stage3, stage4, stage5, run-all.
**Why human:** Requires the installed package entry point to be functional. SUMMARY confirms this passed during development but needs confirmation post all commits.

#### 3. CLI Compound Validation and Traceback Suppression (T-3-04)

**Test:** Run `PYTHONUTF8=1 uv run f1-calibrate stage1 --compound X9`.
**Expected:** Exit code 1; output contains "Invalid input: compound must match ^C[1-5]$"; output does NOT contain "Traceback" or `File "`.
**Why human:** T-3-04 traceback suppression requires live CLI invocation to confirm. This is a security requirement.

#### 4. Stage 4 Integration Tests (MCMC + NetCDF Round-Trip + SBC Gate)

**Test:** Run `uv run pytest packages/calibration/tests/test_stage4_degradation.py -m integration -x` (allow ~3-5 minutes for JAX compilation + sampling).
**Expected:** 3 integration tests pass: test_fit_stage4_smoke (r_hat < 1.05, ESS > 200 on smoke), test_netcdf_roundtrip (posterior values preserved to 1e-8), test_stage4_refuses_on_sbc_failure (RuntimeError raised on mocked SBC failure). Note: tests use _detect_sampler() fallback to "pymc" if numpyro is unavailable.
**Why human:** MCMC sampling takes ~3 min; cannot run inline. The numpyro/JAX version mismatch in the current environment means production behavior (NUTS with JAX gradients) has not been verified end-to-end — only the "pymc" fallback path.

#### 5. CALIB-03 T_opt/sigma_T Design Decision Acceptance

**Test:** Review the Stage 3 implementation decision and confirm acceptability for Phase 3 closure.
**Expected:** Stage 3 holds T_opt=95.0 and sigma_T=20.0 fixed (nominal values) rather than fitting them, because they are non-identifiable from thermal ODE residuals alone. CALIB-03's "±10 deg C T_opt, ±5 deg C sigma_T" accuracy criterion is technically satisfied (exact equality to true values in synthetic test), but by pass-through, not by fitting. The plan intended these to be fitted parameters.
**Why human:** This is a physics design decision with downstream implications: T_opt and sigma_T calibration is deferred to Stage 4 MCMC (where the full friction-thermal-degradation chain is active). A developer must confirm this phased approach satisfies the CALIB-03 intent or flag for remediation in Phase 4.

---

### Gaps Summary

No blocking gaps identified at the implementation level. All 16 source modules exist with substantive, wired implementations. All 14 test files exist with the expected test function names. All key links are verified.

Two notable items require human attention:

1. **CALIB-03 T_opt/sigma_T deviation** — T_opt and sigma_T are passed through at nominal values rather than fitted in Stage 3. This is a documented, physically-motivated decision (non-identifiability from thermal residuals). The CALIB-03 tolerance requirement is satisfied by pass-through equality in the synthetic test. This requires developer sign-off that deferred fitting in Stage 4 is acceptable for Phase 3 closure.

2. **NumPyro/JAX production path unverified end-to-end** — The integration tests use a `_detect_sampler()` fallback to "pymc" because numpyro is broken in the current environment (JAX 0.10.0 removed `xla_pmap_p` that numpyro expects). Production code keeps `nuts_sampler="numpyro"` as the default. This means the NumPyro NUTS gradient path has NOT been exercised in this environment. The PyMC fallback sampler produces valid posteriors but without JAX-accelerated NUTS. This is a known environmental limitation, not a code bug, but should be noted for deployment.

---

_Verified: 2026-04-23T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
