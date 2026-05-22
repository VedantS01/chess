"""Match scheduling routes.

Step 8 ships pending/finished CRUD only. Step 9 layers the sandboxed
match_runner on top so scheduling a bot-vs-bot match actually runs it.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.app.auth import CurrentUser
from backend.app.db import get_session
from backend.app.match_runner import execute_pending_match
from backend.app.models import Bot, Match, MatchResult, MatchStatus

router = APIRouter(prefix="/matches", tags=["matches"])


class ScheduleMatchRequest(BaseModel):
    white_bot_id: int
    black_bot_id: int


class MatchOut(BaseModel):
    id: int
    white_bot_id: int | None
    black_bot_id: int | None
    status: MatchStatus
    result: MatchResult
    pgn: str | None
    termination: str | None


def _match_out(m: Match) -> MatchOut:
    assert m.id is not None
    return MatchOut(
        id=m.id,
        white_bot_id=m.white_bot_id,
        black_bot_id=m.black_bot_id,
        status=m.status,
        result=m.result,
        pgn=m.pgn,
        termination=m.termination,
    )


class ScheduleResponse(BaseModel):
    match: MatchOut


@router.post("/schedule", response_model=MatchOut, status_code=status.HTTP_201_CREATED)
def schedule_match(
    req: ScheduleMatchRequest,
    user: CurrentUser,  # noqa: ARG001  (authn gate; user surface for future per-user quotas)
    session: Annotated[Session, Depends(get_session)],
    run_now: bool = True,
) -> MatchOut:
    if req.white_bot_id == req.black_bot_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "bots must differ")
    for bid in (req.white_bot_id, req.black_bot_id):
        if session.get(Bot, bid) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"bot {bid} not found")
    match = Match(
        white_bot_id=req.white_bot_id,
        black_bot_id=req.black_bot_id,
        status=MatchStatus.pending,
    )
    session.add(match)
    session.commit()
    session.refresh(match)
    if run_now:
        execute_pending_match(session, match)
    return _match_out(match)


@router.get("/{match_id}", response_model=MatchOut)
def get_match(
    match_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> MatchOut:
    m = session.get(Match, match_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "match not found")
    return _match_out(m)


@router.get("", response_model=list[MatchOut])
def list_matches(
    session: Annotated[Session, Depends(get_session)],
    limit: int = 50,
    offset: int = 0,
) -> list[MatchOut]:
    rows = session.exec(
        select(Match).order_by(Match.created_at.desc()).offset(offset).limit(limit)  # type: ignore[attr-defined]
    ).all()
    return [_match_out(m) for m in rows]
