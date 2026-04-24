---
status: partial
phase: 04-simulation-api-uncertainty-quantification
source: [04-VERIFICATION.md]
started: 2026-04-24T12:45:00Z
updated: 2026-04-24T12:45:00Z
---

## Current Test

[awaiting human testing — deferred until Phase 3 calibration artifacts and Phase 5 physics engine are available]

## Tests

### 1. Wall-Time D-04 Budget with Real Physics

expected: After Phase 5 delivers `run_simulation`, run the app locally with a Phase 3 calibration artifact and POST `/simulate` for the canonical Bahrain 2023 VER stint. Cold-path response time < 2.0s with `metadata.k_draws == 100` and all three data levels (per_timestep, per_lap, per_stint) present with CI triplets.
result: [pending — requires Phase 3 calibration artifacts + Phase 5 physics engine]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
