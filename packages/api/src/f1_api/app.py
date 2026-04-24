"""F1 Tire Degradation Analyzer — FastAPI app.

Minimal app factory for Phase 5 SSE endpoint. The full Phase 4 app factory
includes lifespan (FastF1 cache init, posterior priming), CORS, and GZip
middleware. This version provides create_app() for the SSE router and tests.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from f1_api.routers import simulate as simulate_router_module


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="F1 Tire Degradation Analyzer",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS — allow all origins for development; restrict in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # GZip compression for large simulation payloads
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Register routers
    app.include_router(simulate_router_module.router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app
