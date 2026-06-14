"""
Clinical trial / Good Clinical Practice (GCP) framework — Division 14.

The regulatory backbone for Quantum Health Solutions. Maps the 8 Division 14
agents to ICH-GCP (E6 R2), FDA 21 CFR (Parts 11, 50, 56, 312, 812), and
ISO 14155 (clinical investigation of medical devices), so the SkinProto wound-
care protocol can be assessed for regulatory readiness the same way Division 12
assesses SPE-PRMS reserves.

╔══════════════════════════════════════════════════════════════════════════╗
║  SCOPE & DISCLAIMER — read before use                                      ║
║  This module provides REGULATORY-READINESS and PROTOCOL-DOCUMENTATION      ║
║  decision support. It is NOT medical advice, NOT a diagnosis, NOT a        ║
║  medical device, and NOT a therapeutic claim. It does NOT replace an       ║
║  IRB/IEC, the FDA/EMA, a sponsor, a qualified clinical investigator, a     ║
║  biostatistician, or any licensed medical professional. "Quantum" refers   ║
║  to the QM2ARL quantum-kernel ANALYSIS stack, not a medical treatment.     ║
║  No protocol may enroll a human subject without independent IRB approval   ║
║  and applicable regulatory authorization.                                  ║
╚══════════════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations

from typing import Any

DISCLAIMER = (
    "Regulatory-readiness & documentation decision support only. NOT medical "
    "advice, a medical device, or a therapeutic claim. Does NOT replace IRB/IEC, "
    "FDA/EMA, sponsor, qualified clinical investigators, or medical professionals. "
    "IRB approval and regulatory authorization required before any human enrollment."
)

GCP_FRAMEWORK: dict[str, Any] = {
    "division": 14,
    "name": "Clinical Trials & Quantum Health Solutions",
    "standards": [
        "ICH E6(R2) Good Clinical Practice",
        "ICH E8(R1) General Considerations for Clinical Studies",
        "FDA 21 CFR Part 11 (electronic records/signatures)",
        "FDA 21 CFR Part 50 (informed consent)",
        "FDA 21 CFR Part 56 (IRBs)",
        "FDA 21 CFR Part 312 (IND) / Part 812 (IDE)",
        "ISO 14155:2020 (clinical investigation of medical devices)",
    ],
    "agent_domains": [
        "protocol_design_endpoints",
        "preclinical_mechanism",
        "cmc_formulation_encapsulation",
        "safety_pharmacovigilance",
        "irb_ethics_consent",
        "data_integrity_part11",
        "statistical_efficacy",
        "regulatory_submission_audit",
    ],
    "disclaimer": DISCLAIMER,
}

AGENT_ROLES: dict[str, str] = {
    "protocol_design_endpoints": "Clinical Scientist — protocol design, objectives & endpoints (ICH E6/E8)",
    "preclinical_mechanism": "Translational Scientist — mechanism, preclinical tox & efficacy evidence",
    "cmc_formulation_encapsulation": "CMC Lead — GMP manufacturing, formulation & encapsulation quality",
    "safety_pharmacovigilance": "Medical Monitor — AE/SAE, DSMB, risk & carcinogenicity/oncology safety",
    "irb_ethics_consent": "Ethics/Reg Affairs — IRB/IEC, informed consent (21 CFR 50/56, Helsinki)",
    "data_integrity_part11": "Data Manager — 21 CFR Part 11, ALCOA+, EDC & audit trail",
    "statistical_efficacy": "Biostatistician — statistical analysis plan, powering, efficacy endpoints",
    "regulatory_submission_audit": "Regulatory Lead — IND/IDE, ISO 14155, submission readiness & audit",
}

# Clinical phase ladder (informational; SkinProto starts pre-IND / first-in-human design).
PHASES = ["preclinical", "phase_0", "phase_1", "phase_2", "phase_3", "phase_4"]


def gcp_status() -> dict[str, Any]:
    return {
        "framework": GCP_FRAMEWORK,
        "agent_roles": AGENT_ROLES,
        "phases": PHASES,
        "disclaimer": DISCLAIMER,
    }
