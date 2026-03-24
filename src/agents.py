"""
QuantumGrokAgent: agent with suggest_coupling_topology for QM2ARL.
Policies can be swapped (dummy first, Grok later).
"""
from __future__ import annotations

import re
from typing import Any

import networkx as nx
import numpy as np

# Optional W&B Weave for tracing (prompt/response, parse success); no-op if weave not installed
try:
    import weave
    _weave_op = weave.op
except ImportError:
    _weave_op = lambda f: f  # no-op decorator


@_weave_op
def parse_topology_response_to_graph(response_text: str, num_agents: int) -> nx.Graph:
    """
    Parse Grok's 5-point topology response into a NetworkX graph.

    Placeholder: looks for point 3 ("which pairs/groups have stronger coupling")
    by scanning for pairs of agent indices (e.g. "agent 0 and 1", "0-1", "(2,3)").
    Can be made smarter later with regex or another Grok call.

    Returns a graph with nodes 0..num_agents-1. If no pairs are found, returns
    an empty graph (caller can fall back to suggest_coupling_topology()).
    """
    G = nx.Graph()
    G.add_nodes_from(range(num_agents))

    # Placeholder: find digit pairs that could be (i, j) agent indices
    # Match "0 and 1", "0-1", "(0, 1)", "0, 1", "agents 0, 1", "pair 2-3", etc.
    pair_pattern = re.compile(
        r"\b(\d+)\s*[-,\s and]+\s*(\d+)\b",
        re.IGNORECASE,
    )
    seen = set()
    for m in pair_pattern.finditer(response_text):
        i, j = int(m.group(1)), int(m.group(2))
        if i == j or i < 0 or j < 0 or i >= num_agents or j >= num_agents:
            continue
        edge = (min(i, j), max(i, j))
        if edge not in seen:
            seen.add(edge)
            G.add_edge(edge[0], edge[1])

    if G.number_of_edges() == 0:
        # Caller will use fallback (e.g. ring); log for debugging / parse success rate
        G.graph["parse_fallback"] = True
        print("[parse_topology_response_to_graph] No edges parsed → fallback topology will be used.")
    else:
        G.graph["parse_fallback"] = False
    return G


class QuantumGrokAgent:
    """
    Agent that can suggest coupling topology for multi-qubit systems
    and act in TELPAIEnv. Policy is pluggable (dummy or Grok-based).
    """

    def __init__(
        self,
        agent_id: int,
        num_agents: int,
        obs_dim: int = 3,
        num_actions: int = 3,
        sparsity_target: float = 0.3,
        max_hops: int = 3,
        memory_capacity: int = 1000,
    ):
        self.agent_id = agent_id
        self.num_agents = num_agents
        self.obs_dim = obs_dim
        self.num_actions = num_actions
        self.sparsity_target = sparsity_target
        self.max_hops = max_hops
        self.engram = ENGRAMENGN(memory_capacity=memory_capacity)

    @_weave_op
    def suggest_coupling_topology(self) -> nx.Graph:
        """
        Suggest a coupling graph for multi-agent / multi-qubit coordination.
        Returns a NetworkX graph with nodes 0..num_agents-1 and edges
        representing preferred coupling. Default: sparse, limited hops.
        """
        n = self.num_agents
        G = nx.Graph()
        G.add_nodes_from(range(n))
        max_edges = max(0, int(0.5 * n * (n - 1) * self.sparsity_target))
        added = 0
        # Prefer short-range couplings (within max_hops in ring)
        for i in range(n):
            for h in range(1, self.max_hops + 1):
                if added >= max_edges:
                    break
                j = (i + h) % n
                if not G.has_edge(i, j):
                    G.add_edge(i, j)
                    added += 1
        return G

    def act(self, obs: np.ndarray, deterministic: bool = True) -> int:
        """
        Choose action from observation. Override or replace with policy.
        Default: dummy policy (round-robin or random).
        """
        # Dummy: use resource level (obs[0]) — low resource -> invest, else extract/explore
        resource_norm = float(obs[0]) if obs.size else 0.5
        if resource_norm < 0.3:
            return 2  # invest
        if resource_norm > 0.7:
            return 1  # extract
        return 0  # explore

    def act_batch(self, observations: np.ndarray, deterministic: bool = True) -> np.ndarray:
        """Vectorized: (n_agents, obs_dim) -> (n_agents,) actions for this agent's slice."""
        # Single agent: one obs row
        return np.array([self.act(observations[self.agent_id], deterministic=deterministic)])


def dummy_policy(obs: np.ndarray, agent_id: int, num_actions: int = 3) -> int:
    """
    Standalone dummy policy for training loop: map obs to action.
    Used when not using QuantumGrokAgent.act.
    """
    resource_norm = float(obs[0]) if obs.size else 0.5
    if resource_norm < 0.3:
        return 2
    if resource_norm > 0.7:
        return 1
    return 0


class ENGRAMENGN:
    """
    Memory buffer with Hμ-based pruning for semantic harmony.
    Keeps high-Hμ (state, action, reward, next_state, hmu) tuples; prunes low-Hμ when over capacity.
    """

    def __init__(self, memory_capacity: int = 1000, prune_threshold: float = 0.5):
        self.memory_capacity = memory_capacity
        self.prune_threshold = prune_threshold  # prune low Hμ memories
        self.memory_buffer: list[tuple[Any, Any, float, Any, float]] = []  # (state, action, reward, next_state, hmu)

    def add_memory(self, state: Any, action: Any, reward: float, next_state: Any, hmu: float) -> None:
        self.memory_buffer.append((state, action, reward, next_state, hmu))
        if len(self.memory_buffer) > self.memory_capacity:
            self.prune()

    def prune(self) -> None:
        if not self.memory_buffer:
            return
        sorted_mem = sorted(self.memory_buffer, key=lambda x: x[4])  # sort by hmu
        keep_num = int(self.memory_capacity * 0.8)
        self.memory_buffer = sorted_mem[-keep_num:]
        print(f"ENGRAM-ENGN pruned: kept {len(self.memory_buffer)} / {self.memory_capacity} memories")

    def refresh_context(self) -> list[tuple[Any, Any, float, Any, float]]:
        """Top recent memories for future policy boost."""
        return self.memory_buffer[-10:]
