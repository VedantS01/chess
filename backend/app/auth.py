"""GitHub OAuth via NextAuth JWT verification + FastAPI deps.

NextAuth signs a JWT with `NEXTAUTH_SECRET` (HS256 by default). The frontend
includes it as `Authorization: Bearer <jwt>`. We trust NextAuth as the
identity provider and lazy-create users on first sight.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session, select

from backend.app.config import settings
from backend.app.db import get_session
from backend.app.models import User


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.nextauth_secret,
            algorithms=[settings.jwt_algorithm],
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"invalid token: {e}") from e


def encode_token(payload: dict[str, Any]) -> str:
    """Test helper / dev-mode token issuance."""
    payload = dict(payload)
    payload.setdefault("iat", int(dt.datetime.now(dt.UTC).timestamp()))
    payload.setdefault("exp", int(dt.datetime.now(dt.UTC).timestamp()) + 3600)
    return jwt.encode(payload, settings.nextauth_secret, algorithm=settings.jwt_algorithm)


def get_bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    return authorization.split(" ", 1)[1].strip()


def get_current_user(
    token: Annotated[str, Depends(get_bearer_token)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    payload = decode_token(token)
    # NextAuth GitHub provider exposes the GitHub numeric id in the `sub` claim
    # when configured; we also accept `github_id` as a backstop.
    github_id_raw: int | str | None = payload.get("github_id") or payload.get("sub")
    if github_id_raw is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token missing github id")
    try:
        github_id = int(github_id_raw)
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad github id in token") from e
    login = payload.get("login") or payload.get("name") or f"user-{github_id}"

    user = session.exec(select(User).where(User.github_id == github_id)).first()
    if user is None:
        user = User(
            github_id=github_id,
            login=str(login),
            name=payload.get("name"),
            avatar_url=payload.get("picture"),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
