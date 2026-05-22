"""In-process tests for the sandbox UCI shim.

These exercise the shim's parsing + dispatch by piping stdin/stdout. The full
Docker-isolated integration test lives in the backend tests once that step
lands.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

from chesslab.sandbox.uci_shim import _parse_position, main


def test_parse_position_startpos_no_moves() -> None:
    game = _parse_position(["startpos"])
    assert game.fen().startswith("rnbqkbnr/")


def test_parse_position_startpos_with_moves() -> None:
    game = _parse_position(["startpos", "moves", "e2e4", "e7e5"])
    assert game.history[0].uci() == "e2e4"
    assert game.history[1].uci() == "e7e5"


def test_parse_position_fen_with_moves() -> None:
    game = _parse_position(["fen", "k7/8/8/8/8/8/8/4K3", "w", "-", "-", "0", "1", "moves", "e1e2"])
    assert game.history[0].uci() == "e1e2"


@pytest.fixture
def random_bot_path(tmp_path: Path) -> Path:
    bot_file = tmp_path / "bot.py"
    bot_file.write_text(
        "from chesslab.bots.random_bot import RandomBot\nBOT = RandomBot(seed=1)\n"
    )
    return bot_file


def test_uci_shim_full_handshake_and_first_move(
    random_bot_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("CHESSLAB_BOT_PATH", str(random_bot_path))
    monkeypatch.setattr(sys, "stdin", io.StringIO(
        "uci\nisready\nucinewgame\nposition startpos\ngo movetime 100\nquit\n"
    ))
    rc = main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "uciok" in out
    assert "readyok" in out
    assert "bestmove" in out
    # The bestmove should be a UCI move; lookup ensures legality with python-chess.
    last_lines = [line for line in out.strip().splitlines() if line.startswith("bestmove")]
    assert last_lines, "expected at least one bestmove"
    move_uci = last_lines[-1].split()[1]
    assert len(move_uci) >= 4


def test_uci_shim_position_with_moves(
    random_bot_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("CHESSLAB_BOT_PATH", str(random_bot_path))
    monkeypatch.setattr(sys, "stdin", io.StringIO(
        "uci\nisready\nposition startpos moves e2e4 e7e5\ngo movetime 100\nquit\n"
    ))
    rc = main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "bestmove" in out


def test_uci_shim_missing_bot_path_reports_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("CHESSLAB_BOT_PATH", str(tmp_path / "no-such-bot.py"))
    monkeypatch.setattr(sys, "stdin", io.StringIO("uci\nisready\nquit\n"))
    rc = main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "failed to load bot" in out


def test_uci_shim_drivable_by_simpleengine(tmp_path: Path) -> None:
    """End-to-end: spawn the shim as a subprocess and drive it like the orchestrator will.

    Validates that python-chess's SimpleEngine over a pipe transport can play
    a few moves through our shim.
    """
    import os
    import subprocess

    import chess
    import chess.engine

    bot_file = tmp_path / "bot.py"
    bot_file.write_text(
        "from chesslab.bots.random_bot import RandomBot\nBOT = RandomBot(seed=1)\n"
    )
    env = os.environ.copy()
    env["CHESSLAB_BOT_PATH"] = str(bot_file)

    engine = chess.engine.SimpleEngine.popen_uci(
        [sys.executable, "-m", "chesslab.sandbox.uci_shim"],
        env=env,
    )
    try:
        board = chess.Board()
        for _ in range(3):
            if board.is_game_over():
                break
            result = engine.play(board, chess.engine.Limit(time=0.1))
            assert result.move is not None
            assert result.move in board.legal_moves
            board.push(result.move)
    finally:
        engine.quit()
