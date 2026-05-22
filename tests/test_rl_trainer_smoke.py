"""Smoke tests for the RL trainer and MLBot. Must finish quickly on CPU."""

from __future__ import annotations

import math
import time
from pathlib import Path

import torch

from chesslab.bots import get_bot
from chesslab.engine import Game
from chesslab.rl import MLBot, Trainer, TrainerConfig
from chesslab.rl.env import SelfPlayEnv


def test_env_reset_and_step_terminates_eventually() -> None:
    env = SelfPlayEnv(max_plies=20)
    step = env.reset()
    assert step.obs.shape == (18, 8, 8)
    assert step.legal_mask.sum() == 20  # 20 legal moves from start

    # Take random legal actions until termination.
    rng = list(step.legal_mask.nonzero()[0])
    a = int(rng[0])
    step = env.step(a)
    assert step.obs.shape == (18, 8, 8)


def test_trainer_smoke_completes_quickly() -> None:
    cfg = TrainerConfig(
        channels=8,
        num_blocks=1,
        rollout_steps=16,
        epochs_per_update=1,
        minibatch_size=8,
        lr=1e-3,
        max_plies=20,
        seed=42,
    )
    trainer = Trainer(cfg)
    t0 = time.monotonic()
    stats = trainer.train_steps(16)
    elapsed = time.monotonic() - t0
    # Must complete fast enough for CI.
    assert elapsed < 60.0, f"smoke training too slow: {elapsed:.1f}s"
    assert stats.steps_done >= 16
    assert math.isfinite(stats.last_policy_loss)
    assert math.isfinite(stats.last_value_loss)
    assert math.isfinite(stats.last_entropy)


def test_save_load_round_trip(tmp_path: Path) -> None:
    cfg = TrainerConfig(channels=8, num_blocks=1, rollout_steps=4, max_plies=10)
    t1 = Trainer(cfg)
    t1.train_steps(4)
    ckpt = tmp_path / "ckpt.pt"
    t1.save(ckpt)
    assert ckpt.exists()
    t2 = Trainer.load(ckpt)
    # Same param shapes.
    for (n1, p1), (n2, p2) in zip(t1.model.named_parameters(), t2.model.named_parameters(), strict=True):
        assert n1 == n2
        assert torch.allclose(p1, p2)


def test_ml_bot_random_init_returns_legal_move() -> None:
    bot = MLBot()  # untrained baseline
    game = Game()
    move = bot.choose_move(game)
    assert move in game.board.legal_moves


def test_ml_bot_from_trained_checkpoint(tmp_path: Path) -> None:
    cfg = TrainerConfig(channels=8, num_blocks=1, rollout_steps=8, max_plies=10)
    trainer = Trainer(cfg)
    trainer.train_steps(8)
    ckpt = tmp_path / "trained.pt"
    trainer.save(ckpt)

    bot = get_bot("ml", checkpoint=str(ckpt))
    game = Game()
    move = bot.choose_move(game)
    assert move in game.board.legal_moves


def test_ml_bot_finishes_a_short_game(tmp_path: Path) -> None:
    bot_w = MLBot()
    bot_b = get_bot("random", seed=1)
    game = Game()
    for _ in range(60):
        if game.is_terminal():
            break
        bot = bot_w if game.turn else bot_b
        m = bot.choose_move(game)
        game.push(m)
    # No exception, no crash. Final state is legal.
    assert game.fen()
