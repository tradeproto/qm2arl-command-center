"""Phase 1 ODL — ledger integrity, HALT scenario, anchor config."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from src.odl.anchor import anchor_config, anchor_epoch
from src.odl.dimensions import Dimension
from src.odl.governance import ValueGovernor
from src.odl.ledger import OmniDimensionalLedger, GENESIS_HASH
from src.odl.resonance import compute_resonance


def test_verify_chain_valid(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    ledger = OmniDimensionalLedger(path)
    state = compute_resonance({Dimension.PROSPERITY: 0.8, Dimension.PLANET: 0.75})
    ledger.append(state.as_dict())
    ledger.append(state.as_dict())
    assert ledger.verify_chain()["valid"] is True
    assert ledger.height() == 2


def test_verify_chain_detects_tamper(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    ledger = OmniDimensionalLedger(path)
    state = compute_resonance({Dimension.PROSPERITY: 0.8})
    ledger.append(state.as_dict())
    lines = path.read_text().splitlines()
    tampered = json.loads(lines[0])
    tampered["resonance"]["system_resonance"] = 0.1
    path.write_text(json.dumps(tampered) + "\n")
    result = OmniDimensionalLedger(path).verify_chain()
    assert result["valid"] is False
    assert result["reason"] == "hash mismatch"


def test_extractive_scenario_halts():
    state = compute_resonance({Dimension.PROSPERITY: 0.95, Dimension.PLANET: 0.20})
    verdict = ValueGovernor().review(state.as_dict())
    assert verdict.decision == "HALT"
    assert "planet" in verdict.breached_floors


def test_anchor_skipped_without_env(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("DRAGON_SEAL_CONTRACT", raising=False)
    monkeypatch.delenv("DRAGON_SEAL_TOKEN_ID", raising=False)
    monkeypatch.delenv("DRAGON_SEAL_WALLET_PRIVATE_KEY", raising=False)
    epoch = {"epoch_id": "ODL-000001-test", "sha256": "a" * 64}
    result = anchor_epoch(epoch)
    assert result["status"] == "SKIPPED"
    assert not result.get("dragon_seal_anchored")


def test_anchor_config_reports_missing():
    cfg = anchor_config()
    assert "ready" in cfg
    assert "missing_env" in cfg