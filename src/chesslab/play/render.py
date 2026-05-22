"""Rendering helpers for the TUI."""

from __future__ import annotations

import chess

from chesslab.engine import Game

FILES = "abcdefgh"

UNICODE_PIECES_WHITE = {
    chess.PAWN: "♙",
    chess.KNIGHT: "♘",
    chess.BISHOP: "♗",
    chess.ROOK: "♖",
    chess.QUEEN: "♕",
    chess.KING: "♔",
}
UNICODE_PIECES_BLACK = {
    chess.PAWN: "♟",
    chess.KNIGHT: "♞",
    chess.BISHOP: "♝",
    chess.ROOK: "♜",
    chess.QUEEN: "♛",
    chess.KING: "♚",
}


def render_board(game: Game, perspective: chess.Color = chess.WHITE) -> str:
    """ASCII board with file/rank labels, sized for an 80-col terminal."""
    board = game.board
    lines: list[str] = []
    ranks = range(7, -1, -1) if perspective == chess.WHITE else range(8)
    files = range(8) if perspective == chess.WHITE else range(7, -1, -1)
    for rank in ranks:
        cells: list[str] = []
        for file in files:
            sq = chess.square(file, rank)
            piece = board.piece_at(sq)
            if piece is None:
                cells.append(".")
            elif piece.color == chess.WHITE:
                cells.append(UNICODE_PIECES_WHITE[piece.piece_type])
            else:
                cells.append(UNICODE_PIECES_BLACK[piece.piece_type])
        lines.append(f"{rank + 1} | " + " ".join(cells))
    lines.append("    " + " ".join(FILES[f] for f in files))
    lines.append("")
    turn = "White" if board.turn == chess.WHITE else "Black"
    lines.append(f"{turn} to move (ply {board.ply()}); FEN: {board.fen()}")
    return "\n".join(lines)


def render_move_list(game: Game) -> str:
    """Render move history in 1. e4 e5 2. Nf3 Nc6 ... format."""
    board = chess.Board()
    pieces: list[str] = []
    for i, move in enumerate(game.history):
        san = board.san(move)
        if i % 2 == 0:
            pieces.append(f"{(i // 2) + 1}.")
        pieces.append(san)
        board.push(move)
    return " ".join(pieces) if pieces else "(no moves)"
