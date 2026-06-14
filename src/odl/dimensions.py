"""
Omni-Dimensional Ledger (ODL) — value dimensions.

The OmniDirectional Ledger whitepaper records value on the 3-axis Trinity Matrix
(economic · ecological · social). The Omni-Dimensional Ledger generalizes that
to an N-dimensional value space so the ledger can "see" everything a one-
dimensional ledger (GDP, share price) erodes.

Each dimension is a measurable scalar in [0, 1] with a target (the level a
flourishing system holds) and a weight (relative importance in the resonance
magnitude). "Coherence" and "Connection/Love" are NOT mysticism here — they are
defined as concrete, computable proxies (verifiable-information integrity and
cooperative/relational alignment respectively), exactly as Hμ encodes harmony
in src/qm2arl_trainer.py.

Honest scope: the dimensions and math are OPERATIONAL (computed, reproducible).
Planetary-scale instrumentation of every proxy is ASPIRATIONAL — the ledger
accepts whatever signals are available and is explicit about coverage.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np


class Dimension(str, Enum):
    """The six value axes of the Omni-Dimensional Ledger."""
    PROSPERITY = "prosperity"      # economic utility, livelihoods, honest surplus (Wealth)
    PLANET = "planet"              # ecological integrity, regeneration within boundaries
    EQUITY = "equity"              # access, fairness — no agent wins by breaking neighbors
    HEALTH = "health"              # human & system vitality, resilience, wellbeing
    KNOWLEDGE = "knowledge"        # verifiable information, audit integrity, truth (Coherence)
    CONNECTION = "connection"      # cooperation, trust, relational alignment (Love)


@dataclass(frozen=True)
class DimensionSpec:
    dimension: Dimension
    label: str
    weight: float            # relative importance in resonance magnitude (normalized later)
    target: float            # flourishing hold-level in [0, 1]
    trinity_pillar: str      # mapping back to the whitepaper Trinity Matrix
    proxy: str               # how it is measured (honest)


# Ordered registry — index position is the canonical dimension order.
DIMENSION_SPECS: tuple[DimensionSpec, ...] = (
    DimensionSpec(Dimension.PROSPERITY, "Prosperity (Wealth)", 1.0, 0.70, "economic",
                  "prosperity-equilibrium, RWA value, LCOE/economic audit scores"),
    DimensionSpec(Dimension.PLANET, "Planet (Ecology)", 1.15, 0.80, "ecological",
                  "CO2 intensity, regeneration, materials lifecycle, footprint"),
    DimensionSpec(Dimension.EQUITY, "Equity (Society)", 1.05, 0.75, "social",
                  "coupling fairness, access, ISO 42001 AI governance compliance"),
    DimensionSpec(Dimension.HEALTH, "Health (Vitality)", 1.10, 0.80, "social",
                  "human/system health & resilience proxies, safety compliance"),
    DimensionSpec(Dimension.KNOWLEDGE, "Knowledge (Coherence)", 1.0, 0.85, "governance",
                  "verifiable-information integrity, audit %, proof-chain completeness"),
    DimensionSpec(Dimension.CONNECTION, "Connection (Love)", 1.0, 0.75, "social",
                  "cooperative alignment Hμ, trust/relational coherence across agents"),
)

DIMENSION_ORDER: tuple[Dimension, ...] = tuple(s.dimension for s in DIMENSION_SPECS)
N_DIMENSIONS = len(DIMENSION_SPECS)
_SPEC_BY_DIM = {s.dimension: s for s in DIMENSION_SPECS}


def spec(dim: Dimension) -> DimensionSpec:
    return _SPEC_BY_DIM[dim]


def weights_vector() -> np.ndarray:
    """Normalized dimension weights (sum to 1)."""
    w = np.array([s.weight for s in DIMENSION_SPECS], dtype=np.float64)
    return w / w.sum()


def targets_vector() -> np.ndarray:
    return np.array([s.target for s in DIMENSION_SPECS], dtype=np.float64)


def to_vector(scores: dict[Dimension | str, float]) -> np.ndarray:
    """
    Build the canonical-order score vector from a (possibly partial) dict.
    Missing dimensions default to their target (neutral — neither helps nor
    penalizes resonance, but is reported as uncovered).
    """
    targets = targets_vector()
    out = targets.copy()
    for i, dim in enumerate(DIMENSION_ORDER):
        if dim in scores:
            out[i] = scores[dim]
        elif dim.value in scores:
            out[i] = scores[dim.value]
    return np.clip(out, 0.0, 1.0)


def coverage(scores: dict[Dimension | str, float]) -> dict[str, Any]:
    """Report which dimensions are actually measured vs defaulted."""
    measured = []
    missing = []
    for dim in DIMENSION_ORDER:
        if dim in scores or dim.value in scores:
            measured.append(dim.value)
        else:
            missing.append(dim.value)
    return {
        "measured": measured,
        "missing": missing,
        "coverage_pct": round(100.0 * len(measured) / N_DIMENSIONS, 1),
    }
