---
phase: 3
slug: bayesian-calibration-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-23
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8+ with pytest-cov 5+, hypothesis 6+ |
| **Config file** | root `pyproject.toml` `[tool.pytest.ini_options]` — already includes `packages/calibration/tests` in `testpaths` |
| **Quick run command** | `uv run pytest packages/calibration/tests -x --tb=short -m "not integration"` |
| **Full suite command** | `uv run pytest packages/calibration/tests -x` |
| **Estimated runtime** | ~30 s unit / ~5 min with integration (Stage 4 MCMC smoke) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest packages/calibration/tests -x --tb=short -m "not integration"`
- **After every plan wave:** Run `uv run pytest packages/calibration/tests -x`
- **Before `/gsd-verify-work`:** Full suite (`uv run pytest`) must be green — includes regressions in core + api
- **Max feedback latency:** ~30 seconds (unit-only mode)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 3-W0-01 | scaffold | 0 | CALIB-07 | — | N/A | infra | `uv run pytest packages/calibration/tests -x --co` | ❌ W0 | ⬜ pending |
| 3-01-01 | stage1 | 1 | CALIB-01 | — | N/A | unit | `uv run pytest packages/calibration/tests/test_stage1_aero.py -x` | ❌ W0 | ⬜ pending |
| 3-02-01 | stage2 | 1 | CALIB-02 | — | N/A | unit | `uv run pytest packages/calibration/tests/test_stage2_friction.py -x` | ❌ W0 | ⬜ pending |
| 3-03-01 | stage3 | 1 | CALIB-03 | — | N/A | unit | `uv run pytest packages/calibration/tests/test_stage3_thermal.py -x` | ❌ W0 | ⬜ pending |
| 3-04-01 | jax_model | 2 | CALIB-04 | T-3-01 | Input `compound` matches `^C[1-5]$` before any DB op | unit | `uv run pytest packages/calibration/tests/test_jax_model.py::test_parity -x` | ❌ W0 | ⬜ pending |
| 3-04-02 | sbc | 2 | CALIB-06 | — | N/A | integration | `uv run pytest packages/calibration/tests/test_sbc.py -x -m integration` | ❌ W0 | ⬜ pending |
| 3-04-03 | stage4 | 2 | CALIB-04 | T-3-02 | NetCDF loaded only from `calibration_runs.netcdf_path` | integration | `uv run pytest packages/calibration/tests/test_stage4_degradation.py -x -m integration` | ❌ W0 | ⬜ pending |
| 3-04-04 | netcdf | 2 | CALIB-07 | T-3-02 | NetCDF path asserted inside `.data/` before write | unit | `uv run pytest packages/calibration/tests/test_stage4_degradation.py::test_netcdf_roundtrip -x` | ❌ W0 | ⬜ pending |
| 3-05-01 | stage5 | 3 | CALIB-05 | — | N/A | integration | `uv run pytest packages/calibration/tests/test_stage5_validation.py -x` | ❌ W0 | ⬜ pending |
| 3-06-01 | baseline | 3 | CALIB-08 | — | N/A | unit | `uv run pytest packages/calibration/tests/test_baseline.py -x` | ❌ W0 | ⬜ pending |
| 3-07-01 | db | 1 | CALIB-07 | T-3-03 | Parameterized queries only; `compound` validated before first DB op | unit | `uv run pytest packages/calibration/tests/test_db.py -x` | ❌ W0 | ⬜ pending |
| 3-08-01 | cli | 3 | CALIB-01–08 | T-3-04 | Path args asserted under workspace root; no traceback leak | integration | `uv run pytest packages/calibration/tests/test_cli.py -x` | ❌ W0 | ⬜ pending |
| 3-09-01 | run-all | 3 | CALIB-07 | — | N/A | integration | `uv run pytest packages/calibration/tests/test_run_all.py::test_resumability -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/calibration/tests/__init__.py` — required for `--import-mode=importlib`
- [ ] `packages/calibration/tests/conftest.py` — shared fixtures:
  - `synthetic_stint` — 50-sample artifact with known ground-truth params
  - `tmp_db_path` — fresh SQLite file per test (tmp_path fixture)
  - `mini_compound_map` — subset dict `{(2023, 1): {"SOFT": "C5", "MEDIUM": "C4", "HARD": "C3"}}` for tests
- [ ] pytest marker config in root `pyproject.toml`:
  ```toml
  [tool.pytest.ini_options]
  markers = [
      "integration: marks slow integration tests requiring full MCMC (deselect with '-m \"not integration\"')",
  ]
  ```
- [ ] JAX compile cache note: first Stage 4 integration test takes ~30 s — CI must not timeout before 60 s
- [ ] `.gitignore` entry: `.data/posteriors/*.nc` (prevent accidental commit of large NetCDF binaries)
- [ ] `packages/calibration/pyproject.toml` — update with calibration dependencies (pymc, numpyro, jax, arviz, netcdf4, scikit-learn)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Stage 4 MCMC trace plots show good mixing (no divergences, no funnel) | CALIB-04 | Visual posterior inspection; r̂ and ESS are automated but trace shape requires human review | Run `az.plot_trace(idata)` after Stage 4 on Bahrain 2023 VER C3; inspect visually |
| RMSE improvement "meaningful" vs linear baseline | CALIB-08 | Threshold ("10%? 20%?") is not yet locked — per open question 3 in RESEARCH.md | Compare Stage 5 per-circuit CSV vs `test_baseline.py` linear RMSE output; expect > 10% improvement |
| Pirelli compound map correctness for edge races | CALIB-05 | ~66-entry hand-curated dict cannot be unit tested without ground truth | Cross-check 5 randomly selected `(year, round)` entries against Pirelli press releases |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s (unit mode)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
