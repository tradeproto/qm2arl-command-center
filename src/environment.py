"""
TELPAIEnv: Geophysical / resource economy environment for QM2ARL.
Shared resources, time-varying regeneration, explore/extract/invest actions,
and prosperity equilibrium penalties.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np


# Action space: 0 = explore, 1 = extract, 2 = invest
EXPLORE = 0
EXTRACT = 1
INVEST = 2
NUM_ACTIONS = 3


@dataclass
class TELPAIEnvConfig:
    """Configuration for TELPAIEnv."""
    resource_budget: float = 1000.0
    max_steps: int = 200
    regen_period: float = 90.0  # time steps for one sinusoidal cycle
    regen_base: float = 5.0
    regen_amplitude: float = 3.0
    extract_rate: float = 10.0   # amount extracted per EXTRACT action
    invest_rate: float = 8.0    # amount added to pool per INVEST action
    explore_gain: float = 1.0   # small reward for explore (information value)
    prosperity_target: float = 500.0  # target resource level for equilibrium
    prosperity_penalty_scale: float = 0.01  # penalty per squared deviation
    prosperity_penalty_cap: float = 10.0  # max absolute penalty (stabilizes learning)
    prosperity_stability_bonus: float = 0.0  # bonus when resource near target (encourages hovering)
    prosperity_stability_band: float = 0.1   # band as fraction of budget (linear mode; ignored if sigma > 0)
    prosperity_stability_sigma: float = 0.0  # Gaussian width; if > 0, bonus = bonus * exp(-dev²/(2*sigma²)) (effective ±3*sigma)
    over_invest_drift_scale: float = 0.0     # optional: negative reward when resource > target (prevents runaway hoarding)
    invest_bonus: float = 0.0   # extra reward per INVEST (quick test: encourage investing)
    extract_penalty: float = 0.0  # subtract from EXTRACT reward (quick test: discourage over-extract)
    invest_reward_multiplier: float = 1.0   # scale invest reward (stronger signal when > 1)
    extract_reward_multiplier: float = 1.0  # scale extract reward (stronger signal when > 1)
    # Semantic harmony bonus (agent spec): 0.1 * Hμ, Hμ = 0.8*R_c + 0.1*A_n + 0.1*Ω
    semantic_harmony_scale: float = 0.1     # multiplier in front of Hμ (0 = disabled)
    semantic_harmony_omega: float = 1.0    # Ω in Hμ (e.g. future alignment term)


@dataclass
class StepResult:
    """Result of env.step() for one step (all agents)."""
    observations: np.ndarray   # (n_agents, obs_dim)
    rewards: np.ndarray        # (n_agents,)
    dones: np.ndarray         # (n_agents,) or scalar
    infos: list[dict[str, Any]] = field(default_factory=list)


class TELPAIEnv:
    """
    Resource economy environment with shared pool, time-varying regen,
    and prosperity equilibrium penalties.
    """

    def __init__(self, num_agents: int, config: TELPAIEnvConfig | None = None):
        self.num_agents = num_agents
        self.config = config or TELPAIEnvConfig()
        self._resource = float(self.config.resource_budget)
        self._step = 0
        # Observation: [resource_level_norm, time_phase, own_last_reward_norm]
        self.obs_dim = 3

    def reset(self, *, seed: int | None = None) -> tuple[np.ndarray, dict]:
        if seed is not None:
            np.random.seed(seed)
        self._resource = float(self.config.resource_budget)
        self._step = 0
        obs = self._get_observations()
        info = {"resource": self._resource, "step": self._step}
        return obs, info

    def _regen(self) -> float:
        """Time-varying regeneration amount."""
        t = self._step
        p = self.config.regen_period
        return self.config.regen_base + self.config.regen_amplitude * math.sin(
            2 * math.pi * t / max(p, 1e-6)
        )

    def _prosperity_penalty(self) -> float:
        """Penalty for deviation from prosperity target (equilibrium).
        Uses normalized deviation (dev / budget) so penalty scale is bounded and
        stable for REINFORCE; optional cap prevents runaway negative reward.
        """
        dev = self._resource - self.config.prosperity_target
        budget = max(self.config.resource_budget, 1e-6)
        dev_norm = dev / budget
        penalty = -self.config.prosperity_penalty_scale * (dev_norm ** 2)
        return max(penalty, -self.config.prosperity_penalty_cap)

    def _stability_bonus(self) -> float:
        """Bonus when resource is close to target. Gaussian mode (sigma>0): smooth peak at target, effective over ±3*sigma."""
        if self.config.prosperity_stability_bonus <= 0:
            return 0.0
        dev = self._resource - self.config.prosperity_target
        sigma = self.config.prosperity_stability_sigma
        if sigma > 0:
            return self.config.prosperity_stability_bonus * math.exp(-(dev ** 2) / (2.0 * sigma ** 2))
        budget = max(self.config.resource_budget, 1e-6)
        band = self.config.prosperity_stability_band * budget
        if abs(dev) >= band:
            return 0.0
        return self.config.prosperity_stability_bonus * (1.0 - abs(dev) / band)

    def _over_invest_drift(self) -> float:
        """Optional negative reward when resource exceeds target; discourages runaway over-investment."""
        if self.config.over_invest_drift_scale <= 0:
            return 0.0
        excess = self._resource - self.config.prosperity_target
        if excess <= 0:
            return 0.0
        budget = max(self.config.resource_budget, 1e-6)
        return -self.config.over_invest_drift_scale * (excess / budget)

    def _get_observations(self) -> np.ndarray:
        """Build observation matrix (num_agents, obs_dim)."""
        resource_norm = self._resource / max(self.config.resource_budget, 1e-6)
        phase = (self._step % max(int(self.config.regen_period), 1)) / max(
            self.config.regen_period, 1e-6
        )
        # Same global obs for all agents; last reward placeholder 0 at reset
        obs = np.tile(
            [resource_norm, phase, 0.0],
            (self.num_agents, 1),
        ).astype(np.float32)
        return obs

    def step(self, actions: np.ndarray) -> StepResult:
        """
        actions: (num_agents,) int array with values in {0, 1, 2}.
        """
        actions = np.asarray(actions, dtype=np.int32)
        assert actions.shape == (self.num_agents,), (
            f"Expected actions shape ({self.num_agents},), got {actions.shape}"
        )

        rewards = np.zeros(self.num_agents, dtype=np.float64)
        total_extract = 0.0
        total_invest = 0.0

        for i in range(self.num_agents):
            a = int(actions[i])
            if a == EXPLORE:
                rewards[i] = self.config.explore_gain
            elif a == EXTRACT:
                take = min(self.config.extract_rate, max(0, self._resource))
                self._resource -= take
                total_extract += take
                r = take - self.config.extract_penalty
                rewards[i] = r * self.config.extract_reward_multiplier
            elif a == INVEST:
                add = self.config.invest_rate
                self._resource += add
                total_invest += add
                r = self.config.invest_bonus
                rewards[i] = r * self.config.invest_reward_multiplier

        # Regeneration
        self._resource += self._regen()
        self._resource = max(0.0, self._resource)

        # Prosperity equilibrium: penalty for deviation + stability bonus (Gaussian or band) + optional over-invest drift
        penalty = self._prosperity_penalty()
        stability = self._stability_bonus()
        drift = self._over_invest_drift()
        rewards += (penalty + stability + drift) / self.num_agents

        # Semantic harmony bonus (agent spec): + 0.1 * Hμ, Hμ = 0.8*R_c + 0.1*A_n + 0.1*Ω
        if self.config.semantic_harmony_scale > 0:
            budget = max(self.config.resource_budget, 1e-6)
            R_c = max(0.0, 1.0 - abs(self._resource - self.config.prosperity_target) / budget)
            n_extract = int(np.sum(actions == EXTRACT))
            A_n = 1.0 - (n_extract / self.num_agents)
            Omega = self.config.semantic_harmony_omega
            H_mu = 0.8 * R_c + 0.1 * A_n + 0.1 * Omega
            rewards += self.config.semantic_harmony_scale * H_mu

        self._step += 1
        done = self._step >= self.config.max_steps
        dones = np.full(self.num_agents, done, dtype=bool)

        obs = self._get_observations()
        # Store last reward in obs for next step (simple convention: column 2)
        obs[:, 2] = rewards

        infos = [
            {
                "resource": self._resource,
                "step": self._step,
                "total_extract": total_extract,
                "total_invest": total_invest,
            }
            for _ in range(self.num_agents)
        ]

        return StepResult(observations=obs, rewards=rewards, dones=dones, infos=infos)

    @property
    def resource(self) -> float:
        return self._resource

    @property
    def current_step(self) -> int:
        return self._step
