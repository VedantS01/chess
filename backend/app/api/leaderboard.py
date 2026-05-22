"""Public leaderboard endpoints (bots + users)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.app.db import get_session
from backend.app.models import Bot, BotStatus, User

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


class BotLeaderboardEntry(BaseModel):
    id: int
    owner_id: int
    name: str
    version: int
    elo: float


class UserLeaderboardEntry(BaseModel):
    id: int
    login: str
    elo: float


@router.get("/bots", response_model=list[BotLeaderboardEntry])
def bot_leaderboard(
    session: Annotated[Session, Depends(get_session)],
    limit: int = 50,
    offset: int = 0,
) -> list[BotLeaderboardEntry]:
    rows = session.exec(
        select(Bot)
        .where(Bot.status == BotStatus.ready)
        .order_by(Bot.elo.desc())  # type: ignore[attr-defined]
        .offset(offset)
        .limit(limit)
    ).all()
    return [
        BotLeaderboardEntry(id=b.id, owner_id=b.owner_id, name=b.name, version=b.version, elo=b.elo)  # type: ignore[arg-type]
        for b in rows
    ]


@router.get("/users", response_model=list[UserLeaderboardEntry])
def user_leaderboard(
    session: Annotated[Session, Depends(get_session)],
    limit: int = 50,
    offset: int = 0,
) -> list[UserLeaderboardEntry]:
    rows = session.exec(
        select(User)
        .order_by(User.elo.desc())  # type: ignore[attr-defined]
        .offset(offset)
        .limit(limit)
    ).all()
    return [
        UserLeaderboardEntry(id=u.id, login=u.login, elo=u.elo)  # type: ignore[arg-type]
        for u in rows
    ]
