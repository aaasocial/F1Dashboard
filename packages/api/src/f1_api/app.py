"""F1 Tire Degradation Analyzer — FastAPI app (Phase 1 + Phase 4 endpoints).

Phase 1 ships API-01, API-02, API-03. Phase 4 adds /simulate, /calibration/{compound},
/sessions/upload, GZipMiddleware, session cleanup daemon, and posterior cache priming.
All endpoints are plain `def` (pitfall P9): FastAPI runs them in its threadpool,
so blocking FastF1 calls don't stall the event loop.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from f1_calibration.db import DEFAULT_DB_PATH
from f1_core.ingestion import init_cache
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from f1_api.routers import calibration as calibration_router
from f1_api.routers import drivers as drivers_router
from f1_api.routers import races as races_router
from f1_api.routers import sessions as sessions_router
from f1_api.routers import simulate as simulate_router
from f1_api.routers import stints as stints_router
from f1_api.services.posterior_store import prime_posterior
from f1_api.services.sessions import start_cleanup_daemon

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Phase 1 + Phase 4 startup: init FastF1 cache, start session TTL daemon,
    prime posterior cache for C1..C5 (best-effort — missing calibrations do
    not block startup)."""
    cache_dir = init_cache()
    log.info("FastF1 cache initialized at %s", cache_dir)

    cleanup_thread, cleanup_stop = start_cleanup_daemon()
    log.info("Session cleanup daemon started (thread=%s)", cleanup_thread.name)

    for compound in ("C1", "C2", "C3", "C4", "C5"):
        try:
            prime_posterior(DEFAULT_DB_PATH, compound)
            log.info("Primed posterior cache for %s", compound)
        except Exception as e:  # noqa: BLE001
            log.warning("Posterior prime failed for %s: %s", compound, e)

    try:
        yield
    finally:
        cleanup_stop.set()
        log.info("Session cleanup daemon stop signaled")


def _allowed_origins() -> list[str]:
    """Default dev origins + any production origin from F1_ALLOWED_ORIGIN env var."""
    defaults = ["http://localhost:5173"]
    extra = os.environ.get("F1_ALLOWED_ORIGIN")
    if extra:
        return [*defaults, extra]
    return defaults


def create_app() -> FastAPI:
    app = FastAPI(
        title="F1 Tire Degradation Analyzer",
        version="0.1.0",
        lifespan=lifespan,
        debug=False,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)
    app.include_router(races_router.router)
    app.include_router(drivers_router.router)
    app.include_router(stints_router.router)
    app.include_router(sessions_router.router)
    app.include_router(simulate_router.router)
    app.include_router(calibration_router.router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
