---
phase: 1
slug: foundation-data-pipeline-module-contracts
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-23
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (per-package) — create in Wave 0 |
| **Quick run command** | `uv run pytest packages/core/tests -x` |
| **Full suite command** | `uv run pytest` (runs all package tests from repo root) |
| **Estimated runtime** | ~30 seconds (integration tests skip network via committed fixtures) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest packages/core/tests -x`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd-verify-work`:** Full suite must be green + `uv run mypy packages/core/src` + `uv run mypy packages/api/src` + `uv run ruff check .`
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-??-01 | TBD | 0 | DATA-01 | — | N/A | integration | `uv run pytest packages/core/tests/test_ingestion.py::test_fetch_canonical_fixture -x` | ❌ W0 | ⬜ pending |
| 1-??-02 | TBD | 0 | DATA-02 | — | N/A | integration | `uv run pytest packages/core/tests/test_cache.py::test_second_call_hits_cache -x` | ❌ W0 | ⬜ pending |
| 1-??-03 | TBD | 0 | DATA-03 | — | N/A | unit | `uv run pytest packages/core/tests/test_curvature.py::test_cross_season_stability -x` | ❌ W0 | ⬜ pending |
| 1-??-04 | TBD | 0 | DATA-04 | — | N/A | unit | `uv run pytest packages/core/tests/test_gear_inference.py::test_infer_bahrain_2023_ver -x` | ❌ W0 | ⬜ pending |
| 1-??-05 | TBD | 0 | DATA-05 | path-traversal (T-1-01) | race_id/driver_id validated against regex before cache path construction | unit | `uv run pytest packages/core/tests/test_data_integrity.py::test_corrupted_fixture_excluded -x` | ❌ W0 | ⬜ pending |
| 1-??-06 | TBD | 0 | DATA-05 | — | N/A | unit | `uv run pytest packages/core/tests/test_data_integrity.py::test_clean_fixture_ok -x` | ❌ W0 | ⬜ pending |
| 1-??-07 | TBD | 0 | DATA-05 | — | N/A | unit | `uv run pytest packages/core/tests/test_data_integrity.py::test_throttle_sentinel_detection -x` | ❌ W0 | ⬜ pending |
| 1-??-08 | TBD | 0 | DATA-06 | — | N/A | unit | `uv run pytest packages/core/tests/test_stint_annotation.py -x` | ❌ W0 | ⬜ pending |
| 1-??-09 | TBD | 0 | PHYS-08 (contract) | — | N/A | unit | `uv run pytest packages/core/tests/test_contracts.py::test_placeholder_satisfies_protocol -x` | ❌ W0 | ⬜ pending |
| 1-??-10 | TBD | 0 | PHYS-08 (contract) | — | N/A | unit | `uv run pytest packages/core/tests/test_contracts.py::test_all_seven_contracts_importable_from_single_module -x` | ❌ W0 | ⬜ pending |
| 1-??-11 | TBD | 0 | PHYS-09 (state obj) | — | N/A | unit | `uv run pytest packages/core/tests/test_contracts.py::test_simulation_state_shape -x` | ❌ W0 | ⬜ pending |
| 1-??-12 | TBD | 0 | API-01 | path-traversal (T-1-01) | race_id validated (^[0-9]{4}-[a-z_]+$) before cache lookup | integration | `uv run pytest packages/api/tests/test_endpoints.py::test_get_races -x` | ❌ W0 | ⬜ pending |
| 1-??-13 | TBD | 0 | API-02 | path-traversal (T-1-01) | driver_id validated (^[A-Z]{3}$) before cache lookup | integration | `uv run pytest packages/api/tests/test_endpoints.py::test_get_drivers_for_bahrain_2023 -x` | ❌ W0 | ⬜ pending |
| 1-??-14 | TBD | 0 | API-03 | path-traversal (T-1-01) | Both params validated before filesystem access | integration | `uv run pytest packages/api/tests/test_endpoints.py::test_get_stints_for_ver_bahrain_2023 -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/core/tests/conftest.py` — shared fixtures, `CACHE_DIR` pointing at repo-local test cache dir
- [ ] `packages/core/tests/fixtures/bahrain_2023_ver_stint2.pkl.gz` — canonical fixture (D-06); committed to git (run `scripts/build_canonical_fixture.py` once)
- [ ] `packages/core/tests/fixtures/corrupted_stint.pkl.gz` — hand-corrupted copy with throttle=104, NaN lap times, compound change (for DATA-05 tests)
- [ ] `packages/api/tests/conftest.py` — TestClient fixture, mock FastF1 cache dir
- [ ] `packages/core/tests/test_contracts.py` — stubs for PHYS-08 (contract), PHYS-09 (state obj)
- [ ] `packages/core/tests/test_ingestion.py` — stubs for DATA-01
- [ ] `packages/core/tests/test_cache.py` — stubs for DATA-02
- [ ] `packages/core/tests/test_curvature.py` — stubs for DATA-03
- [ ] `packages/core/tests/test_gear_inference.py` — stubs for DATA-04
- [ ] `packages/core/tests/test_data_integrity.py` — stubs for DATA-05
- [ ] `packages/core/tests/test_stint_annotation.py` — stubs for DATA-06
- [ ] `packages/api/tests/test_endpoints.py` — stubs for API-01, API-02, API-03
- [ ] Root `ruff.toml` with `line-length=100`, import-sorting enabled
- [ ] Root `pyproject.toml` `[tool.mypy]` strict-mode for `packages/core/src/f1_core/contracts.py`; relaxed elsewhere in Phase 1
- [ ] `[dependency-groups] dev = ["pytest>=8", "ruff>=0.7", "pyright>=1.1"]` in root pyproject.toml

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Second CLI invocation returns cached bytes with no network I/O (human-observable) | DATA-02 | Requires network isolation verification | Run `scripts/fetch.py <race_id> <driver_id>` twice; confirm second run completes in <100ms and no Jolpica HTTP request appears in `fastf1` log at DEBUG level |
| Canonical fixture quality score = 1.0 visually confirmed | DATA-05 A6 | Threshold validation is a judgment call | Run `uv run python -c "from f1_core.data_integrity import analyze; ..."` on the Bahrain 2023 fixture and confirm score ≥ 0.9 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
