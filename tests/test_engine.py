"""Tests for chesslab.engine.Game."""

from __future__ import annotations

import chess
import pytest

from chesslab.engine import Game


def test_initial_position_has_20_legal_moves() -> None:
    game = Game()
    assert len(list(game.legal_moves())) == 20


def test_starting_fen_round_trip() -> None:
    game = Game()
    assert game.fen() == chess.STARTING_FEN
    g2 = Game.from_fen(game.fen())
    assert g2.fen() == game.fen()


def test_push_uci_advances_state() -> None:
    game = Game()
    move = game.push_uci("e2e4")
    assert move == chess.Move.from_uci("e2e4")
    assert game.ply == 1
    assert game.turn == chess.BLACK


def test_illegal_move_raises() -> None:
    game = Game()
    with pytest.raises(ValueError):
        game.push_uci("e2e5")


def test_scholars_mate_is_checkmate() -> None:
    game = Game()
    for san in ["e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6", "Qxf7#"]:
        game.push_san(san)
    assert game.is_terminal()
    assert game.result() == "1-0"


def test_copy_is_independent() -> None:
    g1 = Game()
    g1.push_uci("e2e4")
    g2 = g1.copy()
    g2.push_uci("e7e5")
    assert g1.fen() != g2.fen()
    assert g1.ply == 1
    assert g2.ply == 2


def test_pgn_includes_moves_and_result() -> None:
    game = Game()
    for san in ["e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6", "Qxf7#"]:
        game.push_san(san)
    pgn = game.pgn()
    assert "1. e4 e5" in pgn
    assert "Qxf7#" in pgn
    assert '[Result "1-0"]' in pgn


def test_from_fen_custom_position() -> None:
    fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
    game = Game.from_fen(fen)
    assert game.turn == chess.WHITE
    assert game.fen() == fen


def test_pop_undoes_move() -> None:
    game = Game()
    game.push_uci("e2e4")
    game.pop()
    assert game.fen() == chess.STARTING_FEN
    assert game.ply == 0
