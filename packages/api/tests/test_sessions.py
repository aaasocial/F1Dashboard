"""Phase 4 API-06 tests — /sessions endpoint behaviors.

Requirements: API-06-a through API-06-f (see VALIDATION.md).
Plan 03 replaces pytest.skip(...) stubs with real assertions for 5 of 6 tests.
test_session_routes_simulate (API-06-d) is deferred to Plan 05 (needs /simulate wired
with session_id routing).
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def test_upload_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """API-06-a: POST /sessions/upload with a valid zip returns 200 + session_id."""
    import f1_api.services.sessions as sessions_svc

    sessions_root = tmp_path / "sessions"
    sessions_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sessions_svc, "SESSION_ROOT", sessions_root)

    from f1_api.app import create_app
    from packages.api.tests.fixtures.zip_fixtures import make_valid_zip

    app = create_app()
    with TestClient(app) as client:
        zip_bytes = make_valid_zip()
        resp = client.post(
            "/sessions/upload",
            files={"file": ("cache.zip", zip_bytes, "application/zip")},
        )
    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert re.match(r"^[0-9a-f]{32}$", body["session_id"]) is not None, (
        f"session_id not a 32-char hex string: {body['session_id']!r}"
    )
    assert "expires_at" in body
    # The session directory must exist under the patched SESSION_ROOT
    session_dir = sessions_root / body["session_id"]
    assert session_dir.exists(), f"session dir missing: {session_dir}"


def test_upload_rejects_path_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """API-06-b: Zip-slip upload is rejected before any member extraction (security)."""
    import f1_api.services.sessions as sessions_svc

    sessions_root = tmp_path / "sessions"
    sessions_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sessions_svc, "SESSION_ROOT", sessions_root)

    from f1_api.app import create_app
    from packages.api.tests.fixtures.zip_fixtures import make_zip_slip

    app = create_app()
    with TestClient(app) as client:
        zip_bytes = make_zip_slip()
        resp = client.post(
            "/sessions/upload",
            files={"file": ("malicious.zip", zip_bytes, "application/zip")},
        )
    assert resp.status_code == 400, f"expected 400, got {resp.status_code}"
    detail = resp.json()["detail"]
    assert "escape" in detail.lower() or ".." in detail, (
        f"expected 'escape' or '..' in detail, got: {detail!r}"
    )
    # Session dir must have been cleaned up (rollback on failure)
    for d in sessions_root.iterdir():
        assert not d.exists(), f"session dir was not cleaned up: {d}"


def test_upload_rejects_non_zip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """API-06-c: non-zip upload is rejected at validation, before any extraction."""
    import f1_api.services.sessions as sessions_svc

    sessions_root = tmp_path / "sessions"
    sessions_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sessions_svc, "SESSION_ROOT", sessions_root)

    from f1_api.app import create_app

    app = create_app()
    with TestClient(app) as client:
        resp = client.post(
            "/sessions/upload",
            files={"file": ("not_a_zip.txt", b"plain text", "text/plain")},
        )
    assert resp.status_code in (400, 415, 422), (
        f"expected 4xx, got {resp.status_code}: {resp.text}"
    )


@pytest.mark.integration
def test_session_routes_simulate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """API-06-d: uploaded session routes /simulate without Jolpica."""
    import f1_api.services.sessions as sessions_svc

    # Patch SESSION_ROOT and FastF1 cache to tmp_path
    sessions_root = tmp_path / "sessions"
    fastf1_root = tmp_path / "fastf1_cache"
    sessions_root.mkdir(parents=True)
    fastf1_root.mkdir(parents=True)
    monkeypatch.setattr(sessions_svc, "SESSION_ROOT", sessions_root)
    monkeypatch.setattr("f1_api.services.simulate.SESSION_ROOT", sessions_root)

    # Patch init_cache to return our tmp fastf1_root
    monkeypatch.setattr(
        "f1_api.services.simulate.init_cache",
        lambda: fastf1_root,
    )

    # 1. Upload a zip via POST /sessions/upload
    from packages.api.tests.fixtures.zip_fixtures import make_valid_zip
    from f1_api.app import create_app

    app = create_app()
    with TestClient(app) as client:
        upload_resp = client.post(
            "/sessions/upload",
            files={"file": ("cache.zip", make_valid_zip(), "application/zip")},
        )
    assert upload_resp.status_code == 200, upload_resp.text
    session_id = upload_resp.json()["session_id"]

    # 2. Directly call _merge_session_into_cache and assert merge works
    from f1_api.services.simulate import _merge_session_into_cache
    _merge_session_into_cache(session_id)
    merged = list(fastf1_root.iterdir())
    assert merged, "merge did not populate fastf1_root"


def test_session_ttl_cleanup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """API-06-e: Sessions older than TTL are removed by the cleanup task."""
    import f1_api.services.sessions as sessions_svc

    sessions_root = tmp_path / "sessions"
    sessions_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sessions_svc, "SESSION_ROOT", sessions_root)

    from f1_api.services.sessions import cleanup_once

    # Create a fake session directory
    fake_session_dir = sessions_root / ("a" * 32)
    fake_session_dir.mkdir()

    # Set mtime to 2 hours ago (TTL is 1 hour)
    now = time.time()
    old_time = now - 7200  # 2 hours ago
    os.utime(fake_session_dir, (old_time, old_time))

    # cleanup_once should remove it
    removed = cleanup_once(now)
    assert removed == 1, f"expected 1 directory removed, got {removed}"
    assert not fake_session_dir.exists(), f"session dir was not removed: {fake_session_dir}"


def test_upload_rejects_bomb(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """API-06-f: Decompression-bomb zip is rejected before extraction (DoS mitigation)."""
    import f1_api.services.sessions as sessions_svc

    sessions_root = tmp_path / "sessions"
    sessions_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sessions_svc, "SESSION_ROOT", sessions_root)

    from f1_api.app import create_app
    from packages.api.tests.fixtures.zip_fixtures import make_decompression_bomb

    app = create_app()
    with TestClient(app) as client:
        zip_bytes = make_decompression_bomb()
        resp = client.post(
            "/sessions/upload",
            files={"file": ("bomb.zip", zip_bytes, "application/zip")},
        )
    assert resp.status_code == 400, f"expected 400, got {resp.status_code}: {resp.text}"
    detail = resp.json()["detail"]
    assert "cap" in detail.lower() or "expands" in detail.lower(), (
        f"expected 'cap' or 'expands' in detail, got: {detail!r}"
    )


def test_upload_rejects_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-4-SYMLINK: Zip with POSIX symlink member is rejected with 400."""
    import f1_api.services.sessions as sessions_svc

    sessions_root = tmp_path / "sessions"
    sessions_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sessions_svc, "SESSION_ROOT", sessions_root)

    from f1_api.app import create_app
    from packages.api.tests.fixtures.zip_fixtures import make_symlink_zip

    app = create_app()
    with TestClient(app) as client:
        zip_bytes = make_symlink_zip()
        resp = client.post(
            "/sessions/upload",
            files={"file": ("symlink.zip", zip_bytes, "application/zip")},
        )
    assert resp.status_code == 400, f"expected 400, got {resp.status_code}: {resp.text}"
    detail = resp.json()["detail"]
    assert "symlink" in detail.lower(), (
        f"expected 'symlink' in detail, got: {detail!r}"
    )
