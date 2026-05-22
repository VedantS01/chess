"""Bots package. Importing this module side-effect-registers built-in bots."""

from chesslab.bots.base import (
    BOT_REGISTRY,
    Bot,
    get_bot,
    list_bots,
    register,
    register_bot,
)
from chesslab.bots.heuristic import HeuristicBot
from chesslab.bots.random_bot import RandomBot
from chesslab.bots.stockfish_bot import StockfishBot, find_stockfish_binary

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
]
