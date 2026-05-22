"""Stockfish bot: wraps the Stockfish UCI engine via python-chess."""

from __future__ import annotations

import contextlib
import os
import shutil

import chess
import chess.engine

from chesslab.bots.base import Bot, register
from chesslab.engine import Game

DEFAULT_BINARIES = ["stockfish", "/usr/games/stockfish", "/usr/local/bin/stockfish"]


def find_stockfish_binary() -> str | None:
    """Return path to a stockfish binary or None if unavailable."""
    override = os.environ.get("STOCKFISH_PATH")
    if override and os.path.exists(override):
        return override
    for cand in DEFAULT_BINARIES:
        path = shutil.which(cand) if "/" not in cand else (cand if os.path.exists(cand) else None)
        if path:
            return path
    return None


@register("stockfish")
class StockfishBot(Bot):
    name = "stockfish"

    def __init__(
        self,
        binary: str | None = None,
        depth: int | None = 10,
        time_limit_s: float | None = None,
        skill_level: int | None = None,
        threads: int = 1,
        hash_mb: int = 16,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.binary = binary or find_stockfish_binary()
        if self.binary is None:
            raise RuntimeError(
                "Stockfish binary not found. Install stockfish or set STOCKFISH_PATH."
            )
        self.depth = depth
        self.default_time = time_limit_s
        self.skill_level = skill_level
        self.threads = threads
        self.hash_mb = hash_mb
        self._engine: chess.engine.SimpleEngine | None = None

    def _ensure_engine(self) -> chess.engine.SimpleEngine:
        if self._engine is None:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.binary)
            self._engine.configure({"Threads": self.threads, "Hash": self.hash_mb})
            if self.skill_level is not None:
                self._engine.configure({"Skill Level": int(self.skill_level)})
        return self._engine

    def choose_move(self, game: Game, time_limit_s: float | None = None) -> chess.Move:
        engine = self._ensure_engine()
        budget = time_limit_s if time_limit_s is not None else self.default_time
        if budget is not None:
            limit = chess.engine.Limit(time=budget)
        elif self.depth is not None:
            limit = chess.engine.Limit(depth=self.depth)
        else:
            limit = chess.engine.Limit(time=0.1)
        result = engine.play(game.board, limit)
        if result.move is None:
            raise RuntimeError("stockfish returned no move")
        return result.move

    def reset(self) -> None:
        # Keep the engine process alive across games; UCI handles state via fen.
        pass

    def close(self) -> None:
        if self._engine is not None:
            with contextlib.suppress(chess.engine.EngineError):
                self._engine.quit()
            self._engine = None
