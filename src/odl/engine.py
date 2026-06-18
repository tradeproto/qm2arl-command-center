"""
System Resonance Engine — orchestrates the Omni-Dimensional Ledger.

Ingests real signals from across the platform, maps them onto the value
dimensions, computes the System Resonance, records a hash-linked epoch, and runs
the GAI value governor:

    signals (RWA · Divisions 10-14 · TELPAI-Q · Hμ)
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
    """Average best_overall_pct across trained compliance divisions (10-14)."""
    files = {
        "iso_qms": "autoqms_iso_qms_training_summary.json",
        "nqa1": "autoqms_nqa1_training_summary.json",
        "spe_prms": "autoqms_spe_prms_training_summary.json",
        "ni43101": "autoqms_ni43101_training_summary.json",
        "clinical_trials": "autoqms_clinical_trials_training_summary.json",
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
        enable_hdc: bool = True,
        hdc_dim: int = 10_000,
        hdc_seed: int = 42,
        hv_store_path: str | Path | None = None,
    ):
        self.ledger = OmniDimensionalLedger(ledger_path)
        self.governor = ValueGovernor(tier=governor_tier)
        self.vqc_backend = vqc_backend
        self.enable_hdc = enable_hdc
        self._hdc = None
        self._hv_memory = None
        if enable_hdc:
            from .hyperdimensional import HDCSpace, HyperLedgerMemory

            self._hdc = HDCSpace(dim=hdc_dim, seed=hdc_seed)
            self._hv_memory = HyperLedgerMemory(hv_store_path, dim=hdc_dim, seed=hdc_seed)

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
        harmonic_signals: dict[str, Any] | None = None,
        harmonic_weight: float = 0.3,
        sample_rate_hz: float = 1.0,
        live_location: tuple[float, float] | None = None,
        live_min_samples: int = 8,
        seal: bool = False,
    ) -> dict[str, Any]:
        """
        Run one resonance cycle and append it to the ledger.

        harmonic_signals: optional dict of named time-series (vibration, biometrics,
        ecology, economics, weather, ...). When provided, the harmonic Harmony
        Score H is computed (src/odl/harmonic.py) and fused into resonance with
        ``harmonic_weight``; the harmonic diagnosis is recorded in the epoch.

        live_location: (lat, lon) — poll the live TELPAI feeds, buffer the
        snapshot, and use the accumulated buffered series as harmonic_signals
        (when enough samples have accumulated).
        """
        sources: dict[str, Any] = {}
        if scores is None:
            scores, sources = self.signals_from_platform()

        # Live feeds → buffered time-series → harmonic signals.
        if harmonic_signals is None and live_location is not None:
            from .feeds import SignalBuffer, poll_once, live_harmonic_signals

            buf = SignalBuffer()
            poll_once(live_location[0], live_location[1], buffer=buf)
            buffered = live_harmonic_signals(buf, min_samples=live_min_samples)
            if len(buffered) >= 2:
                harmonic_signals = buffered
            else:
                sources["live_feeds"] = {
                    "status": "accumulating",
                    "buffer_height": buf.height(),
                    "signals_ready": list(buffered.keys()),
                }

        harmonic = None
        if harmonic_signals:
            from .harmonic import harmony_from_signals

            harmonic = harmony_from_signals(
                harmonic_signals, sample_rate_hz=sample_rate_hz
            ).as_dict()
            # Fuse the Harmony Score in as the dynamical (Hμ-like) resonance term.
            H = harmonic["harmony_score"]
            hmu = H if hmu is None else 0.5 * (hmu + H)
            hmu_weight = max(hmu_weight, harmonic_weight)
            sources["harmonic"] = {
                "verdict": harmonic["verdict"],
                "harmony_score": harmonic["harmony_score"],
                "dissonant_pairs": harmonic["dissonant_pairs"][:3],
            }

        state = compute_resonance(
            scores, hmu=hmu, hmu_weight=hmu_weight, vqc_backend=self.vqc_backend
        )
        state_dict = state.as_dict()

        # HDC: build a holistic state signature, search history for nearest priors,
        # and seal a compact fingerprint into the epoch body (full HV stored aside).
        hdc_hv = None
        hdc_info = None
        if self.enable_hdc and self._hdc is not None:
            from .hyperdimensional import state_signature, fingerprint

            sig_signals = {"harmony": harmonic["harmony_score"]} if harmonic else None
            hdc_hv = state_signature(self._hdc, state_dict["dimensions"], sig_signals)
            nearest = self._hv_memory.search(hdc_hv, top_k=3)
            hdc_info = {
                "fingerprint": fingerprint(hdc_hv),
                "dim": self._hdc.dim,
                "nearest": [{"epoch_id": m.epoch_id, "similarity": round(m.similarity, 4)}
                            for m in nearest],
                "history_size": self._hv_memory.height(),
            }
            sources["hdc"] = hdc_info

        verdict = self.governor.review(state_dict)
        epoch = self.ledger.append(
            state_dict,
            subject=subject,
            sources=sources,
            governance=verdict.as_dict(),
        )

        # Store the full hypervector keyed by the new epoch_id for future search.
        if hdc_hv is not None:
            self._hv_memory.add(epoch["epoch_id"], hdc_hv)

        sealed = self.ledger.seal_head() if seal else None

        return {
            "epoch": epoch,
            "resonance": state_dict,
            "harmonic": harmonic,
            "hdc": hdc_info,
            "governance": verdict.as_dict(),
            "dragon_seal": sealed,
            "ledger_height": self.ledger.height(),
        }

    def search_history(
        self,
        scores: dict[Dimension | str, float],
        *,
        harmony_score: float | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Find the historical resonance epochs most similar to a given state, by
        HDC signature cosine similarity (instant matmul over the HV bank).
        """
        if not self.enable_hdc or self._hdc is None:
            return []
        from .hyperdimensional import state_signature
        from .dimensions import to_vector, DIMENSION_ORDER

        vec = to_vector(scores)
        dims = {d.value: float(vec[i]) for i, d in enumerate(DIMENSION_ORDER)}
        sig_signals = {"harmony": harmony_score} if harmony_score is not None else None
        hv = state_signature(self._hdc, dims, sig_signals)
        return [{"epoch_id": m.epoch_id, "similarity": round(m.similarity, 4)}
                for m in self._hv_memory.search(hv, top_k=top_k)]
