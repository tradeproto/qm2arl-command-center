"""
On-chain anchoring for ODL resonance epochs via DragonSeal.attestDocument.

Requires env (see .env.example):
  DRAGON_SEAL_CONTRACT, DRAGON_SEAL_TOKEN_ID, DRAGON_SEAL_WALLET_PRIVATE_KEY
  DRAGON_SEAL_CHAIN (sepolia | base | base-sepolia)
  DRAGON_SEAL_RPC_URL (or chain default)

Anchors are recorded in data/odl_anchors.jsonl (append-only, keyed by epoch sha256).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ANCHORS_PATH = _REPO_ROOT / "data" / "odl_anchors.jsonl"

# Minimal ABI — attestDocument only
_DRAGON_SEAL_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"internalType": "bytes32", "name": "documentHash", "type": "bytes32"},
            {"internalType": "string", "name": "documentType", "type": "string"},
        ],
        "name": "attestDocument",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "name": "attestationCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

_CHAIN_DEFAULTS: dict[str, dict[str, str]] = {
    "sepolia": {
        "rpc_env": "DRAGON_SEAL_RPC_URL",
        "default_rpc": "https://rpc.sepolia.org",
        "explorer": "https://sepolia.etherscan.io/tx/",
    },
    "base": {
        "rpc_env": "BASE_RPC_URL",
        "default_rpc": "https://mainnet.base.org",
        "explorer": "https://basescan.org/tx/",
    },
    "base-sepolia": {
        "rpc_env": "BASE_SEPOLIA_RPC_URL",
        "default_rpc": "https://sepolia.base.org",
        "explorer": "https://sepolia.basescan.org/tx/",
    },
}


def anchor_config() -> dict[str, Any]:
    """Return resolved anchor configuration and readiness flags."""
    chain = (os.environ.get("DRAGON_SEAL_CHAIN") or "sepolia").strip().lower()
    chain_meta = _CHAIN_DEFAULTS.get(chain, _CHAIN_DEFAULTS["sepolia"])
    rpc = (
        os.environ.get(chain_meta["rpc_env"])
        or os.environ.get("DRAGON_SEAL_RPC_URL")
        or chain_meta["default_rpc"]
    ).strip()
    contract = (os.environ.get("DRAGON_SEAL_CONTRACT") or "").strip()
    token_id_raw = (os.environ.get("DRAGON_SEAL_TOKEN_ID") or "").strip()
    pk = (os.environ.get("DRAGON_SEAL_WALLET_PRIVATE_KEY") or "").strip()

    missing = []
    if not contract:
        missing.append("DRAGON_SEAL_CONTRACT")
    if not token_id_raw:
        missing.append("DRAGON_SEAL_TOKEN_ID")
    if not pk:
        missing.append("DRAGON_SEAL_WALLET_PRIVATE_KEY")

    return {
        "chain": chain,
        "rpc_url": rpc,
        "contract": contract,
        "token_id": int(token_id_raw) if token_id_raw.isdigit() else None,
        "explorer_base": chain_meta["explorer"],
        "ready": len(missing) == 0,
        "missing_env": missing,
    }


def list_anchors() -> list[dict[str, Any]]:
    if not _ANCHORS_PATH.is_file():
        return []
    out = []
    for line in _ANCHORS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def anchor_for_hash(sha256: str) -> dict[str, Any] | None:
    for rec in reversed(list_anchors()):
        if rec.get("sha256") == sha256:
            return rec
    return None


def _append_anchor(record: dict[str, Any]) -> dict[str, Any]:
    _ANCHORS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _ANCHORS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")
    return record


def anchor_epoch(
    epoch: dict[str, Any],
    *,
    document_type: str = "ODL_EPOCH",
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Anchor an ODL epoch hash on-chain via DragonSeal.attestDocument.

    Returns status: ANCHORED | DRY_RUN | SKIPPED | ERROR
    """
    digest = epoch.get("sha256")
    epoch_id = epoch.get("epoch_id", "unknown")
    if not digest or len(digest) != 64:
        return {"status": "ERROR", "error": "epoch missing valid sha256", "epoch_id": epoch_id}

    existing = anchor_for_hash(digest)
    if existing and existing.get("status") == "ANCHORED":
        return {**existing, "note": "already anchored"}

    cfg = anchor_config()
    base = {
        "epoch_id": epoch_id,
        "sha256": digest,
        "document_type": document_type,
        "chain": cfg["chain"],
        "contract": cfg["contract"],
        "token_id": cfg["token_id"],
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }

    if not cfg["ready"]:
        return {
            **base,
            "status": "SKIPPED",
            "reason": f"Missing env: {', '.join(cfg['missing_env'])}",
            "dragon_seal_anchored": False,
        }

    if dry_run:
        return {
            **base,
            "status": "DRY_RUN",
            "dragon_seal_anchored": False,
            "note": "Config valid; set dry_run=False to broadcast transaction.",
        }

    try:
        from web3 import Web3
        from eth_account import Account
    except ImportError:
        return {
            **base,
            "status": "SKIPPED",
            "reason": "web3 not installed (pip install web3)",
            "dragon_seal_anchored": False,
        }

    try:
        w3 = Web3(Web3.HTTPProvider(cfg["rpc_url"]))
        if not w3.is_connected():
            return {**base, "status": "ERROR", "error": f"RPC not reachable: {cfg['rpc_url']}"}

        acct = Account.from_key(os.environ["DRAGON_SEAL_WALLET_PRIVATE_KEY"])
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(cfg["contract"]),
            abi=_DRAGON_SEAL_ABI,
        )
        doc_hash = bytes.fromhex(digest)
        token_id = int(cfg["token_id"])

        nonce = w3.eth.get_transaction_count(acct.address)
        tx = contract.functions.attestDocument(token_id, doc_hash, document_type).build_transaction(
            {
                "from": acct.address,
                "nonce": nonce,
                "chainId": w3.eth.chain_id,
            }
        )
        try:
            tx["gas"] = w3.eth.estimate_gas(tx)
        except Exception:
            tx["gas"] = 200_000

        signed = acct.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        record = {
            **base,
            "status": "ANCHORED" if receipt.status == 1 else "ERROR",
            "tx_hash": tx_hash.hex(),
            "explorer_url": f"{cfg['explorer_base']}{tx_hash.hex()}",
            "block_number": receipt.blockNumber,
            "dragon_seal_anchored": receipt.status == 1,
        }
        if receipt.status != 1:
            record["error"] = "transaction reverted"
            return record

        return _append_anchor(record)
    except Exception as e:
        return {**base, "status": "ERROR", "error": f"{type(e).__name__}: {e}", "dragon_seal_anchored": False}