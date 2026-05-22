"""PPO-lite actor-critic trainer for chesslab.

CPU-friendly defaults; small rollouts. Supports self-play and (later) play vs
fixed opponents. Checkpoints are plain `torch.save({"state_dict": ..., "config": ...})`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from chesslab.rl.env import SelfPlayEnv
from chesslab.rl.networks import ActorCritic


@dataclass
class TrainerConfig:
    channels: int = 32
    num_blocks: int = 2
    rollout_steps: int = 128
    epochs_per_update: int = 2
    minibatch_size: int = 32
    lr: float = 1e-3
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_ratio: float = 0.2
    value_coef: float = 0.5
    entropy_coef: float = 0.01
    max_grad_norm: float = 1.0
    max_plies: int = 200
    device: str = "cpu"
    seed: int = 0


@dataclass
class TrainingStats:
    steps_done: int = 0
    updates: int = 0
    last_policy_loss: float = float("nan")
    last_value_loss: float = float("nan")
    last_entropy: float = float("nan")
    losses: list[float] = field(default_factory=list)


class Trainer:
    def __init__(self, config: TrainerConfig | None = None) -> None:
        self.config = config or TrainerConfig()
        torch.manual_seed(self.config.seed)
        np.random.seed(self.config.seed)
        self.device = torch.device(self.config.device)
        self.model = ActorCritic(
            channels=self.config.channels, num_blocks=self.config.num_blocks
        ).to(self.device)
        self.optim = torch.optim.Adam(self.model.parameters(), lr=self.config.lr)
        self.env = SelfPlayEnv(max_plies=self.config.max_plies)
        self.stats = TrainingStats()

    # ---- rollout collection ----
    def collect_rollout(self) -> dict[str, torch.Tensor]:
        obs_buf: list[np.ndarray] = []
        mask_buf: list[np.ndarray] = []
        actions: list[int] = []
        logps: list[float] = []
        values: list[float] = []
        rewards: list[float] = []
        dones: list[bool] = []

        step = self.env.reset()
        self.model.eval()
        for _ in range(self.config.rollout_steps):
            obs_t = torch.from_numpy(step.obs).unsqueeze(0).to(self.device)
            mask_t = torch.from_numpy(step.legal_mask).unsqueeze(0).to(self.device)

            with torch.no_grad():
                action, logp, value = self.model.act(obs_t, mask_t, deterministic=False)
            a = int(action.item())

            obs_buf.append(step.obs)
            mask_buf.append(step.legal_mask)
            actions.append(a)
            logps.append(float(logp.item()))
            values.append(float(value.item()))

            step = self.env.step(a)
            rewards.append(step.reward)
            dones.append(step.done)
            if step.done:
                step = self.env.reset()

        # Bootstrap value for the last partial state.
        with torch.no_grad():
            last_obs = torch.from_numpy(step.obs).unsqueeze(0).to(self.device)
            _, last_value = self.model.forward(last_obs)
        last_value = float(last_value.item())

        advantages, returns = self._gae(rewards, values, dones, last_value)

        return {
            "obs": torch.from_numpy(np.stack(obs_buf)).to(self.device),
            "mask": torch.from_numpy(np.stack(mask_buf)).to(self.device),
            "actions": torch.tensor(actions, dtype=torch.long, device=self.device),
            "old_logps": torch.tensor(logps, dtype=torch.float32, device=self.device),
            "returns": torch.tensor(returns, dtype=torch.float32, device=self.device),
            "advantages": torch.tensor(advantages, dtype=torch.float32, device=self.device),
        }

    def _gae(
        self,
        rewards: list[float],
        values: list[float],
        dones: list[bool],
        last_value: float,
    ) -> tuple[list[float], list[float]]:
        gamma = self.config.gamma
        lam = self.config.gae_lambda
        advs: list[float] = [0.0] * len(rewards)
        gae = 0.0
        for t in reversed(range(len(rewards))):
            next_value = last_value if t == len(rewards) - 1 else values[t + 1]
            mask = 0.0 if dones[t] else 1.0
            delta = rewards[t] + gamma * next_value * mask - values[t]
            gae = delta + gamma * lam * mask * gae
            advs[t] = gae
        returns = [a + v for a, v in zip(advs, values, strict=True)]
        # Normalize advantages.
        if len(advs) > 1:
            mean = float(np.mean(advs))
            std = float(np.std(advs)) + 1e-8
            advs = [(a - mean) / std for a in advs]
        return advs, returns

    # ---- PPO update ----
    def update(self, batch: dict[str, torch.Tensor]) -> None:
        n = batch["obs"].shape[0]
        idx_all = np.arange(n)
        for _ in range(self.config.epochs_per_update):
            np.random.shuffle(idx_all)
            for start in range(0, n, self.config.minibatch_size):
                idx = idx_all[start : start + self.config.minibatch_size]
                obs = batch["obs"][idx]
                mask = batch["mask"][idx]
                actions = batch["actions"][idx]
                old_logps = batch["old_logps"][idx]
                returns = batch["returns"][idx]
                advantages = batch["advantages"][idx]

                self.model.train()
                logps, entropy, values = self.model.evaluate_actions(obs, actions, mask)
                ratio = torch.exp(logps - old_logps)
                clipped = torch.clamp(ratio, 1.0 - self.config.clip_ratio, 1.0 + self.config.clip_ratio)
                policy_loss = -torch.min(ratio * advantages, clipped * advantages).mean()
                value_loss = F.mse_loss(values, returns)
                ent = entropy.mean()
                loss = policy_loss + self.config.value_coef * value_loss - self.config.entropy_coef * ent

                self.optim.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config.max_grad_norm)
                self.optim.step()

                self.stats.last_policy_loss = float(policy_loss.item())
                self.stats.last_value_loss = float(value_loss.item())
                self.stats.last_entropy = float(ent.item())
                self.stats.losses.append(float(loss.item()))

    def train_steps(self, steps: int) -> TrainingStats:
        """Train for `steps` total environment steps (approximate)."""
        target = self.stats.steps_done + steps
        while self.stats.steps_done < target:
            batch = self.collect_rollout()
            self.update(batch)
            self.stats.steps_done += self.config.rollout_steps
            self.stats.updates += 1
        return self.stats

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "state_dict": self.model.state_dict(),
                "config": asdict(self.config),
                "stats": asdict(self.stats),
            },
            path,
        )

    @classmethod
    def load(cls, path: str | Path) -> Trainer:
        bundle = torch.load(Path(path), map_location="cpu", weights_only=False)
        cfg = TrainerConfig(**bundle["config"])
        trainer = cls(cfg)
        trainer.model.load_state_dict(bundle["state_dict"])
        return trainer
