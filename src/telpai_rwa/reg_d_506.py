"""
SEC Regulation D — Rule 506(b) / 506(c) offering readiness checklist.

506(c): general solicitation allowed; all purchasers must be verified accredited.
506(b): no general solicitation; up to 35 non-accredited sophisticated investors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


REG_D_506_CHECKLIST: dict[str, list[dict[str, str]]] = {
    "506c": [
        {"id": "form_d", "item": "Form D filed with SEC within 15 days of first sale", "owner": "legal"},
        {"id": "accredited_verification", "item": "Reasonable steps to verify accredited investor status (506(c))", "owner": "compliance"},
        {"id": "no_bad_actor", "item": "Rule 506(d) bad actor disqualification review", "owner": "legal"},
        {"id": "ppm", "item": "Private Placement Memorandum with full risk disclosures", "owner": "legal"},
        {"id": "qre_report", "item": "Independent QRE Property Reserves Report (SPE June 2019 §2.2(f))", "owner": "reserves_engineer"},
        {"id": "qra_audit", "item": "QRA audit opinion — proved aggregate ±10% reasonableness (SPE June 2019 §2.2(g))", "owner": "reserves_engineer"},
        {"id": "prms_classification", "item": "SPE-PRMS classification documented in offering materials", "owner": "prospector_geologist"},
        {"id": "sec_4_10", "item": "SEC Rule 4-10 reserve definitions aligned in disclosures", "owner": "reserves_engineer"},
        {"id": "spv_formation", "item": "Delaware SPV formed; reserve assignment documented", "owner": "legal"},
        {"id": "kyc_aml", "item": "TradeProto KYC/AML + transfer restrictions (ERC-3643)", "owner": "compliance"},
        {"id": "dragon_seal", "item": "QRE report + TELPAI survey Dragon Seal attestation", "owner": "oracle_ops"},
        {"id": "general_solicitation", "item": "506(c): general solicitation permitted — marketing plan filed", "owner": "capital"},
        {"id": "state_blue_sky", "item": "State securities notice filings (blue sky)", "owner": "legal"},
    ],
    "506b": [
        {"id": "form_d", "item": "Form D filed with SEC within 15 days of first sale", "owner": "legal"},
        {"id": "no_general_solicitation", "item": "506(b): NO general solicitation or advertising", "owner": "capital"},
        {"id": "accredited_or_sophisticated", "item": "All accredited OR ≤35 non-accredited sophisticated investors", "owner": "compliance"},
        {"id": "ppm", "item": "Private Placement Memorandum", "owner": "legal"},
        {"id": "qre_report", "item": "Independent QRE reserve report", "owner": "reserves_engineer"},
        {"id": "kyc_aml", "item": "KYC/AML via TradeProto", "owner": "compliance"},
    ],
}


@dataclass
class RegDValidation:
    rule: str
    ready: bool
    completed: list[str]
    missing: list[str]
    blockers: list[str] = field(default_factory=list)
    score_pct: float = 0.0


def validate_reg_d_offering(
    rule: str,
    checklist_state: dict[str, bool],
    *,
    reserve_tokenizable: bool = False,
    qre_signed: bool = False,
    dragon_seal_anchored: bool = False,
) -> RegDValidation:
    """Validate offering readiness against Reg D checklist."""
    rule = rule.lower().replace(" ", "")
    if rule not in ("506b", "506c"):
        rule = "506c"

    items = REG_D_506_CHECKLIST[rule]
    completed = []
    missing = []
    blockers = []

    for entry in items:
        eid = entry["id"]
        if checklist_state.get(eid, False):
            completed.append(eid)
        else:
            missing.append(eid)

    if not reserve_tokenizable:
        blockers.append("Reserve category not tokenizable under SEC primary basis — reclassify or use supplemental/convertible structure.")
    if not qre_signed:
        blockers.append("Independent QRE reserve report required before Reg D offering.")
    if not dragon_seal_anchored:
        blockers.append("Dragon Seal attestation of QRE + TELPAI survey package pending.")

    score = len(completed) / max(len(items), 1) * 100
    ready = len(missing) == 0 and len(blockers) == 0

    return RegDValidation(
        rule=rule,
        ready=ready,
        completed=completed,
        missing=missing,
        blockers=blockers,
        score_pct=round(score, 1),
    )


def checklist_template(rule: str = "506c") -> dict[str, Any]:
    rule = rule.lower().replace(" ", "")
    if rule not in REG_D_506_CHECKLIST:
        rule = "506c"
    return {
        "rule": rule,
        "items": REG_D_506_CHECKLIST[rule],
        "default_state": {item["id"]: False for item in REG_D_506_CHECKLIST[rule]},
    }