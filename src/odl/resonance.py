"""
System Resonance kernel — the core of the Omni-Dimensional Ledger.

"Resonance" is given a precise, defensible definition. A flourishing system is
not one where a single number is maximized; it is one where the value
dimensions are simultaneously **high** (magnitude) and **synchronized**
(coherence) — none sacrificed for another. We measure that two ways and combine:

  1. Magnitude  M = Σ wᵢ aᵢ           weighted mean of dimension scores (how high).

  2. Phase coherence  ρ  (Kuramoto order parameter):
        treat each dimension as an oscillator with amplitude aᵢ and a phase
        θᵢ = π·(aᵢ − targetᵢ)  (0 when on-target, ± when above/below).
        ρ = | Σ aᵢ e^{iθᵢ} | / Σ aᵢ  ∈ [0,1]
        ρ → 1 when all dimensions sit at their targets in phase (synchronized);
        ρ drops when some dimensions race ahead while others collapse.
        This is the same order parameter that quantifies synchronization in
        coupled-oscillator physics — honest, not metaphorical.

  3. Quantum coherence  Q:
        K(a, target) = |⟨φ(a)|φ(target)⟩|²  from the QM2ARL quantum kernel
        (src/quantum_geospatial), run on the same backend ladder as the rest of
        the stack — default.qubit / lightning / BlueQubit cloud. Measures
        alignment of the value state with the flourishing target in an enriched
        feature space.

  System Resonance  R = M · (½ρ + ½Q)  ∈ [0,1]
        High only when the system is both elevated AND coherent.

Optionally fused with the live Harmony Metric Hμ (the dynamical resonance the
QM2ARL agents already optimize) when provided.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .dimension_config import effective_targets, effective_weights
from .dimensions import (
    DIMENSION_ORDER,
    N_DIMENSIONS,
    coverage as _coverage,
    targets_vector,
    to_vector,
    weights_vector,
    Dimension,
)


def _weights() -> np.ndarray:
    try:
        return effective_weights()
    except Exception:
        return weights_vector()


def _targets() -> np.ndarray:
    try:
        return effective_targets()
    except Exception:
        return targets_vector()


@dataclass
class ResonanceState:
    system_resonance: float          # R in [0,1]
    magnitude: float                 # M weighted mean
    phase_coherence: float           # ρ Kuramoto order parameter
    quantum_coherence: float         # Q kernel similarity to target
    hmu: float | None                # fused Harmony Metric, if provided
    verdict: str                     # RESONANT | COHERENT | DISSONANT | FRACTURED
    dimensions: dict[str, float]     # per-dimension scores (canonical order)
    binding_dimension: str           # weakest dimension dragging resonance
    binding_value: float
    backend: str                     # quantum backend used for Q
    coverage: dict[str, Any]
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "system_resonance": round(self.system_resonance, 4),
            "magnitude": round(self.magnitude, 4),
            "phase_coherence": round(self.phase_coherence, 4),
            "quantum_coherence": round(self.quantum_coherence, 4),
            "hmu": round(self.hmu, 4) if self.hmu is not None else None,
            "verdict": self.verdict,
            "dimensions": {k: round(v, 4) for k, v in self.dimensions.items()},
            "binding_dimension": self.binding_dimension,
            "binding_value": round(self.binding_value, 4),
            "backend": self.backend,
            "coverage": self.coverage,
            "notes": self.notes,
        }


def _kuramoto_order_parameter(amplitudes: np.ndarray, targets: np.ndarray) -> float:
    """ρ = |Σ aᵢ e^{iθᵢ}| / Σ aᵢ, θᵢ = π·(aᵢ − targetᵢ)."""
    a = np.clip(amplitudes, 0.0, 1.0)
    total = float(np.sum(a))
    if total <= 1e-9:
        return 0.0
    theta = np.pi * (a - targets)
    z = np.sum(a * np.exp(1j * theta))
    return float(np.clip(np.abs(z) / total, 0.0, 1.0))


def _quantum_coherence(amplitudes: np.ndarray, targets: np.ndarray, *, backend: str) -> tuple[float, str]:
    """Quantum-kernel similarity K(a, target) ∈ [0,1] on the QM2ARL backend ladder."""
    try:
        from src.quantum_geospatial import get_quantum_anomaly_detector

        token = os.environ.get("BLUEQUBIT_API_TOKEN", "")
        detector = get_quantum_anomaly_detector(
            feature_dim=N_DIMENSIONS,
            gamma=0.5,
            use_vqc=True,
            vqc_seed=42,
            vqc_max_wires=N_DIMENSIONS,
            vqc_backend=backend,
            bluequbit_token=token,
        )
        q = float(detector.quantum_kernel(amplitudes, targets))
        return float(np.clip(q, 0.0, 1.0)), detector.active_backend
    except Exception:
        # Classical fallback: cosine-similarity-squared in raw space.
        a = amplitudes / (np.linalg.norm(amplitudes) + 1e-12)
        t = targets / (np.linalg.norm(targets) + 1e-12)
        dot = float(np.clip(np.dot(a, t), -1.0, 1.0))
        return dot * dot, "classical-fallback"


def _verdict(R: float, rho: float) -> str:
    if R >= 0.80 and rho >= 0.85:
        return "RESONANT"
    if R >= 0.65:
        return "COHERENT"
    if R >= 0.45:
        return "DISSONANT"
    return "FRACTURED"


def compute_resonance(
    scores: dict[Dimension | str, float],
    *,
    hmu: float | None = None,
    hmu_weight: float = 0.0,
    vqc_backend: str = "",
) -> ResonanceState:
    """
    Compute the System Resonance state from value-dimension scores.

    scores: partial or full {Dimension|str: value in [0,1]}.
    hmu: optional live Harmony Metric to fuse into resonance (hmu_weight blend).
    vqc_backend: "", "default.qubit", "lightning.qubit", "bluequbit.cpu/gpu".
    """
    backend = vqc_backend or os.environ.get("ODL_QUANTUM_BACKEND", "")
    a = to_vector(scores)
    w = _weights()
    t = _targets()

    magnitude = float(np.dot(w, a))
    rho = _kuramoto_order_parameter(a, t)
    q, active_backend = _quantum_coherence(a, t, backend=backend)

    R = magnitude * (0.5 * rho + 0.5 * q)
    if hmu is not None and hmu_weight > 0.0:
        R = (1.0 - hmu_weight) * R + hmu_weight * float(np.clip(hmu, 0.0, 1.0))
    R = float(np.clip(R, 0.0, 1.0))

    dims = {dim.value: float(a[i]) for i, dim in enumerate(DIMENSION_ORDER)}
    binding_idx = int(np.argmin(a))
    binding_dim = DIMENSION_ORDER[binding_idx].value

    notes: list[str] = []
    cov = _coverage(scores)
    if cov["missing"]:
        notes.append(f"Uncovered dimensions defaulted to target: {', '.join(cov['missing'])}.")
    if active_backend == "classical-fallback":
        notes.append("Quantum kernel unavailable — quantum coherence used classical fallback.")
    elif active_backend.startswith("bluequbit"):
        notes.append("Quantum coherence computed on BlueQubit cloud backend.")

    return ResonanceState(
        system_resonance=R,
        magnitude=magnitude,
        phase_coherence=rho,
        quantum_coherence=q,
        hmu=hmu,
        verdict=_verdict(R, rho),
        dimensions=dims,
        binding_dimension=binding_dim,
        binding_value=float(a[binding_idx]),
        backend=active_backend,
        coverage=cov,
        notes=notes,
    )
