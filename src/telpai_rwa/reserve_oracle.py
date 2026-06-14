"""
Reserve Oracle — TELPAI feed epoch bundles for Dragon Seal + TradeProto proof chain.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def build_oracle_epoch(
    asset_id: str,
    *,
    classification: dict[str, Any],
    telpai_feeds: dict[str, Any],
    volumes: dict[str, float] | None = None,
    reg_d_rule: str = "506c",
    chain: str = "sepolia",
    commodity: str = "oil_gas",
    standard: str | None = None,
    quantum_verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build tamper-evident oracle epoch for on-chain attestation.

    telpai_feeds: keys like seismic, boem, eia, seepage, swarm, emag2, etc.
    commodity: "oil_gas" (SPE-PRMS) or "mineral" (NI 43-101).
    quantum_verification: TELPAI-Q verification result dict (embedded in the
        sealed body so the geophysical verification is tamper-evident).
    """
    ts = datetime.now(timezone.utc).isoformat()
    epoch_id = f"{asset_id}-{int(datetime.now(timezone.utc).timestamp())}"
    std = standard or ("NI-43-101-CIM-2014" if commodity == "mineral" else "SPE-PRMS-2018")

    body = {
        "epoch_id": epoch_id,
        "asset_id": asset_id,
        "timestamp_utc": ts,
        "commodity": commodity,
        "standard": std,
        "sec_basis": classification.get("sec_disclosure_basis") or classification.get("disclosure_basis"),
        "reserve_category": classification.get("category"),
        "certainty_pct": classification.get("certainty_pct") or classification.get("confidence_pct"),
        "volumes": volumes or {},
        "quantum_verification": quantum_verification or {},
        "telpai_feeds": telpai_feeds,
        "reg_d_rule": reg_d_rule,
        "compliance_stack": ["TradeProto", "ERC-3643", "DragonSeal"],
        "chain_target": chain,
    }

    digest = sha256_digest(body)
    return {
        **body,
        "sha256": digest,
        "dragon_seal": {
            "verify_url": f"https://dragonseal.io/verify/{digest}",
            "status": "pending_anchor",
            "method": "DragonSeal.attestDocument",
        },
        "erc3643": {
            "compliance_module": "ModularCompliance",
            "transfer_restrictions": "accredited_investors_reg_d",
        },
        "attestation_note": "QRE report hash must be co-sealed before primary Reg D 506(c) issuance.",
    }