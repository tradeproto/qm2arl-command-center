"""
Division 12 — SPE-PRMS AI audit agents wired into RWA onboarding.

Loads the trained QM2ARL Division 12 results (8 SPE-PRMS auditor agents) and
combines them with the per-asset classification agent scores to produce an
**AI audit posture** for an asset: per-domain readiness, the gating blocker, and
an overall AUDIT-READY verdict that the securities gate can consume.

Trained artifact:
    results/autoqms_spe_prms_training_summary.json
        (produced by simulations/compliance_audit.py configs/compliance_spe_prms.yaml)

The eight agents map 1:1 to SPE-PRMS domains:
    0 prms_framework_definitions   4 technical_evaluation
    1 reserves_classification      5 commercial_evaluation
    2 contingent_resources         6 uncertainty_aggregation
    3 prospective_resources        7 audit_rwa_tokenization
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SUMMARY = _REPO_ROOT / "results" / "autoqms_spe_prms_training_summary.json"

# Audit-readiness gate: overall must clear this and no domain may be NOT ADDRESSED.
AUDIT_READY_THRESHOLD = 85.0
DOMAIN_CRITICAL_FLOOR = 50.0

AGENT_ROLES: dict[str, str] = {
    "prms_framework_definitions": "Geologist — PRMS framework & scope",
    "reserves_classification": "Reserves Engineer — 1P/2P/3P classification",
    "contingent_resources": "Geologist — 1C/2C/3C contingent",
    "prospective_resources": "Prospector — exploration maturity",
    "technical_evaluation": "Petroleum Engineer — volumetrics & simulation",
    "commercial_evaluation": "Reserves Economist — price deck & fiscal",
    "uncertainty_aggregation": "Geostatistician — P10/P50/P90 aggregation",
    "audit_rwa_tokenization": "Audit Lead — SPE audit + on-chain attestation",
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


def build_division12_audit(
    classification: dict[str, Any] | None = None,
    *,
    summary_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Produce the Division 12 AI audit posture for an asset.

    Combines:
      - trained_audit_pct  : the agents' learned audit-readiness per domain
                             (from the training summary on the demo corpus)
      - asset_agent_score  : this asset's per-domain readiness derived from its
                             classification evaluation (heuristic, 0–1 → %)
      - combined_pct       : min(trained, asset) — the binding constraint, since
                             an auditor can only attest what the asset documents

    Returns a structured posture with overall verdict, the gating blocker, and an
    ``audit_gate_passed`` boolean for the securities gate.
    """
    summary = load_training_summary(summary_path)
    classification = classification or {}
    asset_scores = classification.get("agent_scores_division_12", {}) or {}

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

    # Overall verdict: prefer the trained best_overall_pct when available, but
    # never report higher than the weakest critical domain allows.
    if trained_available:
        overall = float(summary.get("best_overall_pct", 0.0))
        status_label = summary.get("best_status", "UNKNOWN")
        blocker = summary.get("rwa_blocker")
    else:
        scored = [d["combined_pct"] for d in domains if d["combined_pct"] is not None]
        overall = round(sum(scored) / len(scored), 1) if scored else 0.0
        status_label = "UNTRAINED — run simulations/compliance_audit.py configs/compliance_spe_prms.yaml"
        blocker = None

    # Identify the binding low domain.
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
        "division": 12,
        "framework": "SPE-PRMS 2018 · Standards Pertaining to Estimating & Auditing of O&G Reserves (June 2019)",
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
        "run_command": "python simulations/compliance_audit.py configs/compliance_spe_prms.yaml",
    }


def _recommendation(passed: bool, low: dict | None, blocker: str | None, trained: bool) -> str:
    if not trained:
        return ("Division 12 agents not yet trained — run the SPE-PRMS audit "
                "config to generate audit-readiness scores.")
    if passed:
        return ("AUDIT-READY — Division 12 agents conform across critical domains. "
                "Proceed to independent QRE report co-seal.")
    parts = []
    if low:
        parts.append(f"Weakest domain: {low['domain']} at {low['combined_pct']}%.")
    if blocker:
        parts.append(f"Blocker: {blocker}")
    parts.append("Remediate the gap (CAPA) before primary Reg D 506(c) issuance.")
    return " ".join(parts)
