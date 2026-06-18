"""
Omni-Dimensional Ledger demo — run a System Resonance cycle and print it.

    python -m src.odl                 # auto-assemble signals from the platform
    python -m src.odl --seal          # also Dragon Seal the head epoch
    python -m src.odl --backend bluequbit.cpu
"""
from __future__ import annotations

import argparse

from .engine import SystemResonanceEngine
from .dimensions import DIMENSION_SPECS


def main() -> int:
    ap = argparse.ArgumentParser(description="Omni-Dimensional Ledger — System Resonance")
    ap.add_argument("--seal", action="store_true", help="Dragon Seal the head epoch")
    ap.add_argument("--anchor", action="store_true", help="On-chain attest head epoch (DragonSeal)")
    ap.add_argument("--anchor-dry-run", action="store_true", help="Validate anchor config without broadcasting")
    ap.add_argument("--backend", default="", help="quantum backend (e.g. bluequbit.cpu)")
    ap.add_argument("--tier", default="GAI", choices=["GAI", "SAI"])
    args = ap.parse_args()

    print("\n=== Omni-Dimensional Ledger · System Resonance ===\n")
    print("Value dimensions:")
    for s in DIMENSION_SPECS:
        print(f"  · {s.label:26} target={s.target:.2f}  ({s.proxy})")

    eng = SystemResonanceEngine(governor_tier=args.tier, vqc_backend=args.backend)
    out = eng.step(seal=args.seal)
    if args.anchor or args.anchor_dry_run:
        from .anchor import anchor_epoch
        out["anchor"] = anchor_epoch(out["epoch"], dry_run=args.anchor_dry_run or not args.anchor)

    r = out["resonance"]
    g = out["governance"]
    print(f"\nCoverage: {r['coverage']['coverage_pct']}%  measured={r['coverage']['measured']}")
    print("\nResonance state:")
    print(f"  System Resonance R : {r['system_resonance']:.3f}   [{r['verdict']}]")
    print(f"  Magnitude     M    : {r['magnitude']:.3f}")
    print(f"  Phase coherence ρ  : {r['phase_coherence']:.3f}  (Kuramoto order parameter)")
    print(f"  Quantum coherence Q: {r['quantum_coherence']:.3f}  (backend: {r['backend']})")
    print(f"  Binding dimension  : {r['binding_dimension']} @ {r['binding_value']:.2f}")
    print("\n  Dimensions:")
    for k, v in r["dimensions"].items():
        print(f"    {k:14} {v:.3f}")

    print(f"\nGovernor [{g['tier']}]: {g['decision']}  (authorized={g['authorized']})")
    print(f"  → {g['directive']}")
    if g["breached_floors"]:
        print(f"  breached floors: {g['breached_floors']}")

    print(f"\nLedger: height={out['ledger_height']}  epoch={out['epoch']['epoch_id']}")
    print(f"  sha256={out['epoch']['sha256']}")
    print(f"  verify={out['epoch']['verify_url']}")
    chain = eng.ledger.verify_chain()
    print(f"  chain integrity: {'VALID' if chain['valid'] else 'BROKEN'} (height {chain.get('height')})")
    if out.get("dragon_seal"):
        print(f"  dragon seal: {out['dragon_seal'].get('seal_id')} [{out['dragon_seal'].get('status')}]")
    if out.get("anchor"):
        a = out["anchor"]
        print(f"  anchor: {a.get('status')}")
        if a.get("tx_hash"):
            print(f"  tx: {a.get('explorer_url')}")
        if a.get("reason"):
            print(f"  anchor note: {a.get('reason')}")

    for n in r["notes"]:
        print(f"  note: {n}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
