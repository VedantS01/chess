"""Standard Elo math.

We use the classic FIDE formula. `K=32` for amateur play; `K=16` for more
stable rated competition. Initial rating defaults to `1500`.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_RATING = 1500.0
DEFAULT_K = 32.0


def expected_score(rating_a: float, rating_b: float) -> float:
    """Expected score for player A vs player B in [0, 1]."""
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def update_ratings(
    rating_a: float,
    rating_b: float,
    score_a: float,
    k: float = DEFAULT_K,
) -> tuple[float, float]:
    """Return updated `(rating_a, rating_b)` after a single game.

    `score_a` is the result from A's perspective: 1 for win, 0.5 for draw, 0 for loss.
    """
    if not 0.0 <= score_a <= 1.0:
        raise ValueError(f"score_a must be in [0,1], got {score_a}")
    expected_a = expected_score(rating_a, rating_b)
    new_a = rating_a + k * (score_a - expected_a)
    new_b = rating_b + k * ((1.0 - score_a) - (1.0 - expected_a))
    return new_a, new_b


@dataclass
class RatingEntry:
    name: str
    rating: float = DEFAULT_RATING
    games: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0

    def record(self, score: float, new_rating: float) -> None:
        self.rating = new_rating
        self.games += 1
        if score == 1.0:
            self.wins += 1
        elif score == 0.0:
            self.losses += 1
        else:
            self.draws += 1


def result_to_scores(result: str) -> tuple[float, float]:
    """Convert PGN-style result string to `(white_score, black_score)`."""
    if result == "1-0":
        return 1.0, 0.0
    if result == "0-1":
        return 0.0, 1.0
    if result == "1/2-1/2":
        return 0.5, 0.5
    raise ValueError(f"unparseable result: {result!r}")
