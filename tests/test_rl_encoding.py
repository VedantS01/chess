"""Tests for chesslab.rl.encoding."""

from __future__ import annotations

import chess
import numpy as np

from chesslab.rl.encoding import (
    ACTION_SIZE,
    board_to_tensor,
    index_to_move,
    legal_action_mask,
    mirror_tensor,
    move_to_index,
)


def test_initial_tensor_shape_and_planes() -> None:
    arr = board_to_tensor(chess.Board())
    assert arr.shape == (18, 8, 8)
    # 8 white pawns on rank 2 (index 1 from white's perspective, file 0..7).
    assert arr[0, 1, :].sum() == 8
    # 8 black pawns on rank 7 (index 6).
    assert arr[6, 6, :].sum() == 8
    # White to move plane is all ones.
    assert arr[12].sum() == 64
    # All four castling planes set initially.
    assert arr[13].sum() == 64
    assert arr[14].sum() == 64
    assert arr[15].sum() == 64
    assert arr[16].sum() == 64
    # No en-passant square initially.
    assert arr[17].sum() == 0


def test_action_size_constant_and_legal_indices() -> None:
    assert ACTION_SIZE > 4000
    board = chess.Board()
    mask = legal_action_mask(board)
    assert mask.sum() == 20
    for mv in board.legal_moves:
        i = move_to_index(mv)
        assert mask[i]


def test_index_round_trip_for_legal_moves() -> None:
    board = chess.Board()
    for mv in board.legal_moves:
        idx = move_to_index(mv)
        recovered = index_to_move(idx)
        assert recovered.from_square == mv.from_square
        assert recovered.to_square == mv.to_square


def test_promotion_in_action_space() -> None:
    # White to move with a pawn on e7 ready to promote on e8 (king on a8 so e8 is empty).
    board = chess.Board("k7/4P3/8/8/8/8/8/4K3 w - - 0 1")
    mask = legal_action_mask(board)
    promotions = [m for m in board.legal_moves if m.promotion is not None]
    assert len(promotions) == 4
    for promo in promotions:
        assert mask[move_to_index(promo)]


def test_mirror_tensor_flips_perspective() -> None:
    board = chess.Board()
    arr = board_to_tensor(board)
    mirrored = mirror_tensor(arr)
    # After mirror, plane 0 (STM-relative own pawn) should hold what was the
    # opponent pawn plane, vertically flipped: 8 pawns on rank index 1.
    assert mirrored[0, 1, :].sum() == 8
    # Plane 6 (STM-relative opponent pawn) holds what was own pawn plane flipped:
    # 8 pawns on rank index 6.
    assert mirrored[6, 6, :].sum() == 8
    # Mirror is an involution: applying it twice recovers the original.
    assert np.array_equal(mirror_tensor(mirrored), arr)


def test_legal_action_mask_dtype_and_shape() -> None:
    mask = legal_action_mask(chess.Board())
    assert mask.dtype == np.bool_
    assert mask.shape == (ACTION_SIZE,)
