"""
TELPAI × RWA API routes — mount on api_server via include_router.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .asset_store import get_asset, list_assets, upsert_asset
from .prms_engine import (
    PRMS_FRAMEWORK,
    CommercialEvaluation,
    TechnicalEvaluation,
    classify_reserves,
    monte_carlo_volumes,
    tokenizability_matrix,
)
from .qre_package import build_qre_data_package
from .reg_d_506 import checklist_template, validate_reg_d_offering
from .reserve_oracle import build_oracle_epoch
from .minerals_engine import (
    NI43101_FRAMEWORK,
    MineralCommercialEvaluation,
    MineralTechnicalEvaluation,
    classify_mineral_resource,
    contained_metal_monte_carlo,
    mineral_tokenizability_matrix,
    qp_engagement_checklist,
)
from .quantum_verify import verify_asset
from .dragon_seal import seal_epoch
from .onboarding import onboard_asset
from .division12 import build_division12_audit, load_training_summary
from .division13 import (
    AGENT_ROLES as NI43101_ROLES,
    build_division13_audit,
    load_training_summary as load_ni43101_summary,
)
from .spe_audit_standards import (
    SPE_AUDIT_STANDARDS,
    qra_engagement_checklist,
    telpai_vs_qre_boundary,
)
from .telpai_feeds import collect_telpai_survey

router = APIRouter(prefix="/rwa", tags=["TELPAI-RWA"])

_SPE_CHECKPOINT = Path("results/autoqms_spe_prms_checkpoint.pt")


class TechnicalInput(BaseModel):
    volumetric_confidence: float = Field(ge=0, le=1)
    seismic_interpretation_confidence: float = Field(ge=0, le=1)
    magnetometry_anomaly_strength: float = Field(ge=0, le=1)
    production_history_months: float = Field(ge=0, default=0)
    analog_match_score: float = Field(ge=0, le=1, default=0)
    simulation_quality: float = Field(ge=0, le=1, default=0)


class CommercialInput(BaseModel):
    price_deck_current: float = Field(ge=0, le=1)
    opex_breakeven_ratio: float = Field(ge=0, le=1)
    fiscal_terms_certainty: float = Field(ge=0, le=1)
    development_plan_approved: bool = False
    pud_five_year_plan: bool = False
    regulatory_approval: float = Field(ge=0, le=1, default=0)


class ClassifyRequest(BaseModel):
    technical: TechnicalInput
    commercial: CommercialInput
    is_producing: bool = False
    behind_pipe: bool = False
    undeveloped: bool = False
    discovery_stage: str = "discovered"


class MonteCarloRequest(BaseModel):
    p50_mmboe: float = Field(gt=0)
    p10_p90_spread: float = 0.35
    n_samples: int = Field(default=10_000, ge=100, le=100_000)


class RegDValidateRequest(BaseModel):
    rule: str = "506c"
    checklist_state: dict[str, bool] = Field(default_factory=dict)
    reserve_tokenizable: bool = False
    qre_signed: bool = False
    dragon_seal_anchored: bool = False


class AssetRegisterRequest(BaseModel):
    asset_id: str
    name: str
    operator: str
    basin: str
    lat: float
    lon: float
    country: str = "USA"
    p50_mmboe: float = Field(gt=0)


class OracleEpochRequest(BaseModel):
    asset_id: str
    classification: dict[str, Any]
    telpai_feeds: dict[str, Any]
    volumes: dict[str, float] | None = None
    reg_d_rule: str = "506c"


class QREPackageRequest(BaseModel):
    asset: dict[str, Any]
    classification: dict[str, Any]
    volumes: dict[str, float]
    telpai_survey: dict[str, Any]


@router.get("/health")
def rwa_health():
    return {
        "status": "live",
        "module": "telpai_rwa",
        "standards": ["SPE-PRMS-2018", "SEC-Rule-4-10", "Reg-D-506"],
        "stack": ["TELPAI", "QM2ARL-Div12", "TradeProto", "DragonSeal", "ERC-3643"],
        "assets_registered": len(list_assets()),
    }


@router.get("/prms/framework")
def prms_framework():
    return {"framework": PRMS_FRAMEWORK, "tokenizability": tokenizability_matrix()}


@router.get("/spe-audit/framework")
def spe_audit_framework():
    """SPE June 2019 Reserves Audit Standards — QRE/QRA rules for Rivers Bend path."""
    return {
        "standards": SPE_AUDIT_STANDARDS,
        "telpai_vs_qre": telpai_vs_qre_boundary(),
    }


@router.get("/qra/engagement-checklist")
def qra_engagement(property_report: bool = True):
    return qra_engagement_checklist(property_report=property_report)


@router.post("/prms/classify")
def prms_classify(req: ClassifyRequest):
    tech = TechnicalEvaluation(**req.technical.model_dump())
    comm = CommercialEvaluation(**req.commercial.model_dump())
    result = classify_reserves(
        tech,
        comm,
        is_producing=req.is_producing,
        behind_pipe=req.behind_pipe,
        undeveloped=req.undeveloped,
        discovery_stage=req.discovery_stage,
    )
    return {
        "category": result.category.value,
        "certainty_pct": result.certainty_pct,
        "technical_score": result.technical_score,
        "commercial_score": result.commercial_score,
        "tokenizable": result.tokenizable,
        "token_tier": result.token_tier,
        "sec_disclosure_basis": result.sec_disclosure_basis,
        "notes": result.notes,
        "agent_scores_division_12": result.agent_scores,
    }


@router.post("/prms/monte-carlo")
def prms_monte_carlo(req: MonteCarloRequest):
    return monte_carlo_volumes(req.p50_mmboe, req.p10_p90_spread, req.n_samples)


@router.get("/regd506/checklist")
def regd_checklist(rule: str = "506c"):
    return checklist_template(rule)


@router.post("/regd506/validate")
def regd_validate(req: RegDValidateRequest):
    v = validate_reg_d_offering(
        req.rule,
        req.checklist_state,
        reserve_tokenizable=req.reserve_tokenizable,
        qre_signed=req.qre_signed,
        dragon_seal_anchored=req.dragon_seal_anchored,
    )
    return {
        "rule": v.rule,
        "ready": v.ready,
        "score_pct": v.score_pct,
        "completed": v.completed,
        "missing": v.missing,
        "blockers": v.blockers,
    }


@router.get("/agents/spe-prms/status")
def spe_prms_agent_status():
    """Division 12 status — real trained audit scores when the summary exists."""
    summary = load_training_summary()
    domains = PRMS_FRAMEWORK["agent_domains"]
    trained_domains = (summary or {}).get("domains", {})
    agents = []
    for d in domains:
        td = trained_domains.get(d, {})
        agents.append({
            "domain": d,
            "role": _agent_role(d),
            "trained_audit_pct": td.get("score_pct"),
            "trained_status": td.get("status"),
            "gap_pct": td.get("gap_pct"),
        })
    return {
        "division": 12,
        "preset": "spe_prms",
        "config": "configs/compliance_spe_prms.yaml",
        "run_command": "python simulations/compliance_audit.py configs/compliance_spe_prms.yaml",
        "trained": summary is not None,
        "episodes": (summary or {}).get("episodes"),
        "overall_audit_pct": (summary or {}).get("best_overall_pct"),
        "audit_status": (summary or {}).get("best_status"),
        "rwa_blocker": (summary or {}).get("rwa_blocker"),
        "checkpoint": str(_SPE_CHECKPOINT),
        "checkpoint_exists": _SPE_CHECKPOINT.exists(),
        "agents": agents,
    }


class Division12AuditRequest(BaseModel):
    classification: dict[str, Any] = Field(default_factory=dict)


@router.post("/agents/spe-prms/audit")
def spe_prms_audit(req: Division12AuditRequest):
    """Division 12 AI audit posture for an asset's classification (gate + blocker)."""
    return build_division12_audit(req.classification)


@router.get("/agents/ni43101/status")
def ni43101_agent_status():
    """Division 13 (NI 43-101 QP) status — real trained audit scores when available."""
    summary = load_ni43101_summary()
    trained_domains = (summary or {}).get("domains", {})
    agents = []
    for d, role in NI43101_ROLES.items():
        td = trained_domains.get(d, {})
        agents.append({
            "domain": d,
            "role": role,
            "trained_audit_pct": td.get("score_pct"),
            "trained_status": td.get("status"),
            "gap_pct": td.get("gap_pct"),
        })
    return {
        "division": 13,
        "preset": "ni43101",
        "config": "configs/compliance_ni43101.yaml",
        "run_command": "python simulations/compliance_audit.py configs/compliance_ni43101.yaml",
        "trained": summary is not None,
        "episodes": (summary or {}).get("episodes"),
        "overall_audit_pct": (summary or {}).get("best_overall_pct"),
        "audit_status": (summary or {}).get("best_status"),
        "agents": agents,
    }


class Division13AuditRequest(BaseModel):
    classification: dict[str, Any] = Field(default_factory=dict)


@router.post("/agents/ni43101/audit")
def ni43101_audit(req: Division13AuditRequest):
    """Division 13 QP AI audit posture for a mineral classification (gate + blocker)."""
    return build_division13_audit(req.classification)


def _agent_role(domain: str) -> str:
    roles = {
        "prms_framework_definitions": "Geologist — PRMS framework & scope",
        "reserves_classification": "Reserves Engineer — 1P/2P/3P classification",
        "contingent_resources": "Geologist — 1C/2C/3C contingent",
        "prospective_resources": "Prospector — exploration maturity",
        "technical_evaluation": "Petroleum Engineer — volumetrics & simulation",
        "commercial_evaluation": "Reserves Economist — price deck & fiscal",
        "uncertainty_aggregation": "Geostatistician — P10/P50/P90 aggregation",
        "audit_rwa_tokenization": "Audit Lead — SPE audit + on-chain attestation",
    }
    return roles.get(domain, "SPE PRMS specialist")


@router.post("/assets")
def register_asset(req: AssetRegisterRequest):
    record = upsert_asset(req.model_dump())
    return {"status": "registered", "asset": record}


@router.get("/assets")
def get_assets():
    return {"assets": list_assets()}


@router.get("/assets/{asset_id}")
def get_asset_by_id(asset_id: str):
    a = get_asset(asset_id)
    if not a:
        raise HTTPException(status_code=404, detail="asset not found")
    return a


@router.post("/oracle/epoch")
def oracle_epoch(req: OracleEpochRequest):
    return build_oracle_epoch(
        req.asset_id,
        classification=req.classification,
        telpai_feeds=req.telpai_feeds,
        volumes=req.volumes,
        reg_d_rule=req.reg_d_rule,
    )


@router.post("/qre/package")
def qre_package(req: QREPackageRequest):
    return build_qre_data_package(
        req.asset,
        req.classification,
        req.volumes,
        req.telpai_survey,
    )


class PipelineEvaluateRequest(BaseModel):
    asset_id: str
    name: str
    operator: str
    basin: str
    lat: float
    lon: float
    p50_mmboe: float = Field(gt=0)
    technical: TechnicalInput
    commercial: CommercialInput
    is_producing: bool = False
    behind_pipe: bool = False
    undeveloped: bool = False
    discovery_stage: str = "discovered"
    reg_d_rule: str = "506c"
    checklist_state: dict[str, bool] = Field(default_factory=dict)


@router.post("/pipeline/evaluate")
def pipeline_evaluate(req: PipelineEvaluateRequest):
    """End-to-end: classify → volumes → QRE package → oracle epoch → Reg D gate."""
    tech = TechnicalEvaluation(**req.technical.model_dump())
    comm = CommercialEvaluation(**req.commercial.model_dump())
    clf = classify_reserves(
        tech,
        comm,
        is_producing=req.is_producing,
        behind_pipe=req.behind_pipe,
        undeveloped=req.undeveloped,
        discovery_stage=req.discovery_stage,
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
    }
    volumes = monte_carlo_volumes(req.p50_mmboe)
    asset = upsert_asset(
        {
            "asset_id": req.asset_id,
            "name": req.name,
            "operator": req.operator,
            "basin": req.basin,
            "lat": req.lat,
            "lon": req.lon,
            "p50_mmboe": req.p50_mmboe,
            "classification": classification,
            "volumes": volumes,
        }
    )
    telpai_survey = collect_telpai_survey(req.lat, req.lon, basin=req.basin)
    qre = build_qre_data_package(asset, classification, volumes, telpai_survey)
    epoch = build_oracle_epoch(
        req.asset_id,
        classification=classification,
        telpai_feeds=telpai_survey,
        volumes=volumes,
        reg_d_rule=req.reg_d_rule,
    )
    regd = validate_reg_d_offering(
        req.reg_d_rule,
        req.checklist_state,
        reserve_tokenizable=clf.tokenizable,
        qre_signed=req.checklist_state.get("qre_report", False),
        dragon_seal_anchored=req.checklist_state.get("dragon_seal", False),
    )
    return {
        "asset": asset,
        "classification": classification,
        "volumes_mmboe": volumes,
        "qre_package": qre,
        "oracle_epoch": epoch,
        "reg_d_506": {
            "ready": regd.ready,
            "score_pct": regd.score_pct,
            "blockers": regd.blockers,
            "missing": regd.missing,
        },
        "division_12_agent_scores": clf.agent_scores,
        "next_steps": _pipeline_next_steps(clf, regd),
    }


class VerifyRequest(BaseModel):
    technical: dict[str, Any] = Field(default_factory=dict)
    telpai_survey: dict[str, Any] | None = None
    lat: float | None = None
    lon: float | None = None
    basin: str = ""
    vqc_backend: str = ""


@router.post("/verify")
def quantum_verify(req: VerifyRequest):
    """TELPAI-Q quantum-kernel geospatial verification of an in-ground asset."""
    survey = req.telpai_survey
    if survey is None and req.lat is not None and req.lon is not None:
        survey = collect_telpai_survey(req.lat, req.lon, basin=req.basin)
    return verify_asset(
        technical=req.technical, telpai_survey=survey, vqc_backend=req.vqc_backend
    ).as_dict()


class SealRequest(BaseModel):
    epoch: dict[str, Any]
    pin_to_lighthouse: bool = False


@router.post("/oracle/seal")
def oracle_seal(req: SealRequest):
    """Seal an oracle epoch → .dragon bundle (+ optional Lighthouse pin)."""
    return seal_epoch(req.epoch, pin_to_lighthouse=req.pin_to_lighthouse)


@router.get("/minerals/framework")
def minerals_framework():
    return {"framework": NI43101_FRAMEWORK,
            "tokenizability": mineral_tokenizability_matrix(),
            "qp_checklist": qp_engagement_checklist()}


class MineralTechnicalInput(BaseModel):
    drill_density_confidence: float = Field(ge=0, le=1)
    assay_qaqc_confidence: float = Field(ge=0, le=1)
    geological_continuity: float = Field(ge=0, le=1)
    magnetometry_anomaly_strength: float = Field(ge=0, le=1, default=0)
    gravity_anomaly_strength: float = Field(ge=0, le=1, default=0)
    metallurgical_recovery: float = Field(ge=0, le=1, default=0)
    twin_hole_match: float = Field(ge=0, le=1, default=0)


class MineralCommercialInput(BaseModel):
    metal_price_deck: float = Field(ge=0, le=1)
    cash_cost_ratio: float = Field(ge=0, le=1)
    permitting_status: float = Field(ge=0, le=1)
    mine_plan_approved: bool = False
    feasibility_study_level: str = "PEA"
    social_license: float = Field(ge=0, le=1, default=0)


class MineralClassifyRequest(BaseModel):
    technical: MineralTechnicalInput
    commercial: MineralCommercialInput
    is_reserve_candidate: bool = False
    discovery_stage: str = "resource"


@router.post("/minerals/classify")
def minerals_classify(req: MineralClassifyRequest):
    tech = MineralTechnicalEvaluation(**req.technical.model_dump())
    comm = MineralCommercialEvaluation(**req.commercial.model_dump())
    r = classify_mineral_resource(
        tech, comm,
        is_reserve_candidate=req.is_reserve_candidate,
        discovery_stage=req.discovery_stage,
    )
    return {
        "category": r.category.value,
        "confidence_pct": r.confidence_pct,
        "technical_score": r.technical_score,
        "commercial_score": r.commercial_score,
        "tokenizable": r.tokenizable,
        "token_tier": r.token_tier,
        "disclosure_basis": r.disclosure_basis,
        "qp_required": r.qp_required,
        "notes": r.notes,
    }


class MineralVolumeRequest(BaseModel):
    tonnage_mt: float = Field(gt=0)
    grade_gpt: float = Field(gt=0)
    recovery: float = Field(ge=0, le=1, default=0.92)


@router.post("/minerals/contained")
def minerals_contained(req: MineralVolumeRequest):
    return contained_metal_monte_carlo(
        req.tonnage_mt, req.grade_gpt, recovery=req.recovery
    )


@router.post("/onboard")
def onboard(asset: dict[str, Any]):
    """
    One-call commodity-agnostic onboarding spine (gas via SPE-PRMS, gold via
    NI 43-101): TELPAI survey → quantum verify → classify → oracle epoch →
    Dragon Seal → Reg D gate. Pass the full asset record as JSON body.
    """
    if "asset_id" not in asset:
        raise HTTPException(status_code=422, detail="asset_id required")
    return onboard_asset(
        asset,
        vqc_backend=asset.get("vqc_backend", ""),
        seal=asset.get("seal", True),
        pin_to_lighthouse=asset.get("pin_to_lighthouse", False),
    )


def _pipeline_next_steps(clf, regd) -> list[str]:
    steps = []
    if not clf.tokenizable:
        steps.append("Engage QRE for contingent/prospective path or re-survey for proved classification.")
    else:
        steps.append("Commission independent QRE report (Ryder Scott / DeGolyer / NSAI).")
    steps.append("Run: python simulations/compliance_audit.py configs/compliance_spe_prms.yaml")
    steps.append("Seal QRE + TELPAI survey on dragonseal.io; anchor Sepolia.")
    if not regd.ready:
        steps.append(f"Complete Reg D checklist — missing: {', '.join(regd.missing[:5])}")
    steps.append("Wire TradeProto ERC-3643 SPV + accredited investor gateway.")
    return steps