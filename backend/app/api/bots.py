"""Bot upload / list / delete routes."""

from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.app.auth import CurrentUser
from backend.app.config import settings
from backend.app.db import get_session
from backend.app.models import Bot, BotStatus

router = APIRouter(prefix="/bots", tags=["bots"])


class BotOut(BaseModel):
    id: int
    owner_id: int
    name: str
    version: int
    description: str | None
    status: BotStatus
    elo: float


def _bot_to_out(bot: Bot) -> BotOut:
    assert bot.id is not None
    return BotOut(
        id=bot.id,
        owner_id=bot.owner_id,
        name=bot.name,
        version=bot.version,
        description=bot.description,
        status=bot.status,
        elo=bot.elo,
    )


def _artifact_dir() -> Path:
    # Resolve at call time so test isolation (CHESSLAB_BOT_DIR override) works.
    import os

    p = Path(os.environ.get("CHESSLAB_BOT_DIR", settings.bot_artifact_dir))
    p.mkdir(parents=True, exist_ok=True)
    return p


def _extract_artifact(upload: UploadFile, dest: Path) -> None:
    """Extract uploaded .zip safely, rejecting absolute paths and traversals."""
    dest.mkdir(parents=True, exist_ok=True)
    upload.file.seek(0)
    with zipfile.ZipFile(upload.file, "r") as zf:
        for member in zf.namelist():
            if member.startswith("/") or ".." in Path(member).parts:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unsafe path in zip: {member}")
        zf.extractall(dest)
    if not (dest / "bot.py").exists():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "zip must contain bot.py at the root")


@router.post("", response_model=BotOut, status_code=status.HTTP_201_CREATED)
async def upload_bot(
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
    name: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
    artifact: UploadFile = File(...),
) -> BotOut:
    if not artifact.filename or not artifact.filename.lower().endswith(".zip"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "artifact must be a .zip")

    existing = session.exec(
        select(Bot).where(Bot.owner_id == user.id, Bot.name == name)
    ).all()
    next_version = max((b.version for b in existing), default=0) + 1

    digest = hashlib.sha256()
    artifact.file.seek(0)
    while True:
        chunk = artifact.file.read(64 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    sha = digest.hexdigest()[:12]
    artifact_root = _artifact_dir() / f"user-{user.id}" / f"{name}-v{next_version}-{sha}"
    if artifact_root.exists():
        shutil.rmtree(artifact_root)
    _extract_artifact(artifact, artifact_root)

    bot = Bot(
        owner_id=int(user.id),  # type: ignore[arg-type]
        name=name,
        version=next_version,
        description=description,
        artifact_path=str(artifact_root),
        status=BotStatus.ready,
    )
    session.add(bot)
    session.commit()
    session.refresh(bot)
    return _bot_to_out(bot)


@router.get("", response_model=list[BotOut])
def list_bots_all(
    session: Annotated[Session, Depends(get_session)],
    owner_id: int | None = None,
) -> list[BotOut]:
    stmt = select(Bot)
    if owner_id is not None:
        stmt = stmt.where(Bot.owner_id == owner_id)
    return [_bot_to_out(b) for b in session.exec(stmt).all()]


@router.get("/mine", response_model=list[BotOut])
def list_my_bots(
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
) -> list[BotOut]:
    return [_bot_to_out(b) for b in session.exec(select(Bot).where(Bot.owner_id == user.id)).all()]


@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bot(
    bot_id: int,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
) -> None:
    bot = session.get(Bot, bot_id)
    if bot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "bot not found")
    if bot.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your bot")
    bot.status = BotStatus.disabled
    session.add(bot)
    session.commit()
