"""
QRE Data Package Generator — formats TELPAI survey output for independent reserves evaluator.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_qre_data_package(
    asset: dict[str, Any],
    classification: dict[str, Any],
    volumes: dict[str, float],
    telpai_survey: dict[str, Any],
) -> dict[str, Any]:
    """Standard QRE input package (Ryder Scott / DeGolyer / NSAI compatible structure)."""
    return {
        "package_version": "1.1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "preparer": "GHI TELPAI-Q / QM2ARL Division 12",
        "qre_required": True,
        "spe_audit_standards": {
            "document": "Standards Pertaining to the Estimating and Auditing of Oil and Gas Reserves Information",
            "revision": "June 2019",
            "source_pdf": (
                "~/Documents/ASI_Investment_Framework/DragonSeal/"
                "Reserves_Audit_Standards_June 2019_Final.pdf"
            ),
            "report_type": "property_reserves_report",
            "proved_audit_tolerance_pct": 10.0,
            "prms_alignment": "SPE-PRMS-2018",
        },
        "asset": {
            "asset_id": asset.get("asset_id"),
            "name": asset.get("name"),
            "operator": asset.get("operator"),
            "basin": asset.get("basin"),
            "country": asset.get("country", "USA"),
            "lat": asset.get("lat"),
            "lon": asset.get("lon"),
            "boe_factor": asset.get("boe_factor", 6.0),
        },
        "classification_summary": {
            "spe_prms_category": classification.get("category"),
            "certainty_pct": classification.get("certainty_pct"),
            "technical_score": classification.get("technical_score"),
            "commercial_score": classification.get("commercial_score"),
            "sec_disclosure_basis": classification.get("sec_disclosure_basis"),
            "notes": classification.get("notes", []),
        },
        "volumetrics": {
            "p10_mmboe": volumes.get("p10_mmboe"),
            "p50_mmboe": volumes.get("p50_mmboe"),
            "p90_mmboe": volumes.get("p90_mmboe"),
            "method": "probabilistic_monte_carlo",
            "aggregation": "SPE-PRMS deterministic + probabilistic per SEC 2009 modernization",
        },
        "telpai_survey_attachments": {
            "seismic": telpai_survey.get("seismic"),
            "magnetometry": telpai_survey.get("emag2") or telpai_survey.get("swarm"),
            "gravity": telpai_survey.get("ggmplus"),
            "seepage": telpai_survey.get("seepage"),
            "boem_lease": telpai_survey.get("boem"),
            "eia_commodity_context": telpai_survey.get("eia_wti") or telpai_survey.get("eia"),
            "firms_flares": telpai_survey.get("firms"),
            "production_analogs": telpai_survey.get("production", []),
        },
        "required_qre_deliverables": [
            "Property Reserves Report (SPE June 2019 §2.2(f))",
            "P10/P50/P90 volume table with economic limit (PRMS 2018 probabilistic thresholds)",
            "Decline curve analysis (PDP/PDNP) — §5.6",
            "PUD development schedule (5-year SEC Rule 4-10)",
            "Management representation letter — §5.1",
        ],
        "required_qra_deliverables": [
            "QRA audit opinion — aggregate proved reasonable within ±10% (§2.2(g))",
            "Exhibit A (consulting QRA) or Exhibit B (internal QRA) form — §6.6",
            "Engagement letter and audit procedure documentation — §6.3-6.5",
        ],
        "telpai_boundary": "TELPAI survey is supplementary geophysical input; not a substitute for QRE report or QRA audit.",
        "rwa_tokenization_path": {
            "eligible": classification.get("tokenizable"),
            "token_tier": classification.get("token_tier"),
            "reg_d_recommended": "506c" if classification.get("tokenizable") else "private_placement_alternate",
        },
    }