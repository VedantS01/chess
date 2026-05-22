"""Bots package. Importing this module side-effect-registers built-in bots."""

from chesslab.bots.base import (
    BOT_REGISTRY,
    Bot,
    get_bot,
    list_bots,
    register,
    register_bot,
    register_lazy,
)
from chesslab.bots.heuristic import HeuristicBot
from chesslab.bots.random_bot import RandomBot
from chesslab.bots.stockfish_bot import StockfishBot, find_stockfish_binary


def _load_ml_bot() -> None:
    """Lazy-import MLBot so torch isn't a hard dependency for everyone."""
    from chesslab.rl.ml_bot import MLBot  # noqa: F401  (side-effect: registers 'ml')


register_lazy("ml", _load_ml_bot)


__all__ = [
    "BOT_REGISTRY",
    "Bot",
    "HeuristicBot",
    "RandomBot",
    "StockfishBot",
    "find_stockfish_binary",
    "get_bot",
    "list_bots",
    "register",
    "register_bot",
    "register_lazy",
]
