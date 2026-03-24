"""
QM2ARL training loop: multi-agent training with TELPAIEnv.
Integrates Grok coupling topology (neighbor-obs aggregation) and learned MLP policy
with REINFORCE when learning=True.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

import numpy as np
import networkx as nx

from src.environment import TELPAIEnv, TELPAIEnvConfig, StepResult, EXTRACT
from src.agents import ENGRAMENGN, QuantumGrokAgent, dummy_policy, parse_topology_response_to_graph
from src.policies import MLPPolicy, reinforce_update

# xAI Grok API (OpenAI-compatible)
XAI_CHAT_URL = "https://api.x.ai/v1/chat/completions"
DEFAULT_GROK_MODEL = "grok-2"

# Optional W&B Weave for tracing Grok calls (prompt/response, latency); no-op if weave not installed
try:
    import weave
    _weave_op = weave.op
except ImportError:
    _weave_op = lambda f: f  # no-op


@_weave_op
def _fetch_grok_topology_response(num_agents: int, config: dict[str, Any]) -> str | None:
    """
    Call Grok (xAI) API to get a 5-point topology recommendation; return raw response text.
    Requires use_grok_topology: true and grok_api_key in config or XAI_API_KEY in env.
    Returns None if disabled, no key, or on request error (then fallback to config text or ring).
    """
    if not config.get("use_grok_topology", False):
        return None
    api_key = config.get("grok_api_key") or os.environ.get("XAI_API_KEY")
    if not api_key:
        return None
    model = config.get("grok_model", DEFAULT_GROK_MODEL)
    prompt = (
        f"You are recommending a coupling topology for a multi-agent resource economy with {num_agents} agents (IDs 0 to {num_agents - 1}). "
        "Reply in exactly 5 short points. "
        "Point 3 must state which pairs or groups have stronger coupling (e.g. 'Agents 0 and 1, agents 2 and 3' or '0-1, 2-3'). "
        "Use clear pair notation so a parser can extract edges (e.g. '0 and 1', '2-3'). "
        "Keep the rest of the points brief (sparsity, rationale, etc.)."
    )
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 500,
        "temperature": 0.3,
    }
    try:
        req = urllib.request.Request(
            XAI_CHAT_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content")
        return content.strip() if isinstance(content, str) and content.strip() else None
    except Exception:
        return None


def calculate_hmu(
    resource: float,
    prosperity_target: float,
    resource_budget: float,
    num_extract: int,
    num_agents: int,
    omega: float = 1.0,
) -> float:
    """Hμ = 0.8*R_c + 0.1*A_n + 0.1*Ω (semantic harmony metric from env spec)."""
    budget = max(resource_budget, 1e-6)
    R_c = max(0.0, 1.0 - abs(resource - prosperity_target) / budget)
    A_n = 1.0 - (num_extract / max(num_agents, 1))
    return 0.8 * R_c + 0.1 * A_n + 0.1 * omega


def topology_extended_obs(obs: np.ndarray, G: nx.Graph) -> np.ndarray:
    """
    Extend observations using Grok coupling graph: each agent sees [own_obs, mean_neighbor_obs].
    obs: (n_agents, obs_dim). Returns (n_agents, 2*obs_dim). No neighbors -> mean_neighbor = 0.
    """
    n, obs_dim = obs.shape
    ext = np.zeros((n, 2 * obs_dim), dtype=np.float32)
    ext[:, :obs_dim] = obs
    for i in range(n):
        neighbors = list(G.neighbors(i))
        if neighbors:
            ext[i, obs_dim:] = np.mean(obs[neighbors], axis=0)
    return ext


def run_multi_agent_training(
    num_agents: int,
    config: TELPAIEnvConfig | dict[str, Any],
    *,
    use_agents: bool = True,
    seed: int | None = None,
    learning: bool = False,
    num_episodes: int = 50,
    use_topology: bool = True,
    learning_rate: float = 1e-3,
    gamma: float = 0.99,
) -> dict[str, Any]:
    """
    Run multi-agent training with TELPAIEnv.
    config: TELPAIEnvConfig or raw dict (e.g. from YAML). If dict, env and
    agent knobs (sparsity_target, max_hops) are read from it.

    If learning=False: single rollout with dummy or existing policy; returns
    rewards_per_step, resource_trajectory, mean_reward for that run.

    If learning=True: num_episodes of rollouts with Grok coupling topology
    (each agent sees [own_obs, mean_neighbor_obs]) and a shared MLP policy
    updated with REINFORCE. Returns same keys plus training_rewards_per_episode
    and (on last episode) rewards_per_step, resource_trajectory.
    """
    if isinstance(config, dict):
        env_config = env_config_from_dict(config)
        agent_kwargs = agent_kwargs_from_dict(config)
    else:
        env_config = config
        agent_kwargs = {}

    env = TELPAIEnv(num_agents=num_agents, config=env_config)
    memory_capacity = int(config.get("memory_capacity", 1000)) if isinstance(config, dict) else 1000
    prune_threshold = float(config.get("prune_threshold", 0.5)) if isinstance(config, dict) else 0.5
    engrams = [ENGRAMENGN(memory_capacity=memory_capacity, prune_threshold=prune_threshold) for _ in range(num_agents)]
    agents = [
        QuantumGrokAgent(
            agent_id=i,
            num_agents=num_agents,
            obs_dim=env.obs_dim,
            num_actions=3,
            **agent_kwargs,
        )
        for i in range(num_agents)
    ]

    if learning:
        # Allow config dict to override learning knobs
        if isinstance(config, dict):
            num_episodes = int(config.get("num_episodes", num_episodes))
            use_topology = config.get("use_topology", use_topology)
            learning_rate = float(config.get("learning_rate", learning_rate))
            gamma = float(config.get("gamma", gamma))
            reward_scale = float(config.get("reward_scale", 0.01))
            reward_clip = float(config.get("reward_clip", 10.0))
            return_clip = float(config.get("return_clip", 0.0)) or None  # 0 = no clip
            epsilon_start = float(config.get("epsilon_start", 1.0))
            epsilon_end = float(config.get("epsilon_end", 0.05))
            epsilon_decay_episodes = int(config.get("epsilon_decay_episodes", 0))  # 0 = use 80% of num_episodes
            use_wandb = config.get("use_wandb", False)
            wandb_project = config.get("wandb_project", "qm2arl")
            wandb_entity = config.get("wandb_entity", None)
        else:
            reward_scale = 0.01
            reward_clip = 10.0
            return_clip = None
            epsilon_start = 1.0
            epsilon_end = 0.05
            epsilon_decay_episodes = 0
            use_wandb = False
            wandb_project = "qm2arl"
            wandb_entity = None
        # Topology: from live Grok call (if use_grok_topology + API key), or from config text, else fallback ring
        topology_graph = None
        if use_topology and isinstance(config, dict):
            raw = None
            from_grok = False
            if config.get("use_grok_topology", False):
                raw = _fetch_grok_topology_response(num_agents, config)
                from_grok = isinstance(raw, str) and bool(raw.strip())
            if not (isinstance(raw, str) and raw.strip()):
                raw = config.get("grok_topology_response") or config.get("topology_response_text")
            if isinstance(raw, str) and raw.strip():
                topology_graph = parse_topology_response_to_graph(raw.strip(), num_agents)
                if topology_graph.number_of_edges() == 0:
                    topology_graph = agents[0].suggest_coupling_topology()
                if from_grok:
                    print("\n--- Grok topology response (5-point) ---")
                    print(raw.strip())
                    print("Parsed edges:", sorted(topology_graph.edges()))
                    print("---\n")
            if topology_graph is None:
                topology_graph = agents[0].suggest_coupling_topology()

        wandb_run = None
        if use_wandb:
            import wandb
            run_existed = wandb.run is not None  # e.g. sweep or simulation already inited
            if not run_existed:
                exp_name = config.get("experiment_name", "default") if isinstance(config, dict) else "default"
                run_name = f"telpai-n{num_agents}-{exp_name}"
                if seed is not None:
                    run_name = f"{run_name}-seed{seed}"
                os.makedirs("results/wandb", exist_ok=True)
                wandb_run = wandb.init(
                    project=wandb_project or "telpai-quantum",
                    entity=wandb_entity,
                    name=run_name,
                    config=config if isinstance(config, dict) else {},
                    dir="results/wandb",
                    settings=wandb.Settings(_disable_stats=True),
                )
            c = config if isinstance(config, dict) else {}
            if not run_existed:
                # Log key knobs for search/filter (skip if sweep already set config)
                wandb.config.update({
                "num_agents": num_agents,
                "prosperity_target": c.get("prosperity_target", env_config.prosperity_target),
                "invest_reward_multiplier": c.get("invest_reward_multiplier", 1.0),
                "extract_reward_multiplier": c.get("extract_reward_multiplier", 1.0),
                "num_episodes": num_episodes,
                "learning_rate": learning_rate,
                "use_topology": use_topology,
                })
            # Save config YAML as artifact when path is provided (e.g. from simulation script)
            if not run_existed:
                config_path = c.get("config_path")
                if config_path and os.path.isfile(config_path):
                    artifact = wandb.Artifact("experiment-config", type="config")
                    artifact.add_file(config_path)
                    wandb.log_artifact(artifact)
            # Optional: W&B Weave for LLM/topology traces (prompt-response, parse success, latency)
            if not run_existed and c.get("use_weave_trace", False):
                try:
                    import weave
                    weave_project = f"{wandb_entity or 'wandb'}/{wandb_project or 'telpai-quantum'}"
                    weave.init(weave_project)
                except Exception:
                    pass
        try:
            out = _run_learning_loop(
                env=env,
                env_config=env_config,
                agents=agents,
                engrams=engrams,
                num_episodes=num_episodes,
                use_topology=use_topology,
                topology_graph=topology_graph,
                learning_rate=learning_rate,
                gamma=gamma,
                seed=seed,
                reward_scale=reward_scale,
                reward_clip=reward_clip,
                return_clip=return_clip,
                epsilon_start=epsilon_start,
                epsilon_end=epsilon_end,
                epsilon_decay_episodes=epsilon_decay_episodes,
            )
        finally:
            if wandb_run is not None:
                import wandb
                wandb.finish()
        return out

    # Single rollout (no learning)
    obs, _ = env.reset(seed=seed)
    rewards_per_step: list[float] = []
    resource_trajectory: list[float] = [env.resource]

    for _ in range(env_config.max_steps - 1):
        if use_agents:
            actions = np.array(
                [agents[i].act(obs[i], deterministic=True) for i in range(num_agents)]
            )
        else:
            actions = np.array(
                [dummy_policy(obs[i], i, num_actions=3) for i in range(num_agents)]
            )

        result: StepResult = env.step(actions)
        obs = result.observations
        mean_reward = float(np.mean(result.rewards))
        rewards_per_step.append(mean_reward)
        resource_trajectory.append(env.resource)

        if result.dones.any():
            break

    return {
        "rewards_per_step": rewards_per_step,
        "resource_trajectory": resource_trajectory,
        "final_resource": env.resource,
        "num_steps": len(rewards_per_step),
        "mean_reward": float(np.mean(rewards_per_step)) if rewards_per_step else 0.0,
    }


def _run_learning_loop(
    env: TELPAIEnv,
    env_config: TELPAIEnvConfig,
    agents: list[QuantumGrokAgent],
    engrams: list,
    num_episodes: int,
    use_topology: bool,
    topology_graph: nx.Graph | None = None,
    learning_rate: float = 1e-3,
    gamma: float = 0.99,
    seed: int | None = None,
    reward_scale: float = 0.01,
    reward_clip: float = 10.0,
    return_clip: float | None = None,
    epsilon_start: float = 1.0,
    epsilon_end: float = 0.05,
    epsilon_decay_episodes: int = 0,
) -> dict[str, Any]:
    """Multi-episode training with Grok topology and REINFORCE.
    Epsilon-greedy: with probability epsilon take random action, else greedy; epsilon decays over episodes.
    If topology_graph is provided (e.g. from parse_topology_response_to_graph), use it; else build via suggest_coupling_topology().
    """
    import torch

    n_agents = env.num_agents
    num_actions = 3
    decay_episodes = epsilon_decay_episodes if epsilon_decay_episodes > 0 else max(1, int(0.8 * num_episodes))
    base_obs_dim = env.obs_dim
    obs_dim = 2 * base_obs_dim if use_topology else base_obs_dim

    # Grok coupling topology: use parsed graph if provided, else build from agent
    G = topology_graph if (use_topology and topology_graph is not None) else (agents[0].suggest_coupling_topology() if use_topology else None)

    policy = MLPPolicy(obs_dim=obs_dim, num_actions=3, seed=seed)
    optimizer = torch.optim.Adam(policy.parameters(), lr=learning_rate)

    training_rewards_per_episode: list[float] = []
    resource_final_per_episode: list[float] = []
    action_pcts_per_episode: list[list[float]] = []
    last_rewards_per_step: list[float] = []
    last_resource_trajectory: list[float] = []
    last_action_list: list[np.ndarray] = []

    for ep in range(num_episodes):
        # Decay epsilon: exploration → exploitation over training
        progress = min(1.0, ep / decay_episodes)
        epsilon = epsilon_start + (epsilon_end - epsilon_start) * progress

        obs, _ = env.reset(seed=seed + ep if seed is not None else None)
        if ep == num_episodes - 1:
            last_rewards_per_step = []
            last_resource_trajectory = [env.resource]
        obs_list: list[np.ndarray] = []
        action_list: list[np.ndarray] = []
        reward_list: list[np.ndarray] = []

        for _ in range(env_config.max_steps - 1):
            obs_ext = (
                topology_extended_obs(obs, G)
                if use_topology and G is not None
                else obs
            )
            if np.random.rand() < epsilon:
                actions = np.random.randint(0, num_actions, size=n_agents)
            else:
                actions, _ = policy.sample_actions(obs_ext, deterministic=True)
            result = env.step(actions)
            # Clip rewards so single steps don't produce -10k+ and gradients stay sane
            rewards = np.clip(result.rewards, -reward_clip, reward_clip)
            next_obs_raw = result.observations
            next_obs_ext = (
                topology_extended_obs(next_obs_raw, G)
                if use_topology and G is not None
                else next_obs_raw
            )
            # ENGRAM: Hμ from env spec, then add_memory per agent
            hmu = calculate_hmu(
                env.resource,
                env_config.prosperity_target,
                env_config.resource_budget,
                int(np.sum(actions == EXTRACT)),
                n_agents,
                getattr(env_config, "semantic_harmony_omega", 1.0),
            )
            for i in range(n_agents):
                engrams[i].add_memory(
                    obs_ext[i].copy(),
                    int(actions[i]),
                    float(rewards[i]),
                    next_obs_ext[i].copy(),
                    hmu,
                )
            obs_list.append(obs_ext)
            action_list.append(actions)
            reward_list.append(rewards)
            obs = next_obs_raw
            if ep == num_episodes - 1:
                last_rewards_per_step.append(float(np.mean(rewards)))
                last_resource_trajectory.append(env.resource)
                last_action_list.append(actions)
            if result.dones.any():
                break

        if not obs_list:
            continue
        # Scale rewards for stable REINFORCE gradients (prosperity penalty can be large)
        if reward_scale != 1.0:
            reward_list = [r * reward_scale for r in reward_list]
        reinforce_update(
            policy,
            optimizer,
            obs_list,
            action_list,
            reward_list,
            gamma=gamma,
            return_clip=return_clip,
        )
        for engram in engrams:
            engram.prune()
        ep_mean = float(np.mean([np.mean(r) for r in reward_list]))
        training_rewards_per_episode.append(ep_mean)
        resource_final_per_episode.append(env.resource)
        # Per-episode action distribution for wandb charts
        ep_action_counts = [0, 0, 0]
        for step_actions in action_list:
            for ai in np.asarray(step_actions, dtype=np.int32).ravel():
                if 0 <= ai < 3:
                    ep_action_counts[int(ai)] += 1
        ep_total = sum(ep_action_counts) or 1
        ep_action_pct = [100.0 * c / ep_total for c in ep_action_counts]
        action_pcts_per_episode.append(ep_action_pct)
        try:
            import wandb
            if wandb.run is not None:
                wandb.log({
                    "episode": ep,
                    "episode_reward_mean": ep_mean,
                    "episode_resource_final": env.resource,
                    "episode_resource_deviation": abs(env.resource - env_config.prosperity_target),
                    "epsilon": epsilon,
                    "action_pct_explore": ep_action_pct[0],
                    "action_pct_extract": ep_action_pct[1],
                    "action_pct_invest": ep_action_pct[2],
                }, step=ep)
        except Exception:
            pass

    # --- Diagnostics at end of training ---
    tr = training_rewards_per_episode
    first_ep_reward = tr[0] if tr else 0.0
    last_ep_reward = tr[-1] if tr else 0.0
    reward_improvement = last_ep_reward - first_ep_reward
    final_epsilon = epsilon_end  # epsilon at end of last episode
    final_resource = env.resource
    resource_min = float(min(last_resource_trajectory)) if last_resource_trajectory else 0.0
    resource_max = float(max(last_resource_trajectory)) if last_resource_trajectory else 0.0

    # Last episode action distribution (explore=0, extract=1, invest=2)
    # last_action_list: list of (n_agents,) arrays, one per step in last episode
    action_counts = [0, 0, 0]
    for step_actions in last_action_list:
        arr = np.asarray(step_actions, dtype=np.int32)
        for ai in arr.ravel():
            if 0 <= ai < 3:
                action_counts[int(ai)] += 1
    total_actions = sum(action_counts)
    if total_actions == 0:
        total_actions = 1  # avoid div by zero; log below
    action_pct = [round(100.0 * c / total_actions, 2) for c in action_counts]

    # Equilibrium quality: mean |resource - target| over last 20% of steps (lower = closer to target)
    tail_frac = 0.2
    n_steps = len(last_resource_trajectory)
    tail_start = max(0, n_steps - max(1, int(n_steps * tail_frac)))
    tail_resources = last_resource_trajectory[tail_start:]
    equilibrium_quality = (
        float(np.mean([abs(r - env_config.prosperity_target) for r in tail_resources]))
        if tail_resources else 0.0
    )

    # --- Sweep-friendly metrics (for W&B sweep metric.name / goal) ---
    # equilibrium_deviation: minimize → find config that keeps resource near prosperity_target
    # training_reward_mean: maximize → find config that maximizes mean episode reward
    prosperity_target = env_config.prosperity_target
    equilibrium_deviation = abs(final_resource - prosperity_target)
    training_reward_mean = float(np.mean(tr)) if tr else 0.0

    diagnostics = {
        "first_episode_reward": round(first_ep_reward, 2),
        "last_episode_reward": round(last_ep_reward, 2),
        "reward_improvement": round(reward_improvement, 2),
        "final_epsilon": round(final_epsilon, 2),
        "final_resource": round(final_resource, 2),
        "resource_min_last_ep": round(resource_min, 2),
        "resource_max_last_ep": round(resource_max, 2),
        "training_reward_mean": round(training_reward_mean, 2),
        "training_reward_std": round(float(np.std(tr)), 2) if tr and len(tr) > 1 else 0.0,
        "action_pct_explore": action_pct[0],
        "action_pct_extract": action_pct[1],
        "action_pct_invest": action_pct[2],
        "num_episodes": len(tr),
        "equilibrium_quality": round(equilibrium_quality, 2),
        "equilibrium_deviation": round(equilibrium_deviation, 2),
    }

    num_episodes = len(tr)
    print("\n--- Training diagnostics ---")
    print(f"  Episodes:                   {num_episodes}")
    print(f"  First episode mean reward:  {first_ep_reward:.2f}")
    print(f"  Last episode mean reward:   {last_ep_reward:.2f}")
    print(f"  Reward improvement:         {reward_improvement:+.2f}")
    print(f"  Final epsilon:              {final_epsilon:.2f}")
    print(f"  Final resource:             {final_resource:.2f}")
    print(f"  Resource range (last ep):   [{resource_min:.2f}, {resource_max:.2f}]")
    print(f"  Equilibrium quality:        {equilibrium_quality:.2f} (mean |r - target| last 20% steps, lower=better)")
    print(f"  Equilibrium deviation:      {equilibrium_deviation:.2f} (|final_resource - target|, sweep metric)")
    if tr:
        print(f"  Training reward mean±std:   {np.mean(tr):.2f} ± {np.std(tr):.2f}")
    if sum(action_counts) == 0:
        print("  Last ep action %:           (no actions recorded)")
    else:
        print(f"  Last ep action %:           explore={action_pct[0]:.2f}%  extract={action_pct[1]:.2f}%  invest={action_pct[2]:.2f}%")
    print("---")

    try:
        import wandb
        import matplotlib.pyplot as plt
        if wandb.run is not None:
            # Sweep-friendly: equilibrium_deviation (minimize) or training_reward_mean (maximize)
            wandb.log({
                "training_reward_mean": training_reward_mean,
                "training_reward_std": float(np.std(tr)) if tr and len(tr) > 1 else 0.0,
                "final_resource": round(final_resource, 2),
                "equilibrium_quality": round(equilibrium_quality, 2),
                "equilibrium_deviation": round(equilibrium_deviation, 2),
                "action_pct_explore": action_pct[0],
                "action_pct_extract": action_pct[1],
                "action_pct_invest": action_pct[2],
            })
            # Optional: resource trajectory plot (last episode)
            if last_resource_trajectory:
                fig, ax = plt.subplots()
                ax.plot(last_resource_trajectory, label="Resource")
                ax.axhline(env_config.prosperity_target, color="gray", ls="--", label="Target")
                ax.set_title("Resource Trajectory (last episode)")
                ax.legend()
                ax.set_xlabel("Step")
                wandb.log({"resource_trajectory": wandb.Image(fig)})
                plt.close(fig)
            # Optional: coupling topology plot (with edge weights if present)
            if G is not None and G.number_of_edges() > 0:
                fig, ax = plt.subplots()
                pos = nx.circular_layout(G)
                edges = list(G.edges(data=True))
                weights = [d.get("weight", 1.0) for _u, _v, d in edges]
                w_min, w_max = min(weights), max(weights)
                if w_max > w_min:
                    nx.draw_networkx_edges(
                        G, pos, width=[2 * (w - w_min) / (w_max - w_min) + 0.5 for w in weights],
                        edge_color=weights, edge_cmap=plt.cm.Blues, ax=ax,
                    )
                else:
                    nx.draw_networkx_edges(G, pos, ax=ax)
                nx.draw_networkx_nodes(G, pos, node_color="lightblue", ax=ax)
                nx.draw_networkx_labels(G, pos, ax=ax)
                ax.set_title("Agent Coupling Topology (edge weight = color)" if w_max > w_min else "Agent Coupling Topology")
                ax.axis("off")
                wandb.log({"coupling_topology": wandb.Image(fig)})
                plt.close(fig)
            # Action distribution over episodes (Seaborn line plot)
            if action_pcts_per_episode:
                try:
                    import pandas as pd
                    import seaborn as sns
                    df = pd.DataFrame({
                        "episode": list(range(len(action_pcts_per_episode))),
                        "explore": [p[0] for p in action_pcts_per_episode],
                        "extract": [p[1] for p in action_pcts_per_episode],
                        "invest": [p[2] for p in action_pcts_per_episode],
                    })
                    df_melt = df.melt(id_vars="episode", var_name="action", value_name="percentage")
                    fig2, ax2 = plt.subplots()
                    sns.lineplot(data=df_melt, x="episode", y="percentage", hue="action", ax=ax2)
                    ax2.set_title("Action distribution over episodes")
                    ax2.set_ylabel("Percentage")
                    wandb.log({"action_distribution_over_time": wandb.Image(fig2)})
                    plt.close(fig2)
                except Exception:
                    pass
            # Episode summary table for custom charts in W&B:
            # - Add panel → Custom chart → data source: episode_summary_table
            # - Multi-facet: resource_final (line) + action stack bar; tooltips on hover
            # - Vega-Lite examples: https://vega.github.io/vega-lite/examples/ (paste JSON into editor, map to table columns)
            n_ep = len(training_rewards_per_episode)
            if n_ep and len(resource_final_per_episode) == n_ep and len(action_pcts_per_episode) == n_ep:
                table = wandb.Table(
                    columns=["episode", "reward_mean", "resource_final", "explore_pct", "extract_pct", "invest_pct"]
                )
                for ep in range(n_ep):
                    table.add_data(
                        ep,
                        round(training_rewards_per_episode[ep], 4),
                        round(resource_final_per_episode[ep], 2),
                        round(action_pcts_per_episode[ep][0], 2),
                        round(action_pcts_per_episode[ep][1], 2),
                        round(action_pcts_per_episode[ep][2], 2),
                    )
                wandb.log({"episode_summary_table": table})
            # Log full diagnostics dict for compare/filter
            wandb.log({f"diagnostics/{k}": v for k, v in diagnostics.items()})
            # Plotly 3D resource trajectory (SciChart-like; interactive in W&B)
            if last_resource_trajectory:
                fig_3d = generate_3d_resource_chart(
                    last_resource_trajectory,
                    env_config.prosperity_target,
                    num_episodes - 1,
                )
                wandb.log({"3D_Resource_Trajectory": wandb.Plotly(fig_3d)})
    except Exception:
        pass

    # Save latest trajectory for the webpage demo
    os.makedirs("results", exist_ok=True)
    np.save("results/last_resource_trajectory.npy", np.array(last_resource_trajectory))

    return {
        "rewards_per_step": last_rewards_per_step,
        "resource_trajectory": last_resource_trajectory,
        "final_resource": env.resource,
        "num_steps": len(last_rewards_per_step),
        "mean_reward": (
            float(np.mean(last_rewards_per_step)) if last_rewards_per_step else 0.0
        ),
        "training_rewards_per_episode": training_rewards_per_episode,
        "diagnostics": diagnostics,
        "topology_graph": G,
    }


def generate_3d_resource_chart(
    resource_trajectory: list[float] | np.ndarray,
    prosperity_target: float,
    episode: int,
) -> "go.Figure":
    """SciChart-like 3D surface chart of resource trajectory + target plane (Plotly, WebGL)."""
    import plotly.graph_objects as go

    traj = np.asarray(resource_trajectory, dtype=float)
    if traj.size == 0:
        return go.Figure()
    t = np.arange(len(traj))
    depth = np.linspace(0, 1000, 50)
    X, Y = np.meshgrid(t, depth)
    Z = np.tile(traj, (50, 1))
    target_z = np.full_like(Z, prosperity_target)

    fig = go.Figure()
    fig.add_trace(go.Surface(z=Z, x=X, y=Y, colorscale="Viridis", name="Resource"))
    fig.add_trace(go.Surface(z=target_z, x=X, y=Y, opacity=0.3, colorscale="Reds", name="Target"))
    fig.add_trace(
        go.Scatter3d(
            x=t,
            y=np.zeros_like(t),
            z=traj,
            mode="lines",
            line=dict(color="white", width=4),
            name="Trajectory",
        )
    )
    fig.update_layout(
        title=f"3D Resource Trajectory — Episode {episode}",
        scene=dict(
            xaxis_title="Time",
            yaxis_title="Depth",
            zaxis_title="Resource",
        ),
        height=600,
    )
    os.makedirs("results", exist_ok=True)
    try:
        fig.write_image(f"results/3d_resource_ep{episode}.png")
    except Exception:
        pass
    return fig


def env_config_from_dict(d: dict[str, Any]) -> TELPAIEnvConfig:
    """Build TELPAIEnvConfig from a config dict (e.g. from YAML)."""
    return TELPAIEnvConfig(
        resource_budget=float(d.get("resource_budget", 1000.0)),
        max_steps=int(d.get("max_steps", 200)),
        regen_period=float(d.get("regen_period", 90.0)),
        regen_base=float(d.get("regen_base", 5.0)),
        regen_amplitude=float(d.get("regen_amplitude", 3.0)),
        extract_rate=float(d.get("extract_rate", 10.0)),
        invest_rate=float(d.get("invest_rate", 8.0)),
        explore_gain=float(d.get("explore_gain", 1.0)),
        prosperity_target=float(d.get("prosperity_target", 500.0)),
        prosperity_penalty_scale=float(d.get("prosperity_penalty_scale", 0.01)),
        prosperity_penalty_cap=float(d.get("prosperity_penalty_cap", 10.0)),
        prosperity_stability_bonus=float(d.get("prosperity_stability_bonus", 0.0)),
        prosperity_stability_band=float(d.get("prosperity_stability_band", 0.1)),
        prosperity_stability_sigma=float(d.get("prosperity_stability_sigma", 0.0)),
        over_invest_drift_scale=float(d.get("over_invest_drift_scale", 0.0)),
        invest_bonus=float(d.get("invest_bonus", 0.0)),
        extract_penalty=float(d.get("extract_penalty", 0.0)),
        invest_reward_multiplier=float(d.get("invest_reward_multiplier", 1.0)),
        extract_reward_multiplier=float(d.get("extract_reward_multiplier", 1.0)),
        semantic_harmony_scale=float(d.get("semantic_harmony_scale", 0.1)),
        semantic_harmony_omega=float(d.get("semantic_harmony_omega", 1.0)),
    )


def agent_kwargs_from_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Extract agent/coupling knobs from config dict for QuantumGrokAgent."""
    return {
        "sparsity_target": float(d.get("sparsity_target", 0.3)),
        "max_hops": int(d.get("max_hops", 3)),
        "memory_capacity": int(d.get("memory_capacity", 1000)),
    }
