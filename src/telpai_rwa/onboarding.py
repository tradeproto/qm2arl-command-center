"""
Commodity-agnostic RWA onboarding orchestrator.

One entry point — ``onboard_asset()`` — drives the full in-ground RWA spine for
either an oil & gas asset (SPE-PRMS) or a mineral asset (NI 43-101 / CIM):

    register  ->  TELPAI survey  ->  TELPAI-Q quantum verify  ->  classify
              ->  QRE/QP package  ->  oracle epoch  ->  Dragon Seal
              ->  securities gate (Reg D 506)

The Streamlit onboarding console and the API both call this so behavior is
identical across surfaces.
"""
from __future__ import annotations

from typing import Any

from .asset_store import upsert_asset
from .division12 import build_division12_audit
from .division13 import build_division13_audit
from .dragon_seal import seal_epoch
from .quantum_verify import verify_asset
from .reg_d_506 import validate_reg_d_offering
from .reserve_oracle import build_oracle_epoch


def _detect_commodity(asset: dict[str, Any]) -> str:
    c = str(asset.get("commodity") or asset.get("commodity_primary") or "").lower()
    if any(k in c for k in ("gold", "silver", "copper", "mineral", "ore", "metal")):
        return "mineral"
    return "oil_gas"


def _collect_survey(asset: dict[str, Any], provided: dict[str, Any] | None) -> dict[str, Any]:
    if provided:
        return provided
    try:
        from .telpai_feeds import collect_telpai_survey

        return collect_telpai_survey(
            float(asset["lat"]), float(asset["lon"]), basin=str(asset.get("basin", ""))
        )
    except Exception as e:
        # Network/feed failure must not block the rest of the pipeline.
        return {
            "status": "offline",
            "error": f"{type(e).__name__}: {e}",
            "lat": asset.get("lat"),
            "lon": asset.get("lon"),
            "basin": asset.get("basin"),
        }


def _classify_oil_gas(asset: dict[str, Any]) -> dict[str, Any]:
    from .prms_engine import (
        CommercialEvaluation,
        TechnicalEvaluation,
        classify_reserves,
        monte_carlo_volumes,
    )

    tech = TechnicalEvaluation(**{
        k: asset["technical"].get(k, d) for k, d in {
            "volumetric_confidence": 0.5, "seismic_interpretation_confidence": 0.5,
            "magnetometry_anomaly_strength": 0.5, "production_history_months": 0.0,
            "analog_match_score": 0.0, "simulation_quality": 0.0,
        }.items()
    })
    comm = CommercialEvaluation(**{
        k: asset["commercial"].get(k, d) for k, d in {
            "price_deck_current": 0.5, "opex_breakeven_ratio": 0.5,
            "fiscal_terms_certainty": 0.5, "development_plan_approved": False,
            "pud_five_year_plan": False, "regulatory_approval": 0.0,
        }.items()
    })
    clf = classify_reserves(
        tech, comm,
        is_producing=asset.get("is_producing", False),
        behind_pipe=asset.get("behind_pipe", False),
        undeveloped=asset.get("undeveloped", False),
        discovery_stage=asset.get("discovery_stage", "discovered"),
    )
    classification = {
        "category": clf.category.value,
        "certainty_pct": clf.certainty_pct,
        "technical_score": clf.technical_score,
        "commercial_score": clf.commercial_score,
        "tokenizable": clf.tokenizable,
        "token_tier": clf.token_tier,
        "sec_disclosure_basis": clf.sec_disclosure_basis,
        "notes": clf.notes,
        "agent_scores_division_12": clf.agent_scores,
    }
    volumes = monte_carlo_volumes(float(asset.get("p50_mmboe", 1.0)))
    return {"classification": classification, "volumes": volumes,
            "tokenizable": clf.tokenizable, "expert": "QRE"}


def _classify_mineral(asset: dict[str, Any]) -> dict[str, Any]:
    from .minerals_engine import (
        MineralCommercialEvaluation,
        MineralTechnicalEvaluation,
        classify_mineral_resource,
        contained_metal_monte_carlo,
    )

    t = asset.get("technical", {})
    c = asset.get("commercial", {})
    tech = MineralTechnicalEvaluation(
        drill_density_confidence=t.get("drill_density_confidence", 0.5),
        assay_qaqc_confidence=t.get("assay_qaqc_confidence", 0.5),
        geological_continuity=t.get("geological_continuity", 0.5),
        magnetometry_anomaly_strength=t.get("magnetometry_anomaly_strength", 0.0),
        gravity_anomaly_strength=t.get("gravity_anomaly_strength", 0.0),
        metallurgical_recovery=t.get("metallurgical_recovery", 0.0),
        twin_hole_match=t.get("twin_hole_match", 0.0),
    )
    comm = MineralCommercialEvaluation(
        metal_price_deck=c.get("metal_price_deck", 0.5),
        cash_cost_ratio=c.get("cash_cost_ratio", 0.5),
        permitting_status=c.get("permitting_status", 0.5),
        mine_plan_approved=c.get("mine_plan_approved", False),
        feasibility_study_level=c.get("feasibility_study_level", "PEA"),
        social_license=c.get("social_license", 0.0),
    )
    clf = classify_mineral_resource(
        tech, comm,
        is_reserve_candidate=asset.get("is_reserve_candidate", False),
        discovery_stage=asset.get("discovery_stage", "resource"),
    )
    classification = {
        "category": clf.category.value,
        "confidence_pct": clf.confidence_pct,
        "technical_score": clf.technical_score,
        "commercial_score": clf.commercial_score,
        "tokenizable": clf.tokenizable,
        "token_tier": clf.token_tier,
        "disclosure_basis": clf.disclosure_basis,
        "notes": clf.notes,
        "qp_required": clf.qp_required,
        "agent_scores_division_13": clf.agent_scores,
    }
    volumes = contained_metal_monte_carlo(
        float(asset.get("tonnage_mt", 1.0)),
        float(asset.get("grade_gpt", 1.0)),
        recovery=float(asset.get("recovery", 0.92)),
    )
    return {"classification": classification, "volumes": volumes,
            "tokenizable": clf.tokenizable, "expert": "QP"}


def onboard_asset(
    asset: dict[str, Any],
    *,
    telpai_survey: dict[str, Any] | None = None,
    vqc_backend: str = "",
    seal: bool = True,
    pin_to_lighthouse: bool = False,
    persist: bool = True,
) -> dict[str, Any]:
    """
    Run the full onboarding spine. ``asset`` must include at least asset_id,
    name, lat, lon, basin, and a ``technical``/``commercial`` block appropriate
    to its commodity.
    """
    commodity = _detect_commodity(asset)

    survey = _collect_survey(asset, telpai_survey)

    verification = verify_asset(
        technical=asset.get("technical", {}),
        telpai_survey=survey,
        vqc_backend=vqc_backend,
    ).as_dict()

    if commodity == "mineral":
        clf_bundle = _classify_mineral(asset)
    else:
        clf_bundle = _classify_oil_gas(asset)
    classification = clf_bundle["classification"]
    volumes = clf_bundle["volumes"]

    # AI audit: Division 12 (SPE-PRMS) for oil & gas, Division 13 (NI 43-101 QP) for minerals.
    division_12_audit = None
    division_13_audit = None
    if commodity == "mineral":
        division_13_audit = build_division13_audit(classification)
        ai_audit = division_13_audit
    else:
        division_12_audit = build_division12_audit(classification)
        ai_audit = division_12_audit

    asset_record = {**asset, "commodity": commodity,
                    "classification": classification, "volumes": volumes,
                    "quantum_verification": verification}
    if persist:
        try:
            upsert_asset(asset_record)
        except Exception:
            pass

    epoch = build_oracle_epoch(
        asset["asset_id"],
        classification=classification,
        telpai_feeds=survey,
        volumes=volumes,
        reg_d_rule=asset.get("reg_d_rule", "506c"),
        commodity=commodity,
        quantum_verification=verification,
    )

    sealed = None
    if seal:
        sealed = seal_epoch(epoch, pin_to_lighthouse=pin_to_lighthouse)

    checklist_state = dict(asset.get("checklist_state", {}))
    expert_signed = checklist_state.get("qre_report") or checklist_state.get("qp_report") or False
    regd = validate_reg_d_offering(
        asset.get("reg_d_rule", "506c"),
        checklist_state,
        reserve_tokenizable=clf_bundle["tokenizable"],
        qre_signed=bool(expert_signed),
        dragon_seal_anchored=bool(sealed and sealed.get("dragon_seal_anchored")),
    )

    # Fold the AI audit (Div 12 or Div 13) into the gate — a failed audit blocks issuance.
    gate_ready = regd.ready
    gate_blockers = list(regd.blockers)
    if ai_audit and not ai_audit.get("audit_gate_passed"):
        gate_ready = False
        gate_blockers.append(
            f"Division {ai_audit.get('division')} AI audit not cleared "
            f"({ai_audit.get('overall_audit_pct')}% — binding domain "
            f"'{ai_audit.get('binding_domain')}')."
        )

    return {
        "asset_id": asset["asset_id"],
        "commodity": commodity,
        "expert_required": clf_bundle["expert"],   # QRE (oil&gas) or QP (minerals)
        "telpai_survey": survey,
        "quantum_verification": verification,
        "classification": classification,
        "division_12_audit": division_12_audit,
        "division_13_audit": division_13_audit,
        "ai_audit": ai_audit,
        "ai_audit_division": ai_audit.get("division") if ai_audit else None,
        "volumes": volumes,
        "oracle_epoch": epoch,
        "dragon_seal": sealed,
        "securities_gate": {
            "rule": regd.rule,
            "ready": gate_ready,
            "score_pct": regd.score_pct,
            "missing": regd.missing,
            "blockers": gate_blockers,
            "ai_audit_passed": ai_audit.get("audit_gate_passed") if ai_audit else None,
            "ai_audit_division": ai_audit.get("division") if ai_audit else None,
        },
        "next_steps": _next_steps(commodity, clf_bundle, verification, regd, sealed, ai_audit),
    }


def _next_steps(commodity, clf_bundle, verification, regd, sealed, ai_audit=None) -> list[str]:
    steps: list[str] = []
    band = verification.get("confidence_band")
    if band == "low":
        steps.append("TELPAI-Q verification LOW — re-survey or add drilling/seismic before offering.")
    if ai_audit and not ai_audit.get("audit_gate_passed"):
        bd = ai_audit.get("binding_domain")
        steps.append(
            f"Division {ai_audit.get('division')} AI audit NOT cleared — remediate '{bd}' "
            f"({ai_audit.get('binding_domain_pct')}%). {ai_audit.get('blocker') or ''}".strip()
        )
    expert = clf_bundle["expert"]
    if clf_bundle["tokenizable"]:
        if commodity == "mineral":
            steps.append("Commission independent QP NI 43-101 Technical Report (Form 43-101F1).")
        else:
            steps.append("Commission independent QRE Property Reserves Report (Ryder Scott / DeGolyer / NSAI).")
    else:
        steps.append(f"Category not tokenizable as primary basis — use convertible/exploration structure or upgrade with {expert}.")
    if sealed and not sealed.get("dragon_seal_anchored"):
        steps.append("Pin .dragon bundle to Lighthouse and anchor on dragonseal.io (Sepolia).")
    if not regd.ready:
        steps.append(f"Complete Reg D {regd.rule} — missing: {', '.join(regd.missing[:5])}")
    steps.append("Wire TradeProto ERC-3643 SPV + accredited-investor gateway.")
    return steps
