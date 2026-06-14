"""
QM2ARL training loop: multi-agent training with TELPAIEnv.
Integrates Grok coupling topology (neighbor-obs aggregation) and learned MLP policy
with REINFORCE when learning=True.
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import networkx as nx

from src.environment import TELPAIEnv, TELPAIEnvConfig, StepResult, EXTRACT
from src.agents import ENGRAMENGN, QuantumGrokAgent, dummy_policy, parse_topology_response_to_graph
from src.policies import MLPPolicy, SharedTrunkPerAgentHeadPolicy, reinforce_update
from src.quantum_geospatial import (
    get_quantum_anomaly_detector,
    load_reference_set,
    save_reference_set,
)

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
                wrn = config.get("wandb_run_name") if isinstance(config, dict) else None
                if isinstance(wrn, str) and wrn.strip():
                    run_name = wrn.strip()
                    if seed is not None:
                        run_name = f"{run_name}-seed{seed}"
                else:
                    exp_name = config.get("experiment_name", "default") if isinstance(config, dict) else "default"
                    run_name = f"telpai-n{num_agents}-{exp_name}"
                    if seed is not None:
                        run_name = f"{run_name}-seed{seed}"
                os.makedirs("results/wandb", exist_ok=True)
                try:
                    wandb_run = wandb.init(
                        project=wandb_project or "telpai-quantum",
                        entity=wandb_entity,
                        name=run_name,
                        config=config if isinstance(config, dict) else {},
                        dir="results/wandb",
                        settings=wandb.Settings(_disable_stats=True, init_timeout=60),
                    )
                except Exception as e:
                    print(f"[wandb] trainer init failed ({type(e).__name__}: {e}); continuing without W&B.")
                    use_wandb = False
                    wandb_run = None
            c = config if isinstance(config, dict) else {}
            if use_wandb and not run_existed and wandb.run is not None:
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
            if use_wandb and not run_existed and wandb.run is not None:
                config_path = c.get("config_path")
                if config_path and os.path.isfile(config_path):
                    artifact = wandb.Artifact("experiment-config", type="config")
                    artifact.add_file(config_path)
                    wandb.log_artifact(artifact)
            # Optional: W&B Weave for LLM/topology traces (prompt-response, parse success, latency)
            if use_wandb and not run_existed and wandb.run is not None and c.get("use_weave_trace", False):
                try:
                    import weave
                    weave_project = f"{wandb_entity or 'wandb'}/{wandb_project or 'telpai-quantum'}"
                    weave.init(weave_project)
                except Exception:
                    pass
        cdict = config if isinstance(config, dict) else {}
        ibm_be = cdict.get("ibm_backend")
        if isinstance(ibm_be, str) and ibm_be.strip():
            os.environ["IBM_BACKEND"] = ibm_be.strip()
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
                use_ibm_quantum=bool(cdict.get("use_ibm_quantum", False)),
                use_quantum_circuit_optimizer=bool(cdict.get("use_quantum_circuit_optimizer", True)),
                quantum_bonus_scale=float(cdict.get("quantum_bonus_scale", 0.4)),
                ibm_quantum_max_agents_per_step=int(cdict.get("ibm_quantum_max_agents_per_step", 1)),
                ibm_quantum_steps=int(cdict.get("ibm_quantum_steps", 8)),
                ibm_quantum_lr=float(cdict.get("ibm_quantum_lr", 0.05)),
                ibm_quantum_every_n_steps=int(cdict.get("ibm_quantum_every_n_steps", 1)),
                quantum_entropy_threshold=float(cdict.get("quantum_entropy_threshold", 0.42)),
                quantum_threshold_bonus_scale=float(cdict.get("quantum_threshold_bonus_scale", 0.0)),
                per_agent_policy_heads=bool(cdict.get("per_agent_policy_heads", False)),
                quantum_kernel_enabled=bool(cdict.get("quantum_kernel_enabled", False)),
                quantum_kernel_feature_dim=int(cdict.get("quantum_kernel_feature_dim", 8)),
                quantum_kernel_gamma=float(cdict.get("quantum_kernel_gamma", 0.5)),
                quantum_kernel_ref_path=str(cdict.get("quantum_kernel_ref_path", "results/kernel_reference.npy")),
                quantum_kernel_ref_update_every=int(cdict.get("quantum_kernel_ref_update_every", 10)),
                quantum_kernel_ref_max=int(cdict.get("quantum_kernel_ref_max", 200)),
                quantum_kernel_anomaly_bonus_scale=float(cdict.get("quantum_kernel_anomaly_bonus_scale", 0.0)),
                quantum_kernel_harmony_ref_enabled=bool(cdict.get("quantum_kernel_harmony_ref_enabled", False)),
                quantum_kernel_harmony_ref_path=str(cdict.get("quantum_kernel_harmony_ref_path", "results/kernel_high_hmu_reference.npy")),
                quantum_kernel_harmony_ref_max=int(cdict.get("quantum_kernel_harmony_ref_max", 200)),
                quantum_kernel_harmony_bonus_scale=float(cdict.get("quantum_kernel_harmony_bonus_scale", 0.0)),
                quantum_kernel_harmony_update_threshold=float(cdict.get("quantum_kernel_harmony_update_threshold", 0.80)),
                quantum_kernel_every_n_steps=int(cdict.get("quantum_kernel_every_n_steps", 1)),
                quantum_kernel_ref_sample_max=int(cdict.get("quantum_kernel_ref_sample_max", 64)),
                quantum_kernel_harmony_ref_sample_max=int(cdict.get("quantum_kernel_harmony_ref_sample_max", 64)),
                engram_kernel_prune_enabled=bool(cdict.get("engram_kernel_prune_enabled", False)),
                engram_kernel_similarity_threshold=float(cdict.get("engram_kernel_similarity_threshold", 0.90)),
                use_vqc_feature_map=bool(cdict.get("use_vqc_feature_map", False)),
                vqc_seed=int(cdict.get("vqc_seed", 42)),
                vqc_max_wires=int(cdict.get("vqc_max_wires", 8)),
                vqc_backend=str(cdict.get("vqc_backend", "")),
                bluequbit_token=str(cdict.get("bluequbit_token", "")),
                resume_training=bool(cdict.get("resume_training", False)),
                training_checkpoint_path=(
                    str(cdict["training_checkpoint_path"]).strip()
                    if cdict.get("training_checkpoint_path")
                    else None
                ),
                checkpoint_every_episodes=int(cdict.get("checkpoint_every_episodes", 1)),
                training_checkpoint_remove_on_complete=bool(
                    cdict.get("training_checkpoint_remove_on_complete", True)
                ),
                hybrid_quantum_enabled=bool(cdict.get("hybrid_quantum_enabled", False)),
                use_quantum_gates=bool(cdict.get("use_quantum_gates", True)),
                use_quantum_annealing=bool(cdict.get("use_quantum_annealing", True)),
                hybrid_cooperation_bonus_scale=float(
                    cdict.get("hybrid_cooperation_bonus_scale", 0.25)
                ),
                annealing_every_n_steps=int(cdict.get("annealing_every_n_steps", 10)),
                annealing_reads=int(cdict.get("annealing_reads", 400)),
                annealing_backend=str(cdict.get("annealing_backend", "auto")),
                annealing_coupling_strength=float(
                    cdict.get("annealing_coupling_strength", 1.0)
                ),
                hybrid_gate_steps=int(cdict.get("hybrid_gate_steps", 4)),
                hybrid_gate_lr=float(cdict.get("hybrid_gate_lr", 0.05)),
                compile_policy_enabled=bool(cdict.get("compile_policy", False)),
                compile_mode=str(cdict.get("compile_mode", "reduce-overhead")),
                binarized_policy=bool(cdict.get("binarized_policy", False)),
                prune_amount=float(cdict.get("prune_amount", 0.0)),
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
    *,
    use_ibm_quantum: bool = False,
    use_quantum_circuit_optimizer: bool = True,
    quantum_bonus_scale: float = 0.4,
    ibm_quantum_max_agents_per_step: int = 1,
    ibm_quantum_steps: int = 8,
    ibm_quantum_lr: float = 0.05,
    ibm_quantum_every_n_steps: int = 1,
    quantum_entropy_threshold: float = 0.42,
    quantum_threshold_bonus_scale: float = 0.0,
    per_agent_policy_heads: bool = False,
    quantum_kernel_enabled: bool = False,
    quantum_kernel_feature_dim: int = 8,
    quantum_kernel_gamma: float = 0.5,
    quantum_kernel_ref_path: str = "results/kernel_reference.npy",
    quantum_kernel_ref_update_every: int = 10,
    quantum_kernel_ref_max: int = 200,
    quantum_kernel_anomaly_bonus_scale: float = 0.0,
    quantum_kernel_harmony_ref_enabled: bool = False,
    quantum_kernel_harmony_ref_path: str = "results/kernel_high_hmu_reference.npy",
    quantum_kernel_harmony_ref_max: int = 200,
    quantum_kernel_harmony_bonus_scale: float = 0.0,
    quantum_kernel_harmony_update_threshold: float = 0.80,
    quantum_kernel_every_n_steps: int = 1,
    quantum_kernel_ref_sample_max: int = 64,
    quantum_kernel_harmony_ref_sample_max: int = 64,
    engram_kernel_prune_enabled: bool = False,
    engram_kernel_similarity_threshold: float = 0.90,
    use_vqc_feature_map: bool = False,
    vqc_seed: int = 42,
    vqc_max_wires: int = 8,
    vqc_backend: str = "",
    bluequbit_token: str = "",
    resume_training: bool = False,
    training_checkpoint_path: str | None = None,
    checkpoint_every_episodes: int = 1,
    training_checkpoint_remove_on_complete: bool = True,
    hybrid_quantum_enabled: bool = False,
    use_quantum_gates: bool = True,
    use_quantum_annealing: bool = True,
    hybrid_cooperation_bonus_scale: float = 0.25,
    annealing_every_n_steps: int = 10,
    annealing_reads: int = 400,
    annealing_backend: str = "auto",
    annealing_coupling_strength: float = 1.0,
    hybrid_gate_steps: int = 4,
    hybrid_gate_lr: float = 0.05,
    compile_policy_enabled: bool = False,
    compile_mode: str = "reduce-overhead",
    binarized_policy: bool = False,
    prune_amount: float = 0.0,
) -> dict[str, Any]:
    """Multi-episode training with Grok topology and REINFORCE.
    Epsilon-greedy: with probability epsilon take random action, else greedy; epsilon decays over episodes.
    If topology_graph is provided (e.g. from parse_topology_response_to_graph), use it; else build via suggest_coupling_topology().
    quantum_entropy_threshold: normalized policy entropy below this counts as crossing the "quantum threshold"
    (committed / low-uncertainty regime; metaphor for audit-style decisive policy, not a QPU claim).
    quantum_threshold_bonus_scale: small per-step reward when in that regime (0 disables).
    per_agent_policy_heads: if True, use shared trunk + per-agent output heads instead of one shared MLP.
    """
    import torch

    n_agents = env.num_agents
    num_actions = 3
    decay_episodes = epsilon_decay_episodes if epsilon_decay_episodes > 0 else max(1, int(0.8 * num_episodes))
    base_obs_dim = env.obs_dim
    obs_dim = 2 * base_obs_dim if use_topology else base_obs_dim

    # Grok coupling topology: use parsed graph if provided, else build from agent
    G = topology_graph if (use_topology and topology_graph is not None) else (agents[0].suggest_coupling_topology() if use_topology else None)

    if use_ibm_quantum:
        from src.quantum_circuit_optimizer import ibm_token_configured, reset_quantum_device

        reset_quantum_device()
        _be = os.getenv("IBM_BACKEND", "ibm_brisbane")
        _skip = os.getenv("QM2ARL_SKIP_IBM", "").strip().lower() in ("1", "true", "yes")
        _tok = ibm_token_configured()
        _bq = bool(os.environ.get("BLUEQUBIT_API_TOKEN", "").strip()) or bool(bluequbit_token)
        print(
            f"\n[quantum] QM2ARL quantum bonus: IBM_remote={_tok and not _skip}, "
            f"skip_ibm={_skip}, backend={_be!r}, bonus_scale={quantum_bonus_scale}, "
            f"every_n_steps={ibm_quantum_every_n_steps}"
        )
        print(
            f"[quantum] BlueQubit available={_bq}, vqc_backend={vqc_backend!r}\n"
        )

    hybrid_coordinator = None
    if hybrid_quantum_enabled:
        from src.hybrid_quantum_stack import probe_hybrid_status

        hq = probe_hybrid_status(vqc_backend=vqc_backend, anneal_backend=annealing_backend)
        print(f"\n[hybrid] {hq.message}\n")
        hybrid_coordinator = hq

    if binarized_policy:
        # "Super-efficient" binarized (BNN) policy — ~32x smaller weights.
        from src.efficient_models import BinarizedMLPPolicy

        if per_agent_policy_heads:
            print(
                "[efficient] binarized_policy ignores per_agent_policy_heads; "
                "using shared BinarizedMLPPolicy."
            )
        policy = BinarizedMLPPolicy(obs_dim=obs_dim, num_actions=3, seed=seed)
        print("[efficient] Using BinarizedMLPPolicy (sign-weight BNN + STE).")
    elif per_agent_policy_heads:
        policy = SharedTrunkPerAgentHeadPolicy(
            obs_dim=obs_dim, num_agents=n_agents, num_actions=3, seed=seed
        )
    else:
        policy = MLPPolicy(obs_dim=obs_dim, num_actions=3, seed=seed)
    optimizer = torch.optim.Adam(policy.parameters(), lr=learning_rate)

    # COMPILE lever: fuse the policy hot path via torch.compile (fail-safe no-op).
    if compile_policy_enabled:
        from src.efficient_models import compile_policy as _compile_policy

        compiled = _compile_policy(policy, mode=compile_mode, enabled=True)
        if compiled is not policy:
            print(f"[efficient] torch.compile applied (mode={compile_mode!r}).")
            policy = compiled
        else:
            print("[efficient] torch.compile unavailable; using eager policy.")

    ckpt_path = (
        Path(training_checkpoint_path).expanduser()
        if isinstance(training_checkpoint_path, str) and training_checkpoint_path.strip()
        else None
    )
    start_ep = 0

    def _checkpoint_meta() -> dict[str, Any]:
        return {
            "obs_dim": int(obs_dim),
            "n_agents": int(n_agents),
            "per_agent_policy_heads": bool(per_agent_policy_heads),
            "num_episodes_target": int(num_episodes),
            "seed": seed,
            "learning_rate": float(learning_rate),
        }

    def _save_training_checkpoint(next_episode: int) -> None:
        if ckpt_path is None:
            return
        cuda_states = None
        if torch.cuda.is_available():
            cuda_states = torch.cuda.get_rng_state_all()
        payload = {
            "version": 1,
            "next_episode": int(next_episode),
            "policy_state_dict": policy.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "numpy_random_state": np.random.get_state(),
            "torch_rng_state": torch.get_rng_state(),
            "torch_cuda_rng_states": cuda_states,
            "meta": _checkpoint_meta(),
        }
        ckpt_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(payload, ckpt_path)

    if ckpt_path is not None and resume_training and ckpt_path.is_file():
        try:
            try:
                ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
            except TypeError:
                ckpt = torch.load(ckpt_path, map_location="cpu")
            meta = ckpt.get("meta") or {}
            ok = (
                int(meta.get("obs_dim", -1)) == int(obs_dim)
                and int(meta.get("n_agents", -1)) == int(n_agents)
                and bool(meta.get("per_agent_policy_heads")) == bool(per_agent_policy_heads)
                and int(meta.get("num_episodes_target", -1)) == int(num_episodes)
                and abs(float(meta.get("learning_rate", -1.0)) - float(learning_rate)) < 1e-12
            )
            if ok:
                ne = int(ckpt.get("next_episode", 0))
                if 0 <= ne < num_episodes:
                    policy.load_state_dict(ckpt["policy_state_dict"])
                    optimizer.load_state_dict(ckpt["optimizer_state_dict"])
                    np.random.set_state(ckpt["numpy_random_state"])
                    torch.set_rng_state(ckpt["torch_rng_state"])
                    cuda_states = ckpt.get("torch_cuda_rng_states")
                    if cuda_states is not None and torch.cuda.is_available():
                        torch.cuda.set_rng_state_all(cuda_states)
                    start_ep = ne
                    print(
                        f"\n[checkpoint] Resuming from episode {start_ep}/{num_episodes} "
                        f"({ckpt_path})\n"
                        "[checkpoint] Policy + optimizer restored; ENGRAM buffers were not restored.\n"
                    )
                elif ne >= num_episodes:
                    print(
                        f"\n[checkpoint] File marks training complete (next_episode={ne}); "
                        "starting a fresh run.\n"
                    )
                else:
                    print("\n[checkpoint] Invalid next_episode in file; starting fresh.\n")
            else:
                print("\n[checkpoint] Checkpoint meta mismatch (topology/agents/episodes); ignoring.\n")
        except Exception as e:
            print(f"\n[checkpoint] Load failed ({type(e).__name__}: {e}); starting fresh.\n")

    training_episodes_requested = num_episodes
    training_rewards_per_episode: list[float] = []
    resource_final_per_episode: list[float] = []
    action_pcts_per_episode: list[list[float]] = []
    mean_anomaly_per_episode: list[float] = []
    mean_entropy_norm_per_episode: list[float] = []
    quantum_threshold_hits_per_episode: list[int] = []
    error_correction_steps_per_episode: list[int] = []
    quantum_kernel_anomaly_per_episode: list[float] = []
    quantum_kernel_harmony_sim_per_episode: list[float] = []
    last_rewards_per_step: list[float] = []
    last_resource_trajectory: list[float] = []
    last_action_list: list[np.ndarray] = []
    last_ep_anomaly_scores: list[float] = []
    last_ep_kernel_anomaly_scores: list[float] = []
    last_ep_kernel_harmony_sim_scores: list[float] = []

    detector = None
    kernel_ref: list[np.ndarray] = []
    if quantum_kernel_enabled:
        detector = get_quantum_anomaly_detector(
            feature_dim=int(quantum_kernel_feature_dim),
            gamma=float(quantum_kernel_gamma),
            use_vqc=bool(use_vqc_feature_map),
            vqc_seed=int(vqc_seed),
            vqc_max_wires=int(vqc_max_wires),
            vqc_backend=str(vqc_backend),
            bluequbit_token=str(bluequbit_token),
        )
        kernel_ref = load_reference_set(quantum_kernel_ref_path)

    harmony_ref: list[np.ndarray] = []
    if quantum_kernel_harmony_ref_enabled:
        if detector is None:
            detector = get_quantum_anomaly_detector(
                feature_dim=int(quantum_kernel_feature_dim),
                gamma=float(quantum_kernel_gamma),
                use_vqc=bool(use_vqc_feature_map),
                vqc_seed=int(vqc_seed),
                vqc_max_wires=int(vqc_max_wires),
                vqc_backend=str(vqc_backend),
                bluequbit_token=str(bluequbit_token),
            )
        harmony_ref = load_reference_set(quantum_kernel_harmony_ref_path)

    for ep in range(start_ep, num_episodes):
        # Decay epsilon: exploration → exploitation over training
        progress = min(1.0, ep / decay_episodes)
        epsilon = epsilon_start + (epsilon_end - epsilon_start) * progress

        obs, _ = env.reset(seed=seed + ep if seed is not None else None)
        if ep == num_episodes - 1:
            last_rewards_per_step = []
            last_resource_trajectory = [env.resource]
            last_ep_anomaly_scores = []
            last_ep_kernel_anomaly_scores = []
            last_ep_kernel_harmony_sim_scores = []
        obs_list: list[np.ndarray] = []
        action_list: list[np.ndarray] = []
        reward_list: list[np.ndarray] = []

        ep_anomaly: list[float] = []
        ep_entropy_norm: list[float] = []
        ep_qthresh_hits = 0
        ep_ec_steps = 0
        ep_kernel_anomaly: list[float] = []
        ep_kernel_harmony_sim: list[float] = []

        last_k_anom: float | None = None
        last_hsim: float | None = None

        for step_i in range(env_config.max_steps - 1):
            obs_ext = (
                topology_extended_obs(obs, G)
                if use_topology and G is not None
                else obs
            )
            greedy_step = np.random.rand() >= epsilon
            if greedy_step:
                actions, _ = policy.sample_actions(obs_ext, deterministic=True)
                h_norm = policy.mean_normalized_entropy(obs_ext)
                ep_entropy_norm.append(h_norm)
                if h_norm < quantum_entropy_threshold:
                    ep_qthresh_hits += 1
            else:
                actions = np.random.randint(0, num_actions, size=n_agents)
            result = env.step(actions)
            # Clip rewards so single steps don't produce -10k+ and gradients stay sane
            rewards = np.clip(result.rewards, -reward_clip, reward_clip)
            if result.infos:
                ep_anomaly.append(float(result.infos[0].get("anomaly_score", 0.0)))
                if result.infos[0].get("error_correction_applied"):
                    ep_ec_steps += 1

            # Quantum kernel anomaly score (simulator-first): computed on current obs (pre-step) mean.
            # If enabled, optionally reward EXPLORE proportionally to anomaly (explore high-anomaly regions).
            do_kernel = (int(quantum_kernel_every_n_steps) <= 1) or (
                step_i % max(1, int(quantum_kernel_every_n_steps)) == 0
            )
            if quantum_kernel_enabled and detector is not None and do_kernel:
                x = np.mean(obs_ext, axis=0)
                refs = kernel_ref
                sm = int(quantum_kernel_ref_sample_max)
                if sm > 0 and len(refs) > sm:
                    idx = np.random.choice(len(refs), size=sm, replace=False)
                    refs = [refs[int(i)] for i in idx]
                k_anom = detector.kernel_anomaly_score(x, refs)
                last_k_anom = float(k_anom)
                ep_kernel_anomaly.append(float(k_anom))
                if quantum_kernel_anomaly_bonus_scale > 0.0:
                    explore_mask = (np.asarray(actions, dtype=np.int32) == 0).astype(np.float64)
                    if explore_mask.any():
                        rewards = rewards + (quantum_kernel_anomaly_bonus_scale * k_anom) * (explore_mask / max(1.0, float(explore_mask.sum())))
                        rewards = np.clip(rewards, -reward_clip, reward_clip)
            elif quantum_kernel_enabled and last_k_anom is not None:
                # Keep a per-step trace without recomputing, so diagnostics align with step count.
                ep_kernel_anomaly.append(float(last_k_anom))

            if quantum_kernel_harmony_ref_enabled and detector is not None and harmony_ref and do_kernel:
                xh = np.mean(obs_ext, axis=0)
                refs = harmony_ref
                sm = int(quantum_kernel_harmony_ref_sample_max)
                if sm > 0 and len(refs) > sm:
                    # Sample refs to keep per-step cost bounded.
                    idx = np.random.choice(len(refs), size=sm, replace=False)
                    refs = [refs[int(i)] for i in idx]
                sims = [detector.quantum_kernel(xh, r) for r in refs]
                hsim = float(np.mean(sims)) if sims else 0.0
                last_hsim = float(hsim)
                ep_kernel_harmony_sim.append(hsim)
                if quantum_kernel_harmony_bonus_scale > 0.0:
                    rewards = rewards + (quantum_kernel_harmony_bonus_scale * hsim) / n_agents
                    rewards = np.clip(rewards, -reward_clip, reward_clip)
            elif quantum_kernel_harmony_ref_enabled and last_hsim is not None:
                ep_kernel_harmony_sim.append(float(last_hsim))
            if (
                greedy_step
                and quantum_threshold_bonus_scale > 0.0
                and ep_entropy_norm
                and ep_entropy_norm[-1] < quantum_entropy_threshold
            ):
                rewards = rewards + quantum_threshold_bonus_scale / n_agents
                rewards = np.clip(rewards, -reward_clip, reward_clip)
            if (
                hybrid_quantum_enabled
                and annealing_every_n_steps > 0
                and (step_i % annealing_every_n_steps == 0)
            ):
                from src.hybrid_quantum_stack import hybrid_cooperation_bonus

                hresult = hybrid_cooperation_bonus(
                    obs_ext if use_topology else obs,
                    actions,
                    G,
                    n_agents,
                    use_quantum_gates=use_quantum_gates,
                    use_quantum_annealing=use_quantum_annealing,
                    cooperation_scale=hybrid_cooperation_bonus_scale,
                    anneal_backend=annealing_backend,
                    anneal_reads=annealing_reads,
                    coupling_strength=annealing_coupling_strength,
                    gate_steps=hybrid_gate_steps,
                    gate_lr=hybrid_gate_lr,
                    vqc_backend=vqc_backend,
                )
                rewards = rewards + hresult.reward_bonus
                rewards = np.clip(rewards, -reward_clip, reward_clip)
            if (
                use_ibm_quantum
                and use_quantum_circuit_optimizer
                and not hybrid_quantum_enabled
                and ibm_quantum_every_n_steps > 0
                and (step_i % ibm_quantum_every_n_steps == 0)
            ):
                from src.quantum_circuit_optimizer import optimize_quantum_circuit

                base_obs_dim = env.obs_dim
                nq = min(n_agents, max(1, ibm_quantum_max_agents_per_step))
                for i in range(nq):
                    mean_neighbor_res = (
                        float(obs_ext[i, base_obs_dim])
                        if (use_topology and G is not None)
                        else 0.0
                    )
                    features = np.array(
                        [float(obs_ext[i, 0]), float(obs_ext[i, 1]), mean_neighbor_res],
                        dtype=np.float64,
                    )
                    _, circuit_score = optimize_quantum_circuit(
                        features,
                        float(rewards[i]),
                        learning_rate=ibm_quantum_lr,
                        steps=ibm_quantum_steps,
                    )
                    rewards[i] += quantum_bonus_scale * float(circuit_score)
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
                if result.infos:
                    last_ep_anomaly_scores.append(
                        float(result.infos[0].get("anomaly_score", 0.0))
                    )
                if ep_kernel_anomaly:
                    last_ep_kernel_anomaly_scores.append(float(ep_kernel_anomaly[-1]))
                if ep_kernel_harmony_sim:
                    last_ep_kernel_harmony_sim_scores.append(float(ep_kernel_harmony_sim[-1]))
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
            if engram_kernel_prune_enabled and detector is not None:
                engram.prune_kernel_diverse(
                    detector=detector,
                    similarity_threshold=float(engram_kernel_similarity_threshold),
                )
            else:
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
        mean_anomaly_per_episode.append(float(np.mean(ep_anomaly)) if ep_anomaly else 0.0)
        quantum_kernel_anomaly_per_episode.append(float(np.mean(ep_kernel_anomaly)) if ep_kernel_anomaly else 0.0)
        quantum_kernel_harmony_sim_per_episode.append(float(np.mean(ep_kernel_harmony_sim)) if ep_kernel_harmony_sim else 0.0)
        mean_entropy_norm_per_episode.append(
            float(np.mean(ep_entropy_norm)) if ep_entropy_norm else 1.0
        )
        quantum_threshold_hits_per_episode.append(ep_qthresh_hits)
        error_correction_steps_per_episode.append(ep_ec_steps)
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
                    "mean_anomaly_score": mean_anomaly_per_episode[-1],
                    "mean_quantum_kernel_anomaly_score": quantum_kernel_anomaly_per_episode[-1],
                    "mean_quantum_kernel_harmony_similarity": quantum_kernel_harmony_sim_per_episode[-1],
                    "mean_policy_entropy_norm": mean_entropy_norm_per_episode[-1],
                    "quantum_threshold_hits": ep_qthresh_hits,
                    "error_correction_steps": ep_ec_steps,
                }, step=ep)
        except Exception:
            pass

        # Update kernel reference set periodically (persist across runs).
        if quantum_kernel_enabled and detector is not None and kernel_ref is not None:
            if (quantum_kernel_ref_update_every > 0 and (ep % int(quantum_kernel_ref_update_every) == 0)) or (
                ep_kernel_anomaly and float(np.mean(ep_kernel_anomaly)) > 0.6
            ):
                if obs_list:
                    kernel_ref.append(np.mean(obs_list[-1], axis=0))
                if int(quantum_kernel_ref_max) > 0 and len(kernel_ref) > int(quantum_kernel_ref_max):
                    kernel_ref = kernel_ref[-int(quantum_kernel_ref_max):]
                save_reference_set(kernel_ref, quantum_kernel_ref_path)

        if quantum_kernel_harmony_ref_enabled and detector is not None:
            # Use episode mean reward (already scaled) as a lightweight proxy for "good behavior".
            if float(ep_mean) >= float(quantum_kernel_harmony_update_threshold):
                if obs_list:
                    harmony_ref.append(np.mean(obs_list[-1], axis=0))
                if int(quantum_kernel_harmony_ref_max) > 0 and len(harmony_ref) > int(quantum_kernel_harmony_ref_max):
                    harmony_ref = harmony_ref[-int(quantum_kernel_harmony_ref_max):]
                save_reference_set(harmony_ref, quantum_kernel_harmony_ref_path)

        if ckpt_path is not None and int(checkpoint_every_episodes) > 0:
            if (ep + 1) % int(checkpoint_every_episodes) == 0:
                _save_training_checkpoint(ep + 1)

    if ckpt_path is not None and training_checkpoint_remove_on_complete:
        try:
            if ckpt_path.is_file():
                ckpt_path.unlink()
                print(f"\n[checkpoint] Removed completed checkpoint: {ckpt_path}\n")
        except OSError as e:
            print(f"\n[checkpoint] Could not remove checkpoint ({e})\n")

    # Post-training magnitude pruning (sparsity lever for super-efficient export).
    achieved_sparsity = 0.0
    if prune_amount and prune_amount > 0.0:
        from src.efficient_models import magnitude_prune_

        target = policy
        # Reach the underlying module if torch.compile wrapped the policy.
        if hasattr(policy, "_orig_mod"):
            target = policy._orig_mod
        achieved_sparsity = magnitude_prune_(target, amount=float(prune_amount))
        print(
            f"[efficient] Magnitude pruning applied: target={prune_amount:.2f}, "
            f"achieved sparsity={achieved_sparsity * 100:.1f}%"
        )

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
        "episodes_configured": training_episodes_requested,
        "equilibrium_quality": round(equilibrium_quality, 2),
        "equilibrium_deviation": round(equilibrium_deviation, 2),
        "mean_anomaly_last_ep": round(float(np.mean(last_ep_anomaly_scores)), 4) if last_ep_anomaly_scores else 0.0,
        "mean_quantum_kernel_anomaly_last_ep": round(float(np.mean(last_ep_kernel_anomaly_scores)), 4) if last_ep_kernel_anomaly_scores else 0.0,
        "mean_quantum_kernel_harmony_similarity_last_ep": round(float(np.mean(last_ep_kernel_harmony_sim_scores)), 4) if last_ep_kernel_harmony_sim_scores else 0.0,
        "mean_entropy_norm_last_ep": round(mean_entropy_norm_per_episode[-1], 4) if mean_entropy_norm_per_episode else 0.0,
        "quantum_threshold_hits_last_ep": quantum_threshold_hits_per_episode[-1] if quantum_threshold_hits_per_episode else 0,
        "error_correction_steps_last_ep": error_correction_steps_per_episode[-1] if error_correction_steps_per_episode else 0,
        "use_vqc_feature_map": bool(use_vqc_feature_map),
        "vqc_backend": detector.active_backend if detector else "none",
        "checkpoint_resume_episode": int(start_ep),
        "efficient_compile": bool(compile_policy_enabled),
        "efficient_binarized": bool(binarized_policy),
        "efficient_prune_amount": float(prune_amount),
        "efficient_achieved_sparsity_pct": round(achieved_sparsity * 100.0, 2),
    }

    n_eps = len(tr)
    print("\n--- Training diagnostics ---")
    if start_ep > 0 and tr:
        print(f"  (Resumed run — episode metrics cover {start_ep}..{num_episodes - 1} only)")
    print(f"  Episodes:                   {n_eps}")
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
    if last_ep_anomaly_scores:
        print(f"  Last ep mean anomaly score: {float(np.mean(last_ep_anomaly_scores)):.4f} (resource jump norm)")
    if last_ep_kernel_anomaly_scores:
        print(
            f"  Last ep mean quantum_kernel_anomaly: {float(np.mean(last_ep_kernel_anomaly_scores)):.4f}"
        )
    if last_ep_kernel_harmony_sim_scores:
        print(
            f"  Last ep mean quantum_kernel_harmony_similarity: {float(np.mean(last_ep_kernel_harmony_sim_scores)):.4f}"
        )
    if use_vqc_feature_map:
        _bk = detector.active_backend if detector else "none"
        print(f"  VQC feature map:             enabled (PennyLane kernel embedding)")
        print(f"  VQC backend:                 {_bk}")
    if mean_entropy_norm_per_episode:
        print(f"  Last ep entropy norm mean:  {mean_entropy_norm_per_episode[-1]:.4f} (policy uncertainty dial)")
        print(f"  Quantum-threshold hits (last ep): {quantum_threshold_hits_per_episode[-1] if quantum_threshold_hits_per_episode else 0}")
        print(f"  Error-correction steps (last ep): {error_correction_steps_per_episode[-1] if error_correction_steps_per_episode else 0}")
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
                last_ep_idx = max(0, len(training_rewards_per_episode) - 1)
                fig_3d = generate_3d_resource_chart(
                    last_resource_trajectory,
                    env_config.prosperity_target,
                    last_ep_idx,
                )
                wandb.log({"3D_Resource_Trajectory": wandb.Plotly(fig_3d)})
    except Exception:
        pass

    # Save latest trajectory for the webpage demo + hyperscale bundle (time, value, target, phase proxy + kernel traces)
    os.makedirs("results", exist_ok=True)
    np.save("results/last_resource_trajectory.npy", np.array(last_resource_trajectory))
    hyperscale_path = os.path.join("results", "last_hyperscale_trajectory.npz")
    n_rw = len(last_rewards_per_step)
    n_r = len(last_resource_trajectory)
    n_hs = min(max(0, n_r - 1), n_rw)
    if n_hs > 0:
        steps = np.arange(n_hs, dtype=np.int64)
        resource_after = np.asarray(last_resource_trajectory[1 : n_hs + 1], dtype=np.float64)
        mean_reward_step = np.asarray(last_rewards_per_step[:n_hs], dtype=np.float64)
        prosperity_col = np.full(n_hs, env_config.prosperity_target, dtype=np.float64)
        rp = max(int(env_config.regen_period), 1)
        time_phase_proxy = (steps % rp).astype(np.float64) / float(rp)
        anom = np.zeros(n_hs, dtype=np.float64)
        for i in range(min(n_hs, len(last_ep_anomaly_scores))):
            anom[i] = last_ep_anomaly_scores[i]
        k_anom = np.zeros(n_hs, dtype=np.float64)
        for i in range(min(n_hs, len(last_ep_kernel_anomaly_scores))):
            k_anom[i] = last_ep_kernel_anomaly_scores[i]
        k_hsim = np.zeros(n_hs, dtype=np.float64)
        for i in range(min(n_hs, len(last_ep_kernel_harmony_sim_scores))):
            k_hsim[i] = last_ep_kernel_harmony_sim_scores[i]
        np.savez(
            hyperscale_path,
            step=steps,
            resource_after_step=resource_after,
            mean_reward_step=mean_reward_step,
            prosperity_target=prosperity_col,
            time_phase_proxy=time_phase_proxy,
            anomaly_score=anom,
            quantum_kernel_anomaly_score=k_anom,
            quantum_kernel_harmony_similarity=k_hsim,
            columns=np.array(
                [
                    "step",
                    "resource_after_step",
                    "mean_reward_step",
                    "prosperity_target",
                    "time_phase_proxy",
                    "anomaly_score",
                    "quantum_kernel_anomaly_score",
                    "quantum_kernel_harmony_similarity",
                ]
            ),
        )
    else:
        hyperscale_path = ""

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
        "hyperscale_trajectory_path": hyperscale_path,
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
        prosperity_stability_bonus=float(
            d.get("prosperity_stability_bonus", d.get("stability_bonus_scale", 0.0))
        ),
        prosperity_stability_band=float(d.get("prosperity_stability_band", 0.1)),
        prosperity_stability_sigma=float(
            d.get("prosperity_stability_sigma", d.get("stability_sigma", 0.0))
        ),
        over_invest_drift_scale=float(d.get("over_invest_drift_scale", 0.0)),
        invest_bonus=float(d.get("invest_bonus", 0.0)),
        extract_penalty=float(d.get("extract_penalty", 0.0)),
        invest_reward_multiplier=float(d.get("invest_reward_multiplier", 1.0)),
        extract_reward_multiplier=float(d.get("extract_reward_multiplier", 1.0)),
        semantic_harmony_scale=float(d.get("semantic_harmony_scale", 0.1)),
        semantic_harmony_omega=float(d.get("semantic_harmony_omega", 1.0)),
        error_correction_scale=float(d.get("error_correction_scale", 0.0)),
        error_correction_syndrome_frac=float(d.get("error_correction_syndrome_frac", 0.12)),
        quantum_light_enabled=bool(d.get("quantum_light_enabled", False)),
        photon_mode_dim=int(d.get("photon_mode_dim", 6)),
        photon_shape_cost=float(d.get("photon_shape_cost", 0.02)),
        photon_channel_noise=float(d.get("photon_channel_noise", 0.08)),
        quantum_fidelity_scale=float(d.get("quantum_fidelity_scale", 0.4)),
        quantum_network_scale=float(d.get("quantum_network_scale", 0.2)),
        quantum_memory_capacity=int(d.get("quantum_memory_capacity", 3)),
        quantum_swap_success_base=float(d.get("quantum_swap_success_base", 0.75)),
        quantum_swap_noise_sensitivity=float(d.get("quantum_swap_noise_sensitivity", 0.6)),
    )


def agent_kwargs_from_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Extract agent/coupling knobs from config dict for QuantumGrokAgent."""
    return {
        "sparsity_target": float(d.get("sparsity_target", 0.3)),
        "max_hops": int(d.get("max_hops", 3)),
        "memory_capacity": int(d.get("memory_capacity", 1000)),
    }
