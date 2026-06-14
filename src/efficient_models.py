"""
Efficient-model layer for QM2ARL — the "binary optimization + compiler" track.

Three independent levers, all optional and fail-safe (fall back to the standard
full-precision Python path if a dependency is missing):

  1. COMPILE   — ``compile_policy()`` wraps a policy with ``torch.compile`` so the
                 forward/backward hot path is fused into compiled kernels instead
                 of interpreted op-by-op eager mode. This is the "bypass the
                 interpreter" lever. No-op (returns the policy unchanged) if
                 torch.compile is unavailable or fails.

  2. BINARIZE  — ``BinaryLinear`` / ``BinarizedMLPPolicy`` implement Binarized
                 Neural Network (BNN) layers: weights are projected to {-1, +1}
                 in the forward pass via ``sign``, with a straight-through
                 estimator (STE) so gradients still flow to the latent
                 full-precision weights during training. This is the literal
                 "binary" lever — ~32x smaller weights, sign-only MACs.

  3. QUANTIZE  — ``dynamic_quantize_policy()`` applies PyTorch int8 dynamic
                 quantization to Linear layers for fast, small inference-time
                 policies (deployment on the office server / edge / TELPAI).

COMPLIANCE NOTE: quantized / binarized policies change numerical results. For
anything entering Chapman's NQA-1 pilot, keep the full-precision reference run
as the validated "golden" artifact. The efficient variants are for throughput
and edge deployment, with the reference kept for audit traceability.
"""
from __future__ import annotations

import io
import math
import time
from dataclasses import dataclass, asdict
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


# ──────────────────────────────────────────────────────────────────────────
# Lever 1 — COMPILE the hot path
# ──────────────────────────────────────────────────────────────────────────
def compile_policy(policy: nn.Module, *, mode: str = "default", enabled: bool = True) -> nn.Module:
    """
    Wrap ``policy`` with ``torch.compile`` for fused kernels. Fail-safe: returns
    the original policy unchanged if compilation is unavailable or errors.

    mode: one of torch.compile modes — "default", "reduce-overhead",
          "max-autotune". "reduce-overhead" is usually best for the small,
          repeatedly-called policy nets here.
    """
    if not enabled:
        return policy
    compile_fn = getattr(torch, "compile", None)
    if compile_fn is None:
        return policy
    try:
        compiled = compile_fn(policy, mode=mode, dynamic=True)
        # torch.compile returns an nn.Module-like wrapper that proxies attributes,
        # so our custom methods (sample_actions, logits_and_log_probs) still work.
        return compiled
    except Exception:
        return policy


# ──────────────────────────────────────────────────────────────────────────
# Lever 2 — BINARIZED layers (BNN) with straight-through estimator
# ──────────────────────────────────────────────────────────────────────────
class _BinarizeSTE(torch.autograd.Function):
    """sign() in forward, identity (clipped) gradient in backward (STE)."""

    @staticmethod
    def forward(ctx, x: torch.Tensor) -> torch.Tensor:
        ctx.save_for_backward(x)
        # sign with 0 -> +1 so we never emit a zero weight
        return torch.where(x >= 0, torch.ones_like(x), -torch.ones_like(x))

    @staticmethod
    def backward(ctx, grad_output: torch.Tensor):
        (x,) = ctx.saved_tensors
        # Cancel gradient where |x| > 1 (htanh derivative); pass through otherwise.
        grad = grad_output.clone()
        grad[x.abs() > 1.0] = 0.0
        return grad


def binarize(x: torch.Tensor) -> torch.Tensor:
    return _BinarizeSTE.apply(x)


class BinaryLinear(nn.Module):
    """
    Linear layer with binarized weights {-1, +1} and a per-output-channel
    scale (alpha = mean |W|), following the XNOR-Net real-valued scaling.

    Latent full-precision weights are kept for training; only their sign (times
    alpha) is used in the forward pass. At deploy time the sign matrix packs to
    1 bit/weight, so the effective model is ~32x smaller than fp32.
    """

    def __init__(self, in_features: int, out_features: int, bias: bool = True):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.weight = nn.Parameter(torch.empty(out_features, in_features))
        self.bias = nn.Parameter(torch.zeros(out_features)) if bias else None
        nn.init.kaiming_uniform_(self.weight, a=math.sqrt(5))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Per-output-row scale keeps activations in a sane range.
        alpha = self.weight.abs().mean(dim=1, keepdim=True)  # (out, 1)
        w_bin = binarize(self.weight) * alpha
        return F.linear(x, w_bin, self.bias)

    @torch.no_grad()
    def packed_bits(self) -> int:
        """Storage in bits if weights were bit-packed (sign) + fp32 alpha scales."""
        return self.weight.numel() + 32 * self.out_features


class _BinaryPolicyMixin:
    """Shared action/entropy API so binarized policies are drop-in replacements."""

    def logits_and_log_probs(self, obs: np.ndarray, actions: np.ndarray):
        obs_t = torch.as_tensor(obs, dtype=torch.float32)
        logits = self.forward(obs_t)
        log_probs = F.log_softmax(logits, dim=-1)
        actions_t = torch.as_tensor(actions, dtype=torch.long)
        chosen = log_probs.gather(-1, actions_t.unsqueeze(-1)).squeeze(-1)
        return logits, chosen

    def sample_actions(self, obs: np.ndarray, deterministic: bool = False):
        with torch.no_grad():
            obs_t = torch.as_tensor(obs, dtype=torch.float32)
            logits = self.forward(obs_t)
            probs = F.softmax(logits, dim=-1)
            if deterministic:
                actions = logits.argmax(dim=-1)
            else:
                actions = torch.distributions.Categorical(probs=probs).sample()
            log_probs = F.log_softmax(logits, dim=-1).gather(
                -1, actions.unsqueeze(-1)
            ).squeeze(-1)
            return actions.numpy(), log_probs.numpy()

    def mean_normalized_entropy(self, obs: np.ndarray) -> float:
        with torch.no_grad():
            obs_t = torch.as_tensor(obs, dtype=torch.float32)
            logits = self.forward(obs_t)
            logp = F.log_softmax(logits, dim=-1)
            p = logp.exp()
            h = -(p * logp).sum(dim=-1)
            h_max = math.log(max(self.num_actions, 2))
            return float((h / h_max).mean().cpu())


class BinarizedMLPPolicy(_BinaryPolicyMixin, nn.Module):
    """
    Drop-in binarized replacement for ``src.policies.MLPPolicy``.

    Input and output projections stay full-precision (standard BNN practice —
    binarizing the first/last layer hurts accuracy disproportionately); the
    hidden layers are binarized. BatchNorm between binary layers stabilizes the
    sign activations.
    """

    def __init__(
        self,
        obs_dim: int,
        num_actions: int = 3,
        hidden_dims: tuple[int, ...] = (64, 32),
        seed: int | None = None,
    ):
        super().__init__()
        if seed is not None:
            torch.manual_seed(seed)
        self.obs_dim = obs_dim
        self.num_actions = num_actions
        self.hidden_dims = tuple(hidden_dims)

        layers: list[nn.Module] = []
        # Full-precision input projection.
        layers.append(nn.Linear(obs_dim, hidden_dims[0]))
        layers.append(nn.BatchNorm1d(hidden_dims[0]))
        layers.append(nn.Hardtanh(inplace=True))
        # Binarized hidden stack.
        for i in range(len(hidden_dims) - 1):
            layers.append(BinaryLinear(hidden_dims[i], hidden_dims[i + 1]))
            layers.append(nn.BatchNorm1d(hidden_dims[i + 1]))
            layers.append(nn.Hardtanh(inplace=True))
        self.features = nn.Sequential(*layers)
        # Full-precision output head.
        self.head = nn.Linear(hidden_dims[-1], num_actions)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.dim() == 1:
            x = x.unsqueeze(0)
        # BatchNorm1d needs >1 row in train mode; switch to eval-style for tiny batches.
        if self.training and x.shape[0] < 2:
            was_training = True
            self.features.eval()
            z = self.features(x)
            self.features.train()
        else:
            z = self.features(x)
        return self.head(z)


# ──────────────────────────────────────────────────────────────────────────
# Lever 3 — int8 dynamic QUANTIZATION (inference)
# ──────────────────────────────────────────────────────────────────────────
def dynamic_quantize_policy(policy: nn.Module) -> nn.Module:
    """
    Apply int8 dynamic quantization to all Linear layers for fast, small
    inference. Returns a quantized copy in eval mode. Fail-safe: returns the
    original policy if the quantization backend is unavailable.

    Dynamic quantization is inference-only — use after training. Weights become
    int8; activations are quantized on the fly per-batch.
    """
    try:
        policy_eval = policy.eval()
        return torch.ao.quantization.quantize_dynamic(
            policy_eval, {nn.Linear}, dtype=torch.qint8
        )
    except Exception:
        try:
            return torch.quantization.quantize_dynamic(
                policy.eval(), {nn.Linear}, dtype=torch.qint8
            )
        except Exception:
            return policy


# ──────────────────────────────────────────────────────────────────────────
# Measurement / reporting
# ──────────────────────────────────────────────────────────────────────────
@dataclass
class EfficiencyReport:
    label: str
    num_params: int
    nonzero_params: int
    sparsity_pct: float
    state_dict_bytes: int
    fwd_latency_ms: float
    throughput_rows_per_s: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _state_dict_bytes(model: nn.Module) -> int:
    buf = io.BytesIO()
    torch.save(model.state_dict(), buf)
    return buf.tell()


def model_efficiency_report(
    model: nn.Module,
    obs_dim: int,
    *,
    label: str = "model",
    batch: int = 64,
    iters: int = 50,
) -> EfficiencyReport:
    """Measure params, sparsity, serialized size, and forward latency."""
    model.eval()
    params = [p for p in model.parameters()]
    n_params = int(sum(p.numel() for p in params))
    nonzero = int(sum(int((p != 0).sum()) for p in params))
    sparsity = 100.0 * (1.0 - nonzero / max(n_params, 1))

    x = torch.randn(batch, obs_dim, dtype=torch.float32)
    with torch.no_grad():
        for _ in range(3):  # warmup (also triggers torch.compile tracing)
            model(x)
        t0 = time.perf_counter()
        for _ in range(iters):
            model(x)
        dt = time.perf_counter() - t0
    latency_ms = 1000.0 * dt / iters
    throughput = (batch * iters) / dt if dt > 0 else float("inf")

    return EfficiencyReport(
        label=label,
        num_params=n_params,
        nonzero_params=nonzero,
        sparsity_pct=round(sparsity, 3),
        state_dict_bytes=_state_dict_bytes(model),
        fwd_latency_ms=round(latency_ms, 4),
        throughput_rows_per_s=round(throughput, 1),
    )


def magnitude_prune_(model: nn.Module, amount: float = 0.3) -> float:
    """
    In-place global magnitude pruning: zero the smallest-|w| fraction of Linear
    weights. Pairs with binarization/quantization for "super-efficient" models.
    Returns the achieved sparsity fraction. amount in [0, 1).
    """
    amount = float(max(0.0, min(0.99, amount)))
    if amount == 0.0:
        return 0.0
    weights = [m.weight for m in model.modules() if isinstance(m, nn.Linear)]
    if not weights:
        return 0.0
    all_abs = torch.cat([w.detach().abs().flatten() for w in weights])
    k = int(amount * all_abs.numel())
    if k <= 0:
        return 0.0
    threshold = torch.kthvalue(all_abs, k).values
    with torch.no_grad():
        for w in weights:
            w.mul_((w.abs() > threshold).to(w.dtype))
    total = sum(w.numel() for w in weights)
    zeros = sum(int((w == 0).sum()) for w in weights)
    return zeros / max(total, 1)
