"""`chesslab tournament` subcommand."""

from __future__ import annotations

import argparse
from pathlib import Path

from chesslab.tournament.runner import default_leaderboard_path, run_tournament


def tournament_command(args: argparse.Namespace) -> int:
    bot_specs = [s.strip() for s in args.bots.split(",") if s.strip()]
    if len(bot_specs) < 2:
        raise SystemExit("need at least 2 bots")
    leaderboard = Path(args.leaderboard) if args.leaderboard else default_leaderboard_path()
    report = run_tournament(
        bot_specs=bot_specs,
        rounds=args.rounds,
        time_limit_s=args.time,
        leaderboard_path=leaderboard,
        persist=not args.no_persist,
    )
    print(f"played {len(report.games)} games; leaderboard:")
    sorted_entries = sorted(report.ratings.values(), key=lambda e: e.rating, reverse=True)
    print(f"{'rank':<4} {'name':<30} {'rating':>8} {'games':>6} {'W':>4} {'D':>4} {'L':>4}")
    for i, e in enumerate(sorted_entries, start=1):
        print(f"{i:<4} {e.name:<30} {e.rating:>8.1f} {e.games:>6} {e.wins:>4} {e.draws:>4} {e.losses:>4}")
    if not args.no_persist:
        print(f"\nleaderboard saved to: {leaderboard}")
    return 0


def add_tournament_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("tournament", help="Round-robin tournament with Elo updates.")
    p.add_argument("--bots", required=True, help="comma-separated bot specs, e.g. random,heuristic:max_depth=2")
    p.add_argument("--rounds", type=int, default=1)
    p.add_argument("--time", type=float, default=0.3, help="per-move budget (s)")
    p.add_argument("--leaderboard", default=None, help="path to leaderboard JSON (default ~/.chesslab/leaderboard.json)")
    p.add_argument("--no-persist", action="store_true", help="don't read/write leaderboard")
    p.set_defaults(func=tournament_command)
