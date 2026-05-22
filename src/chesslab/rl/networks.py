"""ActorCritic network for chesslab RL bots.

Small shared conv trunk + a policy head over the full action space and a value
head with `tanh` output. CPU-friendly defaults so smoke training fits inside
CI budgets.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from chesslab.rl.encoding import ACTION_SIZE, NUM_PLANES


class ConvBlock(nn.Module):
    def __init__(self, channels: int) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm2d(channels)
        self.conv2 = nn.Conv2d(channels, channels, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm2d(channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = F.relu(self.bn1(self.conv1(x)))
        h = self.bn2(self.conv2(h))
        return F.relu(h + x)


class ActorCritic(nn.Module):
    def __init__(self, channels: int = 64, num_blocks: int = 4, action_size: int = ACTION_SIZE) -> None:
        super().__init__()
        self.channels = channels
        self.action_size = action_size
        self.stem = nn.Sequential(
            nn.Conv2d(NUM_PLANES, channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True),
        )
        self.trunk = nn.Sequential(*[ConvBlock(channels) for _ in range(num_blocks)])

        # Policy head: 1x1 conv -> flatten -> linear to action space.
        self.policy_conv = nn.Conv2d(channels, 32, kernel_size=1)
        self.policy_bn = nn.BatchNorm2d(32)
        self.policy_fc = nn.Linear(32 * 8 * 8, action_size)

        # Value head: 1x1 conv -> flatten -> linear -> tanh.
        self.value_conv = nn.Conv2d(channels, 4, kernel_size=1)
        self.value_bn = nn.BatchNorm2d(4)
        self.value_fc1 = nn.Linear(4 * 8 * 8, 64)
        self.value_fc2 = nn.Linear(64, 1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        h = self.stem(x)
        h = self.trunk(h)

        p = F.relu(self.policy_bn(self.policy_conv(h)))
        p = p.flatten(start_dim=1)
        policy_logits = self.policy_fc(p)

        v = F.relu(self.value_bn(self.value_conv(h)))
        v = v.flatten(start_dim=1)
        v = F.relu(self.value_fc1(v))
        value = torch.tanh(self.value_fc2(v)).squeeze(-1)

        return policy_logits, value

    @torch.no_grad()
    def act(
        self,
        obs: torch.Tensor,
        legal_mask: torch.Tensor,
        deterministic: bool = False,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Sample an action with legal-move masking.

        Returns `(action_idx, log_prob, value)` with batch dim preserved.
        """
        policy_logits, value = self.forward(obs)
        # Mask illegal moves with a very negative number.
        masked_logits = policy_logits.masked_fill(~legal_mask, -1e9)
        if deterministic:
            action = masked_logits.argmax(dim=-1)
        else:
            probs = F.softmax(masked_logits, dim=-1)
            action = torch.multinomial(probs, num_samples=1).squeeze(-1)
        log_probs = F.log_softmax(masked_logits, dim=-1)
        action_log_prob = log_probs.gather(-1, action.unsqueeze(-1)).squeeze(-1)
        return action, action_log_prob, value

    def evaluate_actions(
        self,
        obs: torch.Tensor,
        actions: torch.Tensor,
        legal_mask: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """For PPO updates: re-run forward, return log-prob of `actions`, entropy, value."""
        policy_logits, value = self.forward(obs)
        masked_logits = policy_logits.masked_fill(~legal_mask, -1e9)
        log_probs_all = F.log_softmax(masked_logits, dim=-1)
        action_log_prob = log_probs_all.gather(-1, actions.unsqueeze(-1)).squeeze(-1)
        # Entropy over only-legal entries (avoid -inf contributions).
        probs = log_probs_all.exp()
        entropy = -(probs * log_probs_all).where(legal_mask, torch.zeros_like(probs)).sum(dim=-1)
        return action_log_prob, entropy, value
