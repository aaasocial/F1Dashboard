"""Two-layer result cache for POST /simulate (D-06).

Layer 1: in-process OrderedDict LRU, max_entries entries.
Layer 2: SQLite simulation_cache table, BLOB payload.

Invalidation: when a new calibration_runs row for a compound replaces
the old one (different calibration_id), old cache entries are either
explicitly purged (invalidate_for_calibration) or just never match
again (key includes calibration_id).

Threat: T-4-CACHE — cache key is SHA256 of a namespaced tuple, preventing
collisions across schema versions.
"""
from __future__ import annotations
import hashlib
import logging
import sqlite3
import threading
from collections import OrderedDict
from pathlib import Path
from datetime import datetime, timezone

log = logging.getLogger(__name__)


def _resolve_cache_db_path(db_path: str | Path) -> Path:
    """Resolve db_path to absolute Path. Simple resolution for app-owned cache DB.

    Unlike f1_calibration.db.resolve_db_path, this does NOT enforce workspace
    containment — the cache DB is an application-owned file, not user-supplied
    input, so the workspace-containment security check is not applicable here.
    """
    resolved = Path(db_path).expanduser().resolve()
    if resolved.is_symlink():
        raise ValueError(f"cache db_path {resolved} must not be a symlink")
    return resolved

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS simulation_cache (
    cache_key      TEXT PRIMARY KEY,
    calibration_id INTEGER NOT NULL,
    created_at     TEXT NOT NULL,
    payload_json   BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_simulation_cache_cal
    ON simulation_cache (calibration_id);
"""


def make_cache_key(
    race_id: str,
    driver_code: str,
    stint_index: int,
    calibration_id: int,
    overrides_hash: str | None,
) -> str:
    """SHA256 hex of namespaced key tuple. T-4-CACHE."""
    key = f"sim_v1|{race_id}|{driver_code}|{stint_index}|{calibration_id}|{overrides_hash or 'none'}"
    return hashlib.sha256(key.encode()).hexdigest()


def hash_overrides(overrides: dict | None) -> str | None:
    """Canonical SHA256 of sorted override dict (or None if empty/absent)."""
    if not overrides:
        return None
    import json
    normalized = json.dumps(overrides, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode()).hexdigest()


class SimulateCache:
    """In-process LRU over SQLite-persistent /simulate responses."""

    def __init__(self, db_path: str | Path, *, max_entries: int = 64) -> None:
        self._db_path: Path = _resolve_cache_db_path(db_path)
        self._max_entries: int = max_entries
        self._memory: OrderedDict[str, bytes] = OrderedDict()
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.executescript(_SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()

    def get(
        self,
        race_id: str,
        driver_code: str,
        stint_index: int,
        calibration_id: int,
        overrides_hash: str | None,
    ) -> bytes | None:
        key = make_cache_key(race_id, driver_code, stint_index, calibration_id, overrides_hash)
        with self._lock:
            if key in self._memory:
                self._memory.move_to_end(key)  # LRU promote
                return self._memory[key]
        # Fall through to SQLite
        conn = sqlite3.connect(str(self._db_path))
        try:
            cur = conn.execute(
                "SELECT payload_json FROM simulation_cache WHERE cache_key = :k",
                {"k": key},
            )
            row = cur.fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        payload: bytes = bytes(row[0])
        with self._lock:
            if key not in self._memory:          # another thread may have inserted already
                self._memory[key] = payload
                self._memory.move_to_end(key)
                self._evict_locked()
        return payload

    def put(
        self,
        race_id: str,
        driver_code: str,
        stint_index: int,
        calibration_id: int,
        overrides_hash: str | None,
        payload: bytes,
    ) -> None:
        key = make_cache_key(race_id, driver_code, stint_index, calibration_id, overrides_hash)
        with self._lock:
            self._memory[key] = payload
            self._memory.move_to_end(key)
            self._evict_locked()
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.execute(
                "INSERT OR REPLACE INTO simulation_cache "
                "(cache_key, calibration_id, created_at, payload_json) "
                "VALUES (:k, :cid, :ts, :p)",
                {
                    "k": key,
                    "cid": int(calibration_id),
                    "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "p": payload,
                },
            )
            conn.commit()
        finally:
            conn.close()

    def invalidate_for_calibration(self, calibration_id: int) -> int:
        conn = sqlite3.connect(str(self._db_path))
        try:
            cur = conn.execute(
                "DELETE FROM simulation_cache WHERE calibration_id = :cid",
                {"cid": int(calibration_id)},
            )
            conn.commit()
            deleted = cur.rowcount
        finally:
            conn.close()
        # Evict matching in-memory entries — we don't store calibration_id
        # per-key in memory, so we conservatively flush. Cheap at max_entries=64.
        with self._lock:
            self._memory.clear()
        return int(deleted)

    def _evict_locked(self) -> None:
        while len(self._memory) > self._max_entries:
            self._memory.popitem(last=False)

    def clear(self) -> None:
        """Test helper: drop all entries from both layers."""
        with self._lock:
            self._memory.clear()
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.execute("DELETE FROM simulation_cache")
            conn.commit()
        finally:
            conn.close()


__all__ = ["SimulateCache", "make_cache_key", "hash_overrides"]
