# simulations/basic_qm2arl_scale.py
"""
Basic QM2ARL scale simulation: TELPAIEnv + multi-agent training loop.
Uses real rewards from the resource economy environment.
"""
import os
import sys

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import yaml

# Add project root for imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.qm2arl_trainer import run_multi_agent_training


def load_config(config_path: str = None):
    if config_path is None:
        config_path = os.path.join(PROJECT_ROOT, "configs", "default.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    # So wandb can save the config file as an artifact
    config["config_path"] = os.path.abspath(config_path)
    return config


def run_simulation(num_agents: int, config: dict):
    learning = config.get("learning", False)
    mode = "learning (Grok topology + REINFORCE)" if learning else "rollout (dummy policy)"
    # Multi-seed: run_seeds=[42, 43, 44] creates one W&B run per seed for variance comparison
    seeds = config.get("run_seeds", [config.get("seed", 42)])
    seeds = list(seeds) if hasattr(seeds, "__iter__") and not isinstance(seeds, str) else [seeds]

    result = None
    for i, seed in enumerate(seeds):
        seed = int(seed)
        np.random.seed(seed)
        if len(seeds) > 1:
            print(f"Starting simulation with {num_agents} agents — {mode} (seed={seed} [{i+1}/{len(seeds)}])")
        else:
            print(f"Starting simulation with {num_agents} agents — {mode}")
        result = run_multi_agent_training(
            num_agents,
            config,
            use_agents=True,
            seed=seed,
            learning=learning,
            num_episodes=int(config.get("num_episodes", 50)),
            use_topology=config.get("use_topology", True),
            learning_rate=float(config.get("learning_rate", 1e-3)),
            gamma=float(config.get("gamma", 0.99)),
        )
        if len(seeds) > 1:
            print(f"  Seed {seed} — final_resource: {result['final_resource']:.2f}")

    rewards = result["rewards_per_step"]
    resource_traj = result["resource_trajectory"]
    training_rewards = result.get("training_rewards_per_episode")
    topology_graph = result.get("topology_graph")

    # Plot: last-episode reward + resource; if learning, add training curve; if topology, add graph
    n_plots = 3 if training_rewards else 2
    if topology_graph is not None:
        n_plots += 1
    fig, axes = plt.subplots(n_plots, 1, sharex=False, figsize=(8, 2.5 * n_plots))
    axes = np.atleast_1d(axes)
    ax1, ax2 = axes[0], axes[1]
    ax3 = axes[2] if n_plots >= 3 else None
    ax_graph = axes[3] if n_plots >= 4 else None

    ax1.plot(rewards, color="C0")
    ax1.set_ylabel("Mean reward")
    ax1.set_title(f"Last episode: reward over steps (N={num_agents})")
    ax1.grid(True, alpha=0.3)

    ax2.plot(resource_traj, color="C1")
    ax2.set_ylabel("Resource level")
    ax2.set_xlabel("Step")
    ax2.set_title("Shared resource (last episode)")
    ax2.grid(True, alpha=0.3)

    if training_rewards and ax3 is not None:
        ax3.plot(training_rewards, color="C2")
        ax3.set_ylabel("Episode mean reward")
        ax3.set_xlabel("Episode")
        ax3.set_title("Training progress (Grok topology + REINFORCE)")
        ax3.grid(True, alpha=0.3)

    if topology_graph is not None and ax_graph is not None:
        pos = nx.circular_layout(topology_graph) if topology_graph.number_of_nodes() > 0 else {}
        nx.draw(
            topology_graph,
            pos=pos,
            ax=ax_graph,
            with_labels=True,
            node_color="lightblue",
            node_size=400,
            font_size=10,
            edge_color="gray",
        )
        ax_graph.set_title("Coupling topology (agent graph)")
        ax_graph.axis("off")

    plt.tight_layout()
    out_dir = os.path.join(PROJECT_ROOT, "results")
    os.makedirs(out_dir, exist_ok=True)
    suffix = "learning" if learning else "rollout"
    out_path = os.path.join(out_dir, f"rewards_n{num_agents}_{suffix}.png")
    plt.savefig(out_path)
    plt.close()

    print("Simulation done. Plot saved.")
    print(f"  Mean reward (last episode): {result['mean_reward']:.4f}")
    print(f"  Final resource: {result['final_resource']:.2f}")
    if training_rewards:
        print(f"  Training: first ep reward {training_rewards[0]:.4f} -> last ep {training_rewards[-1]:.4f}")
    print(f"  Plot: {os.path.abspath(out_path)}")


if __name__ == "__main__":
    config_path = None
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
        if not os.path.isabs(config_path):
            config_path = os.path.join(PROJECT_ROOT, config_path)
    else:
        # Sweep: agent runs without argv; get config_path from wandb after init
        if os.environ.get("WANDB_SWEEP_ID"):
            import wandb
            wandb.init(project=os.environ.get("WANDB_PROJECT", "telpai-quantum"), entity=os.environ.get("WANDB_ENTITY"))
            config_path = wandb.config.get("config_path", "configs/experiment1.yaml")
            if not os.path.isabs(config_path):
                config_path = os.path.join(PROJECT_ROOT, config_path)
    cfg = load_config(config_path)

    # Sweep compatibility: init wandb early so sweep agent can inject config; merge into cfg
    if cfg.get("use_wandb", False) or os.environ.get("WANDB_SWEEP_ID"):
        import wandb
        if wandb.run is None:
            wandb.init(
                project=cfg.get("wandb_project", "telpai-quantum"),
                entity=cfg.get("wandb_entity"),
                config=cfg,
            )
        cfg = {**cfg, **dict(wandb.config)}

    run_simulation(cfg["num_agents"], cfg)
