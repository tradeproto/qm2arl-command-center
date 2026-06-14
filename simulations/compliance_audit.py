# simulations/compliance_audit.py
"""
AutoQMS Compliance Audit simulation: runs 8 QM2ARL agents on a ComplianceEnv.

Three presets:
  - iso_qms:   Division 10 — ISO 9001/42001/27001 combined compliance
  - nqa1:      Division 11 — ASME NQA-1 nuclear quality assurance
  - spe_prms:  Division 12 — SPE PRMS reserves audit & RWA tokenization

Reuses full QM2ARL training infrastructure (ENGRAM-ENGN, quantum kernels,
VQC, topology coupling, REINFORCE).

Usage:
    python simulations/compliance_audit.py configs/compliance_iso_qms.yaml
    python simulations/compliance_audit.py configs/compliance_nqa1.yaml
    python simulations/compliance_audit.py configs/compliance_spe_prms.yaml
"""
import os
import sys
import json

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import yaml

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass

from src.compliance_env import (
    ComplianceEnv,
    ComplianceStepResult,
    COMPLIANCE_PRESETS,
    compliance_config_from_dict,
    EXPLORE,
    EXTRACT,
    INVEST,
)
from src.agents import ENGRAMENGN, QuantumGrokAgent
from src.policies import MLPPolicy, SharedTrunkPerAgentHeadPolicy, reinforce_update
from src.qm2arl_trainer import calculate_hmu, topology_extended_obs
from src.quantum_geospatial import get_quantum_anomaly_detector, load_reference_set, save_reference_set


def load_config(config_path: str | None = None) -> dict:
    if config_path is None:
        config_path = os.path.join(PROJECT_ROOT, "configs", "compliance_iso_qms.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    config["config_path"] = os.path.abspath(config_path)
    return config


def run_compliance_training(num_agents: int, config: dict) -> dict:
    """Run multi-agent compliance audit training."""
    import torch

    comp_config = compliance_config_from_dict(config)
    env = ComplianceEnv(num_agents=num_agents, config=comp_config)
    preset = config.get("compliance_preset", config.get("preset", ""))
    domain_names = config.get("domain_names") or COMPLIANCE_PRESETS.get(preset, [f"domain_{i}" for i in range(num_agents)])

    memory_capacity = int(config.get("memory_capacity", 1000))
    prune_threshold = float(config.get("prune_threshold", 0.5))
    engrams = [ENGRAMENGN(memory_capacity=memory_capacity, prune_threshold=prune_threshold) for _ in range(num_agents)]
    agents = [
        QuantumGrokAgent(
            agent_id=i, num_agents=num_agents, obs_dim=env.obs_dim, num_actions=3,
            sparsity_target=float(config.get("sparsity_target", 0.25)),
            max_hops=int(config.get("max_hops", 2)),
            memory_capacity=memory_capacity,
        )
        for i in range(num_agents)
    ]

    num_episodes = int(config.get("num_episodes", 100))
    use_topology = config.get("use_topology", True)
    per_agent = config.get("per_agent_policy_heads", True)
    lr = float(config.get("learning_rate", 0.002))
    gamma = float(config.get("gamma", 0.99))
    reward_scale = float(config.get("reward_scale", 0.01))
    reward_clip = float(config.get("reward_clip", 10.0))
    return_clip = float(config.get("return_clip", 5.0))
    max_steps = int(config.get("max_steps", 300))
    learning = config.get("learning", True)
    seed_val = int(config.get("seed", 42))

    epsilon_start = float(config.get("epsilon_start", 0.5))
    epsilon_end = float(config.get("epsilon_end", 0.05))
    epsilon_decay_episodes = int(config.get("epsilon_decay_episodes", 0))
    decay_episodes = epsilon_decay_episodes if epsilon_decay_episodes > 0 else max(1, int(0.8 * num_episodes))

    vqc_backend = str(config.get("vqc_backend", os.environ.get("QM2ARL_BLUEQUBIT_DEVICE", "")))
    bluequbit_token = str(config.get("bluequbit_token", os.environ.get("BLUEQUBIT_API_TOKEN", "")))

    quantum_kernel_enabled = bool(config.get("quantum_kernel_enabled", False))
    detector = None
    kernel_ref: list[np.ndarray] = []
    harmony_ref: list[np.ndarray] = []
    if quantum_kernel_enabled:
        detector = get_quantum_anomaly_detector(
            feature_dim=int(config.get("quantum_kernel_feature_dim", 8)),
            gamma=float(config.get("quantum_kernel_gamma", 0.5)),
            use_vqc=bool(config.get("use_vqc_feature_map", False)),
            vqc_seed=int(config.get("vqc_seed", 42)),
            vqc_max_wires=int(config.get("vqc_max_wires", 8)),
            vqc_backend=vqc_backend,
            bluequbit_token=bluequbit_token,
        )
        kernel_ref = load_reference_set(config.get("quantum_kernel_ref_path", ""))
    if bool(config.get("quantum_kernel_harmony_ref_enabled", False)):
        harmony_ref = load_reference_set(config.get("quantum_kernel_harmony_ref_path", ""))
        if detector is None:
            detector = get_quantum_anomaly_detector(
                feature_dim=int(config.get("quantum_kernel_feature_dim", 8)),
                gamma=float(config.get("quantum_kernel_gamma", 0.5)),
                use_vqc=bool(config.get("use_vqc_feature_map", False)),
                vqc_seed=int(config.get("vqc_seed", 42)),
                vqc_max_wires=int(config.get("vqc_max_wires", 8)),
                vqc_backend=vqc_backend,
                bluequbit_token=bluequbit_token,
            )

    qk_anom_scale = float(config.get("quantum_kernel_anomaly_bonus_scale", 0.0))
    qk_harm_scale = float(config.get("quantum_kernel_harmony_bonus_scale", 0.0))
    qk_every = int(config.get("quantum_kernel_every_n_steps", 5))
    qk_ref_update = int(config.get("quantum_kernel_ref_update_every", 10))
    qk_ref_max = int(config.get("quantum_kernel_ref_max", 200))
    qk_ref_sample = int(config.get("quantum_kernel_ref_sample_max", 64))
    qk_harm_sample = int(config.get("quantum_kernel_harmony_ref_sample_max", 64))
    qk_harm_max = int(config.get("quantum_kernel_harmony_ref_max", 200))
    qk_harm_thresh = float(config.get("quantum_kernel_harmony_update_threshold", 0.005))

    engram_kp_en = bool(config.get("engram_kernel_prune_enabled", False))
    engram_kp_sim = float(config.get("engram_kernel_similarity_threshold", 0.92))

    obs_dim_ext = env.obs_dim
    if use_topology:
        obs_dim_ext = env.obs_dim + env.obs_dim

    seed = int(config.get("seed", 42))
    if per_agent:
        policy = SharedTrunkPerAgentHeadPolicy(
            obs_dim=obs_dim_ext, num_agents=num_agents, num_actions=3, seed=seed
        )
    else:
        policy = MLPPolicy(obs_dim=obs_dim_ext, num_actions=3, seed=seed)
    optimizer = torch.optim.Adam(policy.parameters(), lr=lr)

    resume = config.get("resume_training", False)
    ckpt_path = config.get("training_checkpoint_path", "")
    ckpt_every = int(config.get("checkpoint_every_episodes", 1))
    start_ep = 0
    if resume and ckpt_path and os.path.isfile(os.path.join(PROJECT_ROOT, ckpt_path)):
        ckpt = torch.load(os.path.join(PROJECT_ROOT, ckpt_path), weights_only=False)
        policy.load_state_dict(ckpt["policy"])
        optimizer.load_state_dict(ckpt["optimizer"])
        start_ep = ckpt.get("episode", 0)
        print(f"  Resumed from checkpoint episode {start_ep}")

    all_rewards = []
    all_hmu = []
    best_report = None
    best_hmu = -1e9

    targets = np.array(comp_config.compliance_targets, dtype=np.float64)
    target_sum = float(np.sum(targets))
    budget = 1.0

    print(f"\n=== AutoQMS Compliance Training ===")
    print(f"  Preset: {preset}")
    print(f"  Domains: {domain_names}")
    print(f"  Targets: {list(comp_config.compliance_targets)}")
    print(f"  Episodes: {num_episodes}, agents: {num_agents}")
    print(f"  Quantum kernel: {quantum_kernel_enabled}, VQC: {bool(config.get('use_vqc_feature_map', False))}")
    print()

    G = nx.cycle_graph(num_agents) if use_topology else nx.empty_graph(num_agents)

    for ep in range(start_ep, num_episodes):
        frac = min(1.0, ep / max(1, decay_episodes))
        epsilon = epsilon_start + (epsilon_end - epsilon_start) * frac

        obs, _ = env.reset(seed=seed_val + ep)
        ep_rewards = np.zeros(num_agents, dtype=np.float64)
        obs_list: list[np.ndarray] = []
        action_list: list[np.ndarray] = []
        reward_list: list[np.ndarray] = []
        result: ComplianceStepResult | None = None

        for step_i in range(max_steps):
            obs_ext = topology_extended_obs(obs, G) if use_topology else obs
            greedy = np.random.rand() >= epsilon
            if greedy:
                actions, _ = policy.sample_actions(obs_ext, deterministic=True)
            else:
                actions = np.random.randint(0, 3, size=num_agents)

            result = env.step(actions)
            obs = result.observations
            rews = result.rewards.copy()

            if detector is not None and step_i % qk_every == 0:
                x = np.mean(obs_ext, axis=0)
                refs = kernel_ref[:qk_ref_sample] if kernel_ref else []
                if refs and qk_anom_scale:
                    rews += qk_anom_scale * detector.kernel_anomaly_score(x, refs)
                if harmony_ref and qk_harm_scale:
                    hrefs = harmony_ref[:qk_harm_sample]
                    sims = [detector.quantum_kernel(x, r) for r in hrefs]
                    if sims:
                        rews += qk_harm_scale * float(np.mean(sims)) / num_agents

            rews_clipped = np.clip(rews * reward_scale, -reward_clip, reward_clip)
            ep_rewards += rews_clipped
            obs_list.append(obs_ext)
            action_list.append(actions.astype(np.int64))
            reward_list.append(rews_clipped.copy())

            for i in range(num_agents):
                engrams[i].add_memory(
                    obs[i], int(actions[i]), float(rews_clipped[i]),
                    obs[i], float(np.mean(obs[:, 0])),
                )

            if result.dones[0]:
                break

        if learning and reward_list:
            reinforce_update(
                policy, optimizer, obs_list, action_list, reward_list,
                gamma=gamma, return_clip=return_clip,
            )

        mean_score = float(np.mean([info["score"] for info in (result.infos if result else [])]))
        hmu = calculate_hmu(mean_score, float(np.mean(targets)), budget, 0, num_agents, 1.0)
        all_rewards.append(float(np.mean(ep_rewards)))
        all_hmu.append(hmu)

        report = env.get_compliance_report()
        if hmu > best_hmu:
            best_hmu = hmu
            best_report = report

        if quantum_kernel_enabled and detector is not None and ep % qk_ref_update == 0:
            flat = obs.ravel().astype(np.float64)
            kernel_ref.append(flat.copy())
            if len(kernel_ref) > qk_ref_max:
                kernel_ref = kernel_ref[-qk_ref_max:]
            save_reference_set(kernel_ref, config.get("quantum_kernel_ref_path", ""))

            if harmony_ref is not None and hmu > qk_harm_thresh:
                harmony_ref.append(flat.copy())
                if len(harmony_ref) > qk_harm_max:
                    harmony_ref = harmony_ref[-qk_harm_max:]
                save_reference_set(harmony_ref, config.get("quantum_kernel_harmony_ref_path", ""))

        if engram_kp_en and detector is not None and ep % 5 == 0:
            for eng in engrams:
                if len(eng.memory_buffer) > memory_capacity * 0.9:
                    eng.prune()

        if ckpt_path and ep % ckpt_every == 0:
            torch.save({
                "policy": policy.state_dict(),
                "optimizer": optimizer.state_dict(),
                "episode": ep + 1,
            }, os.path.join(PROJECT_ROOT, ckpt_path))

        if ep % 5 == 0 or ep == num_episodes - 1:
            domain_scores = " | ".join(
                f"{info['domain'][:8]}:{info['compliance_pct']:.0f}%"
                for info in result.infos
            )
            print(
                f"  Episode {ep+1}/{num_episodes} | "
                f"Hmu={hmu:.4f} | "
                f"Overall={report['overall_compliance_pct']:.1f}% [{report['overall_status']}] | "
                f"eps={epsilon:.3f}"
            )
            print(f"    {domain_scores}")

    if ckpt_path:
        cp = os.path.join(PROJECT_ROOT, ckpt_path)
        if config.get("training_checkpoint_remove_on_complete") and os.path.isfile(cp):
            os.remove(cp)

    exp_name = config.get("experiment_name", preset)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].plot(all_rewards, linewidth=0.8)
    axes[0].set_title(f"AutoQMS [{exp_name}] — Mean Reward")
    axes[0].set_xlabel("Episode")
    axes[0].set_ylabel("Reward")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(all_hmu, linewidth=0.8, color="green")
    axes[1].set_title(f"AutoQMS [{exp_name}] — Harmony (Hμ)")
    axes[1].set_xlabel("Episode")
    axes[1].set_ylabel("Hμ")
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plot_path = os.path.join(PROJECT_ROOT, "results", f"autoqms_{preset}_rewards.png")
    plt.savefig(plot_path, dpi=150)
    plt.close()
    print(f"\n  Plot saved: {plot_path}")

    if best_report:
        print(f"\n=== Best Compliance Report (Hmu={best_hmu:.4f}) ===")
        print(f"  Overall: {best_report['overall_compliance_pct']:.1f}% — {best_report['overall_status']}")
        for d in best_report["domains"]:
            print(f"    {d['domain']:30s}  {d['score_pct']:5.1f}%  [{d['status']}]  gap={d['gap_pct']:.1f}%")

    summary_path = _write_training_summary(config, preset, num_episodes, best_hmu, best_report)

    return {
        "experiment": exp_name,
        "preset": preset,
        "episodes": num_episodes,
        "best_hmu": best_hmu,
        "best_report": best_report,
        "final_rewards": all_rewards,
        "summary_path": summary_path,
    }


def _write_training_summary(
    config: dict,
    preset: str,
    num_episodes: int,
    best_hmu: float,
    best_report: dict | None,
) -> str:
    """Persist training snapshot for AutoQMS dashboard (JSON)."""
    if not best_report:
        return ""
    domains_out = {}
    init_scores = []
    for d in best_report.get("domains", []):
        domains_out[d["domain"]] = {
            "score_pct": d["score_pct"],
            "status": d["status"],
            "gap_pct": d.get("gap_pct", 0.0),
        }
        init_scores.append(round(d["score_pct"] / 100.0, 4))
    payload = {
        "experiment": config.get("experiment_name", preset),
        "preset": preset,
        "episodes": num_episodes,
        "best_hmu": round(float(best_hmu), 4),
        "best_overall_pct": best_report.get("overall_compliance_pct"),
        "best_status": best_report.get("overall_status"),
        "compliance_init": init_scores,
        "domains": domains_out,
        "config_path": config.get("config_path", ""),
    }
    out = os.path.join(PROJECT_ROOT, "results", f"autoqms_{preset}_training_summary.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"\n  Summary saved: {out}")
    return out


if __name__ == "__main__":
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else None
    config = load_config(cfg_path)
    n = int(config.get("num_agents", 8))
    run_compliance_training(n, config)
