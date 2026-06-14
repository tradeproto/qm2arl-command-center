"""
SkinProto protocol evaluation orchestrator — Division 14.

One entry point that builds the SkinProto Protocol Matrix from supplied evidence
inputs, derives per-domain GCP readiness, runs the Division 14 clinical AI audit,
and (optionally) records an Omni-Dimensional Ledger resonance epoch so the
clinical program contributes to the platform-wide Health dimension.

    matrix → division14 agent scores → clinical AI audit → (optional) ODL Health signal

NOT medical advice. IRB approval + regulatory authorization required before any
human enrollment.
"""
from __future__ import annotations

from typing import Any

from .division14 import build_division14_audit
from .gcp_framework import DISCLAIMER
from .skinproto import build_skinproto_matrix, division14_agent_scores


def evaluate_protocol(
    inputs: dict[str, Any],
    *,
    record_resonance: bool = False,
) -> dict[str, Any]:
    """
    Evaluate a SkinProto protocol for clinical/regulatory readiness.

    record_resonance: if True, append a Health-dimension resonance epoch to the
    Omni-Dimensional Ledger (best-effort; never blocks evaluation).
    """
    matrix = build_skinproto_matrix(inputs)
    agent_scores = division14_agent_scores(matrix)
    audit = build_division14_audit({"agent_scores_division_14": agent_scores})

    next_steps = _next_steps(matrix, audit)

    resonance_epoch = None
    if record_resonance:
        resonance_epoch = _record_health_resonance(matrix, audit)

    return {
        "matrix": matrix.as_dict(),
        "agent_scores_division_14": {k: round(v, 4) for k, v in agent_scores.items()},
        "clinical_audit": audit,
        "next_steps": next_steps,
        "resonance_epoch": resonance_epoch,
        "disclaimer": DISCLAIMER,
    }


def _next_steps(matrix, audit) -> list[str]:
    steps: list[str] = []
    if audit.get("critical_domain_breach"):
        steps.append("HALT — critical safety/ethics/data-integrity gap. No enrollment; remediate first.")
    for n in matrix.notes:
        steps.append(n)
    if not audit.get("trained"):
        steps.append("Train Division 14 agents: " + audit.get("run_command", ""))
    elif not audit.get("audit_gate_passed"):
        steps.append(f"Strengthen binding domain '{audit.get('binding_domain')}' "
                     f"({audit.get('binding_domain_pct')}%) before sponsor/IRB review.")
    else:
        steps.append("Proceed to sponsor/IRB review and regulatory pre-submission meeting.")
    steps.append("Obtain independent IRB/IEC approval and regulatory authorization before enrollment.")
    return steps


def _record_health_resonance(matrix, audit) -> dict[str, Any] | None:
    """Feed the clinical program's readiness into the ODL Health dimension."""
    try:
        from src.odl import SystemResonanceEngine, Dimension

        # Health proxy = clinical audit readiness; Knowledge proxy = data integrity domain.
        health = float(audit.get("overall_audit_pct", 0.0)) / 100.0
        eng = SystemResonanceEngine()
        out = eng.step(
            {Dimension.HEALTH: health, Dimension.KNOWLEDGE: 0.85},
            subject=f"skinproto:{matrix.indication}",
        )
        return {"epoch_id": out["epoch"]["epoch_id"],
                "system_resonance": out["resonance"]["system_resonance"],
                "verdict": out["resonance"]["verdict"]}
    except Exception:
        return None
