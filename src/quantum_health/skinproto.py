"""
SkinProto Protocol Matrix — Quantum Health Solutions, skin damage & wound care.

A structured CLINICAL-PROTOCOL SCAFFOLD that organizes the four science pillars
the program is built on into an ICH-GCP-shaped protocol synopsis and a
per-domain regulatory-readiness signal for the Division 14 AI audit.

Four pillars (each scored as an evidence/readiness level in [0,1] from inputs):
  · methylation      — epigenetic (DNA-methylation) biomarkers of healing /
                       oncogenic risk used for stratification & monitoring
  · encapsulation    — delivery system (nano / liposomal / hydrogel) for topical
                       wound delivery; CMC & release characterization
  · cross_matrix     — extracellular-matrix / cross-linked scaffold for tissue
                       regeneration and re-epithelialization
  · oncology_safety  — carcinogenicity / oncogenic-risk safety assessment
                       (skin malignancy relevance) — a SAFETY gate, not a claim

╔══════════════════════════════════════════════════════════════════════════╗
║  This is a documentation/readiness scaffold. Evidence levels are inputs    ║
║  the team supplies from real preclinical/clinical data — the module does   ║
║  NOT generate biological evidence and makes NO efficacy or safety claims.  ║
║  IRB approval + regulatory authorization required before human enrollment. ║
╚══════════════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .gcp_framework import DISCLAIMER

_PILLARS = ("methylation", "encapsulation", "cross_matrix", "oncology_safety")


def _clip(x: Any, d: float = 0.0) -> float:
    try:
        return float(np.clip(float(x), 0.0, 1.0))
    except (TypeError, ValueError):
        return d


@dataclass
class SciencePillar:
    name: str
    evidence_level: float        # [0,1] readiness/strength of evidence supplied
    summary: str
    inputs: dict[str, Any] = field(default_factory=dict)


def _score_methylation(d: dict[str, Any]) -> SciencePillar:
    # Stratification biomarker readiness: panel validated, assay QA/QC, cohort.
    ev = np.mean([
        _clip(d.get("biomarker_panel_validated"), 0.3),
        _clip(d.get("assay_qaqc"), 0.3),
        _clip(d.get("reference_cohort_strength"), 0.3),
    ])
    return SciencePillar(
        "methylation", float(ev),
        "DNA-methylation biomarker panel for healing-response stratification and "
        "oncogenic-risk monitoring (epigenetic signature).",
        d,
    )


def _score_encapsulation(d: dict[str, Any]) -> SciencePillar:
    ev = np.mean([
        _clip(d.get("formulation_characterized"), 0.3),
        _clip(d.get("release_kinetics_defined"), 0.3),
        _clip(d.get("gmp_process_readiness"), 0.3),
        _clip(d.get("stability_data"), 0.3),
    ])
    return SciencePillar(
        "encapsulation", float(ev),
        "Delivery system (nano/liposomal/hydrogel) for topical wound delivery; "
        "release kinetics, stability and GMP CMC readiness.",
        d,
    )


def _score_cross_matrix(d: dict[str, Any]) -> SciencePillar:
    ev = np.mean([
        _clip(d.get("scaffold_biocompatibility"), 0.3),
        _clip(d.get("crosslink_characterization"), 0.3),
        _clip(d.get("regeneration_evidence"), 0.3),
    ])
    return SciencePillar(
        "cross_matrix", float(ev),
        "Extracellular-matrix / cross-linked scaffold for tissue regeneration and "
        "re-epithelialization in skin-damage and wound care.",
        d,
    )


def _score_oncology_safety(d: dict[str, Any]) -> SciencePillar:
    ev = np.mean([
        _clip(d.get("carcinogenicity_assessed"), 0.2),
        _clip(d.get("genotoxicity_data"), 0.2),
        _clip(d.get("oncogenic_risk_controlled"), 0.2),
    ])
    return SciencePillar(
        "oncology_safety", float(ev),
        "Carcinogenicity / genotoxicity / oncogenic-risk safety assessment "
        "(skin-malignancy relevance). SAFETY GATE — not an oncology indication claim.",
        d,
    )


@dataclass
class SkinProtoMatrix:
    indication: str
    phase: str
    modality_stack: list[str]
    primary_endpoint: str
    pillars: dict[str, SciencePillar]
    protocol_completeness: float
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "protocol": "SkinProto Protocol Matrix",
            "indication": self.indication,
            "phase": self.phase,
            "modality_stack": self.modality_stack,
            "primary_endpoint": self.primary_endpoint,
            "pillars": {
                k: {"evidence_level": round(p.evidence_level, 3), "summary": p.summary}
                for k, p in self.pillars.items()
            },
            "protocol_completeness": round(self.protocol_completeness, 3),
            "disclaimer": DISCLAIMER,
            "notes": self.notes,
        }


def build_skinproto_matrix(inputs: dict[str, Any]) -> SkinProtoMatrix:
    """
    Build the SkinProto Protocol Matrix from supplied evidence inputs.

    inputs schema (all optional, 0–1 evidence levels per sub-item):
      indication, phase, primary_endpoint,
      methylation{...}, encapsulation{...}, cross_matrix{...}, oncology_safety{...},
      protocol{ synopsis, objectives, inclusion_exclusion, sample_size, ... }
    """
    pillars = {
        "methylation": _score_methylation(inputs.get("methylation", {})),
        "encapsulation": _score_encapsulation(inputs.get("encapsulation", {})),
        "cross_matrix": _score_cross_matrix(inputs.get("cross_matrix", {})),
        "oncology_safety": _score_oncology_safety(inputs.get("oncology_safety", {})),
    }

    proto = inputs.get("protocol", {})
    completeness = float(np.mean([
        _clip(proto.get("synopsis_defined"), 0.3),
        _clip(proto.get("objectives_endpoints_defined"), 0.3),
        _clip(proto.get("inclusion_exclusion_defined"), 0.3),
        _clip(proto.get("sample_size_justified"), 0.2),
    ]))

    notes: list[str] = []
    if pillars["oncology_safety"].evidence_level < 0.5:
        notes.append("Oncology/carcinogenicity safety evidence is LOW — gating for first-in-human.")
    if pillars["encapsulation"].evidence_level < 0.5:
        notes.append("Encapsulation CMC/stability evidence is LOW — strengthen before IND/IDE CMC module.")

    return SkinProtoMatrix(
        indication=str(inputs.get("indication", "Chronic & acute skin damage / wound care")),
        phase=str(inputs.get("phase", "phase_1")),
        modality_stack=list(inputs.get(
            "modality_stack",
            ["methylation-guided stratification", "encapsulated topical delivery",
             "cross-matrix regenerative scaffold"],
        )),
        primary_endpoint=str(inputs.get(
            "primary_endpoint",
            "Time to complete wound re-epithelialization vs standard of care",
        )),
        pillars=pillars,
        protocol_completeness=completeness,
        notes=notes,
    )


def division14_agent_scores(matrix: SkinProtoMatrix) -> dict[str, float]:
    """
    Map SkinProto evidence + protocol completeness to per-domain Division 14
    agent readiness (0–1), one per GCP domain. Used by the clinical AI audit.
    """
    p = matrix.pillars
    c = matrix.protocol_completeness
    meth = p["methylation"].evidence_level
    enc = p["encapsulation"].evidence_level
    xm = p["cross_matrix"].evidence_level
    onc = p["oncology_safety"].evidence_level
    return {
        "protocol_design_endpoints": 0.5 * c + 0.5 * min(meth + xm, 1.0),
        "preclinical_mechanism": float(np.mean([meth, xm])),
        "cmc_formulation_encapsulation": enc,
        "safety_pharmacovigilance": float(np.mean([onc, 0.5 * (enc + xm)])),
        "irb_ethics_consent": 0.4 + 0.5 * c,
        "data_integrity_part11": 0.45 + 0.4 * c,
        "statistical_efficacy": 0.4 + 0.5 * c,
        "regulatory_submission_audit": float(np.mean([c, enc, onc])),
    }
