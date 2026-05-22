"""Tests for the tournament runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chesslab.cli import main
from chesslab.tournament.runner import run_tournament


def test_run_tournament_random_vs_random(tmp_path: Path) -> None:
    lb = tmp_path / "leaderboard.json"
    report = run_tournament(
        bot_specs=["random:seed=1", "random:seed=2"],
        rounds=1,
        time_limit_s=0.05,
        leaderboard_path=lb,
        persist=True,
    )
    # Two bots in a 1-round round-robin: each pair plays twice (both colors).
    assert len(report.games) == 2
    # Leaderboard JSON written and parseable.
    assert lb.exists()
    data = json.loads(lb.read_text())
    assert len(data) == 2  # two distinct display names
    # All bots have games recorded.
    for entry in report.ratings.values():
        assert entry.games > 0


def test_run_tournament_no_persist(tmp_path: Path) -> None:
    lb = tmp_path / "leaderboard.json"
    run_tournament(
        bot_specs=["random:seed=1", "random:seed=2"],
        rounds=1,
        time_limit_s=0.05,
        leaderboard_path=lb,
        persist=False,
    )
    assert not lb.exists()


def test_cli_tournament_subcommand(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    lb = tmp_path / "lb.json"
    rc = main([
        "tournament",
        "--bots", "random:seed=1,random:seed=2",
        "--rounds", "1",
        "--time", "0.05",
        "--leaderboard", str(lb),
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "leaderboard" in out
    assert lb.exists()


def test_tournament_persists_across_runs(tmp_path: Path) -> None:
    lb = tmp_path / "lb.json"
    run_tournament(
        bot_specs=["random:seed=1", "random:seed=2"],
        rounds=1,
        time_limit_s=0.05,
        leaderboard_path=lb,
        persist=True,
    )
    first = json.loads(lb.read_text())
    games_before = sum(e["games"] for e in first.values())
    run_tournament(
        bot_specs=["random:seed=1", "random:seed=2"],
        rounds=1,
        time_limit_s=0.05,
        leaderboard_path=lb,
        persist=True,
    )
    second = json.loads(lb.read_text())
    games_after = sum(e["games"] for e in second.values())
    assert games_after > games_before
