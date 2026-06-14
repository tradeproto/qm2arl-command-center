"""
Division 14 — Clinical Trials & Quantum Health AI audit.

The clinical analogue of division12 (SPE-PRMS) and division13 (NI 43-101).
Loads the trained QM2ARL Division 14 results (8 GCP/ICH/ISO-14155 auditor
agents) and combines them with the per-protocol SkinProto readiness scores to
produce a clinical AI audit posture: per-domain readiness, the gating blocker,
and an overall GCP-AUDIT-READY verdict.

Trained artifact:
    results/autoqms_clinical_trials_training_summary.json
        (simulations/compliance_audit.py configs/compliance_clinical_trials.yaml)

SCOPE: regulatory-readiness decision support only — NOT medical advice and NOT a
substitute for IRB/IEC, FDA/EMA, sponsors, or qualified medical professionals.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .gcp_framework import AGENT_ROLES, DISCLAIMER

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SUMMARY = _REPO_ROOT / "results" / "autoqms_clinical_trials_training_summary.json"

AUDIT_READY_THRESHOLD = 85.0
DOMAIN_CRITICAL_FLOOR = 50.0
# Domains that are hard gates for first-in-human: safety, ethics, data integrity.
CRITICAL_DOMAINS = ("safety_pharmacovigilance", "irb_ethics_consent", "data_integrity_part11")

_ORDER = list(AGENT_ROLES.keys())


def load_training_summary(path: str | Path | None = None) -> dict[str, Any] | None:
    p = Path(path) if path else _DEFAULT_SUMMARY
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def build_division14_audit(
    protocol_scores: dict[str, Any] | None = None,
    *,
    summary_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Division 14 clinical AI audit posture for a protocol.

    protocol_scores: dict with 'agent_scores_division_14' (per-domain readiness
    0–1, e.g. from skinproto.division14_agent_scores).
    """
    summary = load_training_summary(summary_path)
    protocol_scores = protocol_scores or {}
    asset_scores = protocol_scores.get("agent_scores_division_14", {}) or {}

    trained = summary is not None
    trained_domains = (summary or {}).get("domains", {})

    domains: list[dict[str, Any]] = []
    for d in _ORDER:
        td = trained_domains.get(d, {})
        trained_pct = float(td.get("score_pct", 0.0)) if trained else None
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
            "trained_status": td.get("status") if trained else "UNTRAINED",
            "asset_agent_score_pct": asset_pct,
            "combined_pct": combined,
            "gap_pct": td.get("gap_pct"),
            "critical": d in CRITICAL_DOMAINS,
        })

    if trained:
        overall = float(summary.get("best_overall_pct", 0.0))
        status_label = summary.get("best_status", "UNKNOWN")
        blocker = summary.get("rwa_blocker")
    else:
        scored = [d["combined_pct"] for d in domains if d["combined_pct"] is not None]
        overall = round(sum(scored) / len(scored), 1) if scored else 0.0
        status_label = "UNTRAINED — run simulations/compliance_audit.py configs/compliance_clinical_trials.yaml"
        blocker = None

    low = min((d for d in domains if d["combined_pct"] is not None),
              key=lambda d: d["combined_pct"], default=None)
    # A critical-domain gap is an automatic gate failure regardless of overall.
    critical_breach = any(d["critical"] and d["combined_pct"] < DOMAIN_CRITICAL_FLOOR for d in domains)
    audit_gate_passed = bool(
        trained and overall >= AUDIT_READY_THRESHOLD
        and not critical_breach
        and not (low and low["combined_pct"] < DOMAIN_CRITICAL_FLOOR)
    )

    return {
        "division": 14,
        "framework": "ICH-GCP E6(R2) · FDA 21 CFR 11/50/56/312/812 · ISO 14155:2020",
        "trained": trained,
        "training_episodes": (summary or {}).get("episodes"),
        "overall_audit_pct": round(overall, 1),
        "audit_status": status_label,
        "audit_gate_passed": audit_gate_passed,
        "critical_domain_breach": critical_breach,
        "binding_domain": (low or {}).get("domain"),
        "binding_domain_pct": (low or {}).get("combined_pct"),
        "blocker": blocker,
        "domains": domains,
        "recommendation": _recommendation(audit_gate_passed, low, critical_breach, trained),
        "disclaimer": DISCLAIMER,
        "run_command": "python simulations/compliance_audit.py configs/compliance_clinical_trials.yaml",
    }


def _recommendation(passed, low, critical_breach, trained) -> str:
    if not trained:
        return ("Division 14 agents not yet trained — run the clinical-trials audit "
                "config to generate GCP readiness scores.")
    if critical_breach:
        return ("HALT — a critical safety/ethics/data-integrity domain is below floor. "
                "No human enrollment. Remediate and obtain IRB + regulatory authorization.")
    if passed:
        return ("GCP-AUDIT-READY (documentation) — proceed to sponsor/IRB review and "
                "regulatory submission. Independent IRB approval still required before enrollment.")
    parts = []
    if low:
        parts.append(f"Weakest domain: {low['domain']} at {low['combined_pct']}%.")
    parts.append("Remediate (CAPA) and complete sponsor/IRB review before submission.")
    return " ".join(parts)
