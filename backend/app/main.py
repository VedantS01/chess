"""FastAPI app factory + uvicorn entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import auth as auth_router
from backend.app.api import bots as bots_router
from backend.app.api import leaderboard as leaderboard_router
from backend.app.api import matches as matches_router
from backend.app.api import ws as ws_router
from backend.app.config import settings
from backend.app.db import init_db


def create_app() -> FastAPI:
    app = FastAPI(
        title="chesslab backend",
        version="0.1.0",
        description="Chess platform backend - bot uploads, online play, ELO ladder.",
    )

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    init_db()

    app.include_router(auth_router.router, prefix="/api")
    app.include_router(bots_router.router, prefix="/api")
    app.include_router(matches_router.router, prefix="/api")
    app.include_router(leaderboard_router.router, prefix="/api")
    app.include_router(ws_router.router, prefix="/api")

    @app.get("/api/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
