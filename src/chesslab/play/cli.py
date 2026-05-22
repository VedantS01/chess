"""CLI subcommands: `play` (interactive) and `match` (scripted bot-vs-bot)."""

from __future__ import annotations

import argparse
import contextlib
import io
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import chess
import chess.pgn

from chesslab.bots import Bot, get_bot, list_bots
from chesslab.engine import Game
from chesslab.play.render import render_board, render_move_list

HUMAN = "human"


def _parse_player_spec(spec: str) -> tuple[str, dict[str, object]]:
    """Parse 'name[:k=v,k=v]'. Reserved name: 'human'."""
    if ":" not in spec:
        return spec, {}
    name, rest = spec.split(":", 1)
    kwargs: dict[str, object] = {}
    if rest:
        for chunk in rest.split(","):
            if "=" not in chunk:
                raise SystemExit(f"bad player spec '{spec}': expected k=v in '{chunk}'")
            k, v = chunk.split("=", 1)
            kwargs[k.strip()] = _coerce(v.strip())
    return name, kwargs


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


@dataclass
class Players:
    white: Bot | None
    black: Bot | None

    def for_turn(self, turn: chess.Color) -> Bot | None:
        return self.white if turn == chess.WHITE else self.black


@contextlib.contextmanager
def _make_players(white_spec: str, black_spec: str) -> Iterator[Players]:
    white_name, white_kw = _parse_player_spec(white_spec)
    black_name, black_kw = _parse_player_spec(black_spec)
    white = None if white_name == HUMAN else get_bot(white_name, **white_kw)
    black = None if black_name == HUMAN else get_bot(black_name, **black_kw)
    try:
        yield Players(white=white, black=black)
    finally:
        for b in (white, black):
            if b is not None:
                b.close()


def _read_human_move(game: Game, stream: io.TextIOBase | None = None) -> str | None:
    """Return command string or None on EOF."""
    src = stream if stream is not None else sys.stdin
    prompt = "white> " if game.turn == chess.WHITE else "black> "
    if stream is None:
        sys.stdout.write(prompt)
        sys.stdout.flush()
    line = src.readline()
    if not line:
        return None
    return line.strip()


def play_command(args: argparse.Namespace) -> int:
    """Interactive play loop. Supports human and bot players in any combo."""
    with _make_players(args.white, args.black) as players:
        game = Game.from_fen(args.fen) if args.fen else Game()
        if players.white is not None:
            players.white.reset()
        if players.black is not None:
            players.black.reset()

        if not args.quiet:
            print(render_board(game))

        time_limit = args.time

        while not game.is_terminal():
            current_bot = players.for_turn(game.turn)
            if current_bot is None:
                while True:
                    line = _read_human_move(game)
                    if line is None:
                        print("(eof)", file=sys.stderr)
                        return 0
                    if not line:
                        continue
                    cmd = line.lower()
                    if cmd in ("quit", "exit", "resign"):
                        winner = "Black" if game.turn == chess.WHITE else "White"
                        print(f"{winner} wins by resignation.")
                        return 0
                    if cmd == "undo":
                        if game.history:
                            game.pop()
                            if game.history:
                                game.pop()
                        print(render_board(game))
                        continue
                    if cmd == "fen":
                        print(game.fen())
                        continue
                    if cmd == "pgn":
                        print(render_move_list(game))
                        continue
                    try:
                        try:
                            move = game.push_uci(line)
                        except (ValueError, chess.InvalidMoveError):
                            move = game.push_san(line)
                    except (ValueError, chess.IllegalMoveError, chess.InvalidMoveError, chess.AmbiguousMoveError) as e:
                        print(f"invalid move: {e}")
                        continue
                    if not args.quiet:
                        print(f"played {move.uci()}")
                        print(render_board(game))
                    break
            else:
                move = current_bot.choose_move(game, time_limit_s=time_limit)
                san = game.board.san(move)
                game.push(move)
                if not args.quiet:
                    print(f"{current_bot.name} -> {san}")
                    print(render_board(game))

        print(f"Game over: {game.result()}")
        if args.pgn:
            Path(args.pgn).write_text(game.pgn() + "\n")
        return 0


def match_command(args: argparse.Namespace) -> int:
    """Scripted bot-vs-bot matches; emits PGNs (stdout by default)."""
    out_stream: io.TextIOBase = open(args.pgn, "w") if args.pgn else sys.stdout  # noqa: SIM115
    try:
        wins = {"1-0": 0, "0-1": 0, "1/2-1/2": 0}
        with _make_players(args.white, args.black) as players:
            for game_idx in range(args.games):
                if players.white is None or players.black is None:
                    raise SystemExit("match requires two non-human players")
                players.white.reset()
                players.black.reset()
                game = Game.from_fen(args.fen) if args.fen else Game()
                game.headers["Event"] = "chesslab match"
                game.headers["White"] = players.white.name
                game.headers["Black"] = players.black.name
                game.headers["Round"] = str(game_idx + 1)

                while not game.is_terminal():
                    current_bot = players.for_turn(game.turn)
                    assert current_bot is not None
                    move = current_bot.choose_move(game, time_limit_s=args.time)
                    if move not in game.board.legal_moves:
                        # Should not happen with built-in bots; treat as loss.
                        loser = "white" if game.turn == chess.WHITE else "black"
                        winner_result = "0-1" if loser == "white" else "1-0"
                        game.headers["Result"] = winner_result
                        game.headers["Termination"] = f"illegal move by {loser}"
                        break
                    game.push(move)
                result = game.headers.get("Result", game.result())
                wins[result] = wins.get(result, 0) + 1
                out_stream.write(game.pgn() + "\n\n")
                out_stream.flush()
        summary = f"games={args.games} W={wins['1-0']} B={wins['0-1']} D={wins['1/2-1/2']}"
        print(summary, file=sys.stderr)
        return 0
    finally:
        if out_stream is not sys.stdout:
            out_stream.close()


def add_play_subparsers(sub: argparse._SubParsersAction) -> None:
    play = sub.add_parser("play", help="Interactive play (human or bot, any combo).")
    play.add_argument("--white", default=HUMAN, help=f"player spec; default {HUMAN}")
    play.add_argument("--black", default="random", help="player spec; default random")
    play.add_argument("--time", type=float, default=2.0, help="per-move time budget (s)")
    play.add_argument("--fen", default=None, help="start from FEN")
    play.add_argument("--pgn", default=None, help="write final PGN to file")
    play.add_argument("--quiet", action="store_true", help="suppress board rendering")
    play.set_defaults(func=play_command)

    match = sub.add_parser("match", help="Scripted bot-vs-bot matches.")
    match.add_argument("--white", required=True, help="player spec, e.g. heuristic:max_depth=3")
    match.add_argument("--black", required=True, help="player spec, e.g. random")
    match.add_argument("--games", type=int, default=1)
    match.add_argument("--time", type=float, default=1.0)
    match.add_argument("--fen", default=None)
    match.add_argument("--pgn", default=None, help="write PGNs to file (default stdout)")
    match.set_defaults(func=match_command)

    listb = sub.add_parser("list-bots", help="List registered bots.")
    listb.set_defaults(func=lambda _args: (print("\n".join(list_bots())) or 0))
