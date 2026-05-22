"""Backend configuration.

All settings come from env vars. Production sets a real Postgres URL and a
shared NEXTAUTH_SECRET. Dev/tests default to an in-memory or temp SQLite file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.environ.get("CHESSLAB_DATABASE_URL", "sqlite:///./chesslab.db")
    nextauth_secret: str = os.environ.get(
        "NEXTAUTH_SECRET",
        "dev-insecure-secret-change-me-please-min-32-bytes",
    )
    jwt_algorithm: str = os.environ.get("CHESSLAB_JWT_ALGORITHM", "HS256")
    cors_origins: str = os.environ.get("CHESSLAB_CORS_ORIGINS", "http://localhost:3000")
    runner_image: str = os.environ.get("CHESSLAB_RUNNER_IMAGE", "chesslab-runner:dev")
    runner_default_memory_mb: int = int(os.environ.get("CHESSLAB_RUNNER_MEMORY_MB", "512"))
    runner_default_cpus: float = float(os.environ.get("CHESSLAB_RUNNER_CPUS", "1"))
    runner_default_movetime_ms: int = int(os.environ.get("CHESSLAB_RUNNER_MOVETIME_MS", "1000"))
    runner_max_plies: int = int(os.environ.get("CHESSLAB_RUNNER_MAX_PLIES", "300"))
    bot_artifact_dir: str = os.environ.get("CHESSLAB_BOT_DIR", "./bot_artifacts")


settings = Settings()
