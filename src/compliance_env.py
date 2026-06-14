"""
Compliance Environment for AutoQMS — ISO and NQA-1 multi-agent compliance auditing.

Five presets:
  - iso_qms:         Division 10 — ISO 9001/42001/27001 combined compliance
  - nqa1:            Division 11 — ASME NQA-1 nuclear quality assurance
  - spe_prms:        Division 12 — SPE PRMS reserves audit & RWA tokenization
  - ni43101:         Division 13 — NI 43-101 / CIM Qualified Person (QP) minerals audit
  - clinical_trials: Division 14 — ICH-GCP / FDA / ISO 14155 clinical trial QA
                     (Quantum Health Solutions; SkinProto wound-care protocol)

Architecture mirrors MaterialsDesignEnv: 8 agents each own one compliance domain.
State: compliance score vector in [0,1]^8 (normalised).
Actions: EXPLORE (gather evidence), EXTRACT (assess/audit), INVEST (remediate/improve).
Coupling matrix: interdependencies between standard requirements.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

EXPLORE = 0
EXTRACT = 1
INVEST = 2
NUM_ACTIONS = 3

COMPLIANCE_PRESETS: dict[str, list[str]] = {
    "iso_qms": [
        "context_leadership",
        "planning_risk",
        "resources_competence",
        "documentation_control",
        "operations_ai_lifecycle",
        "performance_evaluation",
        "improvement_capa",
        "infosec_cmmc",
    ],
    "nqa1": [
        "organization_authority",
        "qa_program_procedures",
        "design_control",
        "procurement_materials",
        "document_records",
        "process_inspection_test",
        "nonconformance_capa",
        "audit_calibration",
    ],
    "spe_prms": [
        "prms_framework_definitions",
        "reserves_classification",
        "contingent_resources",
        "prospective_resources",
        "technical_evaluation",
        "commercial_evaluation",
        "uncertainty_aggregation",
        "audit_rwa_tokenization",
    ],
    "ni43101": [
        "geology_deposit_model",
        "drilling_exploration",
        "sampling_qaqc",
        "mineral_resource_estimate",
        "mineral_reserve_modifying_factors",
        "metallurgy_recovery",
        "economic_analysis",
        "qp_attestation_tokenization",
    ],
    "clinical_trials": [
        "protocol_design_endpoints",
        "preclinical_mechanism",
        "cmc_formulation_encapsulation",
        "safety_pharmacovigilance",
        "irb_ethics_consent",
        "data_integrity_part11",
        "statistical_efficacy",
        "regulatory_submission_audit",
    ],
}


def _coupling_iso_qms() -> np.ndarray:
    """ISO 9001/42001/27001 interdependency matrix."""
    M = np.zeros((8, 8), dtype=np.float64)
    M[0, 1] = M[1, 0] = 0.12   # context ↔ planning (context drives risk scope)
    M[0, 2] = M[2, 0] = 0.08   # leadership ↔ resources (commitment = adequate resources)
    M[3, 4] = M[4, 3] = 0.11   # documentation ↔ operations (procedures govern execution)
    M[4, 5] = M[5, 4] = 0.10   # operations ↔ performance (outputs measured against objectives)
    M[5, 6] = M[6, 5] = 0.13   # performance ↔ improvement (measurement drives CAPAs)
    M[6, 1] = M[1, 6] = 0.09   # improvement ↔ planning (CAPAs feed back into risk)
    M[4, 1] = M[1, 4] = 0.07   # AI lifecycle ↔ risk (AI changes trigger re-assessment)
    M[7, 3] = M[3, 7] = 0.10   # security ↔ documentation (access control on documents)
    M[2, 4] = M[4, 2] = 0.06   # competence ↔ operations (trained people execute processes)
    return M


def _coupling_nqa1() -> np.ndarray:
    """NQA-1 requirement interdependency matrix."""
    M = np.zeros((8, 8), dtype=np.float64)
    M[0, 1] = M[1, 0] = 0.12   # organization ↔ program (structure matches scope)
    M[2, 4] = M[4, 2] = 0.11   # design control ↔ document control (design changes → docs)
    M[3, 5] = M[5, 3] = 0.10   # procurement ↔ inspection (purchased items inspected per docs)
    M[6, 7] = M[7, 6] = 0.13   # nonconformance ↔ audit (audit findings drive CAPAs)
    M[4, 1] = M[1, 4] = 0.09   # records ↔ program (records prove program execution)
    M[2, 5] = M[5, 2] = 0.08   # design ↔ inspection (design output defines inspection criteria)
    M[6, 1] = M[1, 6] = 0.07   # CAPA ↔ program (corrective actions update procedures)
    M[3, 4] = M[4, 3] = 0.06   # procurement ↔ records (supplier qualifications are records)
    return M


def _coupling_spe_prms() -> np.ndarray:
    """SPE PRMS / reserves audit interdependency matrix."""
    M = np.zeros((8, 8), dtype=np.float64)
    M[0, 1] = M[1, 0] = 0.11   # framework ↔ reserves classification
    M[1, 2] = M[2, 1] = 0.10   # reserves ↔ contingent (project maturity)
    M[2, 3] = M[3, 2] = 0.09   # contingent ↔ prospective (exploration ladder)
    M[4, 1] = M[1, 4] = 0.12   # technical ↔ reserves (volumetrics prove class)
    M[5, 1] = M[1, 5] = 0.11   # commercial ↔ reserves (economic limit)
    M[6, 4] = M[4, 6] = 0.10   # uncertainty ↔ technical (P10/P50/P90)
    M[6, 5] = M[5, 6] = 0.08   # uncertainty ↔ commercial (price/volume risk)
    M[7, 0] = M[0, 7] = 0.09   # audit/RWA ↔ framework (definitions govern token)
    M[7, 4] = M[4, 7] = 0.10   # audit/RWA ↔ technical (proof chain needs eval docs)
    M[7, 6] = M[6, 7] = 0.08   # audit/RWA ↔ uncertainty (disclosure on-chain)
    return M


def _coupling_ni43101() -> np.ndarray:
    """NI 43-101 / CIM QP Technical Report (Form 43-101F1) interdependency matrix."""
    M = np.zeros((8, 8), dtype=np.float64)
    M[0, 1] = M[1, 0] = 0.11   # geology ↔ drilling (model guides drill program)
    M[1, 2] = M[2, 1] = 0.12   # drilling ↔ sampling/QAQC (core → assays)
    M[2, 3] = M[3, 2] = 0.13   # sampling/QAQC ↔ resource estimate (data feeds estimate)
    M[3, 4] = M[4, 3] = 0.12   # resource ↔ reserve (modifying factors convert resource)
    M[5, 4] = M[4, 5] = 0.10   # metallurgy ↔ reserve (recovery sets economic reserve)
    M[6, 4] = M[4, 6] = 0.11   # economic ↔ reserve (cutoff grade, economic viability)
    M[6, 5] = M[5, 6] = 0.08   # economic ↔ metallurgy (recovery drives revenue)
    M[7, 3] = M[3, 7] = 0.09   # QP/token ↔ resource (classification governs token)
    M[7, 6] = M[6, 7] = 0.10   # QP/token ↔ economic (disclosure of economics on-chain)
    M[7, 0] = M[0, 7] = 0.07   # QP/token ↔ geology (deposit basis for attestation)
    return M


def _coupling_clinical_trials() -> np.ndarray:
    """ICH-GCP / FDA / ISO 14155 clinical trial interdependency matrix.

    0 protocol_design_endpoints   4 irb_ethics_consent
    1 preclinical_mechanism        5 data_integrity_part11
    2 cmc_formulation_encapsulation 6 statistical_efficacy
    3 safety_pharmacovigilance     7 regulatory_submission_audit
    """
    M = np.zeros((8, 8), dtype=np.float64)
    M[0, 6] = M[6, 0] = 0.13   # protocol/endpoints ↔ statistics (endpoints power the SAP)
    M[1, 3] = M[3, 1] = 0.12   # preclinical mechanism ↔ safety (MoA drives tox/AE profile)
    M[2, 3] = M[3, 2] = 0.11   # CMC/encapsulation ↔ safety (formulation quality → safety)
    M[0, 4] = M[4, 0] = 0.10   # protocol ↔ IRB/ethics (design must pass ethics review)
    M[4, 5] = M[5, 4] = 0.09   # consent ↔ data integrity (consent & source data records)
    M[3, 5] = M[5, 3] = 0.10   # safety ↔ data integrity (AE/SAE reporting trail)
    M[6, 7] = M[7, 6] = 0.11   # statistics ↔ submission (analysis → regulatory dossier)
    M[2, 7] = M[7, 2] = 0.09   # CMC ↔ submission (CMC module of IND/IDE)
    M[3, 7] = M[7, 3] = 0.12   # safety ↔ submission (safety is gating for approval)
    M[1, 0] = M[0, 1] = 0.08   # preclinical ↔ protocol (evidence justifies design)
    return M


_COUPLING_REGISTRY: dict[str, callable] = {
    "iso_qms": _coupling_iso_qms,
    "nqa1": _coupling_nqa1,
    "spe_prms": _coupling_spe_prms,
    "ni43101": _coupling_ni43101,
    "clinical_trials": _coupling_clinical_trials,
}


@dataclass
class ComplianceEnvConfig:
    """Configuration for ComplianceEnv — covers ISO and NQA-1 domains."""
    max_steps: int = 300
    num_domains: int = 8
    domain_names: list[str] = field(default_factory=lambda: [f"domain_{i}" for i in range(8)])
    preset: str = ""

    compliance_targets: list[float] = field(default_factory=lambda: [0.90] * 8)
    compliance_init: list[float] = field(default_factory=lambda: [0.30] * 8)
    compliance_min: list[float] = field(default_factory=lambda: [0.0] * 8)
    compliance_max: list[float] = field(default_factory=lambda: [1.0] * 8)
    minimise_indices: list[int] = field(default_factory=list)

    invest_rate: float = 0.05
    extract_rate: float = 0.03
    explore_noise: float = 0.02

    coupling_strength: float = 1.0
    stress_amplitude: float = 0.02
    stress_period: float = 50.0

    target_penalty_scale: float = 0.06
    target_penalty_cap: float = 5.0
    stability_bonus: float = 0.35
    stability_sigma: float = 0.12
    explore_info_gain: float = 0.5
    harmony_scale: float = 0.12

    degradation_rate: float = 0.003

    temperature_C: float = 25.0
    temperature_amplitude_C: float = 0.0
    pressure_MPa: float = 0.1
    pressure_amplitude_MPa: float = 0.0


@dataclass
class ComplianceStepResult:
    """Result of one compliance audit step."""
    observations: np.ndarray
    rewards: np.ndarray
    dones: np.ndarray
    infos: list[dict[str, Any]] = field(default_factory=list)


class ComplianceEnv:
    """
    Multi-agent compliance environment: 8 agents each own one standard requirement domain.

    State: compliance score vector in [0,1]^8.
    Actions per agent: EXPLORE (gather evidence), EXTRACT (assess/audit), INVEST (remediate).
    Coupling matrix: requirement interdependencies (improving one domain helps coupled domains).
    Environmental stress: regulatory drift, staff turnover, document decay (simulated degradation).
    """

    def __init__(self, num_agents: int = 8, config: ComplianceEnvConfig | None = None):
        self.config = config or ComplianceEnvConfig()
        self.num_agents = num_agents
        assert num_agents == self.config.num_domains
        self.obs_dim = 3

        self._scores = np.array(self.config.compliance_init, dtype=np.float64)
        self._step = 0
        self._obs_uncertainty = np.ones(num_agents, dtype=np.float64)

        coupling_fn = _COUPLING_REGISTRY.get(self.config.preset)
        if coupling_fn is not None:
            self._coupling = coupling_fn() * self.config.coupling_strength
        else:
            rng = np.random.default_rng(42)
            M = rng.uniform(-0.05, 0.05, size=(num_agents, num_agents))
            M = (M + M.T) / 2.0
            np.fill_diagonal(M, 0.0)
            self._coupling = M * self.config.coupling_strength

        self._targets = np.array(self.config.compliance_targets, dtype=np.float64)
        self._minimise = set(self.config.minimise_indices)

    @property
    def resource(self) -> float:
        return float(np.mean(self._scores))

    @property
    def current_step(self) -> int:
        return self._step

    def reset(self, *, seed: int | None = None) -> tuple[np.ndarray, dict]:
        if seed is not None:
            np.random.seed(seed)
        self._scores = np.array(self.config.compliance_init, dtype=np.float64)
        self._step = 0
        self._obs_uncertainty = np.ones(self.num_agents, dtype=np.float64)
        return self._get_obs(), {}

    def _get_obs(self) -> np.ndarray:
        phase = (self._step / max(1, self.config.max_steps)) * 2 * math.pi
        obs = np.zeros((self.num_agents, self.obs_dim), dtype=np.float32)
        for i in range(self.num_agents):
            noise = np.random.normal(0, 0.01 * self._obs_uncertainty[i])
            obs[i, 0] = np.clip(self._scores[i] + noise, 0, 1)
            obs[i, 1] = math.sin(phase)
            obs[i, 2] = 0.0
        return obs

    def step(self, actions: np.ndarray) -> ComplianceStepResult:
        actions = np.asarray(actions, dtype=int).ravel()
        prev_scores = self._scores.copy()
        deltas = np.zeros(self.num_agents, dtype=np.float64)

        for i in range(self.num_agents):
            a = int(actions[i]) % NUM_ACTIONS
            if a == EXPLORE:
                self._obs_uncertainty[i] = max(0.1, self._obs_uncertainty[i] - self.config.explore_noise)
            elif a == EXTRACT:
                deltas[i] -= self.config.extract_rate
            elif a == INVEST:
                deltas[i] += self.config.invest_rate

        coupling_effect = self._coupling @ deltas
        self._scores += deltas + coupling_effect

        phase = (self._step / max(1, self.config.max_steps)) * 2 * math.pi
        stress = self.config.stress_amplitude * math.sin(phase / self.config.stress_period * 2 * math.pi)
        self._scores -= self.config.degradation_rate + abs(stress) * 0.5

        self._scores = np.clip(self._scores, 0.0, 1.0)
        self._step += 1
        done = self._step >= self.config.max_steps

        rewards = np.zeros(self.num_agents, dtype=np.float64)
        for i in range(self.num_agents):
            gap = abs(self._scores[i] - self._targets[i])
            direction = self._scores[i] - prev_scores[i]

            if i in self._minimise:
                target_r = -gap * self.config.target_penalty_scale
                direction = -direction
            else:
                target_r = -gap * self.config.target_penalty_scale

            target_r = max(target_r, -self.config.target_penalty_cap)

            stability_r = self.config.stability_bonus * math.exp(
                -(gap ** 2) / (2 * self.config.stability_sigma ** 2)
            )

            explore_r = 0.0
            if int(actions[i]) % NUM_ACTIONS == EXPLORE:
                explore_r = self.config.explore_info_gain * (1.0 - self._scores[i])

            progress_r = direction * 2.0

            mean_score = float(np.mean(self._scores))
            harmony_r = self.config.harmony_scale * mean_score

            rewards[i] = target_r + stability_r + explore_r + progress_r + harmony_r

        obs = self._get_obs()
        for i in range(self.num_agents):
            obs[i, 2] = np.clip(rewards[i] / 2.0, -1, 1)

        dones = np.full(self.num_agents, done, dtype=bool)
        infos = [
            {
                "domain": self.config.domain_names[i] if i < len(self.config.domain_names) else f"domain_{i}",
                "score": float(self._scores[i]),
                "target": float(self._targets[i]),
                "gap": float(abs(self._scores[i] - self._targets[i])),
                "compliance_pct": float(self._scores[i] * 100),
            }
            for i in range(self.num_agents)
        ]

        return ComplianceStepResult(
            observations=obs,
            rewards=rewards,
            dones=dones,
            infos=infos,
        )

    def get_compliance_report(self) -> dict[str, Any]:
        """Generate a structured compliance audit report."""
        domains = []
        for i in range(self.num_agents):
            score = float(self._scores[i])
            pct = score * 100
            if pct >= 90:
                status = "CONFORMING"
                risk = "Low"
            elif pct >= 70:
                status = "PARTIALLY CONFORMING"
                risk = "Minor nonconformity"
            elif pct >= 50:
                status = "SIGNIFICANT GAP"
                risk = "Major nonconformity"
            else:
                status = "NOT ADDRESSED"
                risk = "Critical — certification blocker"

            domains.append({
                "domain": self.config.domain_names[i] if i < len(self.config.domain_names) else f"domain_{i}",
                "score_pct": round(pct, 1),
                "target_pct": round(float(self._targets[i]) * 100, 1),
                "status": status,
                "audit_risk": risk,
                "gap_pct": round(abs(float(self._targets[i]) - score) * 100, 1),
            })

        mean_score = float(np.mean(self._scores)) * 100
        if mean_score >= 85:
            overall = "AUDIT-READY"
        elif mean_score >= 70:
            overall = "APPROACHING — remediation needed"
        elif mean_score >= 50:
            overall = "SIGNIFICANT WORK REQUIRED"
        else:
            overall = "EARLY STAGE — major build-out needed"

        return {
            "preset": self.config.preset,
            "overall_compliance_pct": round(mean_score, 1),
            "overall_status": overall,
            "domains": domains,
            "step": self._step,
            "max_steps": self.config.max_steps,
        }


def compliance_config_from_dict(d: dict[str, Any]) -> ComplianceEnvConfig:
    """Build ComplianceEnvConfig from a YAML-loaded dict."""
    preset = str(d.get("compliance_preset", d.get("preset", "")))
    names = d.get("domain_names") or (COMPLIANCE_PRESETS.get(preset) if preset else None) or [f"domain_{i}" for i in range(8)]
    n = len(names)
    return ComplianceEnvConfig(
        max_steps=int(d.get("max_steps", 300)),
        num_domains=n,
        domain_names=list(names),
        preset=preset,
        compliance_targets=list(d.get("compliance_targets", d.get("property_targets", [0.90] * n))),
        compliance_init=list(d.get("compliance_init", d.get("property_init", [0.30] * n))),
        compliance_min=list(d.get("compliance_min", d.get("property_min", [0.0] * n))),
        compliance_max=list(d.get("compliance_max", d.get("property_max", [1.0] * n))),
        minimise_indices=list(d.get("minimise_indices", [])),
        invest_rate=float(d.get("invest_rate", 0.05)),
        extract_rate=float(d.get("extract_rate", 0.03)),
        explore_noise=float(d.get("explore_noise", 0.02)),
        coupling_strength=float(d.get("coupling_strength", 1.0)),
        stress_amplitude=float(d.get("stress_amplitude", 0.02)),
        stress_period=float(d.get("stress_period", 50.0)),
        target_penalty_scale=float(d.get("target_penalty_scale", 0.06)),
        target_penalty_cap=float(d.get("target_penalty_cap", 5.0)),
        stability_bonus=float(d.get("stability_bonus", 0.35)),
        stability_sigma=float(d.get("stability_sigma", 0.12)),
        explore_info_gain=float(d.get("explore_info_gain", 0.5)),
        harmony_scale=float(d.get("harmony_scale", 0.12)),
        degradation_rate=float(d.get("degradation_rate", 0.003)),
        temperature_C=float(d.get("temperature_C", 25.0)),
        temperature_amplitude_C=float(d.get("temperature_amplitude_C", 0.0)),
        pressure_MPa=float(d.get("pressure_MPa", 0.1)),
        pressure_amplitude_MPa=float(d.get("pressure_amplitude_MPa", 0.0)),
    )
