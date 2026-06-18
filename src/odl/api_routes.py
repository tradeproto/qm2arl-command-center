"""
ODL API routes — mount on api_server via include_router.

    GET  /odl/health
    GET  /odl/resonance          — head epoch resonance (or empty)
    GET  /odl/ledger             — epoch list (newest first)
    GET  /odl/ledger/verify      — chain integrity
    GET  /odl/framework          — build completion rollup
    POST /odl/step               — run resonance cycle
    POST /odl/seal               — Dragon Seal head epoch
    POST /odl/anchor             — on-chain attest head epoch
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .anchor import anchor_config, anchor_epoch, anchor_for_hash, list_anchors
from .brain import brain_state, build_brain_graph, coverage_honesty
from .dimension_config import apply_overrides, coupling_matrix, list_dimensions
from .engine import SystemResonanceEngine
from .feeds import SignalBuffer, harmony_from_live, poll_once, synthesize_history
from .ledger import OmniDimensionalLedger
from .nodes import load_manifest, summarize

router = APIRouter(prefix="/odl", tags=["ODL"])


class StepRequest(BaseModel):
    seal: bool = False
    anchor: bool = False
    anchor_dry_run: bool = False
    pin_to_lighthouse: bool = False
    backend: str = ""
    tier: str = Field(default="GAI", pattern="^(GAI|SAI)$")
    live_lat: float | None = None
    live_lon: float | None = None
    sample_rate_hz: float = 1.0


class AnchorRequest(BaseModel):
    dry_run: bool = False
    document_type: str = "ODL_EPOCH"


class DimensionPatch(BaseModel):
    label: str | None = None
    weight: float | None = None
    target: float | None = None
    floor: float | None = None
    trinity_pillar: str | None = None
    proxy: str | None = None


class DimensionsUpdateRequest(BaseModel):
    overrides: dict[str, DimensionPatch]


def _enrich_epoch(epoch: dict[str, Any]) -> dict[str, Any]:
    sha = epoch.get("sha256")
    anchor = anchor_for_hash(sha) if sha else None
    return {**epoch, "anchor": anchor}


@router.get("/health")
def odl_health() -> dict[str, Any]:
    ledger = OmniDimensionalLedger()
    chain = ledger.verify_chain()
    cfg = anchor_config()
    return {
        "status": "ok",
        "module": "Omni-Dimensional Ledger",
        "ledger_height": ledger.height(),
        "chain_valid": chain.get("valid", False),
        "anchor_ready": cfg["ready"],
        "anchor_chain": cfg["chain"],
        "anchor_missing_env": cfg.get("missing_env", []),
    }


@router.get("/resonance")
def odl_resonance() -> dict[str, Any]:
    head = OmniDimensionalLedger().head()
    if not head:
        return {"status": "empty", "message": "No epochs recorded yet. POST /odl/step to run a cycle."}
    return {
        "status": "ok",
        "epoch": _enrich_epoch(head),
        "resonance": head.get("resonance"),
        "governance": head.get("governance"),
    }


@router.get("/ledger")
def odl_ledger(limit: int = 50) -> dict[str, Any]:
    ledger = OmniDimensionalLedger()
    entries = list(reversed(ledger.entries()))[: max(1, min(limit, 500))]
    return {
        "height": ledger.height(),
        "epochs": [_enrich_epoch(e) for e in entries],
        "chain": ledger.verify_chain(),
    }


@router.get("/ledger/verify")
def odl_verify_chain() -> dict[str, Any]:
    return OmniDimensionalLedger().verify_chain()


@router.get("/framework")
def odl_framework() -> dict[str, Any]:
    return summarize(load_manifest())


@router.get("/anchors")
def odl_anchors(limit: int = 50) -> dict[str, Any]:
    anchors = list(reversed(list_anchors()))[: max(1, min(limit, 500))]
    return {"count": len(anchors), "anchors": anchors, "config": anchor_config()}


@router.post("/step")
def odl_step(req: StepRequest) -> dict[str, Any]:
    eng = SystemResonanceEngine(governor_tier=req.tier, vqc_backend=req.backend)
    loc = (
        (req.live_lat, req.live_lon)
        if req.live_lat is not None and req.live_lon is not None
        else None
    )
    out = eng.step(seal=req.seal, live_location=loc, sample_rate_hz=req.sample_rate_hz)
    if req.seal and req.pin_to_lighthouse and out.get("dragon_seal"):
        out["dragon_seal"] = eng.ledger.seal_head(pin_to_lighthouse=True)

    anchor_result = None
    if req.anchor:
        anchor_result = anchor_epoch(out["epoch"], dry_run=req.anchor_dry_run)
        out["anchor"] = anchor_result

    out["epoch"] = _enrich_epoch(out["epoch"])
    return out


@router.post("/seal")
def odl_seal(pin: bool = False) -> dict[str, Any]:
    ledger = OmniDimensionalLedger()
    if not ledger.head():
        raise HTTPException(status_code=404, detail="Ledger is empty")
    sealed = ledger.seal_head(pin_to_lighthouse=pin)
    return {"status": "ok", "dragon_seal": sealed, "epoch": _enrich_epoch(ledger.head())}


@router.post("/anchor")
def odl_anchor(req: AnchorRequest) -> dict[str, Any]:
    ledger = OmniDimensionalLedger()
    head = ledger.head()
    if not head:
        raise HTTPException(status_code=404, detail="Ledger is empty")
    result = anchor_epoch(head, document_type=req.document_type, dry_run=req.dry_run)
    return {"status": "ok", "anchor": result, "epoch": _enrich_epoch(head)}


class PollRequest(BaseModel):
    lat: float = 30.6
    lon: float = -95.1
    radius_km: float = 250.0
    synthetic: int = 0  # >0 seeds N labeled-SYNTHETIC samples (offline demo)


@router.post("/feeds/poll")
def odl_feeds_poll(req: PollRequest) -> dict[str, Any]:
    """Poll live TELPAI feeds at lat/lon, append to the rolling buffer."""
    buf = SignalBuffer()
    seeded = 0
    if req.synthetic > 0:
        seeded = synthesize_history(buf, n=int(req.synthetic))
    result = poll_once(req.lat, req.lon, buffer=buf, radius_km=req.radius_km)
    result["synthetic_seeded"] = seeded
    return result


@router.get("/harmony")
def odl_harmony(min_samples: int = 8, sample_rate_hz: float = 1.0) -> dict[str, Any]:
    """Compute the harmonic Harmony Score from the accumulated signal buffer."""
    return harmony_from_live(
        buffer=SignalBuffer(), poll=False,
        min_samples=min_samples, sample_rate_hz=sample_rate_hz,
    )


@router.get("/similar")
def odl_similar(top_k: int = 5) -> dict[str, Any]:
    """Nearest historical epochs to the head, by HDC state-signature similarity."""
    ledger = OmniDimensionalLedger()
    head = ledger.head()
    if not head:
        return {"status": "empty", "matches": []}
    dims = (head.get("resonance") or {}).get("dimensions") or {}
    if not dims:
        return {"status": "no_dimensions", "matches": []}
    eng = SystemResonanceEngine()
    matches = eng.search_history(dims, top_k=int(top_k) + 1)
    head_id = head.get("epoch_id")
    matches = [m for m in matches if m.get("epoch_id") != head_id][: int(top_k)]
    return {"status": "ok", "head_epoch": head_id, "matches": matches}


@router.get("/dimensions")
def odl_dimensions() -> dict[str, Any]:
    ids, matrix = coupling_matrix()
    return {"dimensions": list_dimensions(), "coupling": {"ids": ids, "matrix": matrix}}


@router.put("/dimensions")
def odl_dimensions_update(req: DimensionsUpdateRequest) -> dict[str, Any]:
    patches = {
        dim_id: patch.model_dump(exclude_none=True)
        for dim_id, patch in req.overrides.items()
    }
    return apply_overrides(patches)


@router.get("/brain")
def odl_brain() -> dict[str, Any]:
    head = OmniDimensionalLedger().head()
    resonance = head.get("resonance") if head else None
    return brain_state(resonance)


@router.get("/brain/graph")
def odl_brain_graph(
    project: str | None = None,
    limit: int = 120,
    q: str | None = None,
) -> dict[str, Any]:
    return build_brain_graph(project=project, limit=limit, search=q)


@router.get("/brain/coverage")
def odl_brain_coverage() -> dict[str, Any]:
    head = OmniDimensionalLedger().head()
    return coverage_honesty(head.get("resonance") if head else None)