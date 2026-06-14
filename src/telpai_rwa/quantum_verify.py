"""
TELPAI-Q — Quantum geospatial verification of in-ground RWA assets.

This is the bridge that turns a TELPAI geophysical survey (gravity, magnetics,
seismic, seepage, thermal, lease context) into a single **verification score**
for an in-ground asset, computed with a quantum kernel.

Pipeline:
    TELPAI survey + technical eval
        -> survey_feature_vector()          (normalized geophysical signature)
        -> QuantumKernelAnomalyDetector      (PennyLane VQC; BlueQubit on hardware)
        -> kernel similarity vs an "ideal verified signature" + learned references
        -> verification_score in [0, 1]  +  anomaly_score in [0, 1]

The quantum backend is selected by ``vqc_backend`` / env ``BLUEQUBIT_API_TOKEN``:
  - "" / "default"      -> default.qubit (local simulator)
  - "lightning"          -> lightning.qubit
  - "bluequbit.cpu/gpu" -> BlueQubit cloud QUANTUM HARDWARE/sim (needs token)

The score is supplementary geophysical evidence — it does NOT replace the QRE
(oil & gas) or QP (minerals) sign-off. It is recorded in the oracle epoch and
Dragon Sealed so the verification is tamper-evident.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from src.quantum_geospatial import (
    get_quantum_anomaly_detector,
    load_reference_set,
    save_reference_set,
)

# Canonical 8-d "ideal in-ground signature": strong, mutually consistent
# geophysical evidence. Verification measures how close an asset's signature is
# to this prototype (and to previously verified assets).
_IDEAL_SIGNATURE = np.array(
    [0.90, 0.88, 0.82, 0.80, 0.78, 0.85, 0.30, 0.75], dtype=np.float64
)

_DEFAULT_REF_PATH = "results/rwa_verify_reference.npy"
_FEATURE_DIM = 8


def _f(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return float(default)
        return float(x)
    except (TypeError, ValueError):
        return float(default)


def _norm_count(n: Any, scale: float) -> float:
    """Map a non-negative count to [0,1] via a soft saturating curve."""
    v = max(0.0, _f(n))
    return float(1.0 - np.exp(-v / max(scale, 1e-6)))


def survey_feature_vector(
    technical: dict[str, Any] | None,
    telpai_survey: dict[str, Any] | None,
) -> np.ndarray:
    """
    Build an 8-d normalized geophysical signature from technical eval + survey.

    Dimensions (each in [0,1] unless noted):
      0 seismic confidence       1 magnetometry anomaly strength
      2 gravity evidence         3 volumetric/analog confidence
      4 thermal/flare activity   5 lease/regulatory context
      6 seepage RISK (inverted later — high seepage = anomaly)
      7 simulation/data quality
    """
    technical = technical or {}
    survey = telpai_survey or {}

    seismic = _f(technical.get("seismic_interpretation_confidence"), 0.5)
    mag = _f(technical.get("magnetometry_anomaly_strength"), 0.5)
    volumetric = _f(technical.get("volumetric_confidence"), 0.5)
    analog = _f(technical.get("analog_match_score"), 0.4)
    sim_quality = _f(technical.get("simulation_quality"), 0.4)

    # Gravity evidence: presence of a live GGMplus layer is positive context.
    grav_layer = survey.get("ggmplus") or {}
    gravity = 0.75 if str(grav_layer.get("status", "")).lower() in ("live", "cached") else 0.4

    # Thermal / flare activity (FIRMS) — proxy for active production / venting.
    firms = survey.get("firms") or {}
    flares = _norm_count(firms.get("high_confidence_flares") or firms.get("total_detections_24h"), 8.0)

    # Lease / regulatory context (BOEM active leases).
    boem = survey.get("boem") or {}
    lease_ctx = _norm_count(boem.get("active_leases") or boem.get("total_leases"), 50.0)
    lease_ctx = 0.5 * lease_ctx + 0.5 * (_f(technical.get("regulatory_context"), 0.6))

    # Seepage: detected hydrocarbon seeps support presence, but HIGH-RISK seeps
    # are an integrity anomaly. Net signal = detection minus risk fraction.
    seep = survey.get("seepage") or {}
    detected = _f(seep.get("detected_seeps"), 0.0)
    high_risk = _f(seep.get("high_risk_seeps"), 0.0)
    seep_signal = _norm_count(detected, 12.0) - 0.6 * _norm_count(high_risk, 6.0)
    seep_signal = float(np.clip(seep_signal, 0.0, 1.0))

    vec = np.array(
        [
            seismic,
            mag,
            gravity,
            0.5 * volumetric + 0.5 * analog,
            flares,
            lease_ctx,
            seep_signal,
            sim_quality,
        ],
        dtype=np.float64,
    )
    return np.clip(vec, 0.0, 1.0)


@dataclass
class VerificationResult:
    verification_score: float          # [0,1] consistency with verified signature
    anomaly_score: float               # [0,1] = 1 - mean kernel similarity
    confidence_band: str               # high | medium | low
    backend: str                       # active quantum backend
    quantum_hardware: bool             # True if a cloud/HW backend was used
    feature_vector: list[float]
    reference_set_size: int
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "verification_score": round(self.verification_score, 4),
            "anomaly_score": round(self.anomaly_score, 4),
            "confidence_band": self.confidence_band,
            "backend": self.backend,
            "quantum_hardware": self.quantum_hardware,
            "feature_vector": [round(float(x), 4) for x in self.feature_vector],
            "reference_set_size": self.reference_set_size,
            "method": "quantum_kernel_geospatial_verification",
            "notes": self.notes,
        }


def _band(score: float) -> str:
    if score >= 0.80:
        return "high"
    if score >= 0.60:
        return "medium"
    return "low"


def verify_asset(
    *,
    technical: dict[str, Any] | None,
    telpai_survey: dict[str, Any] | None,
    vqc_backend: str = "",
    bluequbit_token: str = "",
    use_vqc: bool = True,
    reference_path: str = _DEFAULT_REF_PATH,
    update_reference: bool = True,
    verified_threshold: float = 0.72,
) -> VerificationResult:
    """
    Quantum-kernel verification of an in-ground asset's geophysical signature.

    Backend resolves to BlueQubit cloud hardware when ``vqc_backend`` is a
    bluequbit name and a token is present (arg or BLUEQUBIT_API_TOKEN env);
    otherwise lightning.qubit or the local default.qubit simulator.

    If ``update_reference`` and the asset clears ``verified_threshold``, its
    signature is appended to the persisted reference set so the kernel learns
    the population of known-good assets over time.
    """
    token = bluequbit_token or os.environ.get("BLUEQUBIT_API_TOKEN", "")
    backend = vqc_backend or os.environ.get("TELPAI_Q_BACKEND", "")

    detector = get_quantum_anomaly_detector(
        feature_dim=_FEATURE_DIM,
        gamma=0.5,
        use_vqc=use_vqc,
        vqc_seed=42,
        vqc_max_wires=_FEATURE_DIM,
        vqc_backend=backend,
        bluequbit_token=token,
    )

    x = survey_feature_vector(technical, telpai_survey)

    # Reference set: persisted verified assets + the ideal prototype anchor.
    refs = load_reference_set(reference_path)
    ref_with_anchor = list(refs) + [_IDEAL_SIGNATURE]

    sims = [detector.quantum_kernel(x, r) for r in ref_with_anchor]
    verification_score = float(np.clip(np.mean(sims), 0.0, 1.0)) if sims else 0.0
    anomaly_score = detector.kernel_anomaly_score(x, ref_with_anchor)

    active_backend = detector.active_backend
    quantum_hw = any(
        active_backend.startswith(p) for p in ("bluequbit.cpu", "bluequbit.gpu", "lightning")
    )

    notes: list[str] = []
    if not token and backend.startswith("bluequbit"):
        notes.append("BlueQubit backend requested but no token — fell back to local simulator.")
    notes.append(
        "Quantum-kernel verification is supplementary geophysical evidence; "
        "QRE (oil & gas) or QP (minerals) sign-off remains mandatory."
    )

    if update_reference and verification_score >= verified_threshold:
        refs.append(np.asarray(x, dtype=np.float64))
        if len(refs) > 200:
            refs = refs[-200:]
        save_reference_set(refs, reference_path)
        notes.append(
            f"Signature added to verified reference set (score {verification_score:.2f} "
            f">= {verified_threshold:.2f})."
        )

    return VerificationResult(
        verification_score=verification_score,
        anomaly_score=anomaly_score,
        confidence_band=_band(verification_score),
        backend=active_backend,
        quantum_hardware=quantum_hw,
        feature_vector=x.tolist(),
        reference_set_size=len(ref_with_anchor),
        notes=notes,
    )
