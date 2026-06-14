"""
Quantum Health Solutions — Division 14 (Clinical Trials).

Regulatory-readiness & protocol-documentation decision support for the SkinProto
Protocol Matrix (skin damage & wound care). Built on ICH-GCP / FDA 21 CFR /
ISO 14155, mirroring the Division 12/13 audit pattern.

NOT medical advice · NOT a medical device · NOT a therapeutic claim. Does not
replace IRB/IEC, FDA/EMA, sponsors, qualified investigators, or medical
professionals. IRB approval + regulatory authorization required before any
human enrollment.

Quickstart:
    from src.quantum_health import evaluate_protocol
    out = evaluate_protocol({"indication": "diabetic foot ulcer", ...})
    print(out["clinical_audit"]["audit_gate_passed"], out["matrix"]["protocol_completeness"])
"""
from .gcp_framework import GCP_FRAMEWORK, AGENT_ROLES, DISCLAIMER, gcp_status
from .skinproto import (
    SkinProtoMatrix,
    build_skinproto_matrix,
    division14_agent_scores,
)
from .division14 import build_division14_audit, load_training_summary
from .evaluate import evaluate_protocol

__all__ = [
    "GCP_FRAMEWORK",
    "AGENT_ROLES",
    "DISCLAIMER",
    "gcp_status",
    "SkinProtoMatrix",
    "build_skinproto_matrix",
    "division14_agent_scores",
    "build_division14_audit",
    "load_training_summary",
    "evaluate_protocol",
]
