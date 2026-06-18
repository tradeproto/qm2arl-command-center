"""
Omni-Dimensional Ledger — framework status & cost rollup.

Reads configs/odl_framework_manifest.yaml and reports:
  · build-completion % by layer and overall (operational / partial / to_build)
  · the programmable node-type inventory and what's left to build
  · monthly OpEx and one-time CapEx rollups (AACE Class 5 estimates)
  · per-phase cost envelopes

This makes the framework "operational" in the sense that the codebase reports
its own readiness and run-cost.

    python -m src.odl.nodes
    python -m src.odl.nodes --json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST = _REPO_ROOT / "configs" / "odl_framework_manifest.yaml"

_STATUS_WEIGHT = {"operational": 1.0, "partial": 0.5, "to_build": 0.0}


def load_manifest(path: str | Path | None = None) -> dict[str, Any]:
    import yaml

    p = Path(path) if path else _MANIFEST
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _cost_triplet(d: dict[str, Any] | None) -> tuple[float, float, float]:
    if not d:
        return (0.0, 0.0, 0.0)
    return (float(d.get("low", 0)), float(d.get("expected", 0)), float(d.get("high", 0)))


def _add(acc: list[float], trip: tuple[float, float, float]) -> None:
    for i in range(3):
        acc[i] += trip[i]


def summarize(manifest: dict[str, Any]) -> dict[str, Any]:
    components = manifest.get("components", [])
    layers = {l["id"]: l["name"] for l in manifest.get("layers", [])}

    # Build completion overall + per layer
    by_layer: dict[int, list[float]] = {}
    counts = {"operational": 0, "partial": 0, "to_build": 0}
    weighted = 0.0
    for c in components:
        st = c.get("build_status", "to_build")
        counts[st] = counts.get(st, 0) + 1
        weighted += _STATUS_WEIGHT.get(st, 0.0)
        lid = c.get("layer")
        by_layer.setdefault(lid, [0.0, 0.0])
        by_layer[lid][0] += _STATUS_WEIGHT.get(st, 0.0)
        by_layer[lid][1] += 1.0
    n = max(len(components), 1)
    completion_pct = round(100.0 * weighted / n, 1)

    layer_completion = {
        layers.get(lid, f"layer_{lid}"): round(100.0 * v[0] / max(v[1], 1), 0)
        for lid, v in sorted(by_layer.items())
    }

    # Cost rollups across components + hardware + onchain
    monthly = [0.0, 0.0, 0.0]
    capex = [0.0, 0.0, 0.0]
    for group in ("components", "hardware", "onchain"):
        for item in manifest.get(group, []):
            _add(monthly, _cost_triplet(item.get("monthly_usd")))
            _add(capex, _cost_triplet(item.get("capex_usd")))

    # Node-type inventory
    nodes = manifest.get("node_types", [])
    node_status = {"operational": [], "partial": [], "to_build": []}
    for nt in nodes:
        node_status.setdefault(nt.get("build_status", "to_build"), []).append(nt["id"])

    return {
        "completion_pct": completion_pct,
        "component_counts": counts,
        "layer_completion_pct": layer_completion,
        "node_status": node_status,
        "monthly_usd_rollup": {"low": monthly[0], "expected": monthly[1], "high": monthly[2]},
        "capex_usd_rollup": {"low": capex[0], "expected": capex[1], "high": capex[2]},
        "phases": manifest.get("phases", []),
    }


def _bar(pct: float, width: int = 24) -> str:
    fill = int(round(width * pct / 100.0))
    return "█" * fill + "░" * (width - fill)


def main() -> int:
    ap = argparse.ArgumentParser(description="ODL framework status & cost rollup")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    m = load_manifest()
    s = summarize(m)

    if args.json:
        print(json.dumps(s, indent=2))
        return 0

    print("\n=== Omni-Dimensional Ledger — Framework Suite ===")
    print(f"Estimate basis: {m['meta']['estimate_class']}\n")

    print(f"Overall build completion: {s['completion_pct']}%  {_bar(s['completion_pct'])}")
    c = s["component_counts"]
    print(f"  components: {c.get('operational',0)} operational · "
          f"{c.get('partial',0)} partial · {c.get('to_build',0)} to build\n")

    print("Build completion by layer:")
    for name, pct in s["layer_completion_pct"].items():
        print(f"  {name:24} {pct:5.0f}%  {_bar(pct, 18)}")

    print("\nProgrammable nodes:")
    for st in ("operational", "partial", "to_build"):
        ids = s["node_status"].get(st, [])
        if ids:
            print(f"  {st:11}: {', '.join(ids)}")

    mo = s["monthly_usd_rollup"]
    cx = s["capex_usd_rollup"]
    print("\nCost rollup (AACE Class 5 estimate, USD):")
    print(f"  Monthly OpEx : ${mo['low']:,.0f}  /  ${mo['expected']:,.0f} expected  /  ${mo['high']:,.0f}")
    print(f"  One-time CapEx: ${cx['low']:,.0f}  /  ${cx['expected']:,.0f} expected  /  ${cx['high']:,.0f}")
    print("  (Engineering labor is the dominant cost and is tracked separately.)")

    print("\nPhased envelopes (monthly OpEx · one-time CapEx):")
    for p in s["phases"]:
        mo = p.get("monthly_usd", {})
        cx = p.get("capex_usd", {})
        print(f"  {p['name']}")
        print(f"     OpEx ~${mo.get('expected',0):,.0f}/mo (${mo.get('low',0):,.0f}–${mo.get('high',0):,.0f})  "
              f"· CapEx ~${cx.get('expected',0):,.0f} (${cx.get('low',0):,.0f}–${cx.get('high',0):,.0f})")

    print("\nDetails & roadmap: docs/ODL_FRAMEWORK_SUITE.md")
    print("Manifest: configs/odl_framework_manifest.yaml\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
