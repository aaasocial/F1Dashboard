---
status: partial
phase: 03-bayesian-calibration-pipeline
source: [03-VERIFICATION.md]
started: 2026-04-23T00:00:00Z
updated: 2026-04-23T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Full fast test suite
expected: `uv run pytest packages/calibration/tests -x -m "not integration"` exits 0 with 79 passed, 4 deselected
result: [pending]

### 2. CLI invocation
expected: `PYTHONUTF8=1 uv run f1-calibrate --help` shows all 6 subcommands: stage1, stage2, stage3, stage4, stage5, run-all
result: [pending]

### 3. T-3-04 traceback suppression
expected: `PYTHONUTF8=1 uv run f1-calibrate stage1 --compound X9` exits with code 1, prints "Invalid input" (or similar), and contains NO "Traceback" in output (security requirement)
result: [pending]

### 4. Stage 4 integration tests
expected: `uv run pytest packages/calibration/tests/test_stage4_degradation.py -m integration -x` passes (~3-5 min); validates NumPyro NUTS gradient path end-to-end
result: [pending]

### 5. CALIB-03 T_opt/sigma_T design decision
expected: Developer confirms that Stage 3 holding T_opt=95.0 and sigma_T=20.0 fixed (deferred to Stage 4 MCMC) is acceptable as Phase 3 closure
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
