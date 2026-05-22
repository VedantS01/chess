"""Round-robin tournament runner with Elo persistence.

Each round pairs every bot with every other bot (both colors). After every
game the local leaderboard (a JSON file at `~/.chesslab/leaderboard.json`
unless overridden) is updated atomically.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import chess

from chesslab.bots import Bot, get_bot
from chesslab.engine import Game
from chesslab.tournament.elo import (
    DEFAULT_K,
    DEFAULT_RATING,
    RatingEntry,
    result_to_scores,
    update_ratings,
)


def default_leaderboard_path() -> Path:
    return Path(os.environ.get("CHESSLAB_HOME", str(Path.home() / ".chesslab"))) / "leaderboard.json"


@dataclass
class TournamentGame:
    white: str
    black: str
    result: str
    pgn: str
    round: int
    timestamp: float


@dataclass
class TournamentReport:
    games: list[TournamentGame] = field(default_factory=list)
    ratings: dict[str, RatingEntry] = field(default_factory=dict)


def _load_leaderboard(path: Path) -> dict[str, RatingEntry]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {name: RatingEntry(**entry) for name, entry in raw.items()}


def _save_leaderboard(path: Path, ratings: dict[str, RatingEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = {name: asdict(entry) for name, entry in ratings.items()}
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
    tmp.replace(path)


def _ensure_entry(ratings: dict[str, RatingEntry], name: str) -> RatingEntry:
    if name not in ratings:
        ratings[name] = RatingEntry(name=name, rating=DEFAULT_RATING)
    return ratings[name]


def _play_one_game(
    white_bot: Bot,
    black_bot: Bot,
    white_name: str,
    black_name: str,
    round_idx: int,
    time_limit_s: float,
) -> TournamentGame:
    white_bot.reset()
    black_bot.reset()
    game = Game()
    game.headers["Event"] = "chesslab tournament"
    game.headers["Round"] = str(round_idx + 1)
    game.headers["White"] = white_name
    game.headers["Black"] = black_name
    while not game.is_terminal():
        bot = white_bot if game.turn == chess.WHITE else black_bot
        move = bot.choose_move(game, time_limit_s=time_limit_s)
        if move not in game.board.legal_moves:
            # forfeit
            loser_is_white = game.turn == chess.WHITE
            game.headers["Result"] = "0-1" if loser_is_white else "1-0"
            game.headers["Termination"] = f"illegal move by {white_name if loser_is_white else black_name}"
            break
        game.push(move)
    result = game.headers.get("Result", game.result())
    return TournamentGame(
        white=white_name,
        black=black_name,
        result=result,
        pgn=game.pgn(),
        round=round_idx,
        timestamp=time.time(),
    )


def run_tournament(
    bot_specs: list[str],
    rounds: int = 1,
    time_limit_s: float = 0.5,
    k: float = DEFAULT_K,
    leaderboard_path: Path | None = None,
    persist: bool = True,
) -> TournamentReport:
    """Run a round-robin tournament.

    `bot_specs` are CLI-style specs (e.g., `random:seed=1`, `heuristic:max_depth=2`).
    Bots play both colors against each other in each round.
    """
    if leaderboard_path is None:
        leaderboard_path = default_leaderboard_path()

    bots: list[tuple[str, Bot]] = []
    for spec in bot_specs:
        name, kwargs = _parse_spec(spec)
        display_name = f"{name}@{spec}" if kwargs else name
        bots.append((display_name, get_bot(name, **kwargs)))

    ratings = _load_leaderboard(leaderboard_path) if persist else {}
    for display_name, _ in bots:
        _ensure_entry(ratings, display_name)

    report = TournamentReport(ratings=ratings)
    try:
        for round_idx in range(rounds):
            for i in range(len(bots)):
                for j in range(len(bots)):
                    if i == j:
                        continue
                    wname, wbot = bots[i]
                    bname, bbot = bots[j]
                    game = _play_one_game(wbot, bbot, wname, bname, round_idx, time_limit_s)
                    report.games.append(game)
                    w_score, b_score = result_to_scores(game.result)
                    w_entry = _ensure_entry(ratings, wname)
                    b_entry = _ensure_entry(ratings, bname)
                    new_w, new_b = update_ratings(w_entry.rating, b_entry.rating, w_score, k=k)
                    w_entry.record(w_score, new_w)
                    b_entry.record(b_score, new_b)
                    if persist:
                        _save_leaderboard(leaderboard_path, ratings)
    finally:
        for _, bot in bots:
            bot.close()

    return report


def _parse_spec(spec: str) -> tuple[str, dict[str, object]]:
    if ":" not in spec:
        return spec, {}
    name, rest = spec.split(":", 1)
    out: dict[str, object] = {}
    for chunk in rest.split(","):
        if not chunk:
            continue
        k, v = chunk.split("=", 1)
        out[k.strip()] = _coerce(v.strip())
    return name, out


def _coerce(v: str) -> object:
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v
