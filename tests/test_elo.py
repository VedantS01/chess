"""Tests for chesslab.tournament.elo."""

from __future__ import annotations

import math

from chesslab.tournament.elo import (
    DEFAULT_K,
    expected_score,
    result_to_scores,
    update_ratings,
)


def test_expected_score_symmetry() -> None:
    assert math.isclose(expected_score(1500, 1500), 0.5)
    assert math.isclose(expected_score(1600, 1400) + expected_score(1400, 1600), 1.0)


def test_expected_score_known_values() -> None:
    # 200-point gap -> ~0.760 / 0.240.
    assert math.isclose(expected_score(1500, 1300), 0.7597, rel_tol=1e-3)
    assert math.isclose(expected_score(1300, 1500), 0.2403, rel_tol=1e-3)


def test_update_ratings_zero_sum() -> None:
    a, b = update_ratings(1500, 1500, 1.0, k=DEFAULT_K)
    assert math.isclose(a + b, 3000.0, abs_tol=1e-6)
    assert a > b
    a, b = update_ratings(1500, 1500, 0.5, k=DEFAULT_K)
    assert math.isclose(a, 1500.0)
    assert math.isclose(b, 1500.0)


def test_update_ratings_known_delta() -> None:
    # Equal opponents, A wins -> A gains K/2 = 16; B loses 16.
    a, b = update_ratings(1500, 1500, 1.0, k=32)
    assert math.isclose(a, 1516.0)
    assert math.isclose(b, 1484.0)


def test_result_to_scores() -> None:
    assert result_to_scores("1-0") == (1.0, 0.0)
    assert result_to_scores("0-1") == (0.0, 1.0)
    assert result_to_scores("1/2-1/2") == (0.5, 0.5)
