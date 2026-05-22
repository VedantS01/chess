"""MLBot: a chesslab Bot backed by a trained ActorCritic checkpoint."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import chess
import torch

from chesslab.bots.base import Bot, register
from chesslab.engine import Game
from chesslab.rl.encoding import (
    board_to_tensor,
    index_to_move,
    legal_action_mask,
)
from chesslab.rl.networks import ActorCritic
from chesslab.rl.trainer import TrainerConfig


@register("ml")
class MLBot(Bot):
    name = "ml"

    def __init__(self, checkpoint: str | Path | None = None, deterministic: bool = True, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.deterministic = deterministic
        self.model: ActorCritic
        if checkpoint is None:
            # Untrained baseline (useful for tests).
            self.model = ActorCritic(channels=16, num_blocks=1)
        else:
            bundle = torch.load(Path(checkpoint), map_location="cpu", weights_only=False)
            cfg = TrainerConfig(**bundle["config"])
            self.model = ActorCritic(channels=cfg.channels, num_blocks=cfg.num_blocks)
            self.model.load_state_dict(bundle["state_dict"])
        self.model.eval()

    @classmethod
    def from_checkpoint(cls, path: str | Path) -> MLBot:
        return cls(checkpoint=path)

    def choose_move(self, game: Game, time_limit_s: float | None = None) -> chess.Move:
        board = game.board
        obs = torch.from_numpy(board_to_tensor(board)).unsqueeze(0)
        mask = torch.from_numpy(legal_action_mask(board)).unsqueeze(0)
        with torch.no_grad():
            action, _, _ = self.model.act(obs, mask, deterministic=self.deterministic)
        idx = int(action.item())
        candidate = index_to_move(idx)
        # Reconcile underpromotion ambiguity with the actual legal-move list.
        if candidate in board.legal_moves:
            return candidate
        for m in board.legal_moves:
            if m.from_square == candidate.from_square and m.to_square == candidate.to_square:
                if candidate.promotion is None and m.promotion is not None:
                    return m
                if candidate.promotion is not None and m.promotion == candidate.promotion:
                    return m
        # Fallback (shouldn't happen if mask is correct).
        return next(iter(board.legal_moves))


def serialize_config(cfg: TrainerConfig) -> dict[str, object]:
    """Re-exported for trainer code paths that need a stable serializer."""
    return asdict(cfg)
