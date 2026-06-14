#!/usr/bin/env python3
"""
Benchmark the QM2ARL efficient-model levers against the baseline policy.

Compares, on an identical synthetic obs batch:
  - baseline   : src.policies.MLPPolicy (fp32 eager)
  - compiled   : MLPPolicy + torch.compile
  - binarized  : src.efficient_models.BinarizedMLPPolicy (sign-weight BNN)
  - quantized  : MLPPolicy + int8 dynamic quantization
  - pruned     : MLPPolicy + 50% magnitude pruning

Reports params, serialized size, sparsity, forward latency, throughput, and the
action-agreement vs the baseline (how often the efficient policy picks the same
greedy action) so you can see the accuracy/efficiency trade-off.

Run:
    python scripts/verify_efficient_models.py
    python scripts/verify_efficient_models.py --obs-dim 32 --batch 256
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.policies import MLPPolicy, discounted_returns, _HAS_NUMBA  # noqa: E402
from src.efficient_models import (  # noqa: E402
    BinarizedMLPPolicy,
    compile_policy,
    dynamic_quantize_policy,
    magnitude_prune_,
    model_efficiency_report,
)


def _greedy_actions(model, obs: np.ndarray) -> np.ndarray:
    with torch.no_grad():
        logits = model(torch.as_tensor(obs, dtype=torch.float32))
        return logits.argmax(dim=-1).numpy()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--obs-dim", type=int, default=24)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="results/efficient_models_benchmark.json")
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    obs = np.random.randn(args.batch, args.obs_dim).astype(np.float32)

    print(f"\nQM2ARL efficient-models benchmark — obs_dim={args.obs_dim}, "
          f"batch={args.batch}, iters={args.iters}")
    print(f"numba JIT for returns: {'ENABLED' if _HAS_NUMBA else 'fallback (vectorized numpy)'}\n")

    # Baseline
    base = MLPPolicy(obs_dim=args.obs_dim, num_actions=3, seed=args.seed).eval()
    base_actions = _greedy_actions(base, obs)

    variants: dict[str, torch.nn.Module] = {"baseline": base}

    # Compiled (same weights as baseline)
    compiled = compile_policy(MLPPolicy(obs_dim=args.obs_dim, seed=args.seed).eval())
    variants["compiled"] = compiled

    # Binarized
    variants["binarized"] = BinarizedMLPPolicy(obs_dim=args.obs_dim, seed=args.seed).eval()

    # Quantized (int8 dynamic) — same init weights as baseline
    qbase = MLPPolicy(obs_dim=args.obs_dim, seed=args.seed).eval()
    variants["quantized"] = dynamic_quantize_policy(qbase)

    # Pruned (50% magnitude)
    pruned = MLPPolicy(obs_dim=args.obs_dim, seed=args.seed).eval()
    sp = magnitude_prune_(pruned, amount=0.5)
    variants["pruned50"] = pruned

    reports = []
    base_bytes = None
    base_lat = None
    for label, model in variants.items():
        rep = model_efficiency_report(
            model, args.obs_dim, label=label, batch=args.batch, iters=args.iters
        )
        d = rep.as_dict()
        # Action agreement vs baseline
        try:
            acts = _greedy_actions(model, obs)
            d["action_agreement_pct"] = round(100.0 * float(np.mean(acts == base_actions)), 2)
        except Exception:
            d["action_agreement_pct"] = None
        if label == "baseline":
            base_bytes = d["state_dict_bytes"]
            base_lat = d["fwd_latency_ms"]
        d["size_vs_baseline_x"] = (
            round(base_bytes / d["state_dict_bytes"], 2) if base_bytes and d["state_dict_bytes"] else None
        )
        d["speedup_vs_baseline_x"] = (
            round(base_lat / d["fwd_latency_ms"], 2) if base_lat and d["fwd_latency_ms"] else None
        )
        reports.append(d)

    # Table
    cols = ["label", "num_params", "state_dict_bytes", "sparsity_pct",
            "fwd_latency_ms", "speedup_vs_baseline_x", "size_vs_baseline_x",
            "action_agreement_pct"]
    widths = [10, 11, 16, 12, 14, 14, 14, 14]
    header = "".join(c.ljust(w) for c, w in zip(cols, widths))
    print(header)
    print("-" * len(header))
    for d in reports:
        row = "".join(str(d.get(c, "")).ljust(w) for c, w in zip(cols, widths))
        print(row)

    # Quick correctness check on discounted_returns (JIT vs reference)
    rw = np.random.randn(50, 8).astype(np.float64)
    fast = discounted_returns(rw, 0.99)
    ref = np.zeros_like(rw)
    for i in range(rw.shape[1]):
        R = 0.0
        for t in range(rw.shape[0] - 1, -1, -1):
            R = rw[t, i] + 0.99 * R
            ref[t, i] = R
    max_err = float(np.max(np.abs(fast - ref)))
    print(f"\ndiscounted_returns max error vs reference: {max_err:.2e} "
          f"({'OK' if max_err < 1e-6 else 'MISMATCH'})")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(
            {"config": vars(args), "numba": _HAS_NUMBA,
             "returns_max_err": max_err, "variants": reports},
            f, indent=2,
        )
    print(f"\nSaved: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
