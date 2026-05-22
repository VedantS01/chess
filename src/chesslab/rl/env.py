"""Self-play environment for chesslab RL training.

`SelfPlayEnv` exposes a single-process API compatible with the trainer:
`reset()` -> obs/mask, `step(action_index)` -> obs/mask/reward/done.
Reward is shaped from the perspective of the side that just moved:
+1 for checkmate, 0 for draw, 0 mid-game; if opponent walks into mate next turn,
the move that produced that position is credited at the end of the episode by
the trainer's bootstrap.
"""

from __future__ import annotations

from dataclasses import dataclass

import chess
import numpy as np

from chesslab.rl.encoding import board_to_tensor, index_to_move, legal_action_mask


@dataclass
class StepResult:
    obs: np.ndarray
    legal_mask: np.ndarray
    reward: float
    done: bool
    info: dict[str, object]


class IllegalActionError(RuntimeError):
    pass


class SelfPlayEnv:
    def __init__(self, max_plies: int = 200) -> None:
        self.max_plies = max_plies
        self.board = chess.Board()
        self._ply_count = 0

    def reset(self, fen: str | None = None) -> StepResult:
        self.board = chess.Board(fen) if fen else chess.Board()
        self._ply_count = 0
        return StepResult(
            obs=board_to_tensor(self.board),
            legal_mask=legal_action_mask(self.board),
            reward=0.0,
            done=False,
            info={"fen": self.board.fen()},
        )

    def step(self, action_index: int) -> StepResult:
        legal_mask = legal_action_mask(self.board)
        if not legal_mask[action_index]:
            raise IllegalActionError(f"action {action_index} not legal in {self.board.fen()}")
        move = index_to_move(action_index)
        # The action-space `index_to_move` may return a move with `promotion=None`
        # even though the legal move on the board has `promotion=QUEEN` (auto-Q).
        # Reconcile by looking up the matching legal move.
        if move not in self.board.legal_moves:
            for m in self.board.legal_moves:
                if m.from_square == move.from_square and m.to_square == move.to_square:
                    if move.promotion is None and m.promotion is not None:
                        move = m
                        break
                    if move.promotion is not None and m.promotion == move.promotion:
                        move = m
                        break
        self.board.push(move)
        self._ply_count += 1

        done = self.board.is_game_over(claim_draw=True)
        truncated = self._ply_count >= self.max_plies
        reward = 0.0
        outcome: dict[str, object] = {"fen": self.board.fen(), "truncated": truncated}
        if done:
            result = self.board.result(claim_draw=True)
            outcome["result"] = result
            if result == "1-0":
                # +1 from the perspective of the side that just moved (white).
                reward = 1.0 if self.board.turn == chess.BLACK else -1.0
            elif result == "0-1":
                reward = 1.0 if self.board.turn == chess.WHITE else -1.0
            else:
                reward = 0.0
        elif truncated:
            done = True
            outcome["result"] = "*"

        return StepResult(
            obs=board_to_tensor(self.board),
            legal_mask=legal_action_mask(self.board),
            reward=reward,
            done=done,
            info=outcome,
        )
