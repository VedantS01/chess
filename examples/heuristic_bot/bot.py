"""Example user bot: shallow alpha-beta heuristic."""

from chesslab.bots.heuristic import HeuristicBot

BOT = HeuristicBot(max_depth=3, time_limit_s=1.0)
