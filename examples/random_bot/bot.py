"""Example user bot: random legal move.

This is the minimal interface the sandbox UCI shim expects. Save this file at
the path mounted into the container at `/bot/bot.py` (or set the
`CHESSLAB_BOT_PATH` env var). The shim looks up a top-level symbol `BOT`.

To run locally:

    docker run --rm -i \
        --network=none --read-only --cpus=1 --memory=512m --pids-limit=64 \
        -v "$(pwd)/examples/random_bot:/bot:ro" \
        chesslab-runner:dev
"""

from chesslab.bots.random_bot import RandomBot

BOT = RandomBot(seed=42)
