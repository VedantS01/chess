"""Random bot: picks a uniformly-random legal move."""

from __future__ import annotations

import random

import chess

from chesslab.bots.base import Bot, register
from chesslab.engine import Game


@register("random")
class RandomBot(Bot):
    name = "random"

    def __init__(self, seed: int | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._rng = random.Random(seed)

    def choose_move(self, game: Game, time_limit_s: float | None = None) -> chess.Move:
        moves = list(game.legal_moves())
        if not moves:
            raise RuntimeError("no legal moves in terminal position")
        return self._rng.choice(moves)
