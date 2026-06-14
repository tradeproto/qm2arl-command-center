"""
SPE Standards Pertaining to the Estimating and Auditing of Oil and Gas Reserves
Information — revised June 2019 (SPE Board approved 25 June 2019).

Source: ~/Documents/ASI_Investment_Framework/DragonSeal/
        Reserves_Audit_Standards_June 2019_Final.pdf

Aligns with SPE-PRMS 2018. TELPAI generates data packages; QRE/QRA sign reports.
"""
from __future__ import annotations

from typing import Any

SPE_AUDIT_STANDARDS = {
    "document": "Standards Pertaining to the Estimating and Auditing of Oil and Gas Reserves Information",
    "revision": "June 2019",
    "approved": "2019-06-25",
    "spe_board_approved": True,
    "prms_alignment": "SPE-PRMS-2018",
    "source_pdf": (
        "~/Documents/ASI_Investment_Framework/DragonSeal/"
        "Reserves_Audit_Standards_June 2019_Final.pdf"
    ),
    "scope": "Reserves quantities only (not contingent/prospective resources).",
    "terminology_2019": {
        "QRE": "Qualified Reserves Evaluator (formerly qualified reserves estimator)",
        "QRA": "Qualified Reserves Auditor (formerly reserves auditor)",
    },
    "audit_tolerance": {
        "proved_default_pct": 10.0,
        "note": "Reasonableness = aggregate difference not more than ±10% for proved, "
        "or subject reserves do not meet minimum audit standards (§2.2(g)).",
        "other_categories": "Separate predetermined tolerance may be disclosed.",
    },
    "qre_qualifications": {
        "min_years_practical": 5,
        "min_years_reserves_estimation": 3,
        "degree_or_license": "Bachelor's+ in PE/geology/physical science OR PE/PG license in good standing",
        "competency_areas": [
            "geological maps and models",
            "reservoir analogs",
            "seismic in reserves evaluation",
            "reservoir simulation fundamentals",
            "probabilistic and deterministic methods",
            "production performance techniques",
            "software limitations awareness",
            "fiscal/licensing systems",
            "reserves definitions continuing education",
            "ethics training",
        ],
    },
    "qra_qualifications": {
        "min_years_practical": 10,
        "min_years_reserves_in_charge": 5,
        "degree_or_license": "Same as QRE — bachelor's+ or PE/PG license",
    },
    "independence_consulting_qra": [
        "No material financial interest in entity or properties audited",
        "No material joint ventures with client",
        "No indebtedness to client (except ordinary trade payables)",
        "No contingent fee tied to audit conclusions",
        "Independence statement required in report",
    ],
    "estimation_methods": [
        "volumetric",
        "performance_history",
        "material_balance_simulation",
        "analogy",
    ],
    "estimation_prohibitions": [
        "Do not average results of two or more methodologies (§5.3)",
    ],
    "probabilistic_thresholds_prms_2018": {
        "proved_p90": "≥90% probability actual recovery ≥ estimate",
        "two_p_p50": "≥50% probability actual recovery ≥ 2P sum",
        "three_p_p10": "≥10% probability actual recovery ≥ 3P sum",
        "aggregation": "Arithmetic summation by category beyond field/project level unless regulatory guidance",
    },
    "report_types": {
        "entity_reserves_report": "≥80% of entity reserves/production/revenues",
        "property_reserves_report": "One or more reservoirs/fields/projects (Rivers Bend path)",
        "reserves_audit": "Opinion on reasonableness — generally less rigorous than full reserves report",
        "process_review": "NOT equivalent to reserves audit — no reasonableness opinion",
    },
    "audit_engagement_minimum": [
        "Entity provides all reserves info, basic data, personnel access, nonconfidential third-party data",
        "QRA evaluates methods, definitions, tests data, expresses aggregate reasonableness opinion",
        "Audit report available to independent public accountants on request",
        "Engagement letter for consulting QRA",
    ],
    "audit_procedures": [
        "proper_planning_and_supervision",
        "early_qra_appointment",
        "disclose_qualified_opinion_risk_before_acceptance",
        "interim_audit_procedures",
        "review_entity_policies_controls_revision_trends",
        "evaluate_internal_documentation",
        "compliance_testing",
        "substantive_testing_priority_large_uncertain_properties",
    ],
    "qra_deliverables": [
        "Unqualified or qualified audit opinion (Exhibit A consulting / Exhibit B internal)",
        "Detailed description of audit tests performed",
        "Disclosure of data relied upon without independent verification",
        "Stated audit tolerance (±%) for proved aggregate",
        "PRMS/SEC conformity statement where warranted",
    ],
    "telpai_role": {
        "preparer": "GHI TELPAI-Q — technical survey & volumetric inputs only",
        "not_substitute_for": ["QRE property reserves report", "QRA independent audit opinion"],
        "feeds_qre_package": True,
        "dragon_seal": "Co-seal TELPAI survey hash with QRE report hash before Reg D 506(c) primary issuance",
    },
}


def qra_engagement_checklist(*, property_report: bool = True) -> dict[str, Any]:
    """Pre-engagement checklist for Rivers Bend–style property reserves audit."""
    items = [
        {"id": "engagement_letter", "item": "QRA engagement letter (consulting) or internal charter", "article": "6.3(d)"},
        {"id": "report_type", "item": "Property Reserves Report scope defined (not entity-level 80%)", "article": "2.2(f)"},
        {"id": "prms_definitions", "item": "PRMS 2018 definitions referenced in report", "article": "2.1"},
        {"id": "audit_tolerance", "item": "Predetermined ±% tolerance for proved aggregate disclosed", "article": "2.2(g)"},
        {"id": "data_access", "item": "Full basic data: logs, seismic, production, ownership, price deck", "article": "6.3(a)"},
        {"id": "telpai_survey", "item": "TELPAI geophysical survey attached as supplementary (not substitute)", "article": "5.2"},
        {"id": "independence", "item": "QRA independence statement (consulting) or objectivity (internal)", "article": "4.2-4.5"},
        {"id": "no_contingent_fee", "item": "QRA fee not contingent on audit conclusion", "article": "4.3(j)"},
        {"id": "substantive_tests", "item": "Substantive tests on high-value / high-uncertainty properties", "article": "6.4(h)"},
        {"id": "management_rep", "item": "Management representation letter", "article": "5.1"},
        {"id": "exhibit_opinion", "item": "Audit opinion per Exhibit A (consulting QRA) or B (internal)", "article": "6.6"},
        {"id": "dragon_seal", "item": "QRA opinion PDF hash co-sealed with TELPAI epoch on Dragon Seal", "article": "telpai_rwa"},
    ]
    return {
        "standard": SPE_AUDIT_STANDARDS["document"],
        "revision": SPE_AUDIT_STANDARDS["revision"],
        "report_type": "property_reserves_report" if property_report else "entity_reserves_report",
        "proved_audit_tolerance_pct": SPE_AUDIT_STANDARDS["audit_tolerance"]["proved_default_pct"],
        "checklist": items,
        "rivers_bend_note": "Upper Houston Embayment property report — QRE certifies volumes; "
        "QRA audits aggregate reasonableness before Reg D 506(c) token tranche.",
    }


def telpai_vs_qre_boundary() -> dict[str, Any]:
    """What TELPAI may prepare vs what requires licensed QRE/QRA."""
    return {
        "telpai_may_provide": [
            "Geophysical survey bundle (seismic, gravity, magnetics, seepage, satellite)",
            "Probabilistic volumetric scenarios (inputs to QRE — not certified reserves)",
            "PRMS category screening (software gate — not audit opinion)",
            "Monte Carlo P10/P50/P90 scenarios pending QRE adoption",
            "Reg D 506 checklist tracking",
            "Dragon Seal epoch of survey data integrity",
        ],
        "qre_must_provide": [
            "Property Reserves Report per §2.2(f)",
            "Certified 1P/2P/3P volumes with economic limit",
            "PUD five-year development schedule (SEC Rule 4-10)",
            "Decline curves and production forecasts",
            "Price deck and cost assumptions sign-off",
        ],
        "qra_must_provide": [
            "Independent audit opinion on aggregate reasonableness (±10% proved default)",
            "Substantive test documentation per Article VI",
            "Exhibit A or B opinion letter",
        ],
        "explicitly_not_audit": [
            "TELPAI Monte Carlo output alone",
            "QM2ARL Division 12 agent scores",
            "Process review / procedural audit",
        ],
    }