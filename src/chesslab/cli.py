"""Top-level chesslab CLI dispatcher.

Subcommands are wired in as later steps land. Step 1 only provides the entrypoint.
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chesslab", description="Chess engine + bots + RL + online play.")
    sub = parser.add_subparsers(dest="cmd", required=False)

    sub.add_parser("version", help="Print chesslab version")

    args = parser.parse_args(argv)

    if args.cmd in (None, "version"):
        from chesslab import __version__

        print(f"chesslab {__version__}")
        return 0

    parser.error(f"unknown command: {args.cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
