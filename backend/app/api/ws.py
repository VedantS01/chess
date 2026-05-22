"""WebSocket live-play rooms.

Two endpoints:

- `/api/ws/play/{room_id}`: client connects with `?token=<jwt>&color=white|black|spectator`.
  Messages on the wire:
    - `{"type": "join", "color": "white", "user": {...}}` from server.
    - `{"type": "state", "fen": "...", "moves": [...], "turn": "white", "status": "ongoing"}`.
    - `{"type": "move", "uci": "e2e4"}` from a player.
    - `{"type": "error", "detail": "..."}` from server on illegal moves.
    - `{"type": "end", "result": "1-0", "termination": "checkmate"}` on game end.

Rooms are in-memory for v0.1. Replace with Redis pub/sub before horizontal
scaling.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Annotated

import chess
import chess.pgn
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlmodel import Session

from backend.app.auth import decode_token
from backend.app.db import get_session
from backend.app.elo_service import apply_match_result
from backend.app.models import Match, MatchResult, MatchStatus, User

log = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


@dataclass
class PlayerSlot:
    websocket: WebSocket
    user: User | None
    color: chess.Color | None  # None for spectators


@dataclass
class Room:
    room_id: str
    board: chess.Board = field(default_factory=chess.Board)
    players: dict[chess.Color, PlayerSlot] = field(default_factory=dict)
    spectators: list[PlayerSlot] = field(default_factory=list)
    pgn: chess.pgn.Game = field(default_factory=chess.pgn.Game)
    pgn_node: chess.pgn.GameNode | None = None
    match_id: int | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def is_full(self) -> bool:
        return chess.WHITE in self.players and chess.BLACK in self.players


_rooms: dict[str, Room] = defaultdict(lambda: Room(room_id=""))
_rooms_lock = asyncio.Lock()


async def _get_or_create_room(room_id: str) -> Room:
    async with _rooms_lock:
        if room_id not in _rooms or _rooms[room_id].room_id == "":
            _rooms[room_id] = Room(room_id=room_id)
            _rooms[room_id].pgn_node = _rooms[room_id].pgn
        return _rooms[room_id]


def _color_for(req: str | None, room: Room) -> chess.Color | None:
    if req == "spectator" or req is None:
        return None
    if req == "white":
        return chess.WHITE
    if req == "black":
        return chess.BLACK
    return None


async def _broadcast(room: Room, message: dict[str, object]) -> None:
    targets: list[PlayerSlot] = list(room.players.values()) + room.spectators
    for slot in targets:
        try:
            await slot.websocket.send_json(message)
        except Exception as e:  # noqa: BLE001
            log.warning("ws send failed: %s", e)


def _state_message(room: Room) -> dict[str, object]:
    return {
        "type": "state",
        "fen": room.board.fen(),
        "moves": [m.uci() for m in room.board.move_stack],
        "turn": "white" if room.board.turn == chess.WHITE else "black",
        "status": "ended" if room.board.is_game_over(claim_draw=True) else "ongoing",
        "result": room.board.result(claim_draw=True) if room.board.is_game_over(claim_draw=True) else None,
    }


def _user_from_token(token: str | None, session: Session) -> User | None:
    if not token:
        return None
    try:
        payload = decode_token(token)
    except Exception:  # noqa: BLE001
        return None
    github_id_raw = payload.get("github_id") or payload.get("sub")
    if github_id_raw is None:
        return None
    try:
        gid = int(github_id_raw)
    except (TypeError, ValueError):
        return None
    from sqlmodel import select

    user = session.exec(select(User).where(User.github_id == gid)).first()
    if user is None:
        user = User(
            github_id=gid,
            login=str(payload.get("login") or f"user-{gid}"),
            name=payload.get("name"),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


@router.websocket("/play/{room_id}")
async def play_room(
    websocket: WebSocket,
    room_id: str,
    token: Annotated[str | None, Query()] = None,
    color: Annotated[str | None, Query()] = None,
    session: Annotated[Session, Depends(get_session)] = None,  # type: ignore[assignment]
) -> None:
    await websocket.accept()
    user = _user_from_token(token, session)
    room = await _get_or_create_room(room_id)

    requested = _color_for(color, room)
    slot = PlayerSlot(websocket=websocket, user=user, color=requested)

    async with room.lock:
        if requested is None:
            room.spectators.append(slot)
        elif requested in room.players:
            await websocket.send_json({"type": "error", "detail": f"{color} already taken"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        else:
            room.players[requested] = slot

    await websocket.send_json({
        "type": "join",
        "color": color or "spectator",
        "user": ({"login": user.login, "elo": user.elo} if user else None),
        "room": room_id,
    })
    await _broadcast(room, _state_message(room))

    try:
        while True:
            msg = await websocket.receive_json()
            mtype = msg.get("type")
            if mtype == "move":
                async with room.lock:
                    if requested is None:
                        await websocket.send_json({"type": "error", "detail": "spectators cannot move"})
                        continue
                    if room.board.turn != requested:
                        await websocket.send_json({"type": "error", "detail": "not your turn"})
                        continue
                    uci = msg.get("uci") or ""
                    try:
                        move = chess.Move.from_uci(uci)
                    except chess.InvalidMoveError:
                        await websocket.send_json({"type": "error", "detail": f"bad uci: {uci}"})
                        continue
                    if move not in room.board.legal_moves:
                        await websocket.send_json({"type": "error", "detail": "illegal move"})
                        continue
                    room.board.push(move)
                    if room.pgn_node is None:
                        room.pgn_node = room.pgn
                    room.pgn_node = room.pgn_node.add_variation(move)
                await _broadcast(room, _state_message(room))
                if room.board.is_game_over(claim_draw=True):
                    result = room.board.result(claim_draw=True)
                    await _broadcast(room, {
                        "type": "end",
                        "result": result,
                        "pgn": str(room.pgn),
                    })
                    # Persist h2h match + Elo if both seats are real users.
                    if (
                        chess.WHITE in room.players
                        and chess.BLACK in room.players
                        and room.players[chess.WHITE].user is not None
                        and room.players[chess.BLACK].user is not None
                    ):
                        room.pgn.headers["Result"] = result
                        match = Match(
                            white_user_id=room.players[chess.WHITE].user.id,  # type: ignore[union-attr]
                            black_user_id=room.players[chess.BLACK].user.id,  # type: ignore[union-attr]
                            status=MatchStatus.finished,
                            result=MatchResult(result),
                            pgn=str(room.pgn),
                            termination="terminal",
                        )
                        session.add(match)
                        session.commit()
                        session.refresh(match)
                        apply_match_result(session, match)
            elif mtype == "resign":
                async with room.lock:
                    if requested is None:
                        continue
                    result = "0-1" if requested == chess.WHITE else "1-0"
                await _broadcast(room, {"type": "end", "result": result, "termination": "resignation"})
                break
            elif mtype == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                await websocket.send_json({"type": "error", "detail": f"unknown type: {mtype}"})
    except WebSocketDisconnect:
        pass
    finally:
        async with room.lock:
            if requested is None:
                if slot in room.spectators:
                    room.spectators.remove(slot)
            elif room.players.get(requested) is slot:
                del room.players[requested]
