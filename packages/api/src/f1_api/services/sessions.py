"""Session upload service — secure zip extraction + TTL cleanup (API-06).

Security:
  - T-4-ZIP: per-member path resolution + is_relative_to guard (Zip Slip).
  - T-4-BOMB: ZipInfo.file_size sum cap at 500 MB, member count cap at 10k.
  - T-4-SYMLINK: external_attr bits 0o120000 reject.
  - T-4-PATH: SESSION_ROOT enforced via WORKSPACE_ROOT containment.
"""
from __future__ import annotations

import io
import logging
import shutil
import threading
import time
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from f1_calibration.common import WORKSPACE_ROOT

log = logging.getLogger(__name__)

SESSION_ROOT: Path = WORKSPACE_ROOT / ".data" / "sessions"
SESSION_TTL_SECONDS: int = 3600           # D-07: 1 hour
CLEANUP_INTERVAL_SECONDS: int = 300       # Check every 5 min
MAX_ZIP_TOTAL_UNCOMPRESSED: int = 500 * 1024 * 1024   # 500 MB
MAX_ZIP_MEMBERS: int = 10_000
MAX_UPLOAD_BYTES: int = 100 * 1024 * 1024             # 100 MB compressed (T-4-DOS)
_CHUNK_BYTES: int = 65536


def _ensure_session_root() -> Path:
    SESSION_ROOT.mkdir(parents=True, exist_ok=True)
    return SESSION_ROOT


def register_session_upload() -> tuple[str, Path]:
    """Create a new session directory and return (session_id, session_dir)."""
    _ensure_session_root()
    session_id = uuid.uuid4().hex
    session_dir = SESSION_ROOT / session_id
    session_dir.mkdir(parents=False, exist_ok=False)  # FAIL if collision (astronomically unlikely)
    return session_id, session_dir


def extract_session_zip(zip_bytes: bytes, dest: Path) -> None:
    """Extract zip_bytes safely under dest. Raises ValueError on any security violation.

    T-4-ZIP mitigation: per-member path resolution + is_relative_to guard.
    T-4-BOMB mitigation: member count + uncompressed size cap BEFORE extraction.
    T-4-SYMLINK mitigation: external_attr 0o120000 rejected.
    """
    if len(zip_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"upload is {len(zip_bytes)} bytes, cap is {MAX_UPLOAD_BYTES}"
        )
    dest_resolved = dest.resolve()
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as e:
        raise ValueError(f"not a valid zip file: {e}") from e
    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_ZIP_MEMBERS:
            raise ValueError(f"zip has too many members: {len(infos)}")
        total = sum(i.file_size for i in infos)
        if total > MAX_ZIP_TOTAL_UNCOMPRESSED:
            raise ValueError(
                f"zip expands to {total} bytes, cap is {MAX_ZIP_TOTAL_UNCOMPRESSED}"
            )
        for info in infos:
            # Symlink bits in high 16 of external_attr
            mode = info.external_attr >> 16
            if mode & 0o170000 == 0o120000:
                raise ValueError(f"zip contains symlink member: {info.filename!r}")
            # Path traversal check (Zip Slip)
            target = (dest / info.filename).resolve()
            try:
                target.relative_to(dest_resolved)
            except ValueError as e:
                raise ValueError(
                    f"zip member escapes dest: {info.filename!r}"
                ) from e
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as dst:
                while True:
                    chunk = src.read(_CHUNK_BYTES)
                    if not chunk:
                        break
                    dst.write(chunk)


def cleanup_once(now_seconds: float, *, ttl_seconds: int = SESSION_TTL_SECONDS) -> int:
    """Remove session dirs older than ttl_seconds. Pure function for testability."""
    if not SESSION_ROOT.exists():
        return 0
    removed = 0
    for session_dir in SESSION_ROOT.iterdir():
        if not session_dir.is_dir():
            continue
        try:
            mtime = session_dir.stat().st_mtime
        except FileNotFoundError:
            continue
        if now_seconds - mtime > ttl_seconds:
            shutil.rmtree(session_dir, ignore_errors=True)
            removed += 1
            log.info(
                "cleaned up expired session %s (age %.0fs)",
                session_dir.name,
                now_seconds - mtime,
            )
    return removed


def _cleanup_loop(stop_event: threading.Event) -> None:
    """Daemon loop — sleeps CLEANUP_INTERVAL_SECONDS between passes."""
    while not stop_event.is_set():
        try:
            cleanup_once(time.time())
        except Exception as e:  # noqa: BLE001
            log.warning("cleanup_once failed: %s", e, exc_info=True)
        # Event.wait permits early wake on shutdown
        stop_event.wait(CLEANUP_INTERVAL_SECONDS)


def start_cleanup_daemon() -> tuple[threading.Thread, threading.Event]:
    """Spawn a daemon thread that periodically runs cleanup_once.

    Returns (thread, stop_event). Thread is started. Event can be set by
    the caller to gracefully stop (though daemon=True also kills on process exit).
    """
    _ensure_session_root()
    stop_event = threading.Event()
    thread = threading.Thread(
        target=_cleanup_loop,
        args=(stop_event,),
        daemon=True,
        name="session-ttl-cleanup",
    )
    thread.start()
    return thread, stop_event


def compute_expires_at(now: datetime | None = None) -> str:
    """ISO-8601 UTC timestamp of session expiry."""
    if now is None:
        now = datetime.now(timezone.utc)
    return (now + timedelta(seconds=SESSION_TTL_SECONDS)).isoformat(timespec="seconds")


__all__ = [
    "SESSION_ROOT",
    "SESSION_TTL_SECONDS",
    "MAX_ZIP_TOTAL_UNCOMPRESSED",
    "MAX_ZIP_MEMBERS",
    "MAX_UPLOAD_BYTES",
    "register_session_upload",
    "extract_session_zip",
    "cleanup_once",
    "start_cleanup_daemon",
    "compute_expires_at",
]
