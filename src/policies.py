"""
Learnable policies for QM2ARL: MLP policy with REINFORCE (policy gradient).
Replaces dummy policy so agents can improve rewards over episodes.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

# Optional Numba JIT for the discounted-returns hot loop (the "compiler" lever).
# Falls back to a vectorized NumPy path if numba is not installed — identical math.
try:
    from numba import njit

    @njit(cache=True, fastmath=True)
    def _discounted_returns_njit(rewards: np.ndarray, gamma: float) -> np.ndarray:  # pragma: no cover
        T, n = rewards.shape
        out = np.zeros((T, n), dtype=np.float64)
        for i in range(n):
            R = 0.0
            for t in range(T - 1, -1, -1):
                R = rewards[t, i] + gamma * R
                out[t, i] = R
        return out

    _HAS_NUMBA = True
except Exception:  # numba missing or failed to import
    _discounted_returns_njit = None
    _HAS_NUMBA = False


def discounted_returns(rewards: np.ndarray, gamma: float) -> np.ndarray:
    """
    Per-agent discounted returns R[t,i] = sum_{k>=t} gamma^(k-t) * reward[k,i].
    Uses the Numba-compiled kernel when available, else a vectorized reverse
    scan in NumPy (no Python per-element loop). Both give identical results.
    """
    rewards = np.ascontiguousarray(rewards, dtype=np.float64)
    if _HAS_NUMBA and _discounted_returns_njit is not None:
        return _discounted_returns_njit(rewards, float(gamma))
    T = rewards.shape[0]
    out = np.empty_like(rewards)
    R = np.zeros(rewards.shape[1], dtype=np.float64)
    for t in range(T - 1, -1, -1):  # T steps, each a vectorized op over agents
        R = rewards[t] + gamma * R
        out[t] = R
    return out


class MLPPolicy(nn.Module):
    """
    Shared MLP policy for all agents: obs -> logits over actions.
    Used with topology-extended obs (own + mean neighbor) or raw obs.
    """

    def __init__(
        self,
        obs_dim: int,
        num_actions: int = 3,
        hidden_dims: tuple[int, ...] = (64, 32),
        seed: int | None = None,
    ):
        super().__init__()
        if seed is not None:
            torch.manual_seed(seed)
        self.obs_dim = obs_dim
        self.num_actions = num_actions
        dims = [obs_dim] + list(hidden_dims) + [num_actions]
        layers = []
        for i in range(len(dims) - 1):
            layers.append(nn.Linear(dims[i], dims[i + 1]))
            if i < len(dims) - 2:
                layers.append(nn.ReLU())
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (batch, obs_dim) -> (batch, num_actions) logits."""
        return self.net(x)

    def logits_and_log_probs(
        self, obs: np.ndarray, actions: np.ndarray
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Batch: obs (B, obs_dim), actions (B,) int -> logits, log_prob per action."""
        obs_t = torch.as_tensor(obs, dtype=torch.float32)
        logits = self.forward(obs_t)
        log_probs = F.log_softmax(logits, dim=-1)
        actions_t = torch.as_tensor(actions, dtype=torch.long)
        chosen_log_probs = log_probs.gather(-1, actions_t.unsqueeze(-1)).squeeze(-1)
        return logits, chosen_log_probs

    def sample_actions(
        self, obs: np.ndarray, deterministic: bool = False
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        obs: (n_agents, obs_dim). Returns actions (n_agents,) int, log_probs (n_agents,).
        """
        with torch.no_grad():
            obs_t = torch.as_tensor(obs, dtype=torch.float32)
            logits = self.forward(obs_t)
            probs = F.softmax(logits, dim=-1)
            if deterministic:
                actions = logits.argmax(dim=-1)
            else:
                dist = torch.distributions.Categorical(probs=probs)
                actions = dist.sample()
            log_probs = F.log_softmax(logits, dim=-1).gather(
                -1, actions.unsqueeze(-1)
            ).squeeze(-1)
            return actions.numpy(), log_probs.numpy()

    def mean_normalized_entropy(self, obs: np.ndarray) -> float:
        """
        Mean entropy / log(n_actions) in [0, 1] over agents — quantum-inspired
        uncertainty dial (simulation metaphor, not hardware).
        """
        with torch.no_grad():
            obs_t = torch.as_tensor(obs, dtype=torch.float32)
            logits = self.forward(obs_t)
            logp = F.log_softmax(logits, dim=-1)
            p = logp.exp()
            h = -(p * logp).sum(dim=-1)
            h_max = math.log(max(self.num_actions, 2))
            return float((h / h_max).mean().cpu())


class SharedTrunkPerAgentHeadPolicy(nn.Module):
    """
    Shared representation + one linear head per agent (logits differ by agent ID).
    Training batches are (T * n_agents,) rows in time-major order: row index r
    corresponds to agent r % n_agents.
    """

    def __init__(
        self,
        obs_dim: int,
        num_agents: int,
        num_actions: int = 3,
        hidden_dims: tuple[int, ...] = (64, 32),
        seed: int | None = None,
    ):
        super().__init__()
        if seed is not None:
            torch.manual_seed(seed)
        self.obs_dim = obs_dim
        self.num_agents = num_agents
        self.num_actions = num_actions
        dims = [obs_dim] + list(hidden_dims)
        layers: list[nn.Module] = []
        for i in range(len(dims) - 1):
            layers.append(nn.Linear(dims[i], dims[i + 1]))
            layers.append(nn.ReLU())
        self.trunk = nn.Sequential(*layers)
        h_last = hidden_dims[-1]
        self.heads = nn.ModuleList(
            [nn.Linear(h_last, num_actions) for _ in range(num_agents)]
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, obs_dim) -> (B, num_actions); agent id = row index % num_agents."""
        z = self.trunk(x)
        B = z.shape[0]
        device, dtype = z.device, z.dtype
        agent_idx = torch.arange(B, device=device) % self.num_agents
        logits = torch.zeros(B, self.num_actions, device=device, dtype=dtype)
        for i in range(self.num_agents):
            mask = agent_idx == i
            if mask.any():
                logits[mask] = self.heads[i](z[mask])
        return logits

    def logits_and_log_probs(
        self, obs: np.ndarray, actions: np.ndarray
    ) -> tuple[torch.Tensor, torch.Tensor]:
        obs_t = torch.as_tensor(obs, dtype=torch.float32)
        logits = self.forward(obs_t)
        log_probs = F.log_softmax(logits, dim=-1)
        actions_t = torch.as_tensor(actions, dtype=torch.long)
        chosen_log_probs = log_probs.gather(-1, actions_t.unsqueeze(-1)).squeeze(-1)
        return logits, chosen_log_probs

    def sample_actions(
        self, obs: np.ndarray, deterministic: bool = False
    ) -> tuple[np.ndarray, np.ndarray]:
        with torch.no_grad():
            obs_t = torch.as_tensor(obs, dtype=torch.float32)
            logits = self.forward(obs_t)
            probs = F.softmax(logits, dim=-1)
            if deterministic:
                actions = logits.argmax(dim=-1)
            else:
                dist = torch.distributions.Categorical(probs=probs)
                actions = dist.sample()
            log_probs = F.log_softmax(logits, dim=-1).gather(
                -1, actions.unsqueeze(-1)
            ).squeeze(-1)
            return actions.numpy(), log_probs.numpy()

    def mean_normalized_entropy(self, obs: np.ndarray) -> float:
        with torch.no_grad():
            obs_t = torch.as_tensor(obs, dtype=torch.float32)
            logits = self.forward(obs_t)
            logp = F.log_softmax(logits, dim=-1)
            p = logp.exp()
            h = -(p * logp).sum(dim=-1)
            h_max = math.log(max(self.num_actions, 2))
            return float((h / h_max).mean().cpu())


def reinforce_update(
    policy: nn.Module,
    optimizer: torch.optim.Optimizer,
    obs_list: list[np.ndarray],
    action_list: list[np.ndarray],
    reward_list: list[np.ndarray],
    gamma: float = 0.99,
    baseline: float | None = None,
    normalize_returns: bool = True,
    return_clip: float | None = None,
) -> dict[str, float]:
    """
    One REINFORCE update from a single episode trajectory.
    obs_list[t], action_list[t], reward_list[t] each (n_agents,).
    Uses per-agent returns: R_i = sum_t gamma^t reward_i(t). Baseline = mean return.
    If return_clip > 0, clip advantages to [-return_clip, return_clip] per episode.
    """
    T = len(reward_list)
    n_agents = reward_list[0].shape[0]
    # Compute per-agent returns (discounted, from each t) — JIT/vectorized.
    rewards_arr = np.stack([np.asarray(r, dtype=np.float64) for r in reward_list], axis=0)
    returns = discounted_returns(rewards_arr, gamma)

    if baseline is None:
        baseline = float(np.mean(returns))
    mean_return_raw = float(np.mean(returns))
    returns = returns - baseline
    if return_clip is not None and return_clip > 0:
        returns = np.clip(returns, -return_clip, return_clip)
    if normalize_returns:
        ret_flat = returns.ravel()
        ret_std = max(np.std(ret_flat), 1e-8)
        returns = returns / ret_std

    # Concatenate all steps and agents into one batch
    obs_batch = np.concatenate(obs_list, axis=0)   # (T*n_agents, obs_dim)
    action_batch = np.concatenate(action_list, axis=0)
    returns_batch = returns.ravel()  # (T*n_agents,)

    _, log_probs = policy.logits_and_log_probs(obs_batch, action_batch)
    returns_t = torch.as_tensor(returns_batch, dtype=torch.float32)
    loss = -(log_probs * returns_t).mean()
    optimizer.zero_grad()
    loss.backward()
    torch.nn.utils.clip_grad_norm_(policy.parameters(), max_norm=1.0)
    optimizer.step()

    return {"loss": loss.item(), "mean_return": mean_return_raw}
