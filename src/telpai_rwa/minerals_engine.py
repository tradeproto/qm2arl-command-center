"""
NI 43-101 / CIM mineral resource & reserve classification — gold and hard-rock.

The minerals analogue of prms_engine.py. Canadian NI 43-101 relies on the CIM
Definition Standards (2014):

  Mineral RESOURCES  (increasing geological confidence):
      Inferred  ->  Indicated  ->  Measured
  Mineral RESERVES  (Resources + Modifying Factors + economic viability):
      Probable (from Indicated)  ->  Proven (from Measured)

A Qualified Person (QP) signs the NI 43-101 Technical Report (Form 43-101F1) —
the minerals equivalent of the oil & gas QRE. TELPAI-Q provides supplementary
geophysical verification; it does not replace the QP.

Tokenization gate still routes through SEC Reg D 506(c) (reg_d_506.py); the QP
report + Dragon Seal are prerequisites, exactly as the QRE report is for O&G.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

GRAMS_PER_TROY_OZ = 31.10348


class MineralCategory(str, Enum):
    INFERRED = "inferred_resource"
    INDICATED = "indicated_resource"
    MEASURED = "measured_resource"
    PROBABLE = "probable_reserve"
    PROVEN = "proven_reserve"
    EXPLORATION_TARGET = "exploration_target"
    UNCLASSIFIED = "unclassified"


# CIM geological-confidence thresholds (combined technical score gates).
CIM_CONFIDENCE = {
    MineralCategory.MEASURED: 0.85,
    MineralCategory.INDICATED: 0.65,
    MineralCategory.INFERRED: 0.40,
}

NI43101_FRAMEWORK: dict[str, Any] = {
    "standard": "NI 43-101 / CIM Definition Standards (2014)",
    "report_form": "Form 43-101F1 Technical Report",
    "qualified_person": "QP sign-off mandatory (CIM Professional)",
    "us_analogue": "SEC S-K 1300 (SK-1300) — Measured/Indicated/Inferred parallel",
    "resource_hierarchy": ["inferred_resource", "indicated_resource", "measured_resource"],
    "reserve_hierarchy": ["probable_reserve", "proven_reserve"],
    "modifying_factors": [
        "mining", "processing/metallurgical", "economic", "marketing",
        "legal", "environmental", "social", "governmental",
    ],
}


@dataclass
class MineralTechnicalEvaluation:
    """TELPAI-fed + drill-program technical inputs (0–1 normalized)."""
    drill_density_confidence: float          # spacing / continuity of drilling
    assay_qaqc_confidence: float             # sampling QA/QC quality
    geological_continuity: float             # ore-body model continuity
    magnetometry_anomaly_strength: float = 0.0
    gravity_anomaly_strength: float = 0.0
    metallurgical_recovery: float = 0.0      # expected process recovery
    twin_hole_match: float = 0.0             # verification drilling agreement

    def aggregate_score(self) -> float:
        w = [0.28, 0.22, 0.20, 0.08, 0.07, 0.08, 0.07]
        v = [
            self.drill_density_confidence,
            self.assay_qaqc_confidence,
            self.geological_continuity,
            self.magnetometry_anomaly_strength,
            self.gravity_anomaly_strength,
            self.metallurgical_recovery,
            self.twin_hole_match,
        ]
        return float(np.clip(np.dot(w, v), 0, 1))


@dataclass
class MineralCommercialEvaluation:
    """Economic viability / modifying factors (0–1)."""
    metal_price_deck: float
    cash_cost_ratio: float                   # AISC / price (lower is better)
    permitting_status: float
    mine_plan_approved: bool = False
    feasibility_study_level: str = "PEA"     # PEA | PFS | FS
    social_license: float = 0.0

    def aggregate_score(self) -> float:
        fs_bonus = {"pea": 0.0, "pfs": 0.08, "fs": 0.15}.get(
            self.feasibility_study_level.lower(), 0.0
        )
        base = (
            0.30 * self.metal_price_deck
            + 0.25 * (1.0 - min(1.0, self.cash_cost_ratio))
            + 0.18 * self.permitting_status
            + 0.12 * (1.0 if self.mine_plan_approved else 0.0)
            + 0.15 * self.social_license
        )
        return float(np.clip(base + fs_bonus, 0, 1))


@dataclass
class MineralClassificationResult:
    category: MineralCategory
    confidence_pct: float
    technical_score: float
    commercial_score: float
    tokenizable: bool
    token_tier: str
    disclosure_basis: str
    notes: list[str] = field(default_factory=list)
    qp_required: bool = True
    agent_scores: dict[str, float] = field(default_factory=dict)


def _qp_agent_scores_from_eval(
    tech: MineralTechnicalEvaluation,
    comm: MineralCommercialEvaluation,
    category: MineralCategory,
) -> dict[str, float]:
    """Map the evaluation to Division 13 QP agent readiness (0–1), per NI 43-101 domain."""
    t = tech.aggregate_score()
    c = comm.aggregate_score()
    is_reserve = category in (MineralCategory.PROBABLE, MineralCategory.PROVEN)
    return {
        "geology_deposit_model": 0.55 + 0.4 * tech.geological_continuity,
        "drilling_exploration": tech.drill_density_confidence,
        "sampling_qaqc": tech.assay_qaqc_confidence,
        "mineral_resource_estimate": 0.5 * tech.drill_density_confidence
        + 0.5 * tech.geological_continuity,
        "mineral_reserve_modifying_factors": (min(t, c) * 0.9 + 0.1)
        if is_reserve else (0.45 if comm.mine_plan_approved else 0.30),
        "metallurgy_recovery": tech.metallurgical_recovery or 0.4,
        "economic_analysis": c,
        "qp_attestation_tokenization": (min(t, c) * 0.85)
        if category != MineralCategory.UNCLASSIFIED else 0.20,
    }


def classify_mineral_resource(
    tech: MineralTechnicalEvaluation,
    comm: MineralCommercialEvaluation,
    *,
    is_reserve_candidate: bool = False,
    discovery_stage: str = "resource",
) -> MineralClassificationResult:
    """
    Classify a mineral occurrence under CIM / NI 43-101.

    discovery_stage: exploration | resource | reserve
    is_reserve_candidate: True if a mine plan + modifying factors convert a
                          resource to a reserve (Indicated->Probable, Measured->Proven).
    """
    notes: list[str] = []
    t = tech.aggregate_score()
    c = comm.aggregate_score()
    combined = 0.6 * t + 0.4 * c

    if discovery_stage == "exploration":
        cat = MineralCategory.EXPLORATION_TARGET
        conf = 0.30 * t
        notes.append(
            "Exploration target — conceptual tonnage/grade range only; NOT a "
            "resource. Cannot be the basis of a reserve token (CIM 2014)."
        )
    elif t >= CIM_CONFIDENCE[MineralCategory.MEASURED]:
        if is_reserve_candidate and comm.mine_plan_approved and c >= 0.65:
            cat = MineralCategory.PROVEN
            conf = 0.90 * combined
        else:
            cat = MineralCategory.MEASURED
            conf = CIM_CONFIDENCE[MineralCategory.MEASURED] * combined
            if not comm.mine_plan_approved:
                notes.append("Measured resource — needs modifying factors + mine plan to become Proven reserve.")
    elif t >= CIM_CONFIDENCE[MineralCategory.INDICATED]:
        if is_reserve_candidate and comm.mine_plan_approved and c >= 0.60:
            cat = MineralCategory.PROBABLE
            conf = 0.75 * combined
        else:
            cat = MineralCategory.INDICATED
            conf = CIM_CONFIDENCE[MineralCategory.INDICATED] * combined
            notes.append("Indicated resource — convertible to Probable reserve with mine plan + economics.")
    elif t >= CIM_CONFIDENCE[MineralCategory.INFERRED]:
        cat = MineralCategory.INFERRED
        conf = CIM_CONFIDENCE[MineralCategory.INFERRED] * combined
        notes.append(
            "Inferred resource — lowest confidence; CIM prohibits use in economic "
            "studies (PFS/FS) and as reserve-token basis."
        )
    else:
        cat = MineralCategory.UNCLASSIFIED
        conf = combined
        notes.append("Insufficient drilling/QAQC for a CIM resource category.")

    tok = mineral_tokenizability_matrix().get(cat.value, {})
    return MineralClassificationResult(
        category=cat,
        confidence_pct=round(conf * 100, 1),
        technical_score=round(t, 4),
        commercial_score=round(c, 4),
        tokenizable=bool(tok.get("tokenizable", False)),
        token_tier=str(tok.get("token_tier", "none")),
        disclosure_basis=str(tok.get("disclosure_basis", "not_disclosed")),
        notes=notes,
        agent_scores=_qp_agent_scores_from_eval(tech, comm, cat),
    )


def contained_metal_monte_carlo(
    tonnage_mt: float,
    grade_gpt: float,
    *,
    tonnage_spread: float = 0.25,
    grade_spread: float = 0.20,
    recovery: float = 0.92,
    n_samples: int = 10_000,
    seed: int = 42,
) -> dict[str, float]:
    """
    Probabilistic contained gold (troy oz) from tonnage (Mt) × grade (g/t).

    Recoverable oz = tonnes * grade(g/t) * recovery / grams_per_oz.
    Returns P10/P50/P90 contained and recoverable ounces.
    """
    rng = np.random.default_rng(seed)
    t_sigma = max(0.05, float(tonnage_spread))
    g_sigma = max(0.05, float(grade_spread))
    t_mu = math.log(max(tonnage_mt, 1e-9)) - 0.5 * t_sigma**2
    g_mu = math.log(max(grade_gpt, 1e-9)) - 0.5 * g_sigma**2
    tonnes = rng.lognormal(t_mu, t_sigma, n_samples) * 1e6  # Mt -> t
    grade = rng.lognormal(g_mu, g_sigma, n_samples)         # g/t
    contained_oz = tonnes * grade / GRAMS_PER_TROY_OZ
    recoverable_oz = contained_oz * float(np.clip(recovery, 0.0, 1.0))

    def pct(a, p):
        return round(float(np.percentile(a, p)), 1)

    return {
        "p10_contained_oz": pct(contained_oz, 10),
        "p50_contained_oz": pct(contained_oz, 50),
        "p90_contained_oz": pct(contained_oz, 90),
        "p50_recoverable_oz": pct(recoverable_oz, 50),
        "p50_contained_kg": round(float(np.percentile(contained_oz, 50)) * GRAMS_PER_TROY_OZ / 1000.0, 1),
        "recovery_assumed": round(float(recovery), 3),
        "samples": n_samples,
    }


def mineral_tokenizability_matrix() -> dict[str, dict[str, Any]]:
    """CIM/SEC-aligned tokenization gates for mineral categories."""
    return {
        MineralCategory.PROVEN.value: {
            "tokenizable": True,
            "token_tier": "primary_revenue",
            "disclosure_basis": "proven_reserve_ni43101",
            "reg_d_506c": "eligible_primary_offering_basis",
        },
        MineralCategory.PROBABLE.value: {
            "tokenizable": True,
            "token_tier": "development_linked",
            "disclosure_basis": "probable_reserve_ni43101",
            "reg_d_506c": "eligible_with_mine_plan_and_qp",
        },
        MineralCategory.MEASURED.value: {
            "tokenizable": True,
            "token_tier": "supplemental_risk_adjusted",
            "disclosure_basis": "measured_resource_not_reserve",
            "reg_d_506c": "supplemental_disclosure_or_convertible",
        },
        MineralCategory.INDICATED.value: {
            "tokenizable": False,
            "token_tier": "convertible_forward",
            "disclosure_basis": "indicated_resource_not_reserve",
            "reg_d_506c": "convertible_on_reserve_conversion",
        },
        MineralCategory.INFERRED.value: {
            "tokenizable": False,
            "token_tier": "exploration_high_risk",
            "disclosure_basis": "inferred_resource_no_economics",
            "reg_d_506c": "blocked_inferred_no_economic_use",
        },
        MineralCategory.EXPLORATION_TARGET.value: {
            "tokenizable": False,
            "token_tier": "exploration_participation",
            "disclosure_basis": "exploration_target_conceptual",
            "reg_d_506c": "private_placement_exploration_only",
        },
        MineralCategory.UNCLASSIFIED.value: {
            "tokenizable": False,
            "token_tier": "none",
            "disclosure_basis": "not_disclosed",
            "reg_d_506c": "blocked_pending_qp",
        },
    }


def qp_engagement_checklist() -> dict[str, Any]:
    """Qualified Person deliverables for the NI 43-101 Technical Report."""
    return {
        "report_form": "Form 43-101F1",
        "deliverables": [
            "QP site visit / personal inspection (Item 2)",
            "Drill-hole database + QA/QC verification (Item 11)",
            "Mineral Resource estimate w/ classification rationale (Item 14)",
            "Mineral Reserve estimate + modifying factors (Item 15, if reserves)",
            "Metallurgical testwork & recovery basis (Item 13)",
            "Capital & operating cost estimates (Item 21)",
            "Economic analysis — NPV/IRR/cutoff grade (Item 22)",
            "QP certificate & consent (Form 43-101F1 Item 8 / certificates)",
        ],
        "telpai_boundary": (
            "TELPAI-Q geophysical survey + quantum verification is supplementary "
            "exploration input; the QP independently classifies and signs."
        ),
    }
