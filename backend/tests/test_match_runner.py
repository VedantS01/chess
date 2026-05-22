"""Integration tests for the match orchestrator.

Uses `InProcessSandbox` (UCI shim as a plain Python subprocess) so the tests
don't require docker. The DockerSandbox code path is exercised by CI when
the runner image is built; tests there are gated on docker availability.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import Session, select

from backend.app import db as db_module
from backend.app.match_runner import InProcessSandbox, execute_pending_match, run_bot_vs_bot
from backend.app.models import Bot, BotStatus, Match, MatchResult, MatchStatus, RatingHistory, User


def _make_bot(session: Session, user: User, name: str, bot_dir: Path) -> Bot:
    bot_dir.mkdir(parents=True, exist_ok=True)
    (bot_dir / "bot.py").write_text(
        "from chesslab.bots.random_bot import RandomBot\n"
        f"BOT = RandomBot(seed={len(name)})\n"
    )
    bot = Bot(
        owner_id=user.id,  # type: ignore[arg-type]
        name=name,
        version=1,
        artifact_path=str(bot_dir),
        status=BotStatus.ready,
    )
    session.add(bot)
    session.commit()
    session.refresh(bot)
    return bot


def _seed_user(session: Session, login: str, github_id: int) -> User:
    user = User(github_id=github_id, login=login)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.mark.usefixtures("tmp_db")
def test_run_bot_vs_bot_inprocess(tmp_path: Path) -> None:
    with Session(db_module.engine) as session:
        u = _seed_user(session, "tester", 1)
        white = _make_bot(session, u, "white-bot", tmp_path / "w")
        black = _make_bot(session, u, "black-bot", tmp_path / "b")
        outcome = run_bot_vs_bot(
            white,
            black,
            movetime_ms=50,
            max_plies=40,
            sandbox_cls=InProcessSandbox,
        )
        assert outcome.result in (MatchResult.white, MatchResult.black, MatchResult.draw)
        assert outcome.pgn.startswith("[Event")
        assert "Result" in outcome.pgn


@pytest.mark.usefixtures("tmp_db")
def test_execute_pending_match_updates_state_and_elo(tmp_path: Path) -> None:
    with Session(db_module.engine) as session:
        u = _seed_user(session, "rated", 11)
        white = _make_bot(session, u, "w", tmp_path / "w")
        black = _make_bot(session, u, "b", tmp_path / "b")
        match = Match(white_bot_id=white.id, black_bot_id=black.id, status=MatchStatus.pending)
        session.add(match)
        session.commit()
        session.refresh(match)
        # Force the in-process sandbox via monkey-patching.
        import backend.app.match_runner as mr

        original = mr.run_bot_vs_bot
        mr.run_bot_vs_bot = lambda white_bot, black_bot, movetime_ms=1000, max_plies=None, sandbox_cls=None: original(  # noqa: E501
            white_bot, black_bot, movetime_ms=50, max_plies=40, sandbox_cls=InProcessSandbox
        )
        try:
            executed = execute_pending_match(session, match)
        finally:
            mr.run_bot_vs_bot = original

        assert executed.status == MatchStatus.finished
        # Result is finalized.
        assert executed.result in {MatchResult.white, MatchResult.black, MatchResult.draw}
        if executed.result != MatchResult.draw:
            # Elo updates persisted for both bots.
            session.refresh(white)
            session.refresh(black)
            assert (white.elo != 1500.0) or (black.elo != 1500.0)
        # RatingHistory rows exist.
        rows = session.exec(select(RatingHistory).where(RatingHistory.match_id == match.id)).all()
        assert len(rows) >= 2
