"""Shared pytest fixtures for backend tests.

Each test gets an isolated SQLite database under a tmp_path so they don't
interfere. We rebuild the FastAPI app once per test, swap the engine for the
tmp engine, and produce an httpx TestClient + auth helper.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine

from backend.app import db as db_module
from backend.app.auth import encode_token
from backend.app.main import create_app


@pytest.fixture
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    db_path = tmp_path / "test.db"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("CHESSLAB_DATABASE_URL", url)
    monkeypatch.setenv("CHESSLAB_DEV_AUTH", "1")
    monkeypatch.setenv("CHESSLAB_BOT_DIR", str(tmp_path / "bot_artifacts"))
    # Reload settings + engine to pick up env.
    new_engine = create_engine(url, echo=False, connect_args={"check_same_thread": False})
    monkeypatch.setattr(db_module, "engine", new_engine)
    SQLModel.metadata.create_all(new_engine)
    yield


@pytest.fixture
def client(tmp_db: None) -> Iterator[TestClient]:  # noqa: ARG001
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers() -> dict[str, str]:
    # NEXTAUTH_SECRET defaults to the dev value; encode a token in same context.
    token = encode_token({"github_id": 4242, "login": "alice"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def another_user_headers() -> dict[str, str]:
    token = encode_token({"github_id": 8484, "login": "bob"})
    return {"Authorization": f"Bearer {token}"}


def make_bot_zip(bot_py: str = "from chesslab.bots.random_bot import RandomBot\nBOT = RandomBot(seed=1)\n") -> bytes:
    """Build an in-memory zip containing bot.py for upload tests."""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bot.py", bot_py)
    return buf.getvalue()
