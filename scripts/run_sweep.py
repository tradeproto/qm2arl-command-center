#!/usr/bin/env python3
"""
Launch a W&B hyperparameter sweep for QM2ARL (multipliers/sigma).

Usage (run from repo root; activate venv first: source .venv/bin/activate):
  python3 scripts/run_sweep.py [--count 10]
  python3 scripts/run_sweep.py --count 10 --base-config configs/experiment1.yaml
  python3 -m wandb agent ENTITY/PROJECT/SWEEP_ID --count 10   # run agents (use printed SWEEP_ID)

Start with 10–20 trials (--count 10). Early stopping (hyperband) saves compute.

After 10+ runs: edit configs/sweep_multipliers_sigma.yaml (method: random → method: bayes),
then re-run this script. That starts a new sweep with Bayesian search; W&B will suggest
better hyperparams as it runs.
"""
from __future__ import annotations

import argparse
import os
import sys

import yaml

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# Append (don't insert) so a local "wandb" run dir at repo root doesn't shadow the installed package
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)


def load_config(config_path: str) -> dict:
    if not os.path.isabs(config_path):
        config_path = os.path.join(PROJECT_ROOT, config_path)
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)
    cfg["config_path"] = os.path.abspath(config_path)
    return cfg


def train_fn():
    """Called by wandb.agent for each trial. Init must run first so wandb.config is populated."""
    import wandb
    from simulations.basic_qm2arl_scale import run_simulation

    # Agent may not have inited yet; init here so wandb.config has the sweep run's params
    if wandb.run is None:
        wandb.init(
            project=os.environ.get("WANDB_PROJECT") or os.environ.get("SWEEP_PROJECT"),
            entity=os.environ.get("WANDB_ENTITY") or os.environ.get("SWEEP_ENTITY"),
        )

    base_config_path = os.environ.get("SWEEP_BASE_CONFIG", "configs/experiment1.yaml")
    if not os.path.isabs(base_config_path):
        base_config_path = os.path.join(PROJECT_ROOT, base_config_path)
    cfg = load_config(base_config_path)
    cfg = {**cfg, **dict(wandb.config)}
    run_simulation(cfg["num_agents"], cfg)


def main():
    parser = argparse.ArgumentParser(description="Run W&B sweep for QM2ARL")
    parser.add_argument(
        "--sweep-yaml",
        default=os.path.join(PROJECT_ROOT, "configs", "sweep_multipliers_sigma.yaml"),
        help="Path to sweep YAML",
    )
    parser.add_argument("--count", type=int, default=10, help="Number of trials (e.g. 10–20 for first test)")
    parser.add_argument(
        "--base-config",
        default="configs/experiment1.yaml",
        help="Base config to merge sweep params into",
    )
    parser.add_argument("--project", default=None, help="W&B project (default from base config)")
    parser.add_argument("--entity", default=None, help="W&B entity (default from base config)")
    args = parser.parse_args()

    sweep_path = args.sweep_yaml
    if not os.path.isabs(sweep_path):
        sweep_path = os.path.join(PROJECT_ROOT, sweep_path)
    with open(sweep_path, "r") as f:
        sweep_config = yaml.safe_load(f)

    base_cfg = load_config(args.base_config)
    project = args.project or base_cfg.get("wandb_project", "telpai-quantum")
    entity = args.entity or base_cfg.get("wandb_entity")

    # So train_fn can load base config and init wandb with correct project/entity
    os.environ["SWEEP_BASE_CONFIG"] = args.base_config
    os.environ["SWEEP_PROJECT"] = project
    os.environ["SWEEP_ENTITY"] = entity or ""

    # Import wandb with project root out of path so a local "wandb" run dir doesn't shadow the package
    if PROJECT_ROOT in sys.path:
        sys.path.remove(PROJECT_ROOT)
    import wandb
    if PROJECT_ROOT not in sys.path:
        sys.path.append(PROJECT_ROOT)

    if not hasattr(wandb, "sweep"):
        sys.exit(
            "wandb.sweep not found. Activate the project venv (e.g. source .venv/bin/activate) and run again.\n"
            "If the error persists, rename the repo root 'wandb' folder (e.g. to wandb_runs) so it does not shadow the package."
        )

    sweep_id = wandb.sweep(
        sweep_config,
        project=project,
        entity=entity,
    )
    print(f"Sweep created: {sweep_id}. Running {args.count} trials.")
    if entity and project:
        print(f"Run more agents (other terminals): paste this line and use the ID above (not the word SWEEP_ID):")
        print(f"  python3 -m wandb agent {entity}/{project}/{sweep_id} --count {args.count}")
    wandb.agent(sweep_id, function=train_fn, count=args.count)


if __name__ == "__main__":
    main()
