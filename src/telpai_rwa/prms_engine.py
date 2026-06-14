"""
SPE Petroleum Resources Management System (PRMS) — classification & uncertainty.

Maps to Division 12 agents (compliance_spe_prms.yaml):
  prms_framework_definitions, reserves_classification, contingent_resources,
  prospective_resources, technical_evaluation, commercial_evaluation,
  uncertainty_aggregation, audit_rwa_tokenization

References: SPE-PRMS 2018, SEC Rule 4-10, SEC Modernization 2009 (33-8995).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np


class ReserveCategory(str, Enum):
    PDP = "proved_developed_producing"
    PDNP = "proved_developed_non_producing"
    PUD = "proved_undeveloped"
    PROVED_1P = "proved_1p"
    PROBABLE_2P = "probable_2p"
    POSSIBLE_3P = "possible_3p"
    CONTINGENT_1C = "contingent_1c"
    CONTINGENT_2C = "contingent_2c"
    CONTINGENT_3C = "contingent_3c"
    PROSPECTIVE = "prospective"
    UNCLASSIFIED = "unclassified"


# SPE PRMS certainty thresholds (volume recovery confidence)
PRMS_CERTAINTY = {
    ReserveCategory.PROVED_1P: 0.90,
    ReserveCategory.PROBABLE_2P: 0.50,
    ReserveCategory.POSSIBLE_3P: 0.10,
}

PRMS_FRAMEWORK: dict[str, Any] = {
    "standard": "SPE-PRMS 2018",
    "audit_standard": "Standards Pertaining to the Estimating and Auditing of Oil and Gas Reserves Information",
    "sec_primary": "SEC Rule 4-10 (Regulation S-X)",
    "sec_supplemental": "SEC Modernization 2009 (Release 33-8995)",
    "agents_division": 12,
    "agent_domains": [
        "prms_framework_definitions",
        "reserves_classification",
        "contingent_resources",
        "prospective_resources",
        "technical_evaluation",
        "commercial_evaluation",
        "uncertainty_aggregation",
        "audit_rwa_tokenization",
    ],
    "hierarchy": {
        "piip": "Total Petroleum Initially in Place",
        "discovered_commercial": "Reserves (1P/2P/3P)",
        "discovered_subcommercial": "Contingent Resources (1C/2C/3C)",
        "undiscovered": "Prospective Resources",
    },
}


@dataclass
class TechnicalEvaluation:
    """TELPAI-fed technical inputs (0–1 normalized scores)."""
    volumetric_confidence: float
    seismic_interpretation_confidence: float
    magnetometry_anomaly_strength: float
    production_history_months: float = 0.0
    analog_match_score: float = 0.0
    simulation_quality: float = 0.0

    def aggregate_score(self) -> float:
        w = [0.25, 0.20, 0.15, 0.15, 0.10, 0.15]
        v = [
            self.volumetric_confidence,
            self.seismic_interpretation_confidence,
            self.magnetometry_anomaly_strength,
            min(1.0, self.production_history_months / 24.0),
            self.analog_match_score,
            self.simulation_quality,
        ]
        return float(np.clip(np.dot(w, v), 0, 1))


@dataclass
class CommercialEvaluation:
    """Economic / commerciality inputs (0–1)."""
    price_deck_current: float
    opex_breakeven_ratio: float
    fiscal_terms_certainty: float
    development_plan_approved: bool
    pud_five_year_plan: bool = False
    regulatory_approval: float = 0.0

    def aggregate_score(self) -> float:
        base = (
            0.30 * self.price_deck_current
            + 0.25 * (1.0 - min(1.0, self.opex_breakeven_ratio))
            + 0.20 * self.fiscal_terms_certainty
            + 0.15 * (1.0 if self.development_plan_approved else 0.0)
            + 0.10 * self.regulatory_approval
        )
        return float(np.clip(base, 0, 1))


@dataclass
class ClassificationResult:
    category: ReserveCategory
    certainty_pct: float
    technical_score: float
    commercial_score: float
    tokenizable: bool
    token_tier: str
    sec_disclosure_basis: str
    notes: list[str] = field(default_factory=list)
    agent_scores: dict[str, float] = field(default_factory=dict)


def _agent_scores_from_eval(tech: TechnicalEvaluation, comm: CommercialEvaluation, category: ReserveCategory) -> dict[str, float]:
    """Map evaluation to Division 12 agent readiness (0–1)."""
    t = tech.aggregate_score()
    c = comm.aggregate_score()
    return {
        "prms_framework_definitions": 0.94 if category != ReserveCategory.UNCLASSIFIED else 0.40,
        "reserves_classification": t * 0.5 + c * 0.5,
        "contingent_resources": 0.85 if "contingent" in category.value else 0.45,
        "prospective_resources": 0.80 if category == ReserveCategory.PROSPECTIVE else 0.40,
        "technical_evaluation": t,
        "commercial_evaluation": c,
        "uncertainty_aggregation": min(t, c) * 0.9 + 0.1,
        "audit_rwa_tokenization": min(t, c) * 0.85 if category != ReserveCategory.UNCLASSIFIED else 0.20,
    }


def classify_reserves(
    tech: TechnicalEvaluation,
    comm: CommercialEvaluation,
    *,
    is_producing: bool = False,
    behind_pipe: bool = False,
    undeveloped: bool = False,
    discovery_stage: str = "discovered",
) -> ClassificationResult:
    """
    Classify reserve category from TELPAI technical + commercial scores.

    discovery_stage: discovered | contingent | prospective
    """
    notes: list[str] = []
    t_score = tech.aggregate_score()
    c_score = comm.aggregate_score()
    combined = 0.55 * t_score + 0.45 * c_score

    if discovery_stage == "prospective":
        cat = ReserveCategory.PROSPECTIVE
        certainty = PRMS_CERTAINTY[ReserveCategory.POSSIBLE_3P] * t_score
        notes.append("Undiscovered — exploration participation only; not SEC primary reserve basis.")
    elif c_score < 0.45:
        if combined >= 0.35:
            cat = ReserveCategory.CONTINGENT_2C
            certainty = 0.50 * combined
            notes.append("Sub-commercial discovered — contingent resource; convertible token structure only.")
        else:
            cat = ReserveCategory.UNCLASSIFIED
            certainty = combined
            notes.append("Insufficient commercial evidence for reserves or contingent classification.")
    elif combined >= PRMS_CERTAINTY[ReserveCategory.PROVED_1P] and c_score >= 0.70:
        if is_producing:
            cat = ReserveCategory.PDP
        elif behind_pipe:
            cat = ReserveCategory.PDNP
        elif undeveloped:
            cat = ReserveCategory.PUD
            if not comm.pud_five_year_plan:
                notes.append("SEC PUD: requires 5-year development plan (Rule 4-10).")
        else:
            cat = ReserveCategory.PROVED_1P
        certainty = PRMS_CERTAINTY[ReserveCategory.PROVED_1P] * combined
    elif combined >= PRMS_CERTAINTY[ReserveCategory.PROBABLE_2P]:
        cat = ReserveCategory.PROBABLE_2P
        certainty = PRMS_CERTAINTY[ReserveCategory.PROBABLE_2P] * combined
        notes.append("Probable — supplemental disclosure only; not primary SEC filing basis.")
    elif combined >= PRMS_CERTAINTY[ReserveCategory.POSSIBLE_3P]:
        cat = ReserveCategory.POSSIBLE_3P
        certainty = PRMS_CERTAINTY[ReserveCategory.POSSIBLE_3P] * combined
        notes.append("Possible — high-risk supplemental tier only.")
    else:
        cat = ReserveCategory.CONTINGENT_1C
        certainty = 0.70 * combined
        notes.append("Discovered sub-commercial — contingent until commerciality demonstrated.")

    tok = tokenizability_matrix().get(cat.value, {})
    return ClassificationResult(
        category=cat,
        certainty_pct=round(certainty * 100, 1),
        technical_score=round(t_score, 4),
        commercial_score=round(c_score, 4),
        tokenizable=bool(tok.get("tokenizable", False)),
        token_tier=str(tok.get("token_tier", "none")),
        sec_disclosure_basis=str(tok.get("sec_basis", "not_disclosed")),
        notes=notes,
        agent_scores=_agent_scores_from_eval(tech, comm, cat),
    )


def monte_carlo_volumes(
    p50_mmboe: float,
    p10_p90_spread: float = 0.35,
    n_samples: int = 10_000,
    seed: int = 42,
) -> dict[str, float]:
    """Log-normal volume draw → P10/P50/P90 (MMBOE)."""
    rng = np.random.default_rng(seed)
    sigma = max(0.05, float(p10_p90_spread))
    mu = math.log(max(p50_mmboe, 1e-6)) - 0.5 * sigma**2
    samples = rng.lognormal(mu, sigma, size=n_samples)
    return {
        "p10_mmboe": round(float(np.percentile(samples, 10)), 3),
        "p50_mmboe": round(float(np.percentile(samples, 50)), 3),
        "p90_mmboe": round(float(np.percentile(samples, 90)), 3),
        "mean_mmboe": round(float(np.mean(samples)), 3),
        "samples": n_samples,
    }


def tokenizability_matrix() -> dict[str, dict[str, Any]]:
    """SEC-aligned tokenization gates per TELPAI RWA Master Framework §2.3."""
    return {
        ReserveCategory.PDP.value: {
            "tokenizable": True,
            "token_tier": "primary_revenue",
            "sec_basis": "proved_developed_producing",
            "reg_d_506c": "eligible_primary_offering_basis",
        },
        ReserveCategory.PDNP.value: {
            "tokenizable": True,
            "token_tier": "milestone_revenue",
            "sec_basis": "proved_developed_non_producing",
            "reg_d_506c": "eligible_with_workover_disclosure",
        },
        ReserveCategory.PUD.value: {
            "tokenizable": True,
            "token_tier": "development_linked",
            "sec_basis": "proved_undeveloped_5yr_plan",
            "reg_d_506c": "eligible_with_pud_plan_and_qre",
        },
        ReserveCategory.PROVED_1P.value: {
            "tokenizable": True,
            "token_tier": "primary_revenue",
            "sec_basis": "proved_reserves",
            "reg_d_506c": "eligible_primary_offering_basis",
        },
        ReserveCategory.PROBABLE_2P.value: {
            "tokenizable": True,
            "token_tier": "supplemental_risk_adjusted",
            "sec_basis": "supplemental_only",
            "reg_d_506c": "supplemental_disclosure_only",
        },
        ReserveCategory.POSSIBLE_3P.value: {
            "tokenizable": True,
            "token_tier": "exploration_high_risk",
            "sec_basis": "supplemental_only",
            "reg_d_506c": "supplemental_disclosure_only",
        },
        ReserveCategory.CONTINGENT_1C.value: {
            "tokenizable": False,
            "token_tier": "convertible_forward",
            "sec_basis": "not_reserves",
            "reg_d_506c": "forward_contract_structure",
        },
        ReserveCategory.CONTINGENT_2C.value: {
            "tokenizable": False,
            "token_tier": "convertible_forward",
            "sec_basis": "not_reserves",
            "reg_d_506c": "forward_contract_structure",
        },
        ReserveCategory.CONTINGENT_3C.value: {
            "tokenizable": False,
            "token_tier": "convertible_forward",
            "sec_basis": "not_reserves",
            "reg_d_506c": "forward_contract_structure",
        },
        ReserveCategory.PROSPECTIVE.value: {
            "tokenizable": False,
            "token_tier": "exploration_participation",
            "sec_basis": "pre_discovery",
            "reg_d_506c": "private_placement_exploration_only",
        },
        ReserveCategory.UNCLASSIFIED.value: {
            "tokenizable": False,
            "token_tier": "none",
            "sec_basis": "not_disclosed",
            "reg_d_506c": "blocked_pending_qre",
        },
    }