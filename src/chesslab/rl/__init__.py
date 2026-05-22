"""RL framework public surface."""

from chesslab.rl.encoding import (
    ACTION_SIZE,
    INDEX_MOVE,
    MOVE_INDEX,
    NUM_PLANES,
    board_to_tensor,
    index_to_move,
    legal_action_mask,
    mirror_tensor,
    move_to_index,
)
from chesslab.rl.env import IllegalActionError, SelfPlayEnv, StepResult
from chesslab.rl.ml_bot import MLBot
from chesslab.rl.networks import ActorCritic
from chesslab.rl.trainer import Trainer, TrainerConfig, TrainingStats

__all__ = [
    "ACTION_SIZE",
    "ActorCritic",
    "INDEX_MOVE",
    "IllegalActionError",
    "MLBot",
    "MOVE_INDEX",
    "NUM_PLANES",
    "SelfPlayEnv",
    "StepResult",
    "Trainer",
    "TrainerConfig",
    "TrainingStats",
    "board_to_tensor",
    "index_to_move",
    "legal_action_mask",
    "mirror_tensor",
    "move_to_index",
]
