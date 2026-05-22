"""`chesslab train` subcommand."""

from __future__ import annotations

import argparse
from pathlib import Path


def train_command(args: argparse.Namespace) -> int:
    from chesslab.rl.trainer import Trainer, TrainerConfig

    cfg = TrainerConfig(
        channels=args.channels,
        num_blocks=args.blocks,
        rollout_steps=args.rollout_steps,
        epochs_per_update=args.epochs,
        minibatch_size=args.minibatch,
        lr=args.lr,
        max_plies=args.max_plies,
        seed=args.seed,
    )
    trainer = Trainer(cfg)
    print(f"Training for {args.steps} steps; cfg={cfg}")
    stats = trainer.train_steps(args.steps)
    print(f"steps_done={stats.steps_done} updates={stats.updates} "
          f"last_policy_loss={stats.last_policy_loss:.4f} "
          f"last_value_loss={stats.last_value_loss:.4f} "
          f"last_entropy={stats.last_entropy:.4f}")
    out_path = Path(args.checkpoint)
    trainer.save(out_path)
    print(f"checkpoint -> {out_path}")
    return 0


def add_train_subparser(sub: argparse._SubParsersAction) -> None:
    train = sub.add_parser("train", help="Train an actor-critic RL bot via self-play.")
    train.add_argument("--steps", type=int, default=256, help="env steps to collect")
    train.add_argument("--checkpoint", required=True, help="path to write .pt checkpoint")
    train.add_argument("--channels", type=int, default=32)
    train.add_argument("--blocks", type=int, default=2)
    train.add_argument("--rollout-steps", type=int, default=128)
    train.add_argument("--epochs", type=int, default=2)
    train.add_argument("--minibatch", type=int, default=32)
    train.add_argument("--lr", type=float, default=1e-3)
    train.add_argument("--max-plies", type=int, default=200)
    train.add_argument("--seed", type=int, default=0)
    train.set_defaults(func=train_command)
