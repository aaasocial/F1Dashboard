# Phase 1: Foundation, Data Pipeline & Module Contracts - Research

**Researched:** 2026-04-23
**Domain:** Python scientific-app scaffolding — uv workspace layout, FastF1 ingestion + caching, data-integrity scoring, typed physics-module contracts, FastAPI read-only endpoints
**Confidence:** HIGH (stack choices already locked upstream; Phase 1 research is about correctly wiring them)

---

## Summary

Phase 1 is a structural phase: no physics computation, no Bayesian inference, no frontend. The deliverables are (a) a three-package uv workspace with a shared lockfile, (b) a FastF1 ingestion layer with a two-layer disk cache and an explicit `data_integrity.py` module, (c) per-circuit curvature and per-team gear-ratio inference utilities that feed Phase 2, (d) seven typed `@dataclass` contracts plus a `PhysicsModule` `Protocol`, and (e) three read-only FastAPI endpoints (`/races`, `/races/{id}/drivers`, `/stints/{race_id}/{driver_id}`) serving cached data.

Every stack decision that matters is already locked in CONTEXT.md: uv workspaces, `@dataclass` (not Pydantic) for physics, `typing.Protocol` for contracts, Pydantic v2 only at the API edge, the canonical 2023 Bahrain VER stint as the integration fixture. The research below is prescriptive — it documents how to implement those locked choices correctly, not which alternatives to consider.

**Primary recommendation:** Build the skeleton top-down in this order: (1) uv workspace + lint/format/test scaffolding, (2) contracts module with placeholder implementations and conformance tests, (3) FastF1 ingestion with two-layer cache, (4) `data_integrity.py` + `stint_annotation.py` + `curvature.py` + `gear_inference.py` as orthogonal `packages/core` sub-modules, (5) FastAPI read-only endpoints, (6) fetch CLI at the very end. Contracts and cache are the unblocking dependencies for Phases 2–4; everything else is supporting infrastructure.

---

## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01: Repo layout** — Monorepo with a deeper package structure at root:
```
F1 Dashboard/
├── packages/
│   ├── core/          # physics contracts, data pipeline, curvature/gear inference
│   ├── api/           # FastAPI app, depends on core
│   └── calibration/   # offline CLI calibration pipeline, depends on core
├── frontend/          # React + TypeScript + Vite
├── notebooks/         # educational Jupyter notebooks
├── scripts/           # prewarm, fetch CLI, etc.
├── .planning/
└── pyproject.toml     # uv workspace root
```

**D-02:** Python inter-package dependencies managed via **uv workspaces** — single `pyproject.toml` at repo root declares all three packages as workspace members; uv resolves a shared lockfile. No manual `pip install -e .` steps.

**D-03:** The seven physics state contracts use **plain Python `@dataclass`** — zero construction overhead in the 4 Hz simulation hot path. Matches the "typed dataclass contracts" language in REQUIREMENTS (PHYS-08, PHYS-09). The seven contracts: `KinematicState`, `WheelLoads`, `ContactPatch`, `SlipState`, `ThermalState`, `DegradationState`, `SimulationState`.

**D-04:** FastAPI **response schemas are separate Pydantic v2 `BaseModel` classes** defined in `packages/api/`. They accept dataclass inputs via `model_config = ConfigDict(from_attributes=True)`. Physics types never import Pydantic. Clear boundary: physics stays fast, serialization happens at the API layer only.

**D-05:** The `PhysicsModule` protocol is a **`typing.Protocol`** (structural subtyping). Any class with the correct method signatures satisfies it at type-check time without inheritance. Mypy/pyright enforces compliance statically. No ABC boilerplate. Placeholder modules for Phase 1 testing require zero special base class.

**D-06:** Canonical development fixture throughout all 7 phases: **2023 Bahrain Grand Prix, Verstappen, Stint 2 (MEDIUM compound, laps 16–38, ~23 laps)**. Integration test baseline, Phase 2 benchmark target, Phase 3 calibration validation case.

### Claude's Discretion

- Cache directory path (for local dev: `.data/` gitignored; Fly.io: `/data` persistent volume — planner decides the config abstraction)
- Savitzky-Golay filter window (7–11, order 2–3 per spec — pick based on FastF1 4 Hz sample rate)
- Lint/format tooling (Ruff is the obvious choice given uv workspace; planner decides)
- CI trigger configuration (GitHub Actions, test-on-PR — standard)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-01 | Fetch FastF1 telemetry (V, X, Y, RPM, gear, throttle, brake, T_track, T_air at ~4 Hz) from 2022–present via Jolpica-F1 API | "FastF1 Ingestion" section — `Session.load()` + `get_car_data()` + `add_distance()` pattern; Jolpica rate-limit handling |
| DATA-02 | Two-layer disk cache (FastF1 native + app-level pickle keyed by race/driver/stint/preprocessing_version); fetch-once, run-many | "Two-Layer Cache" section — `fastf1.Cache.enable_cache()` + app-level gzip-pickle artifacts with `preprocessing_version` in key |
| DATA-03 | Per-circuit reference curvature map κ(s) from the fastest 20 % of laps, cached per circuit per season | "Curvature Map" section — `scipy.interpolate.CubicSpline` parameterized by arc length, `session.laps.pick_quicklaps(0.2)` for fast-lap subset |
| DATA-04 | Per-team gear-ratio inference (8 ratios + final drive) from steady-speed segments (throttle=100 %, gear constant) | "Gear-Ratio Inference" section — segment `gear` channel, mean `V / (RPM · R_0 · 2π/60)` per gear |
| DATA-05 | Data-quality score: throttle=104 sentinel, NaN lap times, mislabeled compounds, missing positions; warn-but-simulate or exclude-from-calibration | "Data Integrity" section — `data_integrity.py` produces a `QualityReport` with a numeric score + boolean `exclude_from_calibration` flag |
| DATA-06 | Lap annotation: compound→C1–C5, tire age, fuel estimate, weather, in/out-lap, SC/VSC flag; excluded laps omitted from degrading-lap view | "Lap Annotation" section — single `annotate_stint()` function producing `AnnotatedLap` dataclass; uses `session.track_status` + `session.race_control_messages` |
| PHYS-08 (contract) | Each module implements a typed `PhysicsModule` protocol (invariant tests land in Phase 2) | "Physics Contracts" section — `typing.Protocol` structural-subtyping definition; placeholder module + conformance test |
| PHYS-09 (state-object) | Simulation state (temperatures, cumulative energy, μ₀) carried in an explicit `SimulationState` object (strict-sequence execution enforced in Phase 2) | "Physics Contracts" section — `SimulationState` dataclass holds the per-tire carryover fields |
| API-01 | GET /races → (year, round, name) for 2022–present, served from cache | "FastAPI Endpoints" section — `fastf1.get_event_schedule(year)` wrapped in router, 1-year HTTP cache-control |
| API-02 | GET /races/{race_id}/drivers → drivers who completed that race with stint summary | "FastAPI Endpoints" section — `session.drivers` + per-driver stint list from `session.laps` |
| API-03 | GET /stints/{race_id}/{driver_id} → stint list with compound, lap count, pit info, tire age, data quality score | "FastAPI Endpoints" section — groupby on `laps['Stint']` + data-quality report join |

---

## Standard Stack

### Core (Python runtime and packaging)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12.x | Runtime `[VERIFIED: local machine is 3.12.0; JAX wheels still missing for 3.13]` | Upstream CLAUDE.md locks this. Scientific Python ecosystem (NumPy 2.x, SciPy 1.17, PyMC 5.x, NumPyro) all ship prebuilt wheels for 3.12. `[CITED: CLAUDE.md]` |
| uv | 0.10+ | Package manager + workspace orchestrator `[VERIFIED: local machine is 0.10.8]` | Single lockfile across three workspace members, editable installs are automatic, 10–100× faster than pip. Standard 2026 Python monorepo tool. `[CITED: docs.astral.sh/uv/concepts/projects/workspaces]` |
| Ruff | 0.7+ | Lint + format (single binary) `[ASSUMED]` | Discretion-level decision. Drop-in replacement for ESLint+Prettier; speeds up CI; integrates with uv. |
| pytest | 8.x | Test framework `[ASSUMED]` | Standard Python testing; required for PHYS-08 invariant tests in Phase 2 |
| mypy or pyright | latest | Static type checker for `PhysicsModule` protocol conformance `[ASSUMED]` | Enforces D-05 (Protocol) at CI time. See pitfall P1 below on slots + Protocol |

### Data / Science (Phase 1 subset of backend stack)

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| fastf1 | 3.8.2 | Telemetry + schedule + session data access `[CITED: docs.fastf1.dev/api_reference/index.html]` | Already on Jolpica-F1 backend. Handles Ergast→Jolpica migration transparently. |
| numpy | 2.1+ | Array math for curvature, gear inference, Savitzky-Golay `[CITED: CLAUDE.md]` | No version surprises — wheels stable on 3.12 |
| scipy | 1.17.x | `signal.savgol_filter` (speed differentiation), `interpolate.CubicSpline` (curvature) `[CITED: docs.scipy.org/doc/scipy/reference/generated/scipy.signal.savgol_filter.html]` | `scipy.integrate.solve_ivp` is NOT needed in Phase 1 — deferred to Phase 2 |
| pandas | 2.2+ | FastF1 returns DataFrames; stint/lap manipulation `[CITED: CLAUDE.md]` | Do not reshape to DataFrames inside hot loops in Phase 2 — but in Phase 1 ingestion, idiomatic pandas is fine |

### Persistence (Phase 1 subset)

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| stdlib `sqlite3` + `SQLAlchemy 2.0` | latest | **Only needed if a parameter-table stub is introduced in Phase 1** | Physics-module parameter storage is Phase 3, not Phase 1. Phase 1 can defer the `parameter_sets` table entirely and ship a dummy in-memory dict. |
| Alembic | 1.13+ | Schema migrations `[CITED: CLAUDE.md]` | Deferred — Alembic lands when the first real SQL schema lands (Phase 3). Phase 1 does not need it. |

**Recommendation on ORM layer:** Defer SQLModel-vs-SQLAlchemy decision to Phase 3. Phase 1 ships the cache as plain files (FastF1 cache + gzip-pickles) and doesn't need any ORM. Explicitly mark this as out of Phase 1 scope so the planner doesn't create a SQLModel task.

### FastAPI stack (Phase 1 subset)

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| fastapi | 0.136.x | HTTP API, typed routes, auto OpenAPI `[CITED: CLAUDE.md]` | |
| uvicorn | 0.32+ | ASGI server (dev) `[CITED: CLAUDE.md]` | |
| pydantic | 2.x | Response schemas only (per D-04) `[CITED: docs.pydantic.dev/latest/api/config/]` | `ConfigDict(from_attributes=True)` replaces v1's `orm_mode`. Use `Model.model_validate(dataclass_instance)` to convert. |
| httpx | latest | Only if an outbound HTTP client is needed (unlikely in Phase 1) `[ASSUMED]` | FastF1 owns its own client; not needed for Phase 1 |

### Alternatives Considered and Rejected

| Instead of | Could Use | Rejected Because |
|------------|-----------|------------------|
| `@dataclass` for physics states | Pydantic v2 `BaseModel` | D-03 locked: construction cost matters in 4 Hz hot path. ~10× slower instantiation kills Phase 2 budget. |
| `typing.Protocol` | `abc.ABC` / base class | D-05 locked: Protocol is structural, no inheritance boilerplate, placeholder modules need zero base class. |
| Poetry / Rye / pip-tools | uv workspaces | D-02 locked: uv is the 2026 de-facto for Python monorepos with shared lockfile + editable workspace installs. |
| Single package in `src/` | Three packages under `packages/` | D-01 locked: separation lets api/ depend on core/ without pulling PyMC, lets calibration/ run offline without FastAPI. |
| FastAPI `BackgroundTasks` for simulate | sync def + threadpool | CLAUDE.md locked: `BackgroundTasks` is fire-and-forget (no return value). Phase 4 will use sync def + `asyncio.to_thread`. Phase 1 endpoints are read-only and sub-ms, no concurrency question arises. |
| SQLModel for everything | SQLAlchemy 2.0 + separate Pydantic | D-04 is the reason: physics cannot depend on Pydantic. SQLModel couples ORM + Pydantic. For the parameter table (Phase 3) SQLModel is still fine, but it must live in `packages/api/` or `packages/calibration/`, never `packages/core/`. |

### Installation Skeleton

Root `pyproject.toml`:
```toml
[project]
name = "f1-dashboard-root"
version = "0.0.0"
requires-python = ">=3.12,<3.13"

[tool.uv.workspace]
members = ["packages/core", "packages/api", "packages/calibration"]

[tool.uv.sources]
f1-core = { workspace = true }
f1-api = { workspace = true }
f1-calibration = { workspace = true }
```

`packages/core/pyproject.toml`:
```toml
[project]
name = "f1-core"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
    "fastf1==3.8.2",
    "numpy>=2.1,<3",
    "scipy>=1.17,<2",
    "pandas>=2.2,<3",
]

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.7", "mypy>=1.13"]
```

`packages/api/pyproject.toml`:
```toml
[project]
name = "f1-api"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
    "f1-core",
    "fastapi>=0.136",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.6",
]

[tool.uv.sources]
f1-core = { workspace = true }
```

**Version verification (done 2026-04-23):**
- `fastf1 3.8.2` — latest on PyPI, supports Jolpica-F1 `[CITED: docs.fastf1.dev]`
- `uv 0.10.8` — verified locally
- `Python 3.12.0` — verified locally (CLAUDE.md locks 3.12)
- `[ASSUMED]` Ruff, pytest, mypy specific minor versions — use latest stable in planner-generated pyproject

---

## Architecture Patterns

### Recommended Project Structure

```
F1 Dashboard/
├── pyproject.toml              # uv workspace root
├── uv.lock                     # shared lockfile (committed)
├── .python-version             # "3.12"
├── ruff.toml                   # root lint config
├── packages/
│   ├── core/
│   │   ├── pyproject.toml
│   │   └── src/f1_core/
│   │       ├── __init__.py
│   │       ├── contracts.py           # 7 dataclasses + PhysicsModule Protocol (D-03, D-05)
│   │       ├── ingestion/
│   │       │   ├── __init__.py
│   │       │   ├── fastf1_client.py   # fastf1.Cache setup + session loader
│   │       │   ├── cache.py           # Layer-2 gzip-pickle cache
│   │       │   └── config.py          # CACHE_DIR resolution (env var, fly volume, local)
│   │       ├── data_integrity.py      # DATA-05: QualityReport, sentinel detection
│   │       ├── stint_annotation.py    # DATA-06: AnnotatedLap, compound→C1-C5, SC/VSC flags
│   │       ├── curvature.py           # DATA-03: per-circuit κ(s) map
│   │       ├── gear_inference.py      # DATA-04: per-team gear ratios
│   │       └── filters.py             # Savitzky-Golay wrapper with fixed window=9, order=3
│   │   └── tests/
│   │       ├── test_contracts.py      # PhysicsModule conformance test (PHYS-08 contract portion)
│   │       ├── test_cache.py          # DATA-02 fetch-once round-trip
│   │       ├── test_data_integrity.py # DATA-05 with corrupted fixtures
│   │       ├── test_curvature.py      # DATA-03 cross-season stability
│   │       ├── test_gear_inference.py # DATA-04
│   │       └── fixtures/
│   │           ├── bahrain_2023_ver_stint2.pkl.gz   # canonical fixture (D-06)
│   │           └── corrupted_stint.pkl.gz           # for DATA-05 testing
│   ├── api/
│   │   ├── pyproject.toml
│   │   └── src/f1_api/
│   │       ├── __init__.py
│   │       ├── app.py                 # FastAPI() instance, CORS, routers
│   │       ├── routers/
│   │       │   ├── races.py           # API-01
│   │       │   ├── drivers.py         # API-02
│   │       │   └── stints.py          # API-03
│   │       ├── schemas/
│   │       │   ├── races.py           # Pydantic v2 response models
│   │       │   ├── drivers.py
│   │       │   └── stints.py
│   │       └── dependencies.py        # Depends(get_cache_dir), etc.
│   │   └── tests/
│   │       └── test_endpoints.py      # API-01/02/03 against cached fixtures
│   └── calibration/
│       ├── pyproject.toml             # empty shell in Phase 1 (Phase 3 fills it)
│       └── src/f1_calibration/
│           └── __init__.py
├── scripts/
│   ├── fetch.py                       # CLI: fetch <race_id> <driver_id>
│   └── prewarm.py                     # deferred to Phase 7
├── notebooks/                         # empty in Phase 1
├── frontend/                          # untouched in Phase 1
├── .data/                             # gitignored — local FastF1 cache + layer-2 pickles
└── .planning/
```

### Pattern 1: uv Workspace Editable Installs

**What:** Packages under `packages/` with their own `pyproject.toml` files are automatically installed editable within the shared virtual environment.
**When to use:** Any cross-package import in Phase 1 and beyond.
**Example:**
```python
# packages/api/src/f1_api/routers/races.py
from f1_core.ingestion.fastf1_client import load_schedule  # works — editable workspace install
```
Run `uv sync` once at repo root; all packages are importable. No `pip install -e .`. `[CITED: docs.astral.sh/uv/concepts/projects/workspaces]`

### Pattern 2: Seven Physics Contracts + Protocol

**What:** Plain `@dataclass(slots=True)` state objects, plus a `typing.Protocol` defining the module shape.
**When to use:** Define once in Phase 1; every Phase 2 module implements the Protocol.
**Example:**
```python
# packages/core/src/f1_core/contracts.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
import numpy as np

@dataclass(slots=True)
class KinematicState:
    """Module A output. Shape: (N_samples,) for scalar fields, (N_samples, 4) for per-tire."""
    t: np.ndarray              # timestamps [s]
    v: np.ndarray              # speed [m/s]
    a_lat: np.ndarray          # lateral acceleration [m/s^2]
    a_long: np.ndarray         # longitudinal acceleration [m/s^2]
    psi: np.ndarray            # heading [rad]
    v_sx_rear: np.ndarray      # rear longitudinal slip velocity [m/s]
    kappa: np.ndarray          # curvature [1/m]

@dataclass(slots=True)
class WheelLoads:
    """Module B output. Shape: (N_samples, 4) FL/FR/RL/RR."""
    t: np.ndarray
    f_z: np.ndarray            # per-tire vertical load [N], >= 50 N clipped

@dataclass(slots=True)
class ContactPatch:
    t: np.ndarray
    a_cp: np.ndarray           # contact-patch half-length [m], shape (N, 4)
    p_bar: np.ndarray          # mean contact pressure [Pa], shape (N, 4)

@dataclass(slots=True)
class SlipState:
    t: np.ndarray
    theta: np.ndarray          # normalized slip parameter, shape (N, 4)
    alpha: np.ndarray          # slip angle [rad], shape (N, 4)
    v_sy: np.ndarray           # lateral slip velocity [m/s], shape (N, 4)
    p_slide: np.ndarray        # sliding power [W], shape (N, 4)
    p_total: np.ndarray        # total dissipated power [W], shape (N, 4)

@dataclass(slots=True)
class ThermalState:
    t: np.ndarray
    t_tread: np.ndarray        # [°C], shape (N, 4)
    t_carc: np.ndarray         # [°C], shape (N, 4)
    t_gas: np.ndarray          # [°C], shape (N, 4)

@dataclass(slots=True)
class DegradationState:
    t: np.ndarray
    e_tire: np.ndarray         # cumulative energy [J], shape (N, 4)
    mu_0: np.ndarray           # reference friction (scalar per timestep)
    d_tread: np.ndarray        # tread thickness [m], shape (N, 4)

@dataclass(slots=True)
class SimulationState:
    """PHYS-09 state carrier. Holds all per-tire fields that persist across timesteps."""
    t_tread: np.ndarray        # shape (4,) — last known tread temperature
    t_carc: np.ndarray         # shape (4,)
    t_gas: np.ndarray          # shape (4,)
    e_tire: np.ndarray         # shape (4,) — cumulative energy
    mu_0: float                # scalar — current reference friction
    d_tread: np.ndarray        # shape (4,) — tread thickness

@runtime_checkable
class PhysicsModule(Protocol):
    """Every module A–G implements this Protocol. Structural typing —
    inheritance is not required; mypy/pyright verify the signature at static-check time."""
    def step(self, state_in: SimulationState, telemetry_sample, params) -> SimulationState:
        ...
```

**IMPORTANT pitfall (P1 below):** `@dataclass(slots=True)` + `Protocol` interact badly with mypy. See pitfall P1 for the workaround.

### Pattern 3: Two-Layer Cache with Versioned Keys

**What:** FastF1 native cache (Layer 1) + app-level gzip-pickle of the processed stint artifact (Layer 2), keyed by `(fastf1_version, race_id, driver_id, stint_index, preprocessing_version)`.
**When to use:** Every call that would otherwise hit FastF1.
**Example:**
```python
# packages/core/src/f1_core/ingestion/fastf1_client.py
import fastf1
from pathlib import Path
import os

def init_cache() -> Path:
    """Call ONCE at app startup. D-02 layer 1."""
    cache_dir = Path(os.environ.get("F1_CACHE_DIR", ".data/fastf1_cache"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_dir))
    return cache_dir
```

```python
# packages/core/src/f1_core/ingestion/cache.py
import gzip
import pickle
from pathlib import Path
from dataclasses import dataclass
import fastf1

PREPROCESSING_VERSION = "v1"  # bump when ingestion logic changes

@dataclass(slots=True)
class StintKey:
    year: int
    round: int            # 1-indexed round number within the season
    driver_code: str      # 'VER', 'HAM', etc. (3-letter)
    stint_index: int      # 1-indexed

    def path(self, root: Path) -> Path:
        fastf1_ver = fastf1.__version__
        name = f"{self.year}_{self.round:02d}_{self.driver_code}_stint{self.stint_index}"
        name += f"__ff1-{fastf1_ver}__prep-{PREPROCESSING_VERSION}.pkl.gz"
        return root / "stints" / name

def load_or_fetch(key: StintKey, root: Path, fetcher):
    """Layer-2 cache. If path exists, unpickle; else call fetcher and write."""
    p = key.path(root)
    if p.exists():
        with gzip.open(p, "rb") as f:
            return pickle.load(f)
    artifact = fetcher(key)
    p.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, "wb") as f:
        pickle.dump(artifact, f, protocol=pickle.HIGHEST_PROTOCOL)
    return artifact
```

### Pattern 4: Data Integrity Report Dataclass

**What:** A single `QualityReport` dataclass returned by `data_integrity.analyze(stint)`, consumed by downstream code and serialized out of API-03.
**When to use:** Every stint, every time, at ingestion boundary.
**Example:**
```python
# packages/core/src/f1_core/data_integrity.py
from dataclasses import dataclass, field
from enum import Enum

class QualityVerdict(str, Enum):
    OK = "ok"
    WARN = "warn"              # simulate but flag in UI (DATA-05)
    EXCLUDE = "exclude"        # exclude from calibration only; simulate may still run
    REFUSE = "refuse"          # too broken to simulate

@dataclass(slots=True)
class QualityReport:
    score: float                            # 0–1; 1 = perfect
    verdict: QualityVerdict
    issues: list[str] = field(default_factory=list)
    throttle_sentinel_count: int = 0
    nan_lap_time_count: int = 0
    compound_mislabel: bool = False
    missing_position_pct: float = 0.0
```

### Pattern 5: FastAPI Read-Only Endpoints with Pydantic v2 from Dataclass

**What:** Pydantic v2 response models accept the core dataclass instances via `model_config = ConfigDict(from_attributes=True)`.
**When to use:** Every API endpoint where a physics/ingestion dataclass crosses the HTTP boundary.
**Example:**
```python
# packages/api/src/f1_api/schemas/stints.py
from pydantic import BaseModel, ConfigDict

class StintSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    stint_index: int
    compound: str
    compound_letter: str           # C1–C5
    lap_count: int
    pit_in_lap: int | None
    pit_out_lap: int | None
    tire_age_at_start: int
    quality_score: float
    quality_verdict: str
```

```python
# packages/api/src/f1_api/routers/stints.py
from fastapi import APIRouter, Response
from f1_core.ingestion.fastf1_client import load_stints_for_driver
from f1_api.schemas.stints import StintSummaryResponse

router = APIRouter()

@router.get("/stints/{race_id}/{driver_id}", response_model=list[StintSummaryResponse])
def get_stints(race_id: str, driver_id: str, response: Response):
    stints = load_stints_for_driver(race_id, driver_id)  # returns list of dataclasses
    # Completed races are immutable — aggressive caching is safe
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return [StintSummaryResponse.model_validate(s) for s in stints]
```

`[CITED: docs.pydantic.dev/latest/api/config/]` — `from_attributes=True` replaces v1's `orm_mode`.

### Anti-Patterns to Avoid

- **Do not `import pydantic` from `packages/core/`.** D-04 is violated. Physics types must stay Pydantic-free for Phase 2's 4 Hz hot path.
- **Do not inherit from `PhysicsModule`.** Protocol is structural; `class KinematicFrontEnd(PhysicsModule):` defeats the point and fights mypy.
- **Do not instantiate `fastf1.Session` inside a request handler.** FastF1's session load is seconds. Preload on startup, or rely on Layer-1 + Layer-2 cache hit paths.
- **Do not `async def` a route that calls FastF1's blocking IO.** Either make the route `def` (runs on threadpool) or wrap the FastF1 call in `asyncio.to_thread(...)`. In Phase 1 all endpoints are trivial — use `def`. `[CITED: fastapi.tiangolo.com/async/]`
- **Do not write the FastF1 cache into the container image at build time.** `fly.toml` volume mounts at `/data`; the image should be stateless. Phase 7 adds the prewarm script; Phase 1 just ensures the cache dir is env-configurable.
- **Do not hand-roll a physics-module registry.** `PhysicsModule` is a static type, not a runtime registry. Phase 2's orchestrator is a simple `[kin, loads, forces, contact, slip, thermal, degrad]` list, iterated in order.
- **Do not use `pickle` for anything that crosses process boundaries long-term.** Fine for local stint cache (same Python version, same class definitions). Pitfall P6 below — do not cache PyMC traces this way in Phase 3.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Savitzky-Golay smoothing / differentiation | Custom polynomial regression | `scipy.signal.savgol_filter(v, window_length=9, polyorder=3, deriv=1, delta=0.25)` | Numerically correct and O(n); `delta=0.25` is the 4 Hz sampling interval. `[CITED: docs.scipy.org/doc/scipy/reference/generated/scipy.signal.savgol_filter.html]` |
| Curvature computation | Manual finite differences on X,Y | `scipy.interpolate.CubicSpline` parameterized by arc length, then κ = X'·Y'' − Y'·X'' | CubicSpline with arc-length parameterization lets you use the identity `(X'²+Y'²)^(3/2)=1` as in model_spec §A.1 |
| FastF1 HTTP caching | Custom requests wrapper | `fastf1.Cache.enable_cache(path)` | FastF1 already layers `requests-cache` + parsed-session pickle. Free rate-limit protection. `[CITED: docs.fastf1.dev]` |
| Rate-limit back-off for Jolpica | Custom retry loop | Rely on FastF1's built-in enforcement + warn at app layer | Jolpica: 4 req/s burst, 500/hr sustained. FastF1 handles this. `[CITED: github.com/jolpica/jolpica-f1/blob/main/docs/rate_limits.md]` |
| Monorepo dependency linking | `pip install -e .` loops | uv workspaces (`[tool.uv.workspace]`) | Single lockfile, automatic editable installs. `[CITED: docs.astral.sh/uv/concepts/projects/workspaces]` |
| SC/VSC/red-flag detection | Parsing timing messages yourself | `session.track_status` (DataFrame with Time + numeric Status + Message) + `session.race_control_messages` | FastF1 ships this parsed. `[CITED: docs.fastf1.dev/api.html]` |
| Compound→C1–C5 mapping | String matching by year | Maintain a `compound_mapping.yaml` keyed by `(year, circuit_id)` | Pirelli shuffles the C1–C5 assignments per race. Pinned table is the only reliable source. |
| HTTP response models | Dict-with-untyped-keys | Pydantic v2 `BaseModel` with `ConfigDict(from_attributes=True)` | Auto-OpenAPI, validation, TypeScript client gen for frontend in Phase 5 |
| Static type checking for the Protocol | Runtime isinstance checks with ABC | `typing.Protocol` + mypy/pyright in CI | D-05: structural subtyping, zero boilerplate |

**Key insight:** Phase 1 is 80 % wiring together well-established libraries and 20 % domain-specific logic (compound mapping, quality-score formula, gear-ratio inference). Hand-rolling any of the "Don't Build" column is a reliable way to miss the <2 s Phase 4 budget.

---

## Runtime State Inventory

Phase 1 is greenfield — no prior application state exists. Only cold-start runtime state considerations:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — fresh project, no pre-existing databases | None |
| Live service config | None — no deployed services yet | None |
| OS-registered state | None — no scheduled tasks, systemd units, pm2 process registrations | None |
| Secrets/env vars | `F1_CACHE_DIR` (new, optional, defaults to `.data/fastf1_cache`); no FastF1 auth required for Jolpica | Document in README; no .env needed for Phase 1 |
| Build artifacts | Will be created: `uv.lock`, `.venv/`, `packages/*/src/*.egg-info/` (from editable installs) | Add to `.gitignore`: `.venv/`, `*.egg-info/`, `.data/`, `__pycache__/`. Commit `uv.lock`. |

**Nothing found in category:** Confirmed explicitly — there is no legacy state to migrate. CONTEXT.md reusable-assets says "None — fresh start."

---

## Common Pitfalls

### P1: `@dataclass(slots=True)` + `typing.Protocol` — mypy rejects, pyright accepts

**What goes wrong:** Using `@dataclass(slots=True)` for state objects is the right choice for hot-path performance. But if you simultaneously want a state object to *satisfy* a `Protocol` (e.g., passing a subclass that happens to have all fields), mypy refuses to see the slot attributes as satisfying protocol attributes. Pyright is fine. Type-checking in CI can spuriously fail. `[CITED: github.com/python/typing/issues/1367]`

**Why it happens:** `__slots__` declares attributes but doesn't put them in `__annotations__` in a way mypy consistently respects.

**How to avoid:**
1. **For the physics state objects (`KinematicState`, `WheelLoads`, …):** use `@dataclass(slots=True, frozen=False)`. They are data containers, not Protocol implementations. No conflict.
2. **For `PhysicsModule` implementations (Phase 2):** they are plain classes, not dataclasses. No slots, no conflict.
3. **Choose the type checker before Phase 2 lands.** Recommend pyright (used by VS Code out of the box). Document this choice. `[CITED: runebook.dev/en/docs/python/library/typing/typing.Protocol]`

**Warning signs:** CI type check fails on `some_fn(x: PhysicsModule) -> ...` with error about "missing attribute" on a slotted class. Solution: don't slot the thing that's supposed to be a `PhysicsModule`.

### P2: FastF1 throttle=104 and similar sentinels

**What goes wrong:** FastF1 emits `throttle=104` as a telemetry error/unavailable flag (values should be 0–100). Feeding a sentinel into the physics model produces garbage forces. The 2022 Japanese GP is a known offender. `[CITED: github.com/theOehrly/Fast-F1/issues/772]`

**Why it happens:** Upstream timing data quality issues; FastF1 passes the raw byte through without clipping.

**How to avoid:**
- `data_integrity.py` scans for `throttle > 100` and counts sentinels.
- If `throttle_sentinel_count / n_samples > 0.001` → `verdict = WARN`; `> 0.05` → `verdict = EXCLUDE`.
- Clip `throttle` to `[0, 100]` before passing to Phase 2 modules.
- Log the count as a structured field in the stint artifact.

**Warning signs:** Quality score drops on a stint where no human intervention would suggest a problem. Check raw car_data `Throttle` column for values > 100.

### P3: Compound mislabeling (e.g., wet tires labeled MEDIUM)

**What goes wrong:** FastF1's compound labeling can be wrong for specific races. `[CITED: github.com/theOehrly/Fast-F1/issues/779]` example: 2025 Belgian GP intermediates labeled MEDIUM in the public feed. Applying dry-compound priors to a wet stint makes predictions meaningless.

**Why it happens:** Upstream timing feed error; FastF1 reflects what the feed reports.

**How to avoid:**
- Maintain a hand-curated `known_issues.yaml` in `packages/core/src/f1_core/data/known_issues.yaml`.
- `data_integrity.py` checks this file for `(year, round)` matches and overrides compound or flags with verdict=EXCLUDE.
- Also cross-check compound continuity within a stint — any within-stint compound change is a red flag.

**Warning signs:** A MEDIUM stint at a wet race; unusually high lap times for a compound that should be faster.

### P4: Savitzky-Golay filter window choice — even vs odd, edge effects

**What goes wrong:** `savgol_filter` requires `window_length` to be an odd positive integer and `polyorder < window_length`. Passing 8 raises ValueError at runtime. At stint boundaries, edge effects distort `a_long` at laps 1 and N.

**Why it happens:** Savitzky-Golay fits a polynomial inside a moving window; the first and last `window_length // 2` samples use asymmetric fits.

**How to avoid:**
- Pick `window_length=9` (odd, in the 7–11 range per CLAUDE.md), `polyorder=3`.
- Use `mode='interp'` for the default edge handling.
- Pass `delta=0.25` (4 Hz sampling interval) so `deriv=1` gives actual `dV/dt` in m/s².
- At the physics-module boundary, discard the first and last 2 samples of each stint from calibration (but keep them for display — they belong to in/out laps, which are excluded from degradation analysis anyway per DATA-06). `[CITED: docs.scipy.org/doc/scipy/reference/generated/scipy.signal.savgol_filter.html]`

**Warning signs:** `a_long` showing spikes of ±20 m/s² at lap 1 or the last lap; Pandas DataFrame length mismatch after filter application.

### P5: Jolpica rate-limit silent throttling

**What goes wrong:** Jolpica imposes 4 req/s burst and 500 req/hour sustained. FastF1 tries to enforce this but raises rate-limit warnings at INFO log level, not ERROR. Easy to miss during development, fatal in CI that loops over races. `[CITED: github.com/jolpica/jolpica-f1/blob/main/docs/rate_limits.md]`

**Why it happens:** Jolpica uses HTTP 429 + Retry-After headers; FastF1 retries silently.

**How to avoid:**
- Set FastF1 logging to WARNING level at app startup:
  ```python
  import logging
  logging.getLogger("fastf1").setLevel(logging.WARNING)
  ```
- For CI: hand-seed the fixture cache (Bahrain 2023 VER stint 2) into `packages/core/tests/fixtures/` so no Jolpica calls are made during tests.
- For the prewarm script (Phase 7, not Phase 1): rate-limit to 1 request per 2 seconds (well under 500/hr) and run overnight.

**Warning signs:** `requests-cache` misses on every call in a loop; FastF1 logs show "rate limit" at INFO level.

### P6: Pickling FastF1 session objects — version fragility

**What goes wrong:** `fastf1.Session` objects contain references to pandas DataFrames of parsed telemetry. Pickling them works in Python 3.12 with fastf1 3.8.2, but breaks across FastF1 or pandas major versions.

**Why it happens:** pickle encodes class paths; an upgrade that renames or moves a class invalidates old pickles.

**How to avoid:**
- **Do not pickle the `Session` object.** Pickle the extracted dict of numpy arrays / pandas DataFrames only.
- Include `fastf1.__version__` + `PREPROCESSING_VERSION` in the cache key (see Pattern 3).
- On a version bump, the cache key changes and stale pickles are automatically skipped — they remain on disk but nothing reads them. Add a cleanup script as part of Phase 7.

**Warning signs:** `AttributeError: Can't get attribute 'X' on module 'fastf1.core'` when unpickling after an upgrade.

### P7: uv workspace member ordering — editable installs silently broken

**What goes wrong:** uv requires `[tool.uv.sources]` entries to resolve workspace members. If `f1-api` lists `f1-core` as a dependency but doesn't have `f1-core = { workspace = true }` under `[tool.uv.sources]`, uv tries to resolve `f1-core` from PyPI and fails (or, worse, installs an unrelated package). `[CITED: docs.astral.sh/uv/concepts/projects/workspaces]`

**Why it happens:** `[project.dependencies]` is a standard PEP 621 table, agnostic of workspace concepts. `[tool.uv.sources]` tells uv "resolve this name as a workspace member."

**How to avoid:**
- Every workspace package that depends on another workspace package MUST list it under `[tool.uv.sources]` with `{ workspace = true }`.
- Add a CI check: `uv sync --locked` and verify `uv run python -c "import f1_core"` in the api package's venv.

**Warning signs:** `ModuleNotFoundError: No module named 'f1_core'` after `uv sync`, or uv installs an unexpected `f1-core` version from PyPI.

### P8: Curvature map computed from a single lap — noise dominates

**What goes wrong:** FastF1 XY position is 4 Hz (via interpolation from the ~20–30 Hz raw feed). A single lap has ~800 samples for a 90 s lap. Differentiating once for tangent and again for curvature amplifies noise. Curvature from one lap produces a spiky κ(s) with 10× the true values at random points.

**Why it happens:** Second derivative of noisy data is always dangerous; F1 laps differ enough (line variation) that averaging across laps is what academic telemetry does.

**How to avoid:**
- Aggregate the fastest 20% of laps in a session (`session.laps.pick_quicklaps(0.2)`).
- Align each lap by cumulative arc length `s`.
- Fit `CubicSpline(s, X)` and `CubicSpline(s, Y)` jointly for each lap, evaluate κ on a shared `s` grid, then take the median across laps per `s`.
- Smooth with a Gaussian kernel (σ ~ 5 m) along `s` before storing.
- Cache per `(circuit_id, season)` — aero regs reset every year; track surface is occasionally repaved.

**Warning signs:** Cross-season stability test (Success Criterion 3) fails — two seasons at Bahrain produce κ(s) that differ by >10 % point-wise at sample locations.

### P9: FastAPI async def for blocking FastF1 calls

**What goes wrong:** FastAPI routes declared `async def` run inside the event loop; any blocking call (FastF1 session load, pandas groupby on 1 M rows) stalls the entire server. With multiple concurrent users, throughput collapses.

**Why it happens:** FastAPI + Uvicorn uses a single-threaded asyncio loop by default. `async def` + blocking IO is a common antipattern. `[CITED: fastapi.tiangolo.com/async/]`

**How to avoid:**
- Declare Phase 1's three endpoints as plain `def` (FastAPI runs them in the threadpool).
- OR: declare them `async def` and wrap every blocking call in `await asyncio.to_thread(...)`.
- Phase 1 endpoints serve mostly from Layer-1/Layer-2 cache → microseconds. Plain `def` is simplest.

**Warning signs:** P99 latency on `/stints/...` spikes to seconds under even 2 concurrent requests in development. Cache hits should be sub-millisecond.

---

## Code Examples

### Canonical fixture loader (one-off script, commit the output)

```python
# scripts/build_canonical_fixture.py
"""Run once to produce packages/core/tests/fixtures/bahrain_2023_ver_stint2.pkl.gz.

Canonical fixture per D-06 from CONTEXT.md.
"""
from pathlib import Path
import gzip, pickle
from f1_core.ingestion.fastf1_client import init_cache, load_stint

init_cache()
stint = load_stint(year=2023, event="Bahrain", session="R",
                   driver_code="VER", stint_index=2)
out = Path(__file__).parent.parent / "packages/core/tests/fixtures/bahrain_2023_ver_stint2.pkl.gz"
out.parent.mkdir(parents=True, exist_ok=True)
with gzip.open(out, "wb") as f:
    pickle.dump(stint, f)
print(f"Wrote fixture: {out} ({out.stat().st_size / 1024:.1f} KB)")
```

### Curvature map computation (source: model_spec.md §A.1)

```python
# packages/core/src/f1_core/curvature.py
import numpy as np
from scipy.interpolate import CubicSpline
from fastf1.core import Session, Laps

def compute_curvature_map(session: Session, grid_meters: np.ndarray) -> np.ndarray:
    """Return median curvature κ(s) at each point on `grid_meters`.

    Source: model_spec.md §A.1 — fit cubic splines to (X(s), Y(s)) from fast laps,
    compute κ = X' Y'' − Y' X''. Since s is arc length, denominator is unity.
    """
    fast_laps: Laps = session.laps.pick_quicklaps(0.2)  # fastest 20%
    per_lap_kappas = []
    for _, lap in fast_laps.iterlaps():
        tel = lap.get_pos_data().add_distance()
        s_lap = tel["Distance"].values
        X = tel["X"].values
        Y = tel["Y"].values
        # enforce monotonic s (edge case: backwards movement in pit lane)
        mask = np.diff(s_lap, prepend=s_lap[0] - 1) > 0
        s_lap, X, Y = s_lap[mask], X[mask], Y[mask]
        cs_x = CubicSpline(s_lap, X)
        cs_y = CubicSpline(s_lap, Y)
        dx = cs_x(grid_meters, 1)
        ddx = cs_x(grid_meters, 2)
        dy = cs_y(grid_meters, 1)
        ddy = cs_y(grid_meters, 2)
        kappa = dx * ddy - dy * ddx  # already arc-length param; denom = 1
        per_lap_kappas.append(kappa)
    return np.median(np.stack(per_lap_kappas), axis=0)
```

### Gear-ratio inference (source: model_spec.md §A.4)

```python
# packages/core/src/f1_core/gear_inference.py
import numpy as np
import pandas as pd

R_0 = 0.330  # tire radius [m], model_spec.md fixed constants

def infer_gear_ratios(car_data: pd.DataFrame) -> dict[int, float]:
    """Given a DataFrame with `Speed`, `RPM`, `Throttle`, `nGear` (FastF1 standard),
    return a dict mapping gear -> G_ratio * G_final (combined ratio).

    Selects steady-state samples: Throttle >= 99 AND gear constant for >= 4 samples (≥1s at 4 Hz).
    Computes V_wheel = 2π · RPM / (60 · combined_ratio) · R_0, inverts.
    """
    df = car_data.copy()
    mask = (df["Throttle"] >= 99) & (df["Speed"] > 50)  # avoid low-speed noise
    df = df[mask]
    ratios = {}
    for gear in sorted(df["nGear"].unique()):
        if gear == 0 or gear > 8:
            continue
        gdf = df[df["nGear"] == gear]
        if len(gdf) < 20:  # need enough samples
            continue
        # V_wheel [m/s] = 2π R_0 · RPM / (60 · ratio)  =>  ratio = 2π R_0 · RPM / (60 · V)
        v_mps = gdf["Speed"].values / 3.6  # FastF1 gives km/h
        rpm = gdf["RPM"].values
        ratios[int(gear)] = float(np.median(2 * np.pi * R_0 * rpm / (60 * v_mps)))
    return ratios  # caller derives G_final from the highest-gear ratio and published gearbox
```

### Data integrity analyzer skeleton

```python
# packages/core/src/f1_core/data_integrity.py
import numpy as np
import pandas as pd
from .contracts import QualityReport, QualityVerdict   # QualityReport lives in contracts.py

SENTINEL_THROTTLE = 104

def analyze(
    car_data: pd.DataFrame,
    laps: pd.DataFrame,
    known_issues: dict,
    year: int,
    round: int,
) -> QualityReport:
    issues = []
    # Throttle sentinels
    throttle_sentinels = int((car_data["Throttle"] > 100).sum())
    if throttle_sentinels > 0:
        issues.append(f"throttle_sentinels={throttle_sentinels}")
    # NaN lap times
    nan_laps = int(laps["LapTime"].isna().sum())
    if nan_laps > 0:
        issues.append(f"nan_lap_times={nan_laps}")
    # Compound continuity within stint
    compound_mislabel = False
    for stint_idx, stint_laps in laps.groupby("Stint"):
        if stint_laps["Compound"].nunique() > 1:
            compound_mislabel = True
            issues.append(f"compound_changes_within_stint_{stint_idx}")
    # Known-issues override
    for issue in known_issues.get(f"{year}-{round}", []):
        issues.append(f"known_issue:{issue['tag']}")
    # Missing positions
    missing_pos_pct = float(car_data[["X", "Y"]].isna().any(axis=1).mean())
    # Score + verdict
    score = 1.0
    score -= min(0.5, throttle_sentinels / max(len(car_data), 1))
    score -= min(0.3, nan_laps / max(len(laps), 1))
    score -= 0.3 if compound_mislabel else 0.0
    score -= min(0.2, missing_pos_pct)
    score = max(0.0, score)
    if score >= 0.9:
        verdict = QualityVerdict.OK
    elif score >= 0.7:
        verdict = QualityVerdict.WARN
    elif score >= 0.4:
        verdict = QualityVerdict.EXCLUDE
    else:
        verdict = QualityVerdict.REFUSE
    return QualityReport(
        score=score, verdict=verdict, issues=issues,
        throttle_sentinel_count=throttle_sentinels,
        nan_lap_time_count=nan_laps,
        compound_mislabel=compound_mislabel,
        missing_position_pct=missing_pos_pct,
    )
```

### PhysicsModule conformance test (PHYS-08 contract portion)

```python
# packages/core/tests/test_contracts.py
from dataclasses import dataclass
import numpy as np
from f1_core.contracts import (
    PhysicsModule, SimulationState,
    KinematicState, WheelLoads, ContactPatch, SlipState,
    ThermalState, DegradationState,
)

@dataclass
class PlaceholderModule:
    """Minimal example showing a class satisfies PhysicsModule via structural subtyping."""
    def step(self, state_in, telemetry_sample, params):
        return state_in

def test_placeholder_satisfies_protocol():
    placeholder = PlaceholderModule()
    assert isinstance(placeholder, PhysicsModule)  # runtime_checkable check

def test_all_seven_contracts_importable_from_single_module():
    # Success Criterion 5: importable from a single module
    from f1_core import contracts
    for name in ("KinematicState", "WheelLoads", "ContactPatch",
                 "SlipState", "ThermalState", "DegradationState",
                 "SimulationState"):
        assert hasattr(contracts, name), f"missing contract: {name}"

def test_simulation_state_shape():
    state = SimulationState(
        t_tread=np.full(4, 100.0), t_carc=np.full(4, 90.0), t_gas=np.full(4, 80.0),
        e_tire=np.zeros(4), mu_0=1.5, d_tread=np.full(4, 0.008),
    )
    assert state.t_tread.shape == (4,)
    assert isinstance(state.mu_0, float)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pip install -e ./packages/core` loop | uv workspaces with shared lockfile | 2024–2025 | Single `uv sync`; editable by default; faster resolution |
| `Config: orm_mode = True` (Pydantic v1) | `model_config = ConfigDict(from_attributes=True)` (Pydantic v2) | Pydantic 2.0 release 2023 | FastAPI 0.100+ defaults to v2; 5–50× faster validation `[CITED: docs.pydantic.dev/latest/api/config/]` |
| `scipy.integrate.odeint` | `scipy.integrate.solve_ivp` | SciPy 1.0+ | `odeint` is legacy-only for new code. Not used in Phase 1 but do not import in Phase 2 either. `[CITED: CLAUDE.md]` |
| `@dataclass` with Protocol+inheritance | Plain Protocol structural subtyping | Python 3.8+ (Protocol) / 3.10+ (slots) | No ABCs, no runtime overhead, static-check only `[CITED: typing.python.org/en/latest/reference/protocols.html]` |
| Ergast API | Jolpica-F1 API | Early 2025 | Ergast shut down; FastF1 3.7+ uses Jolpica transparently. Rate limits differ (500/hr sustained). `[CITED: github.com/jolpica/jolpica-f1/blob/main/docs/rate_limits.md]` |
| `from_orm(obj)` | `Model.model_validate(obj)` with `from_attributes=True` | Pydantic 2.0 | Use the new API; the old is deprecated |

**Deprecated / outdated:**
- **`fastf1.api.*` low-level module** — still exists but public API is `fastf1.get_session()` / `session.load()`. Use the high-level API.
- **Ergast direct URLs** — dead. Anything in older tutorials referencing `ergast.com/api/f1` is defunct. Jolpica serves a compatible endpoint, wrapped by FastF1.
- **Python 3.9, 3.10, 3.11 for this project** — FastAPI 0.130+ requires 3.10; JAX/nutpie need 3.12 in Phase 3. Stay on 3.12.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `throttle > 100` should be treated as sentinel / unavailable | Data Integrity; P2 | If some teams legitimately exceed 100 (overboost / ERS), we'd flag valid data. Mitigation: threshold at 104 specifically (confirmed by FastF1 issue #772). |
| A2 | Savitzky-Golay window=9, order=3 is appropriate for 4 Hz telemetry | Filters pattern; P4 | If noise is higher than assumed, window=11 may be needed. Mitigation: make window/order config-driven and calibrate on the canonical fixture. |
| A3 | Ruff is the preferred lint/format tool | Standard Stack | If team prefers ESLint+Prettier equivalent (flake8+black), switching later is cheap. |
| A4 | The `known_issues.yaml` entries for mislabeled compounds will be maintained by hand | Data Integrity pattern | As FastF1 fixes issues upstream, the list grows stale. Mitigation: annotate each entry with a FastF1 issue number + "fixed in version X" field. |
| A5 | `SimulationState` needs only per-tire thermal state + per-tire energy + scalar μ₀ + per-tire tread thickness — no other carryover | Contracts definition | If Phase 2 Module G needs additional state (e.g., μ_0 as a per-tire array), the contract changes. Mitigation: define `SimulationState` per PHYS-09 + model_spec.md §G; Phase 2 may propose an extension. |
| A6 | Quality-score formula (weights on sentinels, NaN laps, compound mislabel) is reasonable for v1 | Data Integrity code example | The thresholds (0.9 / 0.7 / 0.4) are unvalidated. Mitigation: run on the canonical fixture (should score 1.0) and a hand-corrupted copy (should downgrade to WARN). |
| A7 | pytest is the test framework | Standard Stack | None of the upstream decisions pin it. pytest is overwhelmingly standard for scientific Python — low risk. |
| A8 | `fastf1.Cache.enable_cache()` is safe to call at FastAPI app startup (once per process) | Ingestion pattern | If FastF1 internally uses global state that conflicts with multi-worker Uvicorn, the first request per worker succeeds but later workers race. Mitigation: call in a FastAPI `lifespan` context manager. Verified by FastF1 docs: "configure at the beginning of your script." `[CITED: docs.fastf1.dev/fastf1.html]` |
| A9 | 3-letter driver codes (`VER`, `HAM`) are stable across the 2022–present window | API routes, cache keys | A driver change mid-season keeps the code, but historical records should be immutable. Confirmed stable by FastF1 `session.drivers` semantics. |
| A10 | Alembic is not needed in Phase 1 (no SQL schema yet) | Standard Stack | If the planner decides to persist `QualityReport` in SQLite for reuse across invocations, Alembic becomes necessary. Mitigation: keep `QualityReport` a serializable dataclass and write it alongside the pickle — no DB in Phase 1. |

**Confirmation needed from user before planning:** A2 (filter parameters — discretion-level but baked into Phase 2 performance), A4 (known_issues.yaml maintenance burden), A6 (quality-score threshold numbers).

---

## Open Questions (RESOLVED)

1. **QualityReport persistence — SQLite vs pickle** — RESOLVED: Carried inside the gzip-pickle stint artifact (no new persistence layer). The "calibration dataset" filter is a function over cached artifacts, not a database query. Alembic and SQL schema deferred entirely to Phase 3.

2. **`tire_age_at_start` computation for used-tire race starts** — RESOLVED: Use `TyreLife` first value per stint with `FreshTyre` boolean cross-check; flag inconsistency in `QualityReport.issues` list if they disagree.

3. **`curvature_map` / `gear_ratios` in API-03 response** — RESOLVED: Not exposed via Phase 1 HTTP API. Internal to `packages/core/` only. A `GET /circuits/{id}/reference-data` endpoint can be added in Phase 2 if needed by the simulation endpoint; no API schema change in Phase 1.

4. **`pick_quicklaps(0.2)` availability on FastF1 3.8.2** — RESOLVED: `curvature.py` takes raw `(s, x, y)` arrays passed in from the caller rather than calling `pick_quicklaps` internally, avoiding the API version ambiguity entirely. Fallback expression for callers: `laps[laps['LapTime'] < laps['LapTime'].quantile(0.2)]`.

5. **Container base image choice** — RESOLVED: No Dockerfile in Phase 1. Local development via `uv sync && uv run uvicorn f1_api.app:app --reload`. Container image decision deferred to Phase 7.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All Phase 1 work | Yes | 3.12.0 `[VERIFIED]` | — (locked at 3.12 per CLAUDE.md) |
| uv | Workspace management (D-02) | Yes | 0.10.8 `[VERIFIED]` | pip + per-package `pip install -e .` (worse DX, separate lockfiles) |
| git | version control | Yes (repo already initialized) | — | — |
| Internet / Jolpica-F1 API | First-time FastF1 fetch | Assumed yes | — | If blocked: hand-copy a fixture from another machine. Phase 1 tests must use local fixtures so CI runs offline. |
| FastF1 cache directory | Layer 1 cache | Created on-demand at `.data/fastf1_cache` | — | Environment variable `F1_CACHE_DIR` override |
| Node.js / npm | Frontend scaffolding | Out of Phase 1 scope | — | N/A |
| Docker / Fly.io CLI | Deployment | Out of Phase 1 scope | — | N/A |

**Missing dependencies with no fallback:** None — everything required for Phase 1 is available on the local machine. First-time FastF1 fetch of the canonical fixture (Bahrain 2023 VER stint 2) requires internet but executes once, then tests run offline against the committed fixture.

**Missing dependencies with fallback:** None material.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x `[ASSUMED — A7]` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (per-package) — create in Wave 0 |
| Quick run command | `uv run pytest packages/core/tests -x` |
| Full suite command | `uv run pytest` (runs all package tests, from repo root) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | Fetch stint from FastF1/Jolpica; fields match expected schema | integration | `uv run pytest packages/core/tests/test_ingestion.py::test_fetch_canonical_fixture -x` | ❌ Wave 0 |
| DATA-02 | Second invocation returns cached bytes (no network I/O) | integration | `uv run pytest packages/core/tests/test_cache.py::test_second_call_hits_cache -x` | ❌ Wave 0 |
| DATA-03 | Curvature map cross-season stability on same circuit | unit | `uv run pytest packages/core/tests/test_curvature.py::test_cross_season_stability -x` | ❌ Wave 0 |
| DATA-04 | Gear-ratio inference recovers known ratios on fixture | unit | `uv run pytest packages/core/tests/test_gear_inference.py::test_infer_bahrain_2023_ver -x` | ❌ Wave 0 |
| DATA-05 | Corrupted fixture → score < threshold → verdict EXCLUDE | unit | `uv run pytest packages/core/tests/test_data_integrity.py::test_corrupted_fixture_excluded -x` | ❌ Wave 0 |
| DATA-05 | Clean fixture → score = 1.0 → verdict OK | unit | `uv run pytest packages/core/tests/test_data_integrity.py::test_clean_fixture_ok -x` | ❌ Wave 0 |
| DATA-05 | Throttle=104 detected and counted | unit | `uv run pytest packages/core/tests/test_data_integrity.py::test_throttle_sentinel_detection -x` | ❌ Wave 0 |
| DATA-06 | Lap annotation emits correct (compound, tire age, in/out-lap, SC/VSC) | unit | `uv run pytest packages/core/tests/test_stint_annotation.py -x` | ❌ Wave 0 |
| PHYS-08 (contract) | Placeholder module satisfies `PhysicsModule` Protocol at runtime + static | unit | `uv run pytest packages/core/tests/test_contracts.py::test_placeholder_satisfies_protocol -x` | ❌ Wave 0 |
| PHYS-08 (contract) | All 7 dataclasses importable from single module | unit | `uv run pytest packages/core/tests/test_contracts.py::test_all_seven_contracts_importable_from_single_module -x` | ❌ Wave 0 |
| PHYS-09 (state obj) | `SimulationState` field shapes correct | unit | `uv run pytest packages/core/tests/test_contracts.py::test_simulation_state_shape -x` | ❌ Wave 0 |
| API-01 | GET /races returns 2022–present (year, round, name) | integration | `uv run pytest packages/api/tests/test_endpoints.py::test_get_races -x` | ❌ Wave 0 |
| API-02 | GET /races/{id}/drivers returns expected drivers for canonical fixture race | integration | `uv run pytest packages/api/tests/test_endpoints.py::test_get_drivers_for_bahrain_2023 -x` | ❌ Wave 0 |
| API-03 | GET /stints/{race_id}/{driver_id} returns stints with compound/lap count/quality | integration | `uv run pytest packages/api/tests/test_endpoints.py::test_get_stints_for_ver_bahrain_2023 -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest packages/core/tests -x` (typical subset relevant to the task)
- **Per wave merge:** `uv run pytest` (full suite, both packages)
- **Phase gate:** Full suite green + `uv run mypy packages/core/src` + `uv run mypy packages/api/src` + `uv run ruff check .`

### Wave 0 Gaps
- [ ] Install pytest + ruff + mypy (or pyright) via `[dependency-groups]` in root `pyproject.toml`
- [ ] `packages/core/tests/conftest.py` — shared fixtures, `CACHE_DIR` pointing at repo-local test cache dir
- [ ] `packages/core/tests/fixtures/bahrain_2023_ver_stint2.pkl.gz` — canonical fixture (D-06); committed to git
- [ ] `packages/core/tests/fixtures/corrupted_stint.pkl.gz` — hand-corrupted copy with throttle=104, NaN lap times, compound change (for DATA-05 tests)
- [ ] `packages/api/tests/conftest.py` — TestClient fixture, mock FastF1 cache dir
- [ ] `packages/core/tests/test_contracts.py` — covers PHYS-08 (contract portion), PHYS-09 (state obj)
- [ ] `packages/core/tests/test_ingestion.py`, `test_cache.py` — covers DATA-01, DATA-02
- [ ] `packages/core/tests/test_curvature.py`, `test_gear_inference.py` — covers DATA-03, DATA-04
- [ ] `packages/core/tests/test_data_integrity.py` — covers DATA-05
- [ ] `packages/core/tests/test_stint_annotation.py` — covers DATA-06
- [ ] `packages/api/tests/test_endpoints.py` — covers API-01, API-02, API-03
- [ ] Root `ruff.toml` with line-length=100, import-sorting enabled
- [ ] Root `pyproject.toml` `[tool.mypy]` strict-mode for `packages/core/src/f1_core/contracts.py` minimum; relaxed elsewhere in Phase 1

**Estimated Wave 0 effort:** ~4 tasks (test infra, lint/format infra, fixture generation, CI placeholder).

---

## Security Domain

> `security_enforcement` not explicitly set in config.json — treating as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 1 is a read-only public API serving public FastF1 data; no user accounts. |
| V3 Session Management | no | Stateless HTTP. URL-hash state is client-side only. |
| V4 Access Control | yes | GET endpoints are public. Ensure no path traversal when constructing cache paths from request params. |
| V5 Input Validation | yes | race_id, driver_id come from path params — validate shape/charset with Pydantic. |
| V6 Cryptography | no | No secrets handled in Phase 1. No passwords, no tokens. |

### Known Threat Patterns for Phase 1 stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via `race_id` / `driver_id` in cache file path | Tampering | Validate both against regex (`^[0-9]{4}-[a-z_]+$` for race_id; `^[A-Z]{3}$` for driver_code) using Pydantic `StringConstraints`. Reject before touching the filesystem. |
| SSRF via FastF1 → Jolpica | Info disclosure | Not an external-input concern — Jolpica URL is compiled into FastF1. No user-supplied URLs hit the network. |
| Pickle deserialization of attacker-controlled file | Tampering / RCE | Phase 1 pickles are WRITTEN by our code, READ by our code, under a path we control (`F1_CACHE_DIR`). Do not accept user-uploaded pickles. (Phase 4's POST /sessions/upload needs separate hardening — out of Phase 1 scope.) |
| CORS misconfiguration | Info disclosure | Default FastAPI CORS middleware with explicit origins list — add `localhost:5173` (Vite dev) for now; tighten in Phase 7. |
| Cache poisoning via concurrent writes | Tampering | Atomic writes: write to `tmp` then `os.replace()`. Stint pickles are per-unique-key so concurrent writes to the same key are idempotent. |
| Rate-limit exhaustion of Jolpica via scrape loops | DoS (upstream) | App-side rate limit on `/races` and `/stints` if exposed publicly (1 req/s per IP per path). Phase 1 can skip this (dev only); Phase 7 adds it. |

---

## Sources

### Primary (HIGH confidence)
- [FastF1 3.8.2 API Reference](https://docs.fastf1.dev/api_reference/index.html) — session loading, caching, Jolpica integration
- [FastF1 General Functions (Cache.enable_cache)](https://docs.fastf1.dev/fastf1.html) — cache directory configuration
- [Jolpica-F1 Rate Limits](https://github.com/jolpica/jolpica-f1/blob/main/docs/rate_limits.md) — 4 req/s burst, 500/hr sustained
- [uv Workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/) — pyproject `[tool.uv.workspace]` / `[tool.uv.sources]` semantics
- [Pydantic v2 Configuration](https://docs.pydantic.dev/latest/api/config/) — `ConfigDict`, `from_attributes`, dataclass support
- [SciPy savgol_filter](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.savgol_filter.html) — window_length, polyorder, deriv, delta
- [typing.Protocol reference](https://typing.python.org/en/latest/reference/protocols.html) — structural subtyping semantics
- [Python typing spec: Dataclasses](https://typing.python.org/en/latest/spec/dataclasses.html) — dataclass + Protocol interactions
- [FastAPI Concurrency](https://fastapi.tiangolo.com/async/) — sync def vs async def, threadpool
- [CLAUDE.md](./CLAUDE.md) — locked stack decisions (FastAPI 0.136, Python 3.12, NumPy 2.1, SciPy 1.17, fastf1 3.8.2)
- [model_spec.md](./model_spec.md) — physics contracts: which fields each module's state object needs; §A.1 curvature, §A.4 gear ratios, §G.1 energy accumulation
- [.planning/research/PITFALLS.md](./.planning/research/PITFALLS.md) — C3 (FastF1 data quality), M3 (module interface drift)
- [.planning/research/ARCHITECTURE.md](./.planning/research/ARCHITECTURE.md) — Q1 (contracts), Q2 (two-layer cache), Q4 (sync vs async)

### Secondary (MEDIUM confidence)
- [FastF1 issue #772 — throttle >100%](https://github.com/theOehrly/Fast-F1/issues/772) — sentinel value confirmation
- [FastF1 issue #779 — compound mislabeling](https://github.com/theOehrly/Fast-F1/issues/779) — 2025 Belgian GP example
- [mypy Protocols docs](https://mypy.readthedocs.io/en/stable/protocols.html) — Protocol + slots edge case
- [Python typing issue #1367 — slots + Protocol](https://github.com/python/typing/issues/1367) — pyright vs mypy divergence
- [How to set up Python monorepo with uv workspaces (pydevtools)](https://pydevtools.com/handbook/how-to/how-to-set-up-a-python-monorepo-with-uv-workspaces/) — concrete layout example
- [SQLModel vs SQLAlchemy 2.0 — multiple 2026 comparisons](https://erenertem.medium.com/why-i-choose-sqlmodel-over-sqlalchemy-when-building-fastapi-apis-6916f1c3b81f) — for Phase 3 reference, not Phase 1 decision

### Tertiary (LOW confidence — flagged for validation)
- Ruff as the lint/format tool (discretion-level)
- pytest 8.x version pin (standard but not verified against this project's needs)
- Quality-score formula weights (0.9/0.7/0.4 thresholds are my invention, not from literature)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — locked in CLAUDE.md + CONTEXT.md; all verified against official docs within the last day
- Architecture / patterns: HIGH — direct implementation of locked decisions D-01 through D-06; code examples derived from model_spec.md and official docs
- Pitfalls: HIGH for FastF1-specific items (corroborated by multiple GitHub issues and upstream docs); MEDIUM for Python-toolchain items (P1, P7) because the behavior can change across mypy/uv versions
- Data integrity: MEDIUM — the score formula (A6) is a reasonable starting point but should be validated against the canonical fixture + a known-corrupted stint before being locked in

**Research date:** 2026-04-23
**Valid until:** 2026-05-23 (FastF1 3.8.x is stable; uv changes its workspace semantics roughly every 6 months — re-verify before the next major uv upgrade)

---

*Phase: 01-foundation-data-pipeline-module-contracts*
*Research complete: 2026-04-23*
