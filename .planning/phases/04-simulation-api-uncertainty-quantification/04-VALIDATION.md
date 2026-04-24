---
phase: 4
slug: simulation-api-uncertainty-quantification
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-24
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8+ (already installed in root `dev` dependency group) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` at repo root |
| **Quick run command** | `pytest packages/api/tests/ -x` |
| **Full suite command** | `pytest packages/api/tests/ packages/core/tests/ -v` |
| **Integration marker** | `-m "integration"` (already in pyproject.toml markers list) |
| **Estimated runtime** | ~15 s (unit); ~60 s (integration w/ K=100 benchmark) |

---

## Sampling Rate

- **After every task commit:** Run `pytest packages/api/tests/ -x`
- **After every plan wave:** Run `pytest packages/api/tests/ -v` plus `-m integration` benchmarks introduced in that wave
- **Before `/gsd-verify-work`:** Full suite `pytest -v` + `pytest packages/api/tests/ -m integration` must be green
- **Max feedback latency:** 15 seconds (unit), 60 seconds (integration)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 4-W0-01 | W0 | 0 | API-04 | — | N/A | unit | `pytest packages/api/tests/test_simulate.py -x` | ❌ W0 | ⬜ pending |
| 4-W0-02 | W0 | 0 | API-05 | — | N/A | unit | `pytest packages/api/tests/test_calibration.py -x` | ❌ W0 | ⬜ pending |
| 4-W0-03 | W0 | 0 | API-06 | Zip Slip | Path traversal rejected | unit | `pytest packages/api/tests/test_sessions.py -x` | ❌ W0 | ⬜ pending |
| 4-04-a | 04 | 1 | API-04 | — | N/A | unit | `pytest packages/api/tests/test_simulate.py::test_simulate_happy_path -x` | ❌ W0 | ⬜ pending |
| 4-04-b | 04 | 1 | API-04 | — | N/A | unit | `pytest packages/api/tests/test_simulate.py::test_simulate_three_levels -x` | ❌ W0 | ⬜ pending |
| 4-04-c | 04 | 1 | API-04 | — | N/A | unit | `pytest packages/api/tests/test_simulate.py::test_simulate_ci_triplets -x` | ❌ W0 | ⬜ pending |
| 4-04-d | 04 | 1 | API-04 | — | Override abuse | unit | `pytest packages/api/tests/test_simulate.py::test_simulate_overrides -x` | ❌ W0 | ⬜ pending |
| 4-04-e | 04 | 1 | API-04 | — | N/A | integration | `pytest packages/api/tests/test_simulate.py::test_simulate_cache_hit -m integration` | ❌ W0 | ⬜ pending |
| 4-04-f | 04 | 1 | API-04 | — | N/A | unit | `pytest packages/api/tests/test_simulate.py::test_simulate_cache_invalidation -x` | ❌ W0 | ⬜ pending |
| 4-04-g | 04 | 1 | API-04 | DoS | Wall-time budget enforced | integration | `pytest packages/api/tests/test_simulate.py::test_simulate_wall_time -m integration` | ❌ W0 | ⬜ pending |
| 4-04-h | 04 | 1 | API-04 | D-05 | No PyMC imported at runtime | unit | `pytest packages/api/tests/test_simulate.py::test_no_mcmc_at_runtime -x` | ❌ W0 | ⬜ pending |
| 4-05-a | 05 | 1 | API-05 | — | N/A | unit | `pytest packages/api/tests/test_calibration.py::test_calibration_happy_path -x` | ❌ W0 | ⬜ pending |
| 4-05-b | 05 | 1 | API-05 | SQL injection | Compound whitelist enforced | unit | `pytest packages/api/tests/test_calibration.py::test_calibration_invalid_compound -x` | ❌ W0 | ⬜ pending |
| 4-05-c | 05 | 1 | API-05 | — | 404 on missing data | unit | `pytest packages/api/tests/test_calibration.py::test_calibration_no_data -x` | ❌ W0 | ⬜ pending |
| 4-05-d | 05 | 1 | API-05 | — | N/A | unit | `pytest packages/api/tests/test_calibration.py::test_calibration_all_stages -x` | ❌ W0 | ⬜ pending |
| 4-05-e | 05 | 1 | API-05 | — | N/A | unit | `pytest packages/api/tests/test_calibration.py::test_calibration_stage4_diagnostics -x` | ❌ W0 | ⬜ pending |
| 4-06-a | 06 | 2 | API-06 | — | N/A | unit | `pytest packages/api/tests/test_sessions.py::test_upload_happy_path -x` | ❌ W0 | ⬜ pending |
| 4-06-b | 06 | 2 | API-06 | Zip Slip | Path traversal rejected | unit (**SECURITY**) | `pytest packages/api/tests/test_sessions.py::test_upload_rejects_path_traversal -x` | ❌ W0 | ⬜ pending |
| 4-06-c | 06 | 2 | API-06 | — | 400 on non-zip | unit | `pytest packages/api/tests/test_sessions.py::test_upload_rejects_non_zip -x` | ❌ W0 | ⬜ pending |
| 4-06-d | 06 | 2 | API-06 | — | N/A | integration | `pytest packages/api/tests/test_sessions.py::test_session_routes_simulate -m integration` | ❌ W0 | ⬜ pending |
| 4-06-e | 06 | 2 | API-06 | — | TTL enforced | unit | `pytest packages/api/tests/test_sessions.py::test_session_ttl_cleanup -x` | ❌ W0 | ⬜ pending |
| 4-06-f | 06 | 2 | API-06 | Decompression bomb | Oversized zip rejected | unit | `pytest packages/api/tests/test_sessions.py::test_upload_rejects_bomb -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/api/tests/test_simulate.py` — stubs for API-04-a..h
- [ ] `packages/api/tests/test_calibration.py` — stubs for API-05-a..e
- [ ] `packages/api/tests/test_sessions.py` — stubs for API-06-a..f
- [ ] `packages/api/tests/fixtures/` — new directory
- [ ] `packages/api/tests/fixtures/calibration_fixture.py` — builds a tiny 2-chain 50-draw Stage-4 NetCDF + inserts a single SQLite `calibration_runs` row
- [ ] `packages/api/tests/fixtures/zip_fixtures.py` — builds valid + malicious zips programmatically (zip slip, bomb, symlink, non-zip)
- [ ] `packages/api/tests/conftest.py` — extend with: NetCDF fixture, temporary DB path, monkeypatched `run_simulation` (fast unit path), monkeypatched `load_stint` (session tests)

No framework install needed — pytest 8+ already in root dev group.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| GZip compression effective on large per-timestep payloads | API-04 | Requires live curl + response size measurement | `curl -H "Accept-Encoding: gzip" -o /dev/null -w "%{size_download}" http://localhost:8000/simulate` with a 22-lap stint; verify compressed < 500 KB |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING (❌ W0) references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s (unit), < 60s (integration)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
