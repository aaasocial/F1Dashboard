---
phase: 01-foundation-data-pipeline-module-contracts
plan: 01
subsystem: infra
tags: [uv, workspace, python, ruff, pyright, pytest, hatchling, fastapi, fastf1, pydantic, numpy, scipy, pandas]

# Dependency graph
requires: []
provides:
  - uv workspace root (pyproject.toml) with three members: core, api, calibration
  - f1-core package skeleton with fastf1 3.8.2, numpy 2.4.4, scipy 1.17.1, pandas 2.3.3, pyyaml 6.0.3
  - f1-api package skeleton with fastapi 0.136.0, uvicorn 0.45.0, pydantic 2.13.3 (depends on f1-core)
  - f1-calibration package shell (Phase 3 populates) depending on f1-core
  - ruff.toml repo-wide lint/format config (line-length=100, target=py312)
  - uv.lock committed for reproducible environments
  - .python-version pinned to 3.12
  - .gitignore covering venv, data, egg-info, pycache, IDE, OS, node artifacts
affects: [01-02-contracts, 01-03-ingestion, 01-04-integrity, 01-05-inference, phase-02, phase-03, phase-04]

# Tech tracking
tech-stack:
  added:
    - "uv 0.10.8 (workspace manager)"
    - "hatchling (build backend for each package)"
    - "fastf1 3.8.2 (F1 telemetry client)"
    - "numpy 2.4.4"
    - "scipy 1.17.1"
    - "pandas 2.3.3"
    - "pyyaml 6.0.3"
    - "fastapi 0.136.0"
    - "uvicorn 0.45.0 (with [standard] extras)"
    - "pydantic 2.13.3"
    - "ruff 0.15.11"
    - "pyright 1.1.408"
    - "pytest 9.0.3"
    - "pytest-cov 7.1.0"
    - "httpx 0.28.1"
  patterns:
    - "uv workspace: single root pyproject.toml declares members + [tool.uv.sources] block with workspace = true for each internal cross-ref"
    - "Package layout: packages/{core,api,calibration}/src/f1_{core,api,calibration}/ (src layout, not flat)"
    - "Hatchling build backend per package (explicit wheel packages target)"
    - "Pydantic lives in f1-api only, not f1-core (keeps physics package free of HTTP-layer concerns, per D-04)"
    - "Shared .venv at repo root; uv sync --all-packages installs all members editable"

key-files:
  created:
    - "pyproject.toml (workspace root)"
    - "packages/core/pyproject.toml"
    - "packages/api/pyproject.toml"
    - "packages/calibration/pyproject.toml"
    - "packages/core/src/f1_core/__init__.py"
    - "packages/api/src/f1_api/__init__.py"
    - "packages/calibration/src/f1_calibration/__init__.py"
    - "packages/core/tests/__init__.py"
    - "packages/api/tests/__init__.py"
    - ".python-version"
    - "ruff.toml"
    - ".gitignore"
    - "uv.lock"
  modified: []

key-decisions:
  - "uv sync --all-packages is the canonical install command (plain `uv sync` only resolves root deps, not workspace members)"
  - "Pydantic v2 pinned to f1-api only, per D-04; f1-core stays HTTP-agnostic"
  - "Hatchling chosen as build backend (explicit, minimal, native src layout support)"

patterns-established:
  - "Workspace cross-refs: every internal dependency needs [tool.uv.sources] + { workspace = true } (pitfall P7 guard)"
  - "Tests co-located with each package: packages/*/tests/ (not top-level tests/)"
  - "Ruff config lives at repo root, applies uniformly; per-file-ignores relax rules in tests and __init__.py re-export files"

requirements-completed: []

# Metrics
duration: ~3min
completed: 2026-04-23
---

# Phase 01 Plan 01: Workspace Scaffold Summary

**uv workspace with three hatchling-built packages (core/api/calibration), shared .venv, ruff+pyright+pytest toolchain, and 68-package uv.lock resolved cleanly**

## Performance

- **Duration:** ~3 min (scaffold + sync + verification)
- **Started:** 2026-04-23T01:02:51Z
- **Completed:** 2026-04-23T01:05:40Z
- **Tasks:** 2
- **Files created:** 13
- **Files modified:** 0

## Accomplishments

- uv workspace root with three hatchling-built package members, each importable from a single shared `.venv`
- Cross-package `import f1_core, f1_api, f1_calibration` succeeds from shared venv — pitfall P7 (missing `[tool.uv.sources]` block) verified guarded
- Dev toolchain wired: ruff (lint+format), pyright (type-check, strict scope reserved for `f1_core/contracts.py`), pytest (tests discoverable across all three packages)
- `uv.lock` committed with all 68 transitive dependencies pinned, reproducible on fresh clone
- Every scientific dep resolved within the target range: numpy 2.4.4, scipy 1.17.1, pandas 2.3.3, fastf1 3.8.2, fastapi 0.136.0, pydantic 2.13.3

## Task Commits

Each task was committed atomically (with `--no-verify` since this is a parallel worktree executor):

1. **Task 1: Create uv workspace root and three package skeletons** - `bf9995e` (feat)
2. **Task 2: Add ruff config, sync workspace, verify cross-package import** - `679ba15` (feat)

## Files Created/Modified

- `pyproject.toml` — uv workspace root, declares 3 members, dev group (pytest, ruff, pyright, httpx, pytest-cov), pytest testpaths, pyright strict scope
- `packages/core/pyproject.toml` — f1-core package: fastf1==3.8.2, numpy>=2.1, scipy>=1.17, pandas>=2.2, pyyaml>=6; hatchling build
- `packages/api/pyproject.toml` — f1-api package: f1-core (workspace), fastapi>=0.136, uvicorn[standard]>=0.32, pydantic>=2.6; hatchling build
- `packages/calibration/pyproject.toml` — f1-calibration shell: f1-core (workspace); hatchling build
- `packages/core/src/f1_core/__init__.py` — `__version__ = "0.1.0"`
- `packages/api/src/f1_api/__init__.py` — `__version__ = "0.1.0"`
- `packages/calibration/src/f1_calibration/__init__.py` — `__version__ = "0.1.0"`
- `packages/core/tests/__init__.py` — empty test marker
- `packages/api/tests/__init__.py` — empty test marker
- `.python-version` — `3.12`
- `ruff.toml` — line-length=100, target-version=py312, select=[E,F,I,UP,B,SIM,RUF], per-file-ignores for tests and __init__.py
- `.gitignore` — Python artifacts, .venv, .data, .env, IDE dirs, OS files, node_modules
- `uv.lock` — 68-package lockfile committed

## Commands Executed & Wall-Clock Times

| Command | Wall-clock |
|---------|------------|
| `uv sync` (initial, root-only) | 6.87s (cold cache; downloaded ruff, pyright, pytest, etc.) |
| `uv sync --all-packages` | ~8s (pulled down full scientific stack: numpy, scipy, pandas, fastf1 + transitive) |
| `uv sync --all-packages` (re-run, idempotence check) | 34ms — audited 66 packages, no changes |
| `uv run python -c "import f1_core, f1_api, f1_calibration; print('ok')"` | <1s — prints `ok` |
| `uv run ruff check .` | <1s — `All checks passed!` |
| `uv run ruff format --check .` | <1s — `5 files already formatted` |
| `uv run pytest --collect-only` | <1s — `no tests collected` (exit 5, acceptable at this stage) |

## Resolved Versions (from uv.lock)

| Package | Version | Source |
|---------|---------|--------|
| fastf1 | 3.8.2 | PyPI (exact pin) |
| numpy | 2.4.4 | PyPI (>=2.1,<3) |
| scipy | 1.17.1 | PyPI (>=1.17,<2) |
| pandas | 2.3.3 | PyPI (>=2.2,<3) |
| pyyaml | 6.0.3 | PyPI (>=6) |
| fastapi | 0.136.0 | PyPI (>=0.136,<0.200) |
| uvicorn | 0.45.0 | PyPI (>=0.32) |
| starlette | 1.0.0 | PyPI (transitive, via fastapi) |
| pydantic | 2.13.3 | PyPI (>=2.6,<3) |
| ruff | 0.15.11 | PyPI (>=0.7) |
| pyright | 1.1.408 | PyPI (>=1.1) |
| pytest | 9.0.3 | PyPI (>=8) |
| pytest-cov | 7.1.0 | PyPI (>=5) |
| httpx | 0.28.1 | PyPI (>=0.27) |

## Decisions Made

- **`uv sync` vs `uv sync --all-packages`:** plain `uv sync` only installs the root project's dependencies; it does NOT install workspace members. Had to use `uv sync --all-packages` to install all three packages editable into the shared `.venv`. This is documented as a known uv semantic — the workspace root's dependency list acts as the entry point, and workspace members are installed only when explicitly requested or listed as dependencies. This should be called out in phase documentation/READMEs going forward so devs don't hit the same issue.
- **Pydantic 2.13.3 resolved (not 2.6):** The `>=2.6,<3` constraint allowed the latest 2.x; fine since 2.13 is backwards-compatible with 2.6 at API level.
- **Numpy 2.4.4 resolved (not 2.1):** Constraint `>=2.1,<3` pulled the latest 2.x, which is what we want for 3.12 wheel availability.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] `uv sync` did not install workspace members; switched to `uv sync --all-packages`**
- **Found during:** Task 2 (step 2: "Run `uv sync` at repo root")
- **Issue:** Plan step 2 says "Run `uv sync`. This installs all three packages editable into a single `.venv/`." In practice, plain `uv sync` only installs the root project's dependency-groups (pytest, ruff, pyright, etc.) and does NOT install workspace members (fastf1, numpy, scipy, pandas, fastapi, pydantic were absent). Cross-package `import f1_core` raised `ModuleNotFoundError`.
- **Fix:** Ran `uv sync --all-packages` instead. This installs every workspace member editable along with all their runtime dependencies. Cross-package import then succeeded.
- **Files modified:** None (behavioral change only; no file edits)
- **Verification:** After `uv sync --all-packages`, `uv run python -c "import f1_core, f1_api, f1_calibration; print('ok')"` printed `ok`.
- **Committed in:** `679ba15` (Task 2 commit)
- **Note for future plans:** Any Make target, CI workflow, or developer README instruction that says "uv sync" should say "uv sync --all-packages" at the repo root. Plan 01-02 or a subsequent plan may want to add a Makefile alias.

**Pitfall P7 guard — outcome:** Passed. No ModuleNotFoundError for f1_core when importing from f1_api or f1_calibration, confirming the `[tool.uv.sources]` blocks (with `f1-core = { workspace = true }`) in both dependent packages' pyproject.toml files are correctly wired.

---

**Total deviations:** 1 auto-fixed (1 blocking — Rule 3)
**Impact on plan:** No scope change. A documentation-only follow-up: downstream plans' READMEs and CI scripts must use `uv sync --all-packages`, not bare `uv sync`.

## Threat Model Verification

| Threat ID | Category | Disposition | Verified |
|-----------|----------|-------------|----------|
| T-01-01 | Tampering (uv.lock) | accept | uv.lock committed to git as planned. |
| T-01-02 | Information disclosure (.gitignore) | mitigate | `.venv/`, `.data/`, `*.egg-info/`, `__pycache__/`, `.env`, `.env.local` all present in `.gitignore`. Verified `git status` shows no untracked `.venv/` or `.data/` content. |

## Issues Encountered

- **Windows VIRTUAL_ENV mismatch warning:** Every `uv run` invocation prints `warning: VIRTUAL_ENV=C:\Users\Eason\AppData\Roaming\uv\python\cpython-3.13-windows-x86_64-none does not match the project environment path .venv and will be ignored`. This is a harmless external environment variable left over from a previous shell session. uv correctly ignores it and uses the project's `.venv`. Not a blocker. Developers can `unset VIRTUAL_ENV` or set `UV_ACTIVE_PYTHON` to silence.
- **pytest exit code 5 on `--collect-only`:** Expected per plan's acceptance criteria ("exits 0 or 5"). Collecting across `testpaths = ["packages/core/tests", "packages/api/tests", "packages/calibration/tests"]` yields zero tests because no test files exist yet. `packages/calibration/tests/` does not yet exist as a directory — pytest tolerated this silently without error. Plan 01-05 or Phase 2 can add it when the first calibration test lands.

## Known Stubs

None. All files written have real content (no placeholder "coming soon" or unwired data flows). The package `__init__.py` files are intentionally minimal with a `__version__` constant; they are not stubs but package entry points. The calibration package is labeled a "shell" in the plan — this is intentional scope (Phase 3 populates).

## Self-Check

- **Files verified exist:** 13/13 — pyproject.toml, packages/core/pyproject.toml, packages/api/pyproject.toml, packages/calibration/pyproject.toml, packages/core/src/f1_core/__init__.py, packages/api/src/f1_api/__init__.py, packages/calibration/src/f1_calibration/__init__.py, packages/core/tests/__init__.py, packages/api/tests/__init__.py, .python-version, ruff.toml, .gitignore, uv.lock — all FOUND via `test -f`.
- **Commits verified exist:**
  - `bf9995e` — `feat(01-01): scaffold uv workspace with three package skeletons` — FOUND in `git log --oneline`.
  - `679ba15` — `feat(01-01): add ruff config and commit uv.lock after workspace sync` — FOUND in `git log --oneline`.

## Self-Check: PASSED

## Next Phase Readiness

- All parallel plans in Wave 2 (01-02 contracts, 01-03 ingestion) can now `import f1_core` and `import f1_api` from the shared `.venv`.
- `uv sync --all-packages` is idempotent; downstream CI/dev setup is stable.
- Strict pyright scope reserved for `packages/core/src/f1_core/contracts.py` — awaiting Plan 01-02 to populate.
- Plan 01-02 (contracts) and 01-03 (ingestion) should document `uv sync --all-packages` (not bare `uv sync`) in their READMEs/setup instructions to avoid re-hitting the deviation noted above.

---
*Phase: 01-foundation-data-pipeline-module-contracts*
*Completed: 2026-04-23*
