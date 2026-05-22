"""Tests for the Stockfish bot. Skipped when no stockfish binary is on PATH."""

from __future__ import annotations

import pytest

from chesslab.bots import find_stockfish_binary, get_bot
from chesslab.engine import Game

pytestmark = pytest.mark.skipif(
    find_stockfish_binary() is None,
    reason="stockfish binary not available",
)


def test_stockfish_returns_legal_move() -> None:
    with get_bot("stockfish", depth=4) as bot:
        game = Game()
        move = bot.choose_move(game, time_limit_s=0.5)
        assert move in game.board.legal_moves


def test_stockfish_time_budget() -> None:
    with get_bot("stockfish", time_limit_s=0.2) as bot:
        game = Game()
        m1 = bot.choose_move(game, time_limit_s=0.2)
        # Push and ask again, ensure engine is reused without crash.
        game.push(m1)
        m2 = bot.choose_move(game, time_limit_s=0.2)
        assert m2 in game.board.legal_moves


def test_stockfish_finds_mate_in_one() -> None:
    game = Game()
    for san in ["e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6"]:
        game.push_san(san)
    with get_bot("stockfish", depth=10) as bot:
        move = bot.choose_move(game, time_limit_s=1.0)
        assert game.board.san(move) == "Qxf7#"
