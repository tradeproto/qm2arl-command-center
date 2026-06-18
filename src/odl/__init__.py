"""
Omni-Dimensional Ledger (ODL) — the System Resonance layer of QM2ARL.

Generalizes the OmniDirectional Ledger (3-axis Trinity) into an N-dimensional
value space with a quantum-hardware-ready System Resonance kernel, an
append-only hash-linked ledger, and a GAI→SAI value governor.

Quickstart:
    from src.odl import SystemResonanceEngine, Dimension
    eng = SystemResonanceEngine()
    out = eng.step()                      # auto-assemble signals from the platform
    print(out["resonance"]["verdict"], out["resonance"]["system_resonance"])

Demo:
    python -m src.odl
"""
from .dimensions import (
    Dimension,
    DIMENSION_SPECS,
    DIMENSION_ORDER,
    N_DIMENSIONS,
)
from .resonance import ResonanceState, compute_resonance
from .harmonic import harmony_from_signals, HarmonyResult
from .hyperdimensional import (
    HDCSpace,
    AssociativeMemory,
    HyperLedgerMemory,
    state_signature,
    quantum_similarity,
    fingerprint,
)
from .feeds import (
    SignalBuffer,
    collect_live_signals,
    poll_once,
    harmony_from_live,
    live_harmonic_signals,
)
from .ledger import OmniDimensionalLedger
from .governance import ValueGovernor, GovernanceVerdict, VALUE_FLOORS
from .engine import SystemResonanceEngine

__all__ = [
    "Dimension",
    "DIMENSION_SPECS",
    "DIMENSION_ORDER",
    "N_DIMENSIONS",
    "ResonanceState",
    "compute_resonance",
    "harmony_from_signals",
    "HarmonyResult",
    "HDCSpace",
    "AssociativeMemory",
    "HyperLedgerMemory",
    "state_signature",
    "quantum_similarity",
    "fingerprint",
    "SignalBuffer",
    "collect_live_signals",
    "poll_once",
    "harmony_from_live",
    "live_harmonic_signals",
    "OmniDimensionalLedger",
    "ValueGovernor",
    "GovernanceVerdict",
    "VALUE_FLOORS",
    "SystemResonanceEngine",
]
