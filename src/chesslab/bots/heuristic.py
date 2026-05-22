"""Heuristic search bot.

Negamax + alpha-beta + iterative deepening + quiescence on captures +
Zobrist-keyed transposition table. Evaluation is material + classic piece-square
tables (mirrored for black). Designed to be readable and to serve as a baseline
opponent for the RL trainer.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import chess
import chess.polyglot

from chesslab.bots.base import Bot, register
from chesslab.engine import Game

# Centipawn values
PIECE_VALUE: dict[int, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}

# Piece-square tables (from White's perspective, A1 = index 0, H8 = index 63).
# Standard textbook PSTs — small bonuses for centralization / pawn structure.
PST: dict[int, list[int]] = {
    chess.PAWN: [
         0,   0,   0,   0,   0,   0,   0,   0,
         5,  10,  10, -20, -20,  10,  10,   5,
         5,  -5, -10,   0,   0, -10,  -5,   5,
         0,   0,   0,  20,  20,   0,   0,   0,
         5,   5,  10,  25,  25,  10,   5,   5,
        10,  10,  20,  30,  30,  20,  10,  10,
        50,  50,  50,  50,  50,  50,  50,  50,
         0,   0,   0,   0,   0,   0,   0,   0,
    ],
    chess.KNIGHT: [
       -50, -40, -30, -30, -30, -30, -40, -50,
       -40, -20,   0,   5,   5,   0, -20, -40,
       -30,   5,  10,  15,  15,  10,   5, -30,
       -30,   0,  15,  20,  20,  15,   0, -30,
       -30,   5,  15,  20,  20,  15,   5, -30,
       -30,   0,  10,  15,  15,  10,   0, -30,
       -40, -20,   0,   0,   0,   0, -20, -40,
       -50, -40, -30, -30, -30, -30, -40, -50,
    ],
    chess.BISHOP: [
       -20, -10, -10, -10, -10, -10, -10, -20,
       -10,   5,   0,   0,   0,   0,   5, -10,
       -10,  10,  10,  10,  10,  10,  10, -10,
       -10,   0,  10,  10,  10,  10,   0, -10,
       -10,   5,   5,  10,  10,   5,   5, -10,
       -10,   0,   5,  10,  10,   5,   0, -10,
       -10,   0,   0,   0,   0,   0,   0, -10,
       -20, -10, -10, -10, -10, -10, -10, -20,
    ],
    chess.ROOK: [
         0,   0,   0,   5,   5,   0,   0,   0,
        -5,   0,   0,   0,   0,   0,   0,  -5,
        -5,   0,   0,   0,   0,   0,   0,  -5,
        -5,   0,   0,   0,   0,   0,   0,  -5,
        -5,   0,   0,   0,   0,   0,   0,  -5,
        -5,   0,   0,   0,   0,   0,   0,  -5,
         5,  10,  10,  10,  10,  10,  10,   5,
         0,   0,   0,   0,   0,   0,   0,   0,
    ],
    chess.QUEEN: [
       -20, -10, -10,  -5,  -5, -10, -10, -20,
       -10,   0,   5,   0,   0,   0,   0, -10,
       -10,   5,   5,   5,   5,   5,   0, -10,
         0,   0,   5,   5,   5,   5,   0,  -5,
        -5,   0,   5,   5,   5,   5,   0,  -5,
       -10,   0,   5,   5,   5,   5,   0, -10,
       -10,   0,   0,   0,   0,   0,   0, -10,
       -20, -10, -10,  -5,  -5, -10, -10, -20,
    ],
    chess.KING: [
        20,  30,  10,   0,   0,  10,  30,  20,
        20,  20,   0,   0,   0,   0,  20,  20,
       -10, -20, -20, -20, -20, -20, -20, -10,
       -20, -30, -30, -40, -40, -30, -30, -20,
       -30, -40, -40, -50, -50, -40, -40, -30,
       -30, -40, -40, -50, -50, -40, -40, -30,
       -30, -40, -40, -50, -50, -40, -40, -30,
       -30, -40, -40, -50, -50, -40, -40, -30,
    ],
}

MATE_SCORE = 100_000
INF = 10_000_000


def _square_for_color(square: int, color: chess.Color) -> int:
    """Mirror square vertically for black so PSTs read as White's perspective."""
    return square if color == chess.WHITE else chess.square_mirror(square)


def evaluate(board: chess.Board) -> int:
    """Static eval from the side-to-move's perspective in centipawns."""
    if board.is_checkmate():
        return -MATE_SCORE + board.ply()
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        return 0

    score = 0
    for piece_type in (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING):
        pst = PST[piece_type]
        value = PIECE_VALUE[piece_type]
        for sq in board.pieces(piece_type, chess.WHITE):
            score += value + pst[_square_for_color(sq, chess.WHITE)]
        for sq in board.pieces(piece_type, chess.BLACK):
            score -= value + pst[_square_for_color(sq, chess.BLACK)]
    return score if board.turn == chess.WHITE else -score


@dataclass
class TTEntry:
    depth: int
    score: int
    flag: str  # "EXACT" | "LOWER" | "UPPER"
    best_move: chess.Move | None


class _TimeUp(Exception):
    pass


@register("heuristic")
class HeuristicBot(Bot):
    name = "heuristic"

    def __init__(
        self,
        max_depth: int = 4,
        time_limit_s: float = 2.0,
        quiescence: bool = True,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.max_depth = max_depth
        self.default_time = time_limit_s
        self.quiescence = quiescence
        self._tt: dict[int, TTEntry] = {}
        self._deadline: float = float("inf")

    def reset(self) -> None:
        self._tt.clear()

    def choose_move(self, game: Game, time_limit_s: float | None = None) -> chess.Move:
        budget = time_limit_s if time_limit_s is not None else self.default_time
        self._deadline = time.monotonic() + budget
        board = game.board.copy(stack=False)

        best_move: chess.Move | None = None
        best_score = -INF
        try:
            for depth in range(1, self.max_depth + 1):
                score, move = self._search_root(board, depth)
                if move is not None:
                    best_move = move
                    best_score = score
                if abs(best_score) >= MATE_SCORE - 1000:
                    break
        except _TimeUp:
            pass

        if best_move is None:
            # Fallback: any legal move (e.g., depth-1 didn't finish).
            moves = list(board.legal_moves)
            if not moves:
                raise RuntimeError("no legal moves in terminal position")
            best_move = moves[0]
        return best_move

    def _check_time(self) -> None:
        if time.monotonic() >= self._deadline:
            raise _TimeUp

    def _search_root(self, board: chess.Board, depth: int) -> tuple[int, chess.Move | None]:
        alpha, beta = -INF, INF
        best_score = -INF
        best_move: chess.Move | None = None
        moves = self._order_moves(board, self._tt_best(board))
        for move in moves:
            board.push(move)
            try:
                score = -self._negamax(board, depth - 1, -beta, -alpha)
            finally:
                board.pop()
            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, score)
        return best_score, best_move

    def _negamax(self, board: chess.Board, depth: int, alpha: int, beta: int) -> int:
        self._check_time()

        key = chess.polyglot.zobrist_hash(board)
        tt_entry = self._tt.get(key)
        if tt_entry is not None and tt_entry.depth >= depth:
            if tt_entry.flag == "EXACT":
                return tt_entry.score
            if tt_entry.flag == "LOWER" and tt_entry.score >= beta:
                return tt_entry.score
            if tt_entry.flag == "UPPER" and tt_entry.score <= alpha:
                return tt_entry.score

        if board.is_game_over(claim_draw=True):
            return evaluate(board)
        if depth <= 0:
            return self._quiesce(board, alpha, beta) if self.quiescence else evaluate(board)

        original_alpha = alpha
        best_score = -INF
        best_move: chess.Move | None = None
        for move in self._order_moves(board, tt_entry.best_move if tt_entry else None):
            board.push(move)
            try:
                score = -self._negamax(board, depth - 1, -beta, -alpha)
            finally:
                board.pop()
            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, score)
            if alpha >= beta:
                break

        flag = "EXACT"
        if best_score <= original_alpha:
            flag = "UPPER"
        elif best_score >= beta:
            flag = "LOWER"
        self._tt[key] = TTEntry(depth=depth, score=best_score, flag=flag, best_move=best_move)
        return best_score

    def _quiesce(self, board: chess.Board, alpha: int, beta: int) -> int:
        self._check_time()
        stand_pat = evaluate(board)
        if stand_pat >= beta:
            return beta
        alpha = max(alpha, stand_pat)

        for move in self._order_moves(board, None, captures_only=True):
            board.push(move)
            try:
                score = -self._quiesce(board, -beta, -alpha)
            finally:
                board.pop()
            if score >= beta:
                return beta
            alpha = max(alpha, score)
        return alpha

    def _tt_best(self, board: chess.Board) -> chess.Move | None:
        entry = self._tt.get(chess.polyglot.zobrist_hash(board))
        return entry.best_move if entry else None

    @staticmethod
    def _order_moves(
        board: chess.Board,
        pv_move: chess.Move | None,
        captures_only: bool = False,
    ) -> list[chess.Move]:
        def score(m: chess.Move) -> int:
            if pv_move is not None and m == pv_move:
                return 10_000_000
            s = 0
            if board.is_capture(m):
                victim = board.piece_at(m.to_square)
                attacker = board.piece_at(m.from_square)
                if victim is not None and attacker is not None:
                    s += 1_000_000 + PIECE_VALUE[victim.piece_type] * 10 - PIECE_VALUE[attacker.piece_type]
                elif board.is_en_passant(m):
                    s += 1_000_000 + PIECE_VALUE[chess.PAWN] * 10 - PIECE_VALUE[chess.PAWN]
            if m.promotion is not None:
                s += 800_000 + PIECE_VALUE.get(m.promotion, 0)
            if board.gives_check(m):
                s += 500
            return s

        if captures_only:
            moves = [m for m in board.legal_moves if board.is_capture(m) or m.promotion is not None]
        else:
            moves = list(board.legal_moves)
        moves.sort(key=score, reverse=True)
        return moves
