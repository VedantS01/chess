"""Thin wrapper around python-chess for the chesslab framework.

`Game` keeps a `chess.Board` plus move history and exposes the operations the
rest of the framework (bots, RL env, sandbox, backend) needs without leaking
`chess.Board` internals across layers.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

import chess
import chess.pgn


@dataclass
class Game:
    board: chess.Board = field(default_factory=chess.Board)
    history: list[chess.Move] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_fen(cls, fen: str) -> Game:
        return cls(board=chess.Board(fen))

    def legal_moves(self) -> Iterator[chess.Move]:
        return iter(self.board.legal_moves)

    def push(self, move: chess.Move) -> None:
        if move not in self.board.legal_moves:
            raise ValueError(f"illegal move: {move.uci()} in position {self.board.fen()}")
        self.history.append(move)
        self.board.push(move)

    def push_uci(self, uci: str) -> chess.Move:
        move = chess.Move.from_uci(uci)
        self.push(move)
        return move

    def push_san(self, san: str) -> chess.Move:
        move = self.board.parse_san(san)
        self.push(move)
        return move

    def pop(self) -> chess.Move:
        move = self.board.pop()
        if self.history:
            self.history.pop()
        return move

    @property
    def turn(self) -> chess.Color:
        return self.board.turn

    @property
    def ply(self) -> int:
        return self.board.ply()

    def is_terminal(self) -> bool:
        return self.board.is_game_over(claim_draw=True)

    def result(self) -> str:
        """Standard PGN result string: '1-0', '0-1', '1/2-1/2', or '*' if ongoing."""
        return self.board.result(claim_draw=True)

    def outcome(self) -> chess.Outcome | None:
        return self.board.outcome(claim_draw=True)

    def fen(self) -> str:
        return self.board.fen()

    def copy(self) -> Game:
        return Game(board=self.board.copy(stack=True), history=list(self.history), headers=dict(self.headers))

    def pgn(self) -> str:
        game = chess.pgn.Game()
        for k, v in self.headers.items():
            game.headers[k] = v
        if self.board.chess960:
            game.headers["Variant"] = "Chess960"
        if self.history:
            node = game
            for move in self.history:
                node = node.add_variation(move)
        game.headers["Result"] = self.result()
        return str(game)

    def unicode_board(self, invert_color: bool = False, perspective: chess.Color = chess.WHITE) -> str:
        return self.board.unicode(invert_color=invert_color, orientation=perspective)

    def __repr__(self) -> str:
        return f"Game(fen={self.fen()!r}, ply={self.ply})"
