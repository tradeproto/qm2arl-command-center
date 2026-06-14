"""Simple JSON persistence for reserve assets (pilot — migrate to TradeProto Postgres)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_STORE = Path(__file__).resolve().parents[2] / "data" / "rwa_assets.json"


def _load() -> dict[str, Any]:
    if not _STORE.exists():
        return {"assets": {}}
    with open(_STORE, encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict[str, Any]) -> None:
    _STORE.parent.mkdir(parents=True, exist_ok=True)
    with open(_STORE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def list_assets() -> list[dict[str, Any]]:
    return list(_load().get("assets", {}).values())


def get_asset(asset_id: str) -> dict[str, Any] | None:
    return _load().get("assets", {}).get(asset_id)


def upsert_asset(record: dict[str, Any]) -> dict[str, Any]:
    data = _load()
    assets = data.setdefault("assets", {})
    aid = record["asset_id"]
    assets[aid] = record
    _save(data)
    return record