"""TELPAI × RWA — SPE PRMS reserves, SEC Reg D 506 gates, Dragon Seal oracle epochs."""

from .prms_engine import (
    PRMS_FRAMEWORK,
    ReserveCategory,
    classify_reserves,
    monte_carlo_volumes,
    tokenizability_matrix,
)
from .reg_d_506 import REG_D_506_CHECKLIST, validate_reg_d_offering
from .reserve_oracle import build_oracle_epoch
from .qre_package import build_qre_data_package
from .minerals_engine import (
    NI43101_FRAMEWORK,
    MineralCategory,
    MineralCommercialEvaluation,
    MineralTechnicalEvaluation,
    classify_mineral_resource,
    contained_metal_monte_carlo,
    mineral_tokenizability_matrix,
    qp_engagement_checklist,
)
from .quantum_verify import verify_asset, survey_feature_vector
from .dragon_seal import seal_epoch, build_dragon_bundle
from .onboarding import onboard_asset
from .division12 import build_division12_audit, load_training_summary
from .division13 import build_division13_audit

__all__ = [
    "PRMS_FRAMEWORK",
    "ReserveCategory",
    "classify_reserves",
    "monte_carlo_volumes",
    "tokenizability_matrix",
    "REG_D_506_CHECKLIST",
    "validate_reg_d_offering",
    "build_oracle_epoch",
    "build_qre_data_package",
    # NI 43-101 minerals
    "NI43101_FRAMEWORK",
    "MineralCategory",
    "MineralTechnicalEvaluation",
    "MineralCommercialEvaluation",
    "classify_mineral_resource",
    "contained_metal_monte_carlo",
    "mineral_tokenizability_matrix",
    "qp_engagement_checklist",
    # TELPAI-Q verification + sealing + orchestration
    "verify_asset",
    "survey_feature_vector",
    "seal_epoch",
    "build_dragon_bundle",
    "onboard_asset",
    # Division 12 SPE-PRMS AI audit
    "build_division12_audit",
    "load_training_summary",
    # Division 13 NI 43-101 QP AI audit
    "build_division13_audit",
]