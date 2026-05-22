"""SQLModel database schema."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum

from sqlmodel import Field, SQLModel


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class BotStatus(StrEnum):
    pending = "pending"
    ready = "ready"
    failed = "failed"
    disabled = "disabled"


class MatchResult(StrEnum):
    white = "1-0"
    black = "0-1"
    draw = "1/2-1/2"
    unfinished = "*"


class MatchStatus(StrEnum):
    pending = "pending"
    running = "running"
    finished = "finished"
    failed = "failed"


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    github_id: int = Field(index=True, unique=True)
    login: str = Field(index=True, unique=True)
    name: str | None = None
    avatar_url: str | None = None
    elo: float = Field(default=1500.0)
    created_at: dt.datetime = Field(default_factory=utcnow, index=True)


class Bot(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(index=True)
    version: int = Field(default=1)
    description: str | None = None
    status: BotStatus = Field(default=BotStatus.pending)
    elo: float = Field(default=1500.0)
    artifact_path: str
    created_at: dt.datetime = Field(default_factory=utcnow, index=True)


class Match(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    white_bot_id: int | None = Field(default=None, foreign_key="bot.id", index=True)
    black_bot_id: int | None = Field(default=None, foreign_key="bot.id", index=True)
    white_user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    black_user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    status: MatchStatus = Field(default=MatchStatus.pending)
    result: MatchResult = Field(default=MatchResult.unfinished)
    pgn: str | None = None
    termination: str | None = None
    created_at: dt.datetime = Field(default_factory=utcnow, index=True)
    finished_at: dt.datetime | None = None


class RatingHistory(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    bot_id: int | None = Field(default=None, foreign_key="bot.id", index=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    match_id: int = Field(foreign_key="match.id", index=True)
    rating_before: float
    rating_after: float
    created_at: dt.datetime = Field(default_factory=utcnow, index=True)
