"""
Omni-Dimensional Ledger — append-only, hash-linked resonance record.

Each entry is a **resonance epoch**: a value-dimension state + its System
Resonance, chained to the previous entry by hash (a lightweight tamper-evident
chain, the same proof-chain discipline as src/telpai_rwa/reserve_oracle and
dragon_seal). Any epoch can be Dragon Sealed and pinned to Lighthouse for
on-chain attestation.

This is the record that makes three-/N-dimensional value **verifiable** — the
ledger the whitepaper calls "the infrastructure for agreement."

Persistence: data/odl_ledger.jsonl (one JSON epoch per line).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_LEDGER = _REPO_ROOT / "data" / "odl_ledger.jsonl"

GENESIS_HASH = "0" * 64


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(obj: Any) -> str:
    return hashlib.sha256(_canonical(obj).encode("utf-8")).hexdigest()


class OmniDimensionalLedger:
    """Append-only hash-linked ledger of resonance epochs."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else _DEFAULT_LEDGER

    # ── read ────────────────────────────────────────────────────────────
    def entries(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def head(self) -> dict[str, Any] | None:
        ents = self.entries()
        return ents[-1] if ents else None

    def head_hash(self) -> str:
        h = self.head()
        return h["sha256"] if h else GENESIS_HASH

    def height(self) -> int:
        return len(self.entries())

    # ── write ───────────────────────────────────────────────────────────
    def append(
        self,
        resonance: dict[str, Any],
        *,
        subject: str = "system",
        sources: dict[str, Any] | None = None,
        governance: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append a resonance epoch, chained to the current head."""
        prev_hash = self.head_hash()
        height = self.height()
        body = {
            "index": height,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "subject": subject,
            "prev_hash": prev_hash,
            "resonance": resonance,
            "sources": sources or {},
            "governance": governance or {},
            "standard": "Omni-Dimensional-Ledger/0.1",
        }
        digest = _sha256(body)
        epoch = {**body, "sha256": digest,
                 "epoch_id": f"ODL-{height:06d}-{digest[:12]}",
                 "verify_url": f"https://dragonseal.io/verify/{digest}"}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(epoch, default=str) + "\n")
        return epoch

    # ── integrity ───────────────────────────────────────────────────────
    def verify_chain(self) -> dict[str, Any]:
        """Recompute hashes and check the prev_hash links."""
        ents = self.entries()
        prev = GENESIS_HASH
        for i, e in enumerate(ents):
            body = {k: e[k] for k in (
                "index", "timestamp_utc", "subject", "prev_hash",
                "resonance", "sources", "governance", "standard",
            ) if k in e}
            recomputed = _sha256(body)
            if e.get("prev_hash") != prev:
                return {"valid": False, "broken_at": i, "reason": "prev_hash mismatch"}
            if e.get("sha256") != recomputed:
                return {"valid": False, "broken_at": i, "reason": "hash mismatch"}
            prev = e["sha256"]
        return {"valid": True, "height": len(ents), "head": prev}

    def seal_head(self, *, pin_to_lighthouse: bool = False) -> dict[str, Any]:
        """Dragon Seal the head epoch (reuses telpai_rwa.dragon_seal.seal_epoch)."""
        h = self.head()
        if not h:
            return {"error": "empty ledger"}
        from src.telpai_rwa.dragon_seal import seal_epoch

        # Present the ODL epoch in the shape seal_epoch expects.
        epoch_for_seal = {
            "epoch_id": h["epoch_id"],
            "asset_id": h.get("subject", "system"),
            "sha256": h["sha256"],
            "standard": h.get("standard"),
            "reserve_category": h["resonance"].get("verdict"),
            "certainty_pct": round(100.0 * h["resonance"].get("system_resonance", 0.0), 1),
            "quantum_verification": h["resonance"],
        }
        return seal_epoch(epoch_for_seal, pin_to_lighthouse=pin_to_lighthouse)
