"""API-01/02/03 integration tests via TestClient. No Jolpica access."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_healthz(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_get_races(client: TestClient) -> None:
    r = client.get("/races")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    first = body[0]
    for field in ("year", "round", "name"):
        assert field in first
    years = {entry["year"] for entry in body}
    assert 2022 in years
    # HTTP cache header set (CTX: completed races are immutable)
    assert "public" in r.headers.get("cache-control", "").lower()


def test_get_races_start_year_rejects_below_2022(client: TestClient) -> None:
    r = client.get("/races", params={"start_year": 2000})
    assert r.status_code == 422


def test_get_drivers_for_bahrain_2023(client: TestClient) -> None:
    r = client.get("/races/2023-bahrain/drivers")
    assert r.status_code == 200
    body = r.json()
    codes = [d["driver_code"] for d in body]
    assert "VER" in codes
    # Schema check
    for d in body:
        assert set(d.keys()) >= {"driver_code", "full_name", "team", "stint_count"}


def test_get_drivers_unknown_race_404(client: TestClient) -> None:
    r = client.get("/races/2099-mars/drivers")
    assert r.status_code == 404


def test_get_stints_for_ver_bahrain_2023(client: TestClient) -> None:
    r = client.get("/stints/2023-bahrain/VER")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 3
    stint2 = next(s for s in body if s["stint_index"] == 2)
    assert stint2["compound"] == "MEDIUM"
    assert stint2["compound_letter"] == "C2"
    assert stint2["lap_count"] == 23
    assert stint2["quality_verdict"] == "ok"
    assert 0.0 <= stint2["quality_score"] <= 1.0


@pytest.mark.parametrize(
    "bad_race_id",
    [
        "../etc/passwd",
        "2023-../evil",
        "2023/bahrain",
        "2023-Bahrain",  # uppercase — regex is [a-z0-9_]
        "23-bahrain",
        "",
    ],
)
def test_path_traversal_rejected_on_drivers(client: TestClient, bad_race_id: str) -> None:
    r = client.get(f"/races/{bad_race_id}/drivers")
    # 422 (pydantic rejection) or 404 (router match failure for / in path) both prove the regex blocks misuse
    assert r.status_code in {422, 404}


@pytest.mark.parametrize(
    "bad_race_id",
    ["../etc/passwd", "2023-Bahrain", "23-bahrain", ""],
)
def test_path_traversal_rejected_on_stints_race_id(client: TestClient, bad_race_id: str) -> None:
    r = client.get(f"/stints/{bad_race_id}/VER")
    assert r.status_code in {422, 404}


@pytest.mark.parametrize("bad_driver", ["ver", "VERS", "VE", "", "V3R"])
def test_driver_code_regex_rejects_invalid(client: TestClient, bad_driver: str) -> None:
    r = client.get(f"/stints/2023-bahrain/{bad_driver}")
    assert r.status_code in {422, 404}


def test_cors_allows_localhost(client: TestClient) -> None:
    r = client.options(
        "/races",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    # FastAPI returns 200 on OPTIONS with CORS middleware configured
    assert r.status_code in {200, 204}
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_rejects_evil_origin(client: TestClient) -> None:
    r = client.options(
        "/races",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # Middleware must NOT echo an unauthorized origin
    allow = r.headers.get("access-control-allow-origin", "")
    assert allow != "https://evil.example.com"
