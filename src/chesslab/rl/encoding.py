"""Board <-> tensor encoding for chesslab RL networks.

`board_to_tensor` returns an `(18, 8, 8)` numpy array:
    planes 0..5   = white piece presence (P,N,B,R,Q,K)
    planes 6..11  = black piece presence (p,n,b,r,q,k)
    plane  12     = side to move (1 if white, else 0)
    planes 13..16 = castling rights (W-K, W-Q, B-K, B-Q)
    plane  17     = en-passant target (1 at ep square)

`MOVE_INDEX` / `INDEX_MOVE` map the action space used by the policy head:
all `(from, to, promotion)` triples that can ever be legal in any standard
chess position. Total action-space size is `ACTION_SIZE` (deterministic).
"""

from __future__ import annotations

import chess
import numpy as np

PIECE_ORDER = (
    chess.PAWN,
    chess.KNIGHT,
    chess.BISHOP,
    chess.ROOK,
    chess.QUEEN,
    chess.KING,
)
NUM_PLANES = 18


def board_to_tensor(board: chess.Board) -> np.ndarray:
    """Return an `(18, 8, 8)` float32 tensor for `board`.

    Always rendered from the perspective of `chess.WHITE` (i.e., A1 = index 0,
    H8 = index 63). Callers that want a side-to-move-relative view can call
    `mirror_tensor` on the result for Black-to-move positions.
    """
    arr = np.zeros((NUM_PLANES, 8, 8), dtype=np.float32)
    for plane, piece_type in enumerate(PIECE_ORDER):
        for sq in board.pieces(piece_type, chess.WHITE):
            f, r = chess.square_file(sq), chess.square_rank(sq)
            arr[plane, r, f] = 1.0
        for sq in board.pieces(piece_type, chess.BLACK):
            f, r = chess.square_file(sq), chess.square_rank(sq)
            arr[plane + 6, r, f] = 1.0
    if board.turn == chess.WHITE:
        arr[12, :, :] = 1.0
    arr[13, :, :] = 1.0 if board.has_kingside_castling_rights(chess.WHITE) else 0.0
    arr[14, :, :] = 1.0 if board.has_queenside_castling_rights(chess.WHITE) else 0.0
    arr[15, :, :] = 1.0 if board.has_kingside_castling_rights(chess.BLACK) else 0.0
    arr[16, :, :] = 1.0 if board.has_queenside_castling_rights(chess.BLACK) else 0.0
    if board.ep_square is not None:
        f, r = chess.square_file(board.ep_square), chess.square_rank(board.ep_square)
        arr[17, r, f] = 1.0
    return arr


def mirror_tensor(arr: np.ndarray) -> np.ndarray:
    """Flip the board vertically AND swap white/black planes.

    Useful for STM-relative views: feed `mirror_tensor(board_to_tensor(b))`
    when `b.turn == BLACK` so the network always sees "side-to-move" at the
    bottom of the board.
    """
    out = arr.copy()
    out[:12] = out[[6, 7, 8, 9, 10, 11, 0, 1, 2, 3, 4, 5]]
    out = out[:, ::-1, :].copy()
    return out


def _build_action_space() -> tuple[dict[tuple[int, int, int | None], int], list[chess.Move]]:
    moves: list[chess.Move] = []
    for fr in chess.SQUARES:
        for to in chess.SQUARES:
            if fr == to:
                continue
            from_rank = chess.square_rank(fr)
            to_rank = chess.square_rank(to)
            # Only allow a single non-promotion entry per from-to pair.
            moves.append(chess.Move(fr, to))
            # Add promotion variants only on legal promotion ranks.
            if (from_rank == 6 and to_rank == 7) or (from_rank == 1 and to_rank == 0):
                for promo in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT):
                    moves.append(chess.Move(fr, to, promotion=promo))
    index: dict[tuple[int, int, int | None], int] = {}
    for i, mv in enumerate(moves):
        index[(mv.from_square, mv.to_square, mv.promotion)] = i
    return index, moves


MOVE_INDEX, INDEX_MOVE = _build_action_space()
ACTION_SIZE = len(INDEX_MOVE)


def move_to_index(move: chess.Move) -> int:
    """Map a `chess.Move` to its flat action index.

    For pawn captures/pushes that don't promote, promotion is `None`. For
    pawn promotions, the promotion piece (Q/R/B/N) is part of the key.
    """
    promo = move.promotion
    key = (move.from_square, move.to_square, promo)
    if key in MOVE_INDEX:
        return MOVE_INDEX[key]
    # Some callers construct promotion-eligible moves without setting `promotion`.
    # Default to queen-promotion in that case.
    fallback_key = (move.from_square, move.to_square, chess.QUEEN)
    if fallback_key in MOVE_INDEX:
        return MOVE_INDEX[fallback_key]
    raise KeyError(f"move not in action space: {move.uci()}")


def index_to_move(index: int) -> chess.Move:
    return INDEX_MOVE[index]


def legal_action_mask(board: chess.Board) -> np.ndarray:
    """Boolean `(ACTION_SIZE,)` mask: True where the corresponding action is legal."""
    mask = np.zeros((ACTION_SIZE,), dtype=bool)
    for move in board.legal_moves:
        try:
            mask[move_to_index(move)] = True
        except KeyError:
            continue
    return mask
