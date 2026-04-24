"""Integration tests for POST /simulate/stream SSE endpoint (DASH-03).

Tests cover:
  - SSE event count and structure
  - Track geometry fields in simulation_complete (Blocker 2 fix)
  - Validation errors
  - Regression guard for sync /simulate
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from f1_api.app import create_app
from f1_api.schemas.simulate import (
    CIArray1D,
    CIArray2D,
    CIValue,
    PerLapRow,
    PerStintSummary,
    PerTimestepBlock,
    SimulateResponse,
    SimulationMetadata,
)

# Minimal fixture response — avoids real FastF1 calls
_META = SimulationMetadata(
    calibration_id=1,
    model_schema_version="v1",
    fastf1_version="3.8.2",
    compound="C3",
    stint_index=1,
    overrides_applied=False,
    k_draws=100,
)
_CI = CIValue(mean=1.0, lo_95=0.9, hi_95=1.1)
_PER_LAP = [
    PerLapRow(
        lap=1,
        compound="C3",
        age=1,
        obs_s=90.0,
        pred_s=_CI,
        delta_s=_CI,
        grip_pct=_CI,
        t_tread_max_c=_CI,
        e_tire_mj=_CI,
    )
]
_PER_STINT = PerStintSummary(
    total_predicted_time_s=_CI,
    stint_end_grip_pct=_CI,
    peak_t_tread_c=_CI,
    total_e_tire_mj=_CI,
)
_PER_TIMESTEP = PerTimestepBlock(
    t=[0.0, 0.25],
    t_tread=CIArray2D(
        mean=[[90.0, 90.0, 90.0, 90.0], [91.0, 91.0, 91.0, 91.0]],
        lo_95=[[88.0, 88.0, 88.0, 88.0], [89.0, 89.0, 89.0, 89.0]],
        hi_95=[[92.0, 92.0, 92.0, 92.0], [93.0, 93.0, 93.0, 93.0]],
    ),
    e_tire=CIArray2D(
        mean=[[0.0, 0.0, 0.0, 0.0], [0.1, 0.1, 0.1, 0.1]],
        lo_95=[[0.0] * 4, [0.05] * 4],
        hi_95=[[0.0] * 4, [0.15] * 4],
    ),
    mu=CIArray2D(
        mean=[[1.4] * 4, [1.39] * 4],
        lo_95=[[1.3] * 4, [1.3] * 4],
        hi_95=[[1.5] * 4, [1.5] * 4],
    ),
    f_z=CIArray2D(
        mean=[[3000.0] * 4, [3000.0] * 4],
        lo_95=[[2900.0] * 4, [2900.0] * 4],
        hi_95=[[3100.0] * 4, [3100.0] * 4],
    ),
    f_y=CIArray2D(
        mean=[[500.0] * 4, [500.0] * 4],
        lo_95=[[450.0] * 4, [450.0] * 4],
        hi_95=[[550.0] * 4, [550.0] * 4],
    ),
    f_x=CIArray2D(
        mean=[[200.0] * 4, [200.0] * 4],
        lo_95=[[180.0] * 4, [180.0] * 4],
        hi_95=[[220.0] * 4, [220.0] * 4],
    ),
    mu_0=CIArray1D(
        mean=[1.4, 1.39],
        lo_95=[1.3, 1.3],
        hi_95=[1.5, 1.5],
    ),
)
_FIXTURE_RESPONSE = SimulateResponse(
    metadata=_META,
    per_timestep=_PER_TIMESTEP,
    per_lap=_PER_LAP,
    per_stint=_PER_STINT,
)

# Fixture track geometry returned by mocked _extract_track_geometry
_FIXTURE_TRACK_GEO = {
    "track": [[0.1, 0.9], [0.5, 0.1], [0.9, 0.9]],
    "sector_bounds": [[0, 1], [1, 2], [2, 3]],
    "turns": [{"n": 1, "at": 0.33}, {"n": 2, "at": 0.66}],
}

VALID_BODY = {
    "race_id": "2023-bahrain_grand_prix",
    "driver_code": "LEC",
    "stint_index": 1,
}


@pytest.fixture()
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def _collect_stream(response) -> list[dict]:
    """Parse SSE stream text into list of {event, data} dicts."""
    events = []
    current: dict = {}
    for line in response.text.splitlines():
        if line.startswith("event: "):
            current["event"] = line[7:].strip()
        elif line.startswith("data: "):
            current["data"] = json.loads(line[6:].strip())
        elif line == "" and current:
            events.append(current)
            current = {}
    if current:
        events.append(current)
    return events


def _patched_stream(client, body=None):
    """Helper: POST /simulate/stream with both heavy deps mocked."""
    body = body or VALID_BODY
    with (
        patch(
            "f1_api.routers.simulate.run_simulation_with_uncertainty",
            return_value=_FIXTURE_RESPONSE,
        ),
        patch(
            "f1_api.routers.simulate._extract_track_geometry",
            return_value=_FIXTURE_TRACK_GEO,
        ),
    ):
        return client.post("/simulate/stream", json=body)


class TestSimulateStream:
    def test_returns_200_and_event_stream_content_type(self, client):
        resp = _patched_stream(client)
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    def test_emits_7_module_complete_events(self, client):
        resp = _patched_stream(client)
        events = _collect_stream(resp)
        module_events = [e for e in events if e.get("event") == "module_complete"]
        assert len(module_events) == 7

    def test_module_complete_payloads_have_required_keys(self, client):
        resp = _patched_stream(client)
        events = _collect_stream(resp)
        for e in events:
            if e.get("event") == "module_complete":
                assert "module" in e["data"]
                assert "name" in e["data"]
                assert isinstance(e["data"]["module"], int)

    def test_module_indices_are_1_through_7_in_order(self, client):
        resp = _patched_stream(client)
        events = _collect_stream(resp)
        indices = [e["data"]["module"] for e in events if e.get("event") == "module_complete"]
        assert indices == list(range(1, 8))

    def test_emits_exactly_1_simulation_complete_event(self, client):
        resp = _patched_stream(client)
        events = _collect_stream(resp)
        complete_events = [e for e in events if e.get("event") == "simulation_complete"]
        assert len(complete_events) == 1

    def test_simulation_complete_contains_metadata_key(self, client):
        resp = _patched_stream(client)
        events = _collect_stream(resp)
        complete = next(e for e in events if e.get("event") == "simulation_complete")
        assert "metadata" in complete["data"]
        assert "per_lap" in complete["data"]
        assert "per_stint" in complete["data"]

    def test_simulation_complete_contains_track_geometry(self, client):
        """Blocker 2 fix: track/sector_bounds/turns present in simulation_complete payload."""
        resp = _patched_stream(client)
        events = _collect_stream(resp)
        complete = next(e for e in events if e.get("event") == "simulation_complete")
        data = complete["data"]
        assert "track" in data, "track geometry missing from simulation_complete"
        assert "sector_bounds" in data, "sector_bounds missing from simulation_complete"
        assert "turns" in data, "turns missing from simulation_complete"
        assert isinstance(data["track"], list)
        assert isinstance(data["sector_bounds"], list)
        assert isinstance(data["turns"], list)
        # Verify structure of track points: list of [x, y] pairs
        assert all(isinstance(pt, list) and len(pt) == 2 for pt in data["track"])
        # Verify turn structure: each has "n" and "at"
        assert all("n" in t and "at" in t for t in data["turns"])

    def test_invalid_driver_code_returns_422(self, client):
        resp = client.post(
            "/simulate/stream",
            json={**VALID_BODY, "driver_code": "leclerc"},  # lowercase, too long
        )
        assert resp.status_code == 422

    def test_response_has_no_cache_header(self, client):
        resp = _patched_stream(client)
        assert resp.headers.get("cache-control") == "no-cache"

    def test_existing_sync_simulate_endpoint_still_works(self, client):
        """Regression: POST /simulate must be unchanged (D-03)."""
        with patch(
            "f1_api.routers.simulate.run_simulation_with_uncertainty",
            return_value=_FIXTURE_RESPONSE,
        ):
            resp = client.post("/simulate", json=VALID_BODY)
        assert resp.status_code == 200
        body = resp.json()
        assert "metadata" in body
        assert "per_lap" in body

    def test_sync_simulate_does_not_contain_track_geometry(self, client):
        """Sync /simulate returns None for track fields (geometry is stream-only in v1)."""
        with patch(
            "f1_api.routers.simulate.run_simulation_with_uncertainty",
            return_value=_FIXTURE_RESPONSE,
        ):
            resp = client.post("/simulate", json=VALID_BODY)
        body = resp.json()
        # track should be absent or null — not a populated list
        assert body.get("track") is None
