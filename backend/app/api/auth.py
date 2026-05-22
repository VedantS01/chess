"""Auth-related routes: /me, dev token issuance."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.app.auth import CurrentUser, encode_token

router = APIRouter(prefix="/auth", tags=["auth"])


class MeResponse(BaseModel):
    id: int
    github_id: int
    login: str
    name: str | None = None
    avatar_url: str | None = None
    elo: float


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUser) -> MeResponse:
    assert user.id is not None
    return MeResponse(
        id=user.id,
        github_id=user.github_id,
        login=user.login,
        name=user.name,
        avatar_url=user.avatar_url,
        elo=user.elo,
    )


class DevTokenRequest(BaseModel):
    github_id: int
    login: str
    name: str | None = None


@router.post("/dev-token", include_in_schema=False)
def dev_token(req: DevTokenRequest) -> dict[str, str]:
    """Issue a NextAuth-shaped JWT for local dev/tests.

    Only enabled when CHESSLAB_DEV_AUTH=1. Production deployments leave this off.
    """
    if os.environ.get("CHESSLAB_DEV_AUTH") != "1":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    token = encode_token({"github_id": req.github_id, "login": req.login, "name": req.name})
    return {"token": token}
