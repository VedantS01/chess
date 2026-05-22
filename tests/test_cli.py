"""End-to-end tests of the offline CLI (play + match + list-bots)."""

from __future__ import annotations

import io
from pathlib import Path

import chess.pgn
import pytest

from chesslab.cli import main


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["version"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "chesslab" in out


def test_list_bots(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["list-bots"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "random" in out
    assert "heuristic" in out


def test_match_random_vs_random_writes_valid_pgn(tmp_path: Path) -> None:
    pgn_path = tmp_path / "match.pgn"
    rc = main([
        "match",
        "--white", "random:seed=1",
        "--black", "random:seed=2",
        "--games", "2",
        "--time", "0.1",
        "--pgn", str(pgn_path),
    ])
    assert rc == 0
    content = pgn_path.read_text()
    assert content.strip(), "PGN file should be non-empty"
    # Each game ends with a Result tag.
    parsed = list(_iter_pgn_games(content))
    assert len(parsed) == 2
    for g in parsed:
        assert g.headers["White"] == "random"
        assert g.headers["Black"] == "random"
        # Game should be terminal: result in {1-0, 0-1, 1/2-1/2}.
        assert g.headers["Result"] in {"1-0", "0-1", "1/2-1/2"}


def test_match_heuristic_vs_random(tmp_path: Path) -> None:
    pgn_path = tmp_path / "match.pgn"
    rc = main([
        "match",
        "--white", "heuristic:max_depth=2,time_limit_s=0.3",
        "--black", "random:seed=1",
        "--games", "1",
        "--time", "0.3",
        "--pgn", str(pgn_path),
    ])
    assert rc == 0
    text = pgn_path.read_text()
    games = list(_iter_pgn_games(text))
    assert len(games) == 1
    assert games[0].headers["White"] == "heuristic"


def _iter_pgn_games(text: str):
    fp = io.StringIO(text)
    while True:
        g = chess.pgn.read_game(fp)
        if g is None:
            return
        yield g
