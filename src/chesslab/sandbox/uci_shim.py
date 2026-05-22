"""UCI shim used as the entrypoint for the chesslab-runner Docker image.

Loads a user-provided bot from `/bot/bot.py` (or `$CHESSLAB_BOT_PATH`) and
exposes it on stdin/stdout speaking a minimal subset of the UCI protocol.
This lets the backend orchestrator drive matches via python-chess's
`SimpleEngine` over a pipe transport.

The bot module must define a top-level symbol named `BOT` that is either:
- an instantiated `chesslab.bots.base.Bot` (preferred), or
- a callable `factory()` returning a `Bot` instance.

Supported UCI commands:
    uci                 -> id name/author, uciok
    isready             -> readyok
    ucinewgame          -> reset() the bot
    position [startpos|fen <FEN>] [moves <m1> <m2> ...]
    go [movetime N] [wtime N] [btime N] [depth N]
    stop                -> (no-op, returns immediately)
    quit                -> exit cleanly

Anything else is acknowledged with `info string ignored`.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import time
import traceback
from pathlib import Path

import chess

from chesslab.bots.base import Bot
from chesslab.engine import Game

DEFAULT_BOT_PATH = "/bot/bot.py"


def _load_bot_from(path: Path) -> Bot:
    if not path.exists():
        raise FileNotFoundError(f"bot path not found: {path}")
    spec = importlib.util.spec_from_file_location("user_bot", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load bot from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "BOT"):
        raise AttributeError(f"bot module {path} must define a top-level `BOT`")
    candidate = module.BOT
    if callable(candidate) and not isinstance(candidate, Bot):
        candidate = candidate()
    if not isinstance(candidate, Bot):
        raise TypeError(f"BOT must be a chesslab Bot instance, got {type(candidate).__name__}")
    return candidate


def _parse_position(parts: list[str]) -> Game:
    game = Game()
    if not parts:
        return game
    idx = 0
    if parts[0] == "startpos":
        idx = 1
    elif parts[0] == "fen":
        fen_tokens = []
        idx = 1
        while idx < len(parts) and parts[idx] != "moves":
            fen_tokens.append(parts[idx])
            idx += 1
        game = Game.from_fen(" ".join(fen_tokens))
    if idx < len(parts) and parts[idx] == "moves":
        for uci in parts[idx + 1 :]:
            game.push_uci(uci)
    return game


def _parse_go_time(parts: list[str], side_to_move: chess.Color) -> float | None:
    """Return per-move budget in seconds based on UCI go params."""
    i = 0
    movetime: int | None = None
    wtime: int | None = None
    btime: int | None = None
    winc: int | None = None
    binc: int | None = None
    depth: int | None = None
    while i < len(parts):
        tok = parts[i]
        if tok == "movetime" and i + 1 < len(parts):
            movetime = int(parts[i + 1])
            i += 2
        elif tok == "wtime" and i + 1 < len(parts):
            wtime = int(parts[i + 1])
            i += 2
        elif tok == "btime" and i + 1 < len(parts):
            btime = int(parts[i + 1])
            i += 2
        elif tok == "winc" and i + 1 < len(parts):
            winc = int(parts[i + 1])
            i += 2
        elif tok == "binc" and i + 1 < len(parts):
            binc = int(parts[i + 1])
            i += 2
        elif tok == "depth" and i + 1 < len(parts):
            depth = int(parts[i + 1])
            i += 2
        else:
            i += 1
    _ = depth  # not honored by all bots; informational
    if movetime is not None:
        return movetime / 1000.0
    side_time = wtime if side_to_move == chess.WHITE else btime
    side_inc = winc if side_to_move == chess.WHITE else binc
    if side_time is None:
        return None
    # Simple budget: 1/30th of remaining + half increment, capped at 5s.
    return min(5.0, side_time / 30_000.0 + (side_inc or 0) / 2_000.0)


def _write(line: str) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _info(msg: str) -> None:
    _write(f"info string {msg}")


def main(argv: list[str] | None = None) -> int:
    bot_path_env = os.environ.get("CHESSLAB_BOT_PATH")
    bot_path = Path(bot_path_env) if bot_path_env else Path(DEFAULT_BOT_PATH)

    bot: Bot | None = None
    game = Game()
    deadline_seed_loaded = False  # noqa: F841 (kept for future enhancement)

    try:
        for raw in sys.stdin:
            line = raw.strip()
            if not line:
                continue
            parts = line.split()
            cmd = parts[0]
            args = parts[1:]

            if cmd == "uci":
                _write("id name chesslab-runner")
                _write("id author chesslab")
                _write("uciok")
            elif cmd == "isready":
                # Lazy-load the bot on first ready check.
                if bot is None:
                    try:
                        bot = _load_bot_from(bot_path)
                    except Exception as e:  # noqa: BLE001
                        _info(f"failed to load bot: {e}")
                        traceback.print_exc(file=sys.stderr)
                        bot = None
                _write("readyok")
            elif cmd == "ucinewgame":
                if bot is not None:
                    bot.reset()
                game = Game()
            elif cmd == "position":
                game = _parse_position(args)
            elif cmd == "go":
                if bot is None:
                    _info("no bot loaded; cannot move")
                    _write("bestmove 0000")
                    continue
                budget = _parse_go_time(args, game.turn)
                t0 = time.monotonic()
                try:
                    move = bot.choose_move(game, time_limit_s=budget)
                except Exception as e:  # noqa: BLE001
                    _info(f"bot raised: {e}")
                    traceback.print_exc(file=sys.stderr)
                    _write("bestmove 0000")
                    continue
                elapsed = time.monotonic() - t0
                _info(f"thinking={elapsed*1000:.0f}ms")
                _write(f"bestmove {move.uci()}")
            elif cmd == "stop":
                pass
            elif cmd == "quit":
                break
            else:
                _info(f"ignored: {line}")
    finally:
        if bot is not None:
            bot.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
