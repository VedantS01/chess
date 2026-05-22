"""Top-level chesslab CLI dispatcher."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chesslab", description="Chess engine + bots + RL + online play.")
    sub = parser.add_subparsers(dest="cmd", required=False)

    sub.add_parser("version", help="Print chesslab version")

    # Import here so importing chesslab.cli is cheap (and so optional deps
    # like torch don't load unless the user invokes those subcommands).
    from chesslab.bots import BOT_REGISTRY  # noqa: F401  (side-effect: register built-ins)
    from chesslab.play.cli import add_play_subparsers

    add_play_subparsers(sub)

    try:
        from chesslab.rl.cli import add_train_subparser

        add_train_subparser(sub)
    except ImportError:
        # torch optional dep not installed; train is unavailable but everything
        # else still works.
        pass

    args = parser.parse_args(argv)

    if args.cmd is None or args.cmd == "version":
        from chesslab import __version__

        print(f"chesslab {__version__}")
        return 0

    if hasattr(args, "func"):
        return int(args.func(args) or 0)

    parser.error(f"unknown command: {args.cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
