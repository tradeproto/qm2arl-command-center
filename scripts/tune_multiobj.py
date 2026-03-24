#!/usr/bin/env python3
"""
Minimal multi-objective Optuna tuning for TELPAI-QUANTUM / QM2ARL.
Minimize equilibrium_deviation and maximize training_reward_mean — get the Pareto front.

Samplers (multi-objective):
  NSGAIISampler    2–3 objectives (default here)  Fast, reliable Pareto, crowding distance
  NSGAIIISampler   4+ objectives                   Better diversity in high dimensions
  BoTorchSampler   GP + qEI                       Sample-efficient, constraints
  MOEADSampler     Many objectives                Uniform coverage

Usage (from repo root; venv active):
  python3 scripts/tune_multiobj.py
  python3 scripts/tune_multiobj.py --n-trials 50 --base-config configs/experiment1.yaml
"""
from __future__ import annotations

import argparse
import os
import sys

import yaml

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)


def load_config(config_path: str) -> dict:
    if not os.path.isabs(config_path):
        config_path = os.path.join(PROJECT_ROOT, config_path)
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)
    cfg["config_path"] = os.path.abspath(config_path)
    return cfg


def objective(trial: "optuna.Trial", base_config: dict, seed: int) -> tuple[float, float]:
    """Two objectives: (minimize equilibrium_deviation, maximize training_reward_mean)."""
    from src.qm2arl_trainer import run_multi_agent_training

    invest_mult = trial.suggest_float("invest_reward_multiplier", 0.5, 5.0, log=True)
    extract_mult = trial.suggest_float("extract_reward_multiplier", 0.2, 2.0, log=True)
    sigma = trial.suggest_float("prosperity_stability_sigma", 50.0, 300.0)
    stability_bonus = trial.suggest_float("prosperity_stability_bonus", 0.3, 0.8)

    cfg = {
        **base_config,
        "invest_reward_multiplier": invest_mult,
        "extract_reward_multiplier": extract_mult,
        "prosperity_stability_sigma": sigma,
        "prosperity_stability_bonus": stability_bonus,
        "use_wandb": False,
    }

    result = run_multi_agent_training(
        cfg["num_agents"],
        cfg,
        use_agents=True,
        seed=seed,
        learning=True,
        num_episodes=int(cfg.get("num_episodes", 150)),
        use_topology=cfg.get("use_topology", True),
        learning_rate=float(cfg.get("learning_rate", 2e-3)),
        gamma=float(cfg.get("gamma", 0.99)),
    )

    diagnostics = result.get("diagnostics") or {}
    equilibrium_deviation = diagnostics.get("equilibrium_deviation")
    if equilibrium_deviation is None:
        equilibrium_deviation = abs(
            result.get("final_resource", 0.0) - cfg.get("prosperity_target", 500.0)
        )
    training_reward_mean = float(diagnostics.get("training_reward_mean", 0.0))
    return (float(equilibrium_deviation), training_reward_mean)


def main() -> None:
    import optuna
    from optuna.samplers import NSGAIISampler

    parser = argparse.ArgumentParser(description="Multi-objective Optuna (Pareto front)")
    parser.add_argument("--n-trials", type=int, default=50, help="Number of trials")
    parser.add_argument("--base-config", default="configs/experiment1.yaml", help="Base config YAML")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--storage",
        default="sqlite:///telpai_study.db",
        help="Optuna storage (same DB as tune.py for dashboard)",
    )
    args = parser.parse_args()

    base_config = load_config(args.base_config)

    # Empty DB workaround
    if args.storage.startswith("sqlite:///"):
        db_path = args.storage.replace("sqlite:///", "").split("?")[0]
        if not os.path.isabs(db_path):
            db_path = os.path.join(PROJECT_ROOT, db_path)
        if os.path.isfile(db_path) and os.path.getsize(db_path) == 0:
            os.remove(db_path)

    # NSGAIISampler: default for 2–3 objectives, fast and reliable Pareto front
    sampler = NSGAIISampler(seed=args.seed)
    study = optuna.create_study(
        study_name="qm2arl-pareto",
        storage=args.storage,
        load_if_exists=True,
        directions=["minimize", "maximize"],
        sampler=sampler,
    )

    def wrapped(trial: optuna.Trial) -> tuple[float, float]:
        return objective(trial, base_config, args.seed)

    study.optimize(wrapped, n_trials=args.n_trials, show_progress_bar=True)

    # Pareto front: non-dominated solutions
    print("\n--- Pareto front (study.best_trials) ---")
    for t in study.best_trials:
        dev, rew = t.values
        print(f"  Trial {t.number}: equilibrium_deviation={dev:.4f}, training_reward_mean={rew:.4f}")
        print(f"    params: {t.params}")
    print(f"  Total Pareto trials: {len(study.best_trials)}")
    print(f"\nVisualize: optuna-dashboard {args.storage}  →  http://localhost:8080")


if __name__ == "__main__":
    main()
