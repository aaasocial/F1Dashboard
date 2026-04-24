---
phase: 01-foundation-data-pipeline-module-contracts
plan: 04
subsystem: core/data-pipeline
tags: [data-integrity, stint-annotation, curvature, gear-inference, savgol, yaml]
requires:
  - f1_core.contracts.QualityReport
  - f1_core.contracts.QualityVerdict
  - f1_core.ingestion.cache.StintArtifact
  - f1_core.ingestion.cache.StintKey
  - packages/core/tests/fixtures/bahrain_2023_ver_stint2.pkl.gz
provides:
  - f1_core.data_integrity.analyze
  - f1_core.stint_annotation.annotate_stint
  - f1_core.stint_annotation.AnnotatedLap
  - f1_core.stint_annotation.AnnotatedStint
  - f1_core.curvature.compute_curvature_map
  - f1_core.curvature.curvature_from_xy
  - f1_core.gear_inference.infer_gear_ratios
  - f1_core.filters.savgol_velocity
  - packages/core/src/f1_core/data/compound_mapping.yaml
  - packages/core/src/f1_core/data/known_issues.yaml
  - packages/core/tests/fixtures/corrupted_stint.pkl.gz
affects:
  - Phase 2 Module A (consumes curvature map + gear ratios)
  - Phase 2/3 (all modules gate on QualityReport.verdict != REFUSE)
  - Phase 5 dashboard (surfaces quality badge)
tech-stack:
  added:
    - pyyaml (YAML loader for mapping/known-issues files via yaml.safe_load)
    - scipy.signal.savgol_filter (velocity differentiation)
    - scipy.interpolate.CubicSpline (curvature)
  patterns:
    - Dataclasses for contract outputs (AnnotatedLap, AnnotatedStint)
    - yaml.safe_load for all YAML reads (T-01-08 mitigation)
    - Score subtracted incrementally, clipped to [0, 1], then bucketed
    - Median aggregation across laps for noise-robust curvature (pitfall P8)
key-files:
  created:
    - packages/core/src/f1_core/filters.py
    - packages/core/src/f1_core/data_integrity.py
    - packages/core/src/f1_core/stint_annotation.py
    - packages/core/src/f1_core/curvature.py
    - packages/core/src/f1_core/gear_inference.py
    - packages/core/src/f1_core/data/__init__.py
    - packages/core/src/f1_core/data/compound_mapping.yaml
    - packages/core/src/f1_core/data/known_issues.yaml
    - packages/core/tests/test_data_integrity.py
    - packages/core/tests/test_stint_annotation.py
    - packages/core/tests/test_curvature.py
    - packages/core/tests/test_gear_inference.py
    - packages/core/tests/fixtures/corrupted_stint.pkl.gz
    - scripts/build_corrupted_fixture.py
  modified: []
decisions:
  - Verdict thresholds wired as OK>=0.9, WARN>=0.7, EXCLUDE>=0.4, REFUSE<0.4 per locked_decisions (A6)
  - Savitzky-Golay defaults locked at window=9, polyorder=3, delta=0.25 (4 Hz telemetry)
  - compound_mapping.yaml keyed by "{year}-{round_zero_padded}" (e.g. "2023-01" for Bahrain 2023)
  - known_issues.yaml keyed likewise; loader uses yaml.safe_load (T-01-08)
  - gear_inference returns the combined ratio G_gear*G_final (caller splits if needed)
  - curvature aggregation uses median across laps (robust to single-lap noise)
metrics:
  duration: ~0.25 h
  completed: 2026-04-23
  tasks: 2
  tests_added: 25 (14 data-integrity/annotation, 5 curvature, 4 gear-inference, +2 savgol edges)
  total_core_tests: 61 (all pass)
  files_created: 14
  files_modified: 1 (stint_annotation.py SIM108 tightening within Task 2)
---

# Phase 1 Plan 04: Data Integrity, Annotation, Curvature & Gear Inference Summary

Turn a raw `StintArtifact` into a physics-ready input: quality scoring (DATA-05), per-lap annotation with compound letter / tire age / fuel / weather / SC-VSC flags (DATA-06), reference curvature kappa(s) from fastest-lap pos_data (DATA-03), and per-team gear ratios from steady-state telemetry (DATA-04). Seven new modules, two YAML data files, 25 new tests, and a committed corrupted-stint fixture — with the canonical Bahrain 2023 VER stint 2 fixture passing end-to-end.

## What Shipped

### DATA-05: `f1_core.data_integrity.analyze`

- Input: `(car_data, laps, pos_data, year, round_number, known_issues?)`
- Output: `QualityReport(score, verdict, issues, throttle_sentinel_count, nan_lap_time_count, compound_mislabel, missing_position_pct)`
- Counts:
  - Throttle sentinels (value > 100 per pitfall P2)
  - NaN LapTime rows
  - Within-stint compound changes (pitfall P3)
  - Missing (X, Y) position fraction
- Known-issues override via `known_issues.yaml` (keyed `"{year}-{round:02d}"`); a `compound_mislabel` tag flips the boolean and downgrades at least one verdict band in practice.
- Thresholds (locked per A6): OK >= 0.9, WARN 0.7-0.9, EXCLUDE 0.4-0.7, REFUSE < 0.4.

### DATA-06: `f1_core.stint_annotation.annotate_stint`

- Input: `StintArtifact + year + round_number`
- Output: `AnnotatedStint(key, laps: list[AnnotatedLap], quality?)`
- Per-lap: `lap_number, compound, compound_letter (C1-C5 or ""), tire_age_laps, fresh_tyre, lap_time_s, fuel_estimate_kg, air_temp_c, track_temp_c, is_in_lap, is_out_lap, is_sc_vsc, exclude_from_degradation`.
- Weather via nearest-time match in `artifact.weather`; fuel via linear burn from FUEL_START_KG=110 at FUEL_BURN_KG_PER_LAP=1.7; SC/VSC overlap via `Status in {4, 6, 7}` on `artifact.track_status` within the lap's `LapStartTime`-`Time` window.

### DATA-03: `f1_core.curvature.compute_curvature_map`

- `curvature_from_xy(x, y, grid)` fits `CubicSpline(s, X)` and `CubicSpline(s, Y)` on arc length s and returns `kappa = X'Y'' - Y'X''`.
- `compute_curvature_map(laps_xy, grid)` median-aggregates per-lap kappa to damp single-lap noise (pitfall P8).

### DATA-04: `f1_core.gear_inference.infer_gear_ratios`

- Filters: `Throttle >= 99` and `Speed > 50 km/h`, grouped by `nGear` (only 1-8 kept, >= 20 samples per gear).
- Returns `{gear: combined_ratio}` with `combined_ratio = 2*pi*R_0*RPM / (60*V_mps)`, R_0 = 0.330 m.

### Shared Filter: `f1_core.filters.savgol_velocity`

- Wraps `scipy.signal.savgol_filter` with 4 Hz defaults: `window=9, polyorder=3, delta=0.25, deriv=1, mode="interp"`.
- Guards: odd-window + order-lt-window ValueError; samples-lt-window falls back to `np.gradient`.

### Data Files

- `packages/core/src/f1_core/data/compound_mapping.yaml` — seeded with 2023-01 (Bahrain), 2023-04 (Azerbaijan), 2024-01 (Bahrain).
- `packages/core/src/f1_core/data/known_issues.yaml` — seeded with 2022-17 (Japan throttle sentinels) and 2025-13 (Belgium compound mislabel).

### Fixtures + Scripts

- `scripts/build_corrupted_fixture.py` mutates the canonical fixture with: 5% throttle=104 rows, NaN LapTime on 3 laps, within-stint compound change (second half -> HARD).
- `packages/core/tests/fixtures/corrupted_stint.pkl.gz` — committed (~21.4 MB).

## Observed Values (Canonical Bahrain 2023 VER Stint 2)

| Check | Expected | Observed |
|-------|----------|----------|
| Quality score (clean) | >= 0.9 | **1.0000** |
| Quality verdict (clean) | OK | **OK** |
| Quality score (corrupted) | < 0.7 | **0.5136** |
| Quality verdict (corrupted) | EXCLUDE or REFUSE | **EXCLUDE** |
| Gears inferred | >= 4 | **6 (gears 3, 4, 5, 6, 7, 8)** |
| Gear-ratio monotonicity | higher gear -> lower ratio | Satisfied (3: 9.13, 4: 7.68, 5: 6.45, 6: 5.61, 7: 4.95, 8: 4.44) |
| Compound letter for SOFT | C3 (per compound_mapping.yaml 2023-01) | **C3** |

**Curvature characterization** (single-lap pos_data slice, grid = np.arange(5, 5400, 5)):
- Grid size: 1079 samples
- Peak |kappa|: 0.0529 (1/R ~ 18.9 m — matches Turn 10 hairpin inner line)
- Median |kappa|: 0.000788 (most of the track is nearly straight between turns)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Adjusted `test_annotate_stint_compound_letter_mapped` to match actual fixture compound**

- **Found during:** Task 1 (writing tests against the canonical fixture)
- **Issue:** The plan test asserted `MEDIUM -> C2` on Bahrain 2023 VER stint 2, but inspecting the committed fixture showed `a.laps.Compound.unique() == ['SOFT']`. VER's stint 2 at Bahrain 2023 was SOFT, not MEDIUM.
- **Fix:** Rewrote the test to assert each compound seen in the fixture maps to its correct letter via the `{SOFT: C3, MEDIUM: C2, HARD: C1}` 2023-01 mapping. Verified SOFT -> C3 on the fixture as the concrete passing case.
- **Files modified:** `packages/core/tests/test_stint_annotation.py`
- **Commit:** 3547611

**2. [Rule 1 - Bug] Fixed `test_compute_curvature_map_cross_lap_median` outlier-rejection assertion**

- **Found during:** Task 2 (first run of test_curvature.py)
- **Issue:** The plan test passed two laps to `compute_curvature_map` (one clean R=100, one noisy R=110) and asserted `|kappa|.mean() < 0.02`. With only two samples, `np.median` is effectively the mean; the noisy lap's second-derivative amplification (O(noise/dx^2)) dominated and pushed `|kappa|` to ~0.167.
- **Fix:** Expanded the test to three clean laps + one noisy outlier, giving median something to suppress. The 4-lap median now cleanly sits at ~0.01.
- **Files modified:** `packages/core/tests/test_curvature.py`
- **Commit:** a3f1636

### Minor Cleanups

**3. [Rule 2 - Robustness] Annotation NaN-safety on numeric row fields**

- **Found during:** Task 1 (writing `annotate_stint` against fixture where some rows have NaN TyreLife/FreshTyre)
- **Issue:** The plan's annotation snippet coerced `row.get("TyreLife", 0)` directly with `int(...)`; if the source DataFrame has NaN for a field, `int(nan)` raises.
- **Fix:** Added `pd.notna(...) else default` guards on `LapNumber`, `TyreLife`, `FreshTyre`, `PitOutTime`, `PitInTime`, plus NaN-safe weather lookups.
- **Files modified:** `packages/core/src/f1_core/stint_annotation.py`
- **Commit:** 3547611 (initial), a3f1636 (SIM108 tightening)

**4. [Rule 1 - Style] Ruff SIM108 on `lap_time_s` assignment**

- **Found during:** Phase-level `uv run ruff check packages/core/src/f1_core` after Task 2
- **Issue:** Four-line `if/else` where ruff preferred a conditional expression.
- **Fix:** Collapsed to a ternary.
- **Files modified:** `packages/core/src/f1_core/stint_annotation.py`
- **Commit:** a3f1636

## Tests

### New Tests Added (25)

**`test_data_integrity.py` (7)**
- `test_clean_fixture_ok`
- `test_corrupted_fixture_excluded`
- `test_throttle_sentinel_detection`
- `test_nan_lap_time_counted`
- `test_compound_mislabel_within_stint`
- `test_missing_position_pct`
- `test_known_issues_override_downgrades_verdict`

**`test_stint_annotation.py` (7)**
- `test_annotate_stint_produces_lap_per_input`
- `test_annotate_stint_compound_letter_mapped` (checks SOFT->C3 on canonical fixture)
- `test_annotate_stint_fuel_estimate_monotonic`
- `test_annotate_stint_in_out_lap_flags`
- `test_annotate_stint_sc_vsc_synthetic`
- `test_savgol_velocity_shape`
- `test_savgol_velocity_rejects_even_window`

**`test_curvature.py` (5)**
- `test_curvature_from_xy_synthetic_circle` (R=100 -> |kappa| in 0.005-0.015)
- `test_compute_curvature_map_deterministic` (bitwise-identical output)
- `test_compute_curvature_map_shape`
- `test_compute_curvature_map_raises_on_empty`
- `test_compute_curvature_map_cross_lap_median` (3 clean + 1 noisy -> median clean)

**`test_gear_inference.py` (4)**
- `test_infer_gear_ratios_rejects_missing_columns`
- `test_infer_gear_ratios_ignores_low_throttle`
- `test_infer_gear_ratios_synthetic_fixed_ratio` (r=4.0 recovered within 0.05)
- `test_infer_gear_ratios_bahrain_2023_ver_canonical` (6 gears, monotonic)

### Suite Health

- `uv run pytest packages/core/tests -x` -> **61 passed in 31.19 s**
- `uv run ruff check packages/core/src/f1_core` -> **All checks passed!**
- `uv run pyright packages/core/src/f1_core/contracts.py` -> **0 errors, 0 warnings**

## Commits

- `3547611` feat(01-04): data integrity + stint annotation + filters + corrupted fixture
- `a3f1636` feat(01-04): curvature map + gear-ratio inference (DATA-03, DATA-04)

## Requirements Closed

- DATA-03 (curvature map)
- DATA-04 (gear ratios)
- DATA-05 (quality scoring)
- DATA-06 (per-lap annotation)

## Follow-ups / Known Deferrals

- **Fastest-20% lap selection in `compute_curvature_map`:** The module accepts a pre-selected list of `(x, y)` per-lap arrays. The caller (Phase 2 Module A or a data-prep utility) is responsible for slicing pos_data per lap and selecting the fastest 20%. A helper wrapper around `StintArtifact.pos_data + StintArtifact.laps` could live here later, but the plan did not mandate it in Phase 1.
- **Curvature cache** on disk (`.data/curvature/{year}_{circuit_slug}.npz` per locked_decisions): not yet wired — again, expected at the Module A integration point in Phase 2.
- **Fuel-burn calibration:** FUEL_START_KG=110, FUEL_BURN_KG_PER_LAP=1.7 are approximations. Phase 3 will refine these either as hyperparameters or by per-race fuel-load tracking.
- **`AnnotatedStint.quality`** is threaded as an optional field; Plan 05 (API stub) is expected to wire `analyze()` + `annotate_stint()` together and populate it before returning.

## Self-Check: PASSED

Files verified present:
- packages/core/src/f1_core/filters.py FOUND
- packages/core/src/f1_core/data_integrity.py FOUND
- packages/core/src/f1_core/stint_annotation.py FOUND
- packages/core/src/f1_core/curvature.py FOUND
- packages/core/src/f1_core/gear_inference.py FOUND
- packages/core/src/f1_core/data/compound_mapping.yaml FOUND
- packages/core/src/f1_core/data/known_issues.yaml FOUND
- packages/core/tests/fixtures/corrupted_stint.pkl.gz FOUND (21.4 MB)
- packages/core/tests/test_data_integrity.py FOUND
- packages/core/tests/test_stint_annotation.py FOUND
- packages/core/tests/test_curvature.py FOUND
- packages/core/tests/test_gear_inference.py FOUND
- scripts/build_corrupted_fixture.py FOUND

Commits verified:
- 3547611 FOUND
- a3f1636 FOUND

Acceptance checks:
- `data_integrity.py` contains `def analyze` -> YES
- `data_integrity.py` uses `yaml.safe_load` -> YES
- `SENTINEL_THROTTLE_THRESHOLD = 100` -> YES
- `stint_annotation.py` contains `class AnnotatedLap` + `class AnnotatedStint` + `def annotate_stint` -> YES
- SC/VSC code set `{4, 6, 7}` -> YES
- `filters.py` defaults `DEFAULT_WINDOW=9, DEFAULT_POLYORDER=3, DEFAULT_DELTA=0.25` -> YES
- `compound_mapping.yaml` contains `"2023-01"` with HARD: C1, MEDIUM: C2, SOFT: C3 -> YES
- `curvature.py` imports `CubicSpline` -> YES
- `gear_inference.py` has `R_0_M = 0.330`, `THROTTLE_MIN = 99.0`, `SPEED_MIN_KMH = 50.0` -> YES
- Corrupted fixture >= 50 KB -> YES (21.4 MB)
- All 13 new tests + full core suite (61) pass -> YES
