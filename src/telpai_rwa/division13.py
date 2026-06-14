"""
Division 13 — NI 43-101 / CIM Qualified Person (QP) AI audit agents for minerals.

The minerals analogue of division12.py (SPE-PRMS). Loads the trained QM2ARL
Division 13 results (8 QP auditor agents) and combines them with the per-asset
mineral classification agent scores to produce an AI audit posture: per-domain
readiness, the gating blocker, and an overall QP-AUDIT-READY verdict the
securities gate consumes.

Trained artifact:
    results/autoqms_ni43101_training_summary.json
        (produced by simulations/compliance_audit.py configs/compliance_ni43101.yaml)

The eight agents map 1:1 to NI 43-101 / Form 43-101F1 domains:
    0 geology_deposit_model              4 mineral_reserve_modifying_factors
    1 drilling_exploration               5 metallurgy_recovery
    2 sampling_qaqc                       6 economic_analysis
    3 mineral_resource_estimate           7 qp_attestation_tokenization
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SUMMARY = _REPO_ROOT / "results" / "autoqms_ni43101_training_summary.json"

AUDIT_READY_THRESHOLD = 85.0
DOMAIN_CRITICAL_FLOOR = 50.0

AGENT_ROLES: dict[str, str] = {
    "geology_deposit_model": "Geologist — deposit model & geological setting (Items 6–8)",
    "drilling_exploration": "Exploration Geologist — drilling & exploration (Items 9–10)",
    "sampling_qaqc": "QA/QC Lead — sampling, prep, data verification (Items 11–12)",
    "mineral_resource_estimate": "Resource Geologist — estimation & classification (Item 14)",
    "mineral_reserve_modifying_factors": "Mining Engineer — reserves & modifying factors (Item 15)",
    "metallurgy_recovery": "Metallurgist — testwork & recovery (Item 13)",
    "economic_analysis": "Mining Economist — capex/opex, NPV/IRR, cutoff (Items 18–22)",
    "qp_attestation_tokenization": "Qualified Person — certificate/consent + on-chain attestation",
}

_ORDER = list(AGENT_ROLES.keys())


def load_training_summary(path: str | Path | None = None) -> dict[str, Any] | None:
    p = Path(path) if path else _DEFAULT_SUMMARY
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def build_division13_audit(
    classification: dict[str, Any] | None = None,
    *,
    summary_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Produce the Division 13 QP AI audit posture for a mineral asset.

    Combines trained agent audit-readiness (from the demo corpus) with this
    asset's per-domain classification readiness; combined = min(trained, asset).
    """
    summary = load_training_summary(summary_path)
    classification = classification or {}
    asset_scores = classification.get("agent_scores_division_13", {}) or {}

    trained_available = summary is not None
    trained_domains = (summary or {}).get("domains", {})

    domains: list[dict[str, Any]] = []
    for d in _ORDER:
        trained = trained_domains.get(d, {})
        trained_pct = float(trained.get("score_pct", 0.0)) if trained_available else None
        trained_status = trained.get("status") if trained_available else "UNTRAINED"
        asset_pct = round(float(asset_scores.get(d, 0.0)) * 100.0, 1) if asset_scores else None

        if trained_pct is not None and asset_pct is not None:
            combined = round(min(trained_pct, asset_pct), 1)
        elif trained_pct is not None:
            combined = round(trained_pct, 1)
        elif asset_pct is not None:
            combined = round(asset_pct, 1)
        else:
            combined = 0.0

        domains.append({
            "agent": _ORDER.index(d),
            "domain": d,
            "role": AGENT_ROLES[d],
            "trained_audit_pct": trained_pct,
            "trained_status": trained_status,
            "asset_agent_score_pct": asset_pct,
            "combined_pct": combined,
            "gap_pct": trained.get("gap_pct"),
        })

    if trained_available:
        overall = float(summary.get("best_overall_pct", 0.0))
        status_label = summary.get("best_status", "UNKNOWN")
        blocker = summary.get("rwa_blocker")
    else:
        scored = [d["combined_pct"] for d in domains if d["combined_pct"] is not None]
        overall = round(sum(scored) / len(scored), 1) if scored else 0.0
        status_label = "UNTRAINED — run simulations/compliance_audit.py configs/compliance_ni43101.yaml"
        blocker = None

    low = min(
        (d for d in domains if d["combined_pct"] is not None),
        key=lambda d: d["combined_pct"],
        default=None,
    )
    critical_fail = bool(low and low["combined_pct"] < DOMAIN_CRITICAL_FLOOR)
    audit_gate_passed = bool(
        trained_available and overall >= AUDIT_READY_THRESHOLD and not critical_fail
    )

    recommendation = _recommendation(audit_gate_passed, low, blocker, trained_available)

    return {
        "division": 13,
        "framework": "NI 43-101 · CIM Definition Standards (2014) · Form 43-101F1 Technical Report",
        "trained": trained_available,
        "training_episodes": (summary or {}).get("episodes"),
        "overall_audit_pct": round(overall, 1),
        "audit_status": status_label,
        "audit_gate_passed": audit_gate_passed,
        "binding_domain": (low or {}).get("domain"),
        "binding_domain_pct": (low or {}).get("combined_pct"),
        "blocker": blocker,
        "domains": domains,
        "recommendation": recommendation,
        "run_command": "python simulations/compliance_audit.py configs/compliance_ni43101.yaml",
    }


def _recommendation(passed: bool, low: dict | None, blocker: str | None, trained: bool) -> str:
    if not trained:
        return ("Division 13 agents not yet trained — run the NI 43-101 audit "
                "config to generate QP audit-readiness scores.")
    if passed:
        return ("QP-AUDIT-READY — Division 13 agents conform across critical domains. "
                "Proceed to independent QP NI 43-101 Technical Report co-seal.")
    parts = []
    if low:
        parts.append(f"Weakest domain: {low['domain']} at {low['combined_pct']}%.")
    if blocker:
        parts.append(f"Blocker: {blocker}")
    parts.append("Remediate the gap (CAPA) before primary Reg D 506(c) issuance.")
    return " ".join(parts)
