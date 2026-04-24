"""POST /simulate and POST /simulate/stream routers — API-04 + DASH-03.

/simulate: CPU-bound (K=100 forward passes) — plain `def` so FastAPI runs it
in the threadpool (CLAUDE.md pattern). D-05: service module refuses to load if
pymc/numpyro/pytensor are already imported.

/simulate/stream: async generator wrapped in StreamingResponse. Physics call is
offloaded with asyncio.to_thread so the event loop is not blocked.
Emits 7 module_complete events then simulation_complete (full result payload
extended with track/sector_bounds/turns circuit geometry).
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import numpy as np
from scipy.signal import savgol_filter
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from f1_api.schemas.simulate import (
    SimulateRequest,
    SimulateResponse,
    SimulateStreamRequest,
)
from f1_api.services.simulate import run_simulation_with_uncertainty

log = logging.getLogger(__name__)
router = APIRouter()

# Physics module names in execution order (7 modules per Phase 4 orchestrator)
_PHYSICS_MODULES = [
    (1, "Kinematics"),
    (2, "Load Transfer"),
    (3, "Friction"),
    (4, "Thermal"),
    (5, "Degradation"),
    (6, "Slip"),
    (7, "Uncertainty"),
]


def _extract_track_geometry(race_id: str) -> dict[str, Any]:
    """Extract circuit outline from FastF1 fastest lap X/Y telemetry.

    Returns dict with:
      track: list of [x, y] normalized [0,1] float pairs
      sector_bounds: [[s1_start,s1_end],[s2_start,s2_end],[s3_start,s3_end]] indices into track
      turns: [{"n": turn_number, "at": fraction_0_to_1}, ...]

    D-01: GPS coordinates from fastest lap, Savitzky-Golay smoothed (window=21, order=3),
    normalized to [0,1] in both axes preserving aspect ratio.
    """
    try:
        import fastf1  # noqa: PLC0415

        # Parse race_id format: "YYYY-event_name" e.g. "2024-bahrain_grand_prix"
        parts = race_id.split("-", 1)
        year = int(parts[0])
        event_name = parts[1].replace("_", " ").title() if len(parts) > 1 else ""

        session = fastf1.get_session(year, event_name, "R")
        session.load(telemetry=True, laps=True, weather=False, messages=False)

        fastest = session.laps.pick_fastest()
        tel = fastest.get_telemetry()

        xs = tel["X"].dropna().values.astype(float)
        ys = tel["Y"].dropna().values.astype(float)

        # Savitzky-Golay smoothing — window=21 requires at least 21 points
        if len(xs) >= 21:
            xs = savgol_filter(xs, window_length=21, polyorder=3)
            ys = savgol_filter(ys, window_length=21, polyorder=3)

        # Normalize to [0,1] preserving aspect ratio
        x_min, x_max = float(np.min(xs)), float(np.max(xs))
        y_min, y_max = float(np.min(ys)), float(np.max(ys))
        scale = max(x_max - x_min, y_max - y_min)
        if scale == 0:
            scale = 1.0
        xs_n = ((xs - x_min) / scale).tolist()
        ys_n = ((ys - y_min) / scale).tolist()

        track = [[round(x, 4), round(y, 4)] for x, y in zip(xs_n, ys_n)]
        n = len(track)

        # Sector bounds: divide track equally into 3 sectors (approximate)
        # More accurate sector splits would require MinisectorTime data — sufficient for v1
        s1_end = n // 3
        s2_end = 2 * n // 3
        sector_bounds = [[0, s1_end], [s1_end, s2_end], [s2_end, n - 1]]

        # Turn markers: approximate from circuit name lookup table
        # For circuits not in the lookup, distribute evenly
        _TURN_FRACS: dict[str, list[float]] = {
            "bahrain": [0.08, 0.13, 0.20, 0.27, 0.33, 0.43, 0.50, 0.55,
                        0.60, 0.65, 0.73, 0.80, 0.87, 0.93],
            "jeddah": [0.05, 0.12, 0.18, 0.27, 0.35, 0.42, 0.50, 0.58,
                       0.65, 0.73, 0.80, 0.88, 0.93, 0.97, 0.99],
            "albert": [0.07, 0.15, 0.23, 0.32, 0.43, 0.52, 0.60, 0.68,
                       0.75, 0.83, 0.90, 0.97, 0.99, 1.0],
            "monza": [0.04, 0.07, 0.17, 0.29, 0.34, 0.42, 0.52, 0.57,
                      0.64, 0.74, 0.83],
            "silverstone": [0.03, 0.10, 0.17, 0.24, 0.31, 0.39, 0.46, 0.54,
                            0.63, 0.71, 0.79, 0.86, 0.94, 0.98, 1.0, 0.01],
            "spa": [0.04, 0.08, 0.16, 0.25, 0.33, 0.42, 0.50, 0.56,
                    0.63, 0.72, 0.80, 0.88, 0.95, 0.99, 1.0,
                    0.02, 0.05, 0.07],
            "suzuka": [0.04, 0.10, 0.16, 0.24, 0.30, 0.37, 0.44, 0.51,
                       0.58, 0.65, 0.72, 0.80, 0.87, 0.94, 0.98, 0.01,
                       0.02, 0.03],
        }
        circuit_key = next(
            (k for k in _TURN_FRACS if k in event_name.lower()),
            None,
        )
        if circuit_key:
            fracs = _TURN_FRACS[circuit_key]
        else:
            # Evenly spaced fallback (unknown circuit)
            n_turns = 16
            fracs = [i / n_turns for i in range(1, n_turns + 1)]

        turns = [{"n": i + 1, "at": round(f, 4)} for i, f in enumerate(fracs)]

        return {"track": track, "sector_bounds": sector_bounds, "turns": turns}

    except Exception as exc:  # noqa: BLE001
        log.warning("track geometry extraction failed for %s: %s", race_id, exc)
        # Return minimal valid geometry rather than failing the whole stream
        return {
            "track": [[0.5, 0.5]],
            "sector_bounds": [[0, 0], [0, 0], [0, 0]],
            "turns": [{"n": 1, "at": 0.25}],
        }


@router.post("/simulate", response_model=SimulateResponse)
def simulate(body: SimulateRequest) -> SimulateResponse:
    """K=100 posterior-draw forward pass; cache hit <50 ms; cold <2 s.

    D-01: three data levels in one response (per-timestep + per-lap + per-stint).
    D-02: CI triplets mean/lo_95/hi_95 at every level.
    D-03: metadata block with calibration_id, model_schema_version, fastf1_version.
    D-04: K=100 draws; overrides apply equally to all K.
    D-05: no PyMC at runtime (enforced by service-module guard).
    D-06: two-layer cache.
    Note: track/sector_bounds/turns are None on the sync endpoint (streaming only).
    """
    try:
        return run_simulation_with_uncertainty(
            race_id=body.race_id,
            driver_code=body.driver_code,
            stint_index=body.stint_index,
            overrides=body.overrides,
            session_id=body.session_id,
        )
    except ValueError as e:
        msg = str(e)
        if "no calibration" in msg.lower():
            raise HTTPException(status_code=404, detail=msg) from e
        if "stint" in msg.lower() and "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg) from e
        raise HTTPException(status_code=422, detail=msg) from e


@router.post("/simulate/stream")
async def simulate_stream(body: SimulateStreamRequest) -> StreamingResponse:
    """SSE endpoint — streams 7 module_complete events then simulation_complete.

    DASH-03: phased progress animation. Each module_complete event fires as soon
    as that module name is 'announced'; the full physics solve runs as a single
    asyncio.to_thread call after all module events are emitted (lap_count derived
    post-solve). The UI shows progress based on module index, not timing.

    simulation_complete payload extends SimulateResponse with:
      - track: circuit outline from FastF1 X/Y (normalized [0,1], Savitzky-Golay smoothed)
      - sector_bounds: index triplets into track for S1/S2/S3
      - turns: turn markers at fractional positions around the lap

    CPU-bound physics -> asyncio.to_thread (event loop is NOT blocked).
    Headers: Cache-Control: no-cache, X-Accel-Buffering: no (Pitfall 8).
    """

    async def event_generator():
        # Emit the 7 module announce events (progress UI update, no data yet)
        for module_n, module_name in _PHYSICS_MODULES:
            payload = json.dumps({"module": module_n, "name": module_name})
            yield f"event: module_complete\ndata: {payload}\n\n"

        # Run the full CPU-bound simulation in a threadpool thread (CLAUDE.md:
        # sync route or asyncio.to_thread for CPU-bound work — never bare async def)
        try:
            result: SimulateResponse = await asyncio.to_thread(
                run_simulation_with_uncertainty,
                race_id=body.race_id,
                driver_code=body.driver_code,
                stint_index=body.stint_index,
                overrides=None,  # streaming endpoint omits overrides
                session_id=body.session_id,
            )
        except ValueError as e:
            msg = str(e)
            error_payload = json.dumps({"error": msg})
            yield f"event: simulation_error\ndata: {error_payload}\n\n"
            return

        # Extract track geometry (FastF1 X/Y telemetry — D-01)
        # Run in threadpool because FastF1 session.load() is blocking I/O
        track_geo = await asyncio.to_thread(_extract_track_geometry, body.race_id)

        # Emit simulation_complete with full SimulateResponse payload + track geometry
        lap_count = len(result.per_lap)
        final_dict = result.model_dump(mode="json")
        final_dict["lap_count"] = lap_count  # convenience field for frontend
        final_dict["track"] = track_geo["track"]
        final_dict["sector_bounds"] = track_geo["sector_bounds"]
        final_dict["turns"] = track_geo["turns"]
        yield f"event: simulation_complete\ndata: {json.dumps(final_dict)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
