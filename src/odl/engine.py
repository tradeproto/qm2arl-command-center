"""
System Resonance Engine — orchestrates the Omni-Dimensional Ledger.

Ingests real signals from across the platform, maps them onto the value
dimensions, computes the System Resonance, records a hash-linked epoch, and runs
the GAI value governor:

    signals (RWA · Divisions 10-13 · TELPAI-Q · Hμ)
        → map to value dimensions
        → compute_resonance()  (quantum-hardware-ready)
        → ledger.append()      (hash-linked, DragonSeal-ready)
        → ValueGovernor.review()

Signal adapters are defensive: any missing source simply lowers dimension
coverage rather than breaking the cycle.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .dimensions import Dimension
from .governance import ValueGovernor
from .ledger import OmniDimensionalLedger
from .resonance import compute_resonance

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RESULTS = _REPO_ROOT / "results"


def _safe_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _avg_division_audit() -> tuple[float | None, dict[str, float]]:
    """Average best_overall_pct across trained compliance divisions (10-13)."""
    files = {
        "iso_qms": "autoqms_iso_qms_training_summary.json",
        "nqa1": "autoqms_nqa1_training_summary.json",
        "spe_prms": "autoqms_spe_prms_training_summary.json",
        "ni43101": "autoqms_ni43101_training_summary.json",
    }
    scores: dict[str, float] = {}
    for preset, fname in files.items():
        d = _safe_json(_RESULTS / fname)
        if d and d.get("best_overall_pct") is not None:
            scores[preset] = float(d["best_overall_pct"]) / 100.0
    if not scores:
        return None, {}
    return sum(scores.values()) / len(scores), scores


class SystemResonanceEngine:
    """Compute → record → govern the Omni-Dimensional Ledger."""

    def __init__(
        self,
        *,
        ledger_path: str | Path | None = None,
        governor_tier: str = "GAI",
        vqc_backend: str = "",
    ):
        self.ledger = OmniDimensionalLedger(ledger_path)
        self.governor = ValueGovernor(tier=governor_tier)
        self.vqc_backend = vqc_backend

    def signals_from_platform(self) -> tuple[dict[Dimension, float], dict[str, Any]]:
        """
        Auto-assemble value-dimension scores from in-repo artifacts.
        Honest: only dimensions with real signals are populated; the rest stay
        uncovered (reported, defaulted to target).
        """
        scores: dict[Dimension, float] = {}
        sources: dict[str, Any] = {}

        # KNOWLEDGE — verifiable-information integrity = mean compliance audit %.
        avg_audit, per_div = _avg_division_audit()
        if avg_audit is not None:
            scores[Dimension.KNOWLEDGE] = avg_audit
            sources["compliance_divisions"] = per_div

        # CONNECTION (Love) — cooperative alignment = best Hμ from SPE-PRMS run.
        spe = _safe_json(_RESULTS / "autoqms_spe_prms_training_summary.json")
        if spe and spe.get("best_hmu") is not None:
            scores[Dimension.CONNECTION] = float(min(1.0, max(0.0, spe["best_hmu"])))
            sources["harmony_hmu"] = spe["best_hmu"]

        # PROSPERITY — RWA assets registered + tokenizable share.
        rwa = _safe_json(_REPO_ROOT / "data" / "rwa_assets.json")
        if rwa and rwa.get("assets"):
            assets = list(rwa["assets"].values())
            tok = [a for a in assets if (a.get("classification") or {}).get("tokenizable")]
            scores[Dimension.PROSPERITY] = 0.4 + 0.5 * (len(tok) / max(len(assets), 1))
            sources["rwa_assets"] = {"count": len(assets), "tokenizable": len(tok)}

        return scores, sources

    def step(
        self,
        scores: dict[Dimension | str, float] | None = None,
        *,
        subject: str = "system",
        hmu: float | None = None,
        hmu_weight: float = 0.0,
        seal: bool = False,
    ) -> dict[str, Any]:
        """Run one resonance cycle and append it to the ledger."""
        sources: dict[str, Any] = {}
        if scores is None:
            scores, sources = self.signals_from_platform()

        state = compute_resonance(
            scores, hmu=hmu, hmu_weight=hmu_weight, vqc_backend=self.vqc_backend
        )
        verdict = self.governor.review(state.as_dict())
        epoch = self.ledger.append(
            state.as_dict(),
            subject=subject,
            sources=sources,
            governance=verdict.as_dict(),
        )
        sealed = self.ledger.seal_head() if seal else None

        return {
            "epoch": epoch,
            "resonance": state.as_dict(),
            "governance": verdict.as_dict(),
            "dragon_seal": sealed,
            "ledger_height": self.ledger.height(),
        }
