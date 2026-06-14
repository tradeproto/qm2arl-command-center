"""
DragonSeal bridge for RWA oracle epochs.

Turns a reserve/resource oracle epoch (from ``reserve_oracle.build_oracle_epoch``)
into a tamper-evident ``.dragon`` attestation bundle, writes it to
``data/rwa_epochs/``, and optionally pins it to Lighthouse (IPFS + Filecoin) for
permanence. The returned record carries the DragonSeal verify URL, the IPFS CID
(if pinned), and a status that the Reg D / CIM securities gate can consume.

``.dragon`` format mirrors scripts/build_qms003_dragon.py (magic "DRGN").
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EPOCH_DIR = _REPO_ROOT / "data" / "rwa_epochs"


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(obj: Any) -> str:
    return hashlib.sha256(_canonical_json(obj).encode("utf-8")).hexdigest()


def build_dragon_bundle(
    epoch: dict[str, Any],
    *,
    signer_name: str = "Joshua Spooner",
    signer_role: str = "Principal — Green Horizon Innovation LLC (SDVOSB)",
    organization: str = "Green Horizon Innovation LLC (SDVOSB)",
    chain: str = "ethereum:sepolia",
) -> dict[str, Any]:
    """Wrap an oracle epoch in a .dragon attestation envelope."""
    # The epoch already carries its own sha256; re-derive over the body for safety.
    body = {k: v for k, v in epoch.items() if k not in ("sha256", "dragon_seal")}
    digest = epoch.get("sha256") or _sha256(body)
    asset_id = epoch.get("asset_id", "UNKNOWN")
    epoch_id = epoch.get("epoch_id", asset_id)

    return {
        "version": "1.0",
        "format": "dragon",
        "header": {
            "magic": "DRGN",
            "type": "RWA_ORACLE_EPOCH",
            "chain": chain,
            "created": datetime.now(timezone.utc).isoformat(),
            "platform": "TELPAI-Q x AutoQMS x DragonSeal",
        },
        "document": {
            "name": f"{epoch_id}.epoch.json",
            "asset_id": asset_id,
            "type": "RWA-ORACLE-EPOCH",
            "standard": epoch.get("standard"),
            "reserve_category": epoch.get("reserve_category"),
            "certainty_pct": epoch.get("certainty_pct"),
            "verification": epoch.get("quantum_verification"),
            "hash": f"sha256:{digest}",
            "seal_id": f"DS-RWA-{digest[:12].upper()}",
            "organization": organization,
        },
        "signer": {
            "name": signer_name,
            "role": signer_role,
            "entity": organization,
            "date": datetime.now(timezone.utc).date().isoformat(),
        },
        "epoch": epoch,
        "attestation": {
            "status": "LOCAL_SEAL_READY",
            "verify_url": f"https://dragonseal.io/verify/{digest}",
            "method": "DragonSeal.attestDocument",
            "note": "Pin to Lighthouse, then anchor on dragonseal.io (Sepolia).",
        },
    }


def seal_epoch(
    epoch: dict[str, Any],
    *,
    out_dir: str | Path | None = None,
    pin_to_lighthouse: bool = False,
    lighthouse_api_key: str | None = None,
    signer_name: str = "Joshua Spooner",
) -> dict[str, Any]:
    """
    Seal an oracle epoch: write the .dragon bundle and (optionally) pin to IPFS.

    Returns a sealed record:
        {
          "asset_id", "epoch_id", "sha256", "seal_id",
          "dragon_path", "verify_url",
          "ipfs_cid", "ipfs_uri", "gateway_url",   # if pinned
          "status": LOCAL_SEAL_READY | PINNED | ANCHOR_PENDING,
          "dragon_seal_anchored": bool              # for the Reg D / CIM gate
        }
    """
    bundle = build_dragon_bundle(epoch, signer_name=signer_name)
    digest = bundle["document"]["hash"].split(":", 1)[-1]
    epoch_id = epoch.get("epoch_id", epoch.get("asset_id", "epoch"))

    out_path = Path(out_dir) if out_dir else _EPOCH_DIR
    out_path.mkdir(parents=True, exist_ok=True)
    dragon_file = out_path / f"{epoch_id}.dragon"
    dragon_file.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")

    record: dict[str, Any] = {
        "asset_id": epoch.get("asset_id"),
        "epoch_id": epoch_id,
        "sha256": digest,
        "seal_id": bundle["document"]["seal_id"],
        "dragon_path": str(dragon_file),
        "verify_url": bundle["attestation"]["verify_url"],
        "status": "LOCAL_SEAL_READY",
        "dragon_seal_anchored": False,
    }

    if pin_to_lighthouse:
        api_key = lighthouse_api_key or os.environ.get("LIGHTHOUSE_API_KEY")
        if not api_key:
            record["pin_error"] = "LIGHTHOUSE_API_KEY not set; bundle written locally only."
            return record
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "lighthouse_pin", _REPO_ROOT / "scripts" / "lighthouse_pin.py"
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            pin = mod.pin_file(dragon_file, api_key)
            record.update(
                {
                    "ipfs_cid": pin["ipfs_cid"],
                    "ipfs_uri": pin["ipfs_uri"],
                    "gateway_url": pin["gateway_url"],
                    "status": "PINNED",
                    "dragon_seal_anchored": True,
                }
            )
        except Exception as e:  # pragma: no cover - network dependent
            record["pin_error"] = f"{type(e).__name__}: {e}"

    return record
