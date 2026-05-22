"""Tests for the bot framework + Random + Heuristic bots."""

from __future__ import annotations

import time

import chess
import pytest

from chesslab.bots import BOT_REGISTRY, Bot, get_bot, list_bots
from chesslab.engine import Game


def test_registry_has_builtins() -> None:
    assert "random" in BOT_REGISTRY
    assert "heuristic" in BOT_REGISTRY
    assert "random" in list_bots()


def test_get_bot_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_bot("does-not-exist")


def test_random_bot_returns_legal_move() -> None:
    bot = get_bot("random", seed=42)
    game = Game()
    move = bot.choose_move(game)
    assert move in game.board.legal_moves


def test_random_bot_seeded_deterministic() -> None:
    a = get_bot("random", seed=7).choose_move(Game())
    b = get_bot("random", seed=7).choose_move(Game())
    assert a == b


def test_heuristic_bot_returns_legal_move() -> None:
    bot = get_bot("heuristic", max_depth=2, time_limit_s=1.0)
    game = Game()
    move = bot.choose_move(game, time_limit_s=1.0)
    assert move in game.board.legal_moves


def test_heuristic_bot_finds_mate_in_one() -> None:
    # White to move, mate in 1 with Qxf7#.
    game = Game.from_fen("r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4")
    # Actually that FEN is after mate. Build mate-in-1 instead:
    game = Game()
    for san in ["e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6"]:
        game.push_san(san)
    bot = get_bot("heuristic", max_depth=3, time_limit_s=3.0)
    move = bot.choose_move(game, time_limit_s=3.0)
    assert game.board.san(move) == "Qxf7#"


def test_heuristic_bot_finishes_in_time_budget() -> None:
    bot = get_bot("heuristic", max_depth=3, time_limit_s=2.0)
    game = Game()
    t0 = time.monotonic()
    bot.choose_move(game, time_limit_s=2.0)
    elapsed = time.monotonic() - t0
    # 2s budget, allow generous overhead for slow CI.
    assert elapsed < 5.0


def test_heuristic_picks_winning_capture() -> None:
    # Hanging queen: black queen on d4 can be taken for free by white knight on c2.
    game = Game.from_fen("4k3/8/8/8/3q4/8/2N5/4K3 w - - 0 1")
    bot = get_bot("heuristic", max_depth=3, time_limit_s=2.0)
    move = bot.choose_move(game, time_limit_s=2.0)
    assert move == chess.Move.from_uci("c2d4")


def test_bot_is_abstract() -> None:
    class Incomplete(Bot):
        pass

    with pytest.raises(TypeError):
        Incomplete()
