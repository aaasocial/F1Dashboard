---
phase: 2
slug: physics-model-modules-a-g
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-23
updated: 2026-04-23
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-benchmark 5.2.3 + hypothesis 6.x |
| **Config file** | root `pyproject.toml` `[tool.pytest.ini_options]` (already exists) |
| **Quick run command** | `uv run pytest packages/core/tests/physics/ -x --benchmark-disable` |
| **Full suite command** | `uv run pytest packages/core/tests/ --benchmark-disable` then `uv run pytest packages/core/tests/physics/test_benchmark.py --benchmark-only` |
| **Estimated runtime** | ~15 seconds (quick), ~45 seconds (full incl. benchmark) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest packages/core/tests/physics/ -x --benchmark-disable`
- **After every plan wave:** Run full suite (correctness + benchmark)
- **Before `/gsd-verify-work`:** Full suite must be green (including benchmark)
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-T1 | 01 | 0 | PHYS-08, PHYS-09 | T-02-01 | uv.lock hashes verified | setup | `uv sync && uv run python -c "import typer, pytest_benchmark, hypothesis"` | ❌ W0 | ⬜ pending |
| 02-01-T2 | 01 | 0 | PHYS-08, PHYS-09 | — | frozen contracts prevent cross-module mutation | unit | `uv run pytest packages/core/tests/test_contracts.py -x --benchmark-disable` | ✅ existing | ⬜ pending |
| 02-01-T3 | 01 | 0 | PHYS-08, PHYS-09 | T-02-04 | pydantic-exclusion extends to physics/ | setup | `uv run python -c "from f1_core.physics import make_nominal_params; make_nominal_params()"` | ❌ W0 | ⬜ pending |
| 02-01-T4 | 01 | 0 | PHYS-01–09 | — | — | setup (stubs) | `uv run pytest packages/core/tests/physics/ --benchmark-disable` (all skip) | ❌ W0 | ⬜ pending |
| 02-02-T1 | 02 | 1 | PHYS-01 | — | — | unit | `uv run python -c "from f1_core.physics.protocols import StintPreprocessor"` | ❌ W0 | ⬜ pending |
| 02-02-T2 | 02 | 1 | PHYS-01 | T-02-05 | NaN / empty-array guard | unit+integration | `uv run pytest packages/core/tests/physics/test_module_a.py -x --benchmark-disable` | ❌ W0 | ⬜ pending |
| 02-03-T1 | 03 | 1 | PHYS-02 | T-02-08 | 50 N floor + unclipped variant | unit+property | `uv run pytest packages/core/tests/physics/test_module_b.py -x --benchmark-disable` | ❌ W0 | ⬜ pending |
| 02-03-T2 | 03 | 1 | PHYS-03 | T-02-07 | division-by-zero guards | unit+property | `uv run pytest packages/core/tests/physics/test_module_c.py -x --benchmark-disable` | ❌ W0 | ⬜ pending |
| 02-04-T1 | 04 | 1 | PHYS-04 | T-02-10, T-02-11 | previous-step T_tread parameter name | unit | `uv run pytest packages/core/tests/physics/test_module_d.py -x --benchmark-disable` | ❌ W0 | ⬜ pending |
| 02-04-T2 | 04 | 1 | PHYS-05 | T-02-09 | MAX_EVENTS=500 cap | unit | `uv run pytest packages/core/tests/physics/test_module_e.py -x --benchmark-disable` | ❌ W0 | ⬜ pending |
| 02-05-T1 | 05 | 1 | PHYS-06 | — | 6000-step stability test | unit+integration | `uv run pytest packages/core/tests/physics/test_module_f.py -x --benchmark-disable` | ❌ W0 | ⬜ pending |
| 02-05-T2 | 05 | 1 | PHYS-07 | T-02-12, T-02-13, T-02-14 | Arrhenius overflow clamp, μ_0/d_tread floors | unit | `uv run pytest packages/core/tests/physics/test_module_g.py -x --benchmark-disable` | ❌ W0 | ⬜ pending |
| 02-06-T1 | 06 | 2 | PHYS-08, PHYS-09 | T-02-18 | events list cap through pipeline | architecture+integration | `uv run pytest packages/core/tests/physics/test_orchestrator.py -x --benchmark-disable` | ❌ W0 | ⬜ pending |
| 02-06-T2 | 06 | 2 | PHYS-08 (CLI D-05) | T-02-15, T-02-16 | driver_code regex upstream, exception messages only | integration | `uv run pytest packages/core/tests/physics/test_cli.py -x --benchmark-disable` | ❌ W0 | ⬜ pending |
| 02-07-T1 | 07 | 3 | PHYS-08, PHYS-09 | — | — | architecture (AST) | `uv run pytest packages/core/tests/physics/test_architecture.py -x --benchmark-disable` | ❌ W0 | ⬜ pending |
| 02-07-T2 | 07 | 3 | Criterion 2 | T-02-21 | two-tier threshold | benchmark | `uv run pytest packages/core/tests/physics/test_benchmark.py --benchmark-only` | ❌ W0 | ⬜ pending |
| 02-07-T3 | 07 | 3 | Criterion 2 | T-02-19, T-02-20 | 15min timeout, pinned action versions | CI | (runs on push to master) | ❌ W0 | ⬜ pending |
| 02-07-T4 | 07 | 3 | Criterion 2 | — | — | manual | human verifies local benchmark + CLI | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

All Wave 0 items are produced by Plan 01 (02-01-infrastructure-and-contracts-PLAN.md) Task 4:

- [ ] `packages/core/tests/physics/__init__.py` — test package marker (Plan 01 Task 3 creates this)
- [ ] `packages/core/tests/physics/conftest.py` — shared fixtures (`canonical_stint_artifact`, `synthetic_kinematic_state`, `nominal_params`)
- [ ] `packages/core/tests/physics/test_module_a.py` through `test_module_g.py` — stub files, one per module
- [ ] `packages/core/tests/physics/test_orchestrator.py` — execution order + state carry stubs
- [ ] `packages/core/tests/physics/test_architecture.py` — AST-walker stubs (no-inner-for-loop, no-sibling-imports)
- [ ] `packages/core/tests/physics/test_cli.py` — Typer CliRunner stub
- [ ] `packages/core/tests/physics/test_benchmark.py` — `@pytest.mark.benchmark` stub for <200ms assertion
- [ ] `uv add --dev pytest-benchmark hypothesis` and `uv add typer` in `packages/core` (Plan 01 Task 1)
- [ ] CI benchmark job committed (`.github/workflows/benchmark.yml`) asserting <600ms on CI (Plan 07 Task 3)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `f1-simulate 2023 Bahrain VER 2` prints complete per-lap table on real FastF1 data | D-05 | Requires network or warm FastF1 cache; impractical in CI cold | Run command, verify 23 rows printed with Lap/Compound/Age/Pred/Obs/Δ/Grip%/T_tread/E_tire columns, exit code 0 |
| Local `<200 ms` benchmark threshold actually holds on developer machine | Criterion 2 | Hardware-dependent; CI uses 600 ms threshold per Pitfall 7 | Run `uv run pytest packages/core/tests/physics/test_benchmark.py --benchmark-only` locally and confirm green |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (Plan 01 creates all stub targets)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (Plan 01)
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved after Plan 01 (Wave 0) completes
