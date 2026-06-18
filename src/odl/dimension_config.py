"""
Editable ODL dimension registry — YAML overrides on top of dimensions.py defaults.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from .dimensions import DIMENSION_ORDER, DIMENSION_SPECS, Dimension, N_DIMENSIONS, spec
from .governance import VALUE_FLOORS

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = _REPO_ROOT / "configs" / "odl_dimensions.yaml"


def _default_floors() -> dict[str, float]:
    return {d.value: float(VALUE_FLOORS[d]) for d in Dimension}


def load_raw_config(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path else _CONFIG_PATH
    if not p.is_file():
        return {"version": "0.1", "signal_map": {}, "dimension_coupling": {}, "overrides": {}}
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_raw_config(data: dict[str, Any], path: str | Path | None = None) -> Path:
    p = Path(path) if path else _CONFIG_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)
    return p


def list_dimensions() -> list[dict[str, Any]]:
    """Full dimension registry for API / Brain UI."""
    raw = load_raw_config()
    overrides = raw.get("overrides") or {}
    signal_map = raw.get("signal_map") or {}
    floors = _default_floors()
    for dim_id, ov in overrides.items():
        if isinstance(ov, dict) and "floor" in ov:
            floors[dim_id] = float(ov["floor"])

    out = []
    for s in DIMENSION_SPECS:
        dim_id = s.dimension.value
        ov = overrides.get(dim_id) or {}
        sm = signal_map.get(dim_id) or {}
        out.append({
            "id": dim_id,
            "label": ov.get("label", s.label),
            "weight": float(ov.get("weight", s.weight)),
            "target": float(ov.get("target", s.target)),
            "floor": float(floors.get(dim_id, VALUE_FLOORS.get(s.dimension, 0.4))),
            "trinity_pillar": ov.get("trinity_pillar", s.trinity_pillar),
            "proxy": ov.get("proxy", s.proxy),
            "signal_map": sm,
        })
    return out


def apply_overrides(updates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Merge dimension overrides into configs/odl_dimensions.yaml."""
    raw = load_raw_config()
    overrides = dict(raw.get("overrides") or {})
    for dim_id, patch in updates.items():
        if dim_id not in {d.value for d in Dimension}:
            continue
        cur = dict(overrides.get(dim_id) or {})
        for key in ("label", "weight", "target", "floor", "trinity_pillar", "proxy"):
            if key in patch and patch[key] is not None:
                cur[key] = patch[key]
        overrides[dim_id] = cur
    raw["overrides"] = overrides
    path = save_raw_config(raw)
    return {"saved": str(path), "dimensions": list_dimensions()}


def effective_weights() -> np.ndarray:
    dims = list_dimensions()
    w = np.array([d["weight"] for d in dims], dtype=np.float64)
    return w / w.sum()


def effective_targets() -> np.ndarray:
    dims = list_dimensions()
    return np.array([d["target"] for d in dims], dtype=np.float64)


def coupling_matrix() -> tuple[list[str], list[list[float]]]:
    """N×N dimension coupling for Brain heatmap."""
    raw = load_raw_config()
    pairs = raw.get("dimension_coupling") or {}
    ids = [d.value for d in DIMENSION_ORDER]
    n = len(ids)
    M = np.eye(n, dtype=np.float64)
    idx = {d: i for i, d in enumerate(ids)}
    for src, targets in pairs.items():
        if src not in idx:
            continue
        if not isinstance(targets, dict):
            continue
        for tgt, val in targets.items():
            if tgt in idx:
                v = float(val)
                M[idx[src], idx[tgt]] = v
                M[idx[tgt], idx[src]] = v
    return ids, M.round(4).tolist()


def signal_map() -> dict[str, dict[str, Any]]:
    raw = load_raw_config()
    defaults = {
        d.value: {
            "path_patterns": [],
            "projects": [],
            "result_files": [],
        }
        for d in Dimension
    }
    for k, v in (raw.get("signal_map") or {}).items():
        if k in defaults and isinstance(v, dict):
            defaults[k].update(v)
    return defaults