#!/usr/bin/env python3
"""
Optuna hyperparameter tuning for QM2ARL (multipliers / sigma / stability bonus).

Single-objective (default): minimize equilibrium_deviation.
Multi-objective (--multi-objective): minimize equilibrium_deviation AND maximize
  training_reward_mean — returns the Pareto front of trade-off solutions.

Usage (from repo root; activate venv first):
  python3 scripts/tune.py --n-trials 20
  python3 scripts/tune.py --n-trials 20 --multi-objective   # Pareto: low deviation + high reward
  python3 scripts/tune.py --n-trials 20 --base-config configs/experiment1.yaml
  python3 scripts/tune.py --n-trials 20 --num-episodes 80   # shorter runs per trial
  python3 scripts/tune.py --n-trials 20 --log-wandb         # log each trial to W&B

Visualize & compare (default storage: sqlite:///telpai_study.db):
  From repo root, in a separate terminal (leave it running):
    optuna-dashboard sqlite:///telpai_study.db
  Then open http://localhost:8080 in your browser. If you get ERR_CONNECTION_REFUSED,
  the dashboard is not running — start the command above first. On a remote machine,
  use: optuna-dashboard sqlite:///telpai_study.db --host 0.0.0.0  and forward port 8080.
  Plots: optimization history, parallel coordinates, parameter importance, contours, slices.
  Then take the best params, create a new YAML, and run a long training job with W&B.
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


def objective(
    trial: "optuna.Trial",
    base_config: dict,
    seed: int | None,
    num_episodes_override: int | None = None,
    log_to_wandb: bool = False,
    multi_objective: bool = False,
) -> float | tuple[float, float]:
    """
    Optuna objective: suggest hyperparameters, run one training run.
    Single-objective: return equilibrium_deviation (minimize).
    Multi-objective: return (equilibrium_deviation, training_reward_mean) for
      directions=["minimize", "maximize"] — Pareto front of trade-offs.
    """
    import optuna
    from src.qm2arl_trainer import run_multi_agent_training

    # Suggest same search space as W&B sweep (multipliers / sigma / stability bonus)
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
    }
    if num_episodes_override is not None:
        cfg["num_episodes"] = num_episodes_override
    cfg.setdefault("use_wandb", False)

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
    equilibrium_deviation = float(equilibrium_deviation)
    training_reward_mean = float(diagnostics.get("training_reward_mean", 0.0))

    if log_to_wandb:
        try:
            import wandb
            if wandb.run is None:
                wandb.init(
                    project=base_config.get("wandb_project", "telpai-quantum"),
                    entity=base_config.get("wandb_entity"),
                    name=f"optuna-trial-{trial.number}",
                    config={**trial.params, "trial_number": trial.number},
                )
            wandb.log({
                "equilibrium_deviation": equilibrium_deviation,
                "training_reward_mean": training_reward_mean,
                "trial": trial.number,
            }, step=trial.number)
            wandb.log({f"params/{k}": v for k, v in trial.params.items()})
            wandb.finish()
        except Exception:
            pass

    if multi_objective:
        return (equilibrium_deviation, training_reward_mean)
    return equilibrium_deviation


def main() -> None:
    import optuna

    parser = argparse.ArgumentParser(description="Optuna tuning for QM2ARL (minimize equilibrium_deviation)")
    parser.add_argument("--n-trials", type=int, default=50, help="Number of Optuna trials")
    parser.add_argument(
        "--base-config",
        default="configs/experiment1.yaml",
        help="Base config YAML to merge trial params into",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for training runs")
    parser.add_argument(
        "--storage",
        default="sqlite:///telpai_study.db",
        help="Optuna storage URL (default: telpai_study.db for optuna-dashboard)",
    )
    parser.add_argument(
        "--log-wandb",
        action="store_true",
        help="Log each Optuna trial to W&B (project/entity from base config)",
    )
    parser.add_argument("--study-name", default="qm2arl-equilibrium", help="Optuna study name")
    parser.add_argument(
        "--multi-objective",
        action="store_true",
        help="Minimize equilibrium_deviation AND maximize training_reward_mean (Pareto front)",
    )
    parser.add_argument(
        "--num-episodes",
        type=int,
        default=None,
        help="Override num_episodes per trial (default from base config)",
    )
    args = parser.parse_args()

    base_config = load_config(args.base_config)

    # Avoid StorageInternalError: remove empty/corrupt SQLite DB so Optuna can reinit
    if args.storage.startswith("sqlite:///"):
        db_path = args.storage.replace("sqlite:///", "").split("?")[0]
        if not os.path.isabs(db_path):
            db_path = os.path.join(PROJECT_ROOT, db_path)
        if os.path.isfile(db_path) and os.path.getsize(db_path) == 0:
            os.remove(db_path)

    if args.multi_objective:
        # Directions: minimize deviation (good centering), maximize reward (good policy)
        study = optuna.create_study(
            study_name="qm2arl-pareto",
            storage=args.storage,
            load_if_exists=True,
            directions=["minimize", "maximize"],
        )
    else:
        study = optuna.create_study(
            study_name=args.study_name,
            storage=args.storage,
            load_if_exists=True,
            direction="minimize",
        )

    callbacks = []
    use_wandb_callback = False
    if args.log_wandb and not args.multi_objective:
        try:
            from optuna.integration.wandb import WeightsAndBiasesCallback
            callbacks.append(
                WeightsAndBiasesCallback(
                    metric_name="equilibrium_deviation",
                    wandb_kwargs={
                        "project": base_config.get("wandb_project", "telpai-quantum"),
                        "entity": base_config.get("wandb_entity"),
                    },
                )
            )
            use_wandb_callback = True
        except Exception:
            pass

    log_to_wandb_manual = args.log_wandb and not use_wandb_callback

    def wrapped(trial: optuna.Trial):
        return objective(
            trial,
            base_config,
            args.seed,
            num_episodes_override=args.num_episodes,
            log_to_wandb=log_to_wandb_manual,
            multi_objective=args.multi_objective,
        )

    study.optimize(
        wrapped,
        n_trials=args.n_trials,
        show_progress_bar=True,
        callbacks=callbacks if callbacks else None,
    )

    if args.multi_objective:
        print("\n--- Pareto front (trade-off solutions) ---")
        for i, t in enumerate(study.best_trials):
            v0, v1 = t.values
            print(f"  Trial {t.number}: equilibrium_deviation={v0:.4f}, training_reward_mean={v1:.4f}")
            print(f"    params: {t.params}")
        print(f"  Total Pareto trials: {len(study.best_trials)}")
    else:
        print("\n--- Best trial ---")
        print(f"  equilibrium_deviation: {study.best_value:.4f}")
        print("  params:", study.best_params)

    if args.storage and "sqlite" in args.storage:
        print(f"\nVisualize: optuna-dashboard {args.storage}  →  http://localhost:8080")


if __name__ == "__main__":
    main()
