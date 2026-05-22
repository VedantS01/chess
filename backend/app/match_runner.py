"""Run a bot-vs-bot match between two sandboxed runner containers.

The orchestrator drives the two sandboxes as UCI engines via
`python-chess`'s `SimpleEngine`. Each side has a per-move time limit and a
total wall-clock limit; illegal moves or timeouts forfeit.

For deployment, a Docker daemon socket must be available to the backend
process (mounted at `/var/run/docker.sock`). For tests + local dev without
Docker, `InProcessSandbox` runs the UCI shim as a plain Python subprocess
(no isolation) so the orchestrator and Elo flow can be exercised end to end.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import chess
import chess.engine
import chess.pgn
from sqlmodel import Session

from backend.app.config import settings
from backend.app.elo_service import apply_match_result
from backend.app.models import Bot, Match, MatchResult, MatchStatus

log = logging.getLogger(__name__)


class SandboxProcess(Protocol):
    def start(self) -> chess.engine.SimpleEngine: ...
    def stop(self) -> None: ...


@dataclass
class InProcessSandbox:
    bot_dir: Path
    _engine: chess.engine.SimpleEngine | None = None

    def start(self) -> chess.engine.SimpleEngine:
        env = os.environ.copy()
        env["CHESSLAB_BOT_PATH"] = str(self.bot_dir / "bot.py")
        self._engine = chess.engine.SimpleEngine.popen_uci(
            [sys.executable, "-m", "chesslab.sandbox.uci_shim"],
            env=env,
        )
        return self._engine

    def stop(self) -> None:
        if self._engine is not None:
            import contextlib

            with contextlib.suppress(chess.engine.EngineError, OSError):
                self._engine.quit()
            self._engine = None


@dataclass
class DockerSandbox:
    bot_dir: Path
    image: str = ""
    cpus: float = 1.0
    memory_mb: int = 512
    pids_limit: int = 64
    name_prefix: str = "chesslab-runner-"
    _engine: chess.engine.SimpleEngine | None = None
    _container_name: str | None = None

    def start(self) -> chess.engine.SimpleEngine:
        if not shutil.which("docker"):
            raise RuntimeError("docker binary not on PATH")
        import uuid

        self._container_name = f"{self.name_prefix}{uuid.uuid4().hex[:8]}"
        image = self.image or settings.runner_image
        cmd = [
            "docker", "run", "--rm", "-i",
            "--name", self._container_name,
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            f"--pids-limit={self.pids_limit}",
            f"--cpus={self.cpus}",
            f"--memory={self.memory_mb}m",
            "-v", f"{self.bot_dir}:/bot:ro",
            image,
        ]
        self._engine = chess.engine.SimpleEngine.popen_uci(cmd)
        return self._engine

    def stop(self) -> None:
        if self._engine is not None:
            import contextlib

            with contextlib.suppress(chess.engine.EngineError, OSError):
                self._engine.quit()
            self._engine = None
        if self._container_name is not None:
            subprocess.run(
                ["docker", "rm", "-f", self._container_name],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._container_name = None


SandboxFactory = type[SandboxProcess]


@dataclass
class MatchOutcome:
    result: MatchResult
    pgn: str
    termination: str | None = None


def _bot_dir(bot: Bot) -> Path:
    return Path(bot.artifact_path)


def run_bot_vs_bot(
    white_bot: Bot,
    black_bot: Bot,
    movetime_ms: int = 1000,
    max_plies: int | None = None,
    sandbox_cls: type[SandboxProcess] | None = None,
) -> MatchOutcome:
    """Drive a single bot-vs-bot match. Returns the outcome.

    `sandbox_cls` defaults to `InProcessSandbox` if docker is missing;
    `DockerSandbox` is used otherwise (production path).
    """
    if sandbox_cls is None:
        sandbox_cls = DockerSandbox if shutil.which("docker") else InProcessSandbox

    if max_plies is None:
        max_plies = settings.runner_max_plies

    white = sandbox_cls(bot_dir=_bot_dir(white_bot))  # type: ignore[call-arg]
    black = sandbox_cls(bot_dir=_bot_dir(black_bot))  # type: ignore[call-arg]

    white_engine: chess.engine.SimpleEngine | None = None
    black_engine: chess.engine.SimpleEngine | None = None
    board = chess.Board()
    pgn_game = chess.pgn.Game()
    pgn_game.headers["White"] = f"{white_bot.name} v{white_bot.version}"
    pgn_game.headers["Black"] = f"{black_bot.name} v{black_bot.version}"
    pgn_game.headers["Date"] = dt.datetime.now(dt.UTC).strftime("%Y.%m.%d")
    node = pgn_game

    termination: str | None = None
    try:
        white_engine = white.start()
        black_engine = black.start()
        limit = chess.engine.Limit(time=movetime_ms / 1000.0)
        plies = 0
        while not board.is_game_over(claim_draw=True) and plies < max_plies:
            engine_to_move = white_engine if board.turn == chess.WHITE else black_engine
            side = "white" if board.turn == chess.WHITE else "black"
            try:
                play = engine_to_move.play(board, limit)
            except chess.engine.EngineError as e:
                termination = f"{side} engine error: {e}"
                pgn_game.headers["Result"] = "0-1" if side == "white" else "1-0"
                break
            move = play.move
            if move is None or move not in board.legal_moves:
                termination = f"{side} returned illegal move {move}"
                pgn_game.headers["Result"] = "0-1" if side == "white" else "1-0"
                break
            board.push(move)
            node = node.add_variation(move)
            plies += 1
        else:
            if plies >= max_plies and not board.is_game_over():
                termination = f"truncated at {max_plies} plies"
                pgn_game.headers["Result"] = "1/2-1/2"
            else:
                pgn_game.headers["Result"] = board.result(claim_draw=True)
    finally:
        white.stop()
        black.stop()

    result_str = pgn_game.headers["Result"]
    result_enum = MatchResult(result_str) if result_str in {"1-0", "0-1", "1/2-1/2"} else MatchResult.unfinished
    return MatchOutcome(result=result_enum, pgn=str(pgn_game), termination=termination)


def execute_pending_match(session: Session, match: Match) -> Match:
    """Run a pending bot-vs-bot match end to end and persist outcome + ratings."""
    if match.white_bot_id is None or match.black_bot_id is None:
        match.status = MatchStatus.failed
        match.termination = "missing bot ids"
        session.add(match)
        session.commit()
        return match

    white = session.get(Bot, match.white_bot_id)
    black = session.get(Bot, match.black_bot_id)
    if white is None or black is None:
        match.status = MatchStatus.failed
        match.termination = "bot lookup failed"
        session.add(match)
        session.commit()
        return match

    match.status = MatchStatus.running
    session.add(match)
    session.commit()

    try:
        outcome = run_bot_vs_bot(
            white_bot=white,
            black_bot=black,
            movetime_ms=settings.runner_default_movetime_ms,
            max_plies=settings.runner_max_plies,
        )
    except Exception as e:  # noqa: BLE001
        log.exception("match execution failed")
        match.status = MatchStatus.failed
        match.termination = f"orchestrator error: {e}"
        session.add(match)
        session.commit()
        return match

    match.status = MatchStatus.finished
    match.result = outcome.result
    match.pgn = outcome.pgn
    match.termination = outcome.termination
    match.finished_at = dt.datetime.now(dt.UTC)
    session.add(match)
    session.commit()
    session.refresh(match)

    apply_match_result(session, match)
    session.refresh(match)
    return match
