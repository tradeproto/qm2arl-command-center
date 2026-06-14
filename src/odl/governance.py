"""
ODL governance — the GAI → SAI value governor.

Acronyms (spelled out):
  GAI = General AI   (artificial general intelligence — human-level breadth)
  SAI = Super AI     (artificial superintelligence — beyond human capability)

The ledger records resonance; the governor decides what to do about it under
**value constraints**. This is where "the AI mirror reflects what we encode":
the governor will not authorize an action that lifts one dimension by collapsing
another below its floor — cooperation is enforced structurally, not hoped for.

Two tiers, honestly labeled:

  GAI — General AI  (OPERATIONAL):
        a transparent, rule + agent-collective policy. Reads the resonance
        state, checks value floors, and returns a verdict + directive. This is
        what runs today. Human-in-the-loop by design.

  SAI — Super AI  (ASPIRATIONAL):
        the future tier that would autonomously re-allocate across the whole
        coupled system, faster and wider than humans can. Represented here as an
        interface and a mode flag so the architecture is ready; it does NOT act
        autonomously today — it still escalates every authorization to humans.

Verdicts:
  PROCEED   — resonant/coherent and no floor breached → authorize.
  REBALANCE — overall acceptable but a dimension is below floor → corrective directive.
  HALT      — fractured or a critical floor breached → block, escalate to humans.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .dimensions import DIMENSION_ORDER, spec, Dimension


# Per-dimension hard floors — no action may push a dimension below these.
VALUE_FLOORS: dict[Dimension, float] = {
    Dimension.PROSPERITY: 0.35,
    Dimension.PLANET: 0.45,        # planetary boundary — strictest
    Dimension.EQUITY: 0.45,
    Dimension.HEALTH: 0.45,
    Dimension.KNOWLEDGE: 0.50,     # truth/verifiability floor
    Dimension.CONNECTION: 0.40,
}


@dataclass
class GovernanceVerdict:
    tier: str                       # GAI | SAI
    decision: str                   # PROCEED | REBALANCE | HALT
    authorized: bool
    breached_floors: list[str] = field(default_factory=list)
    directive: str = ""
    escalate_to_human: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "decision": self.decision,
            "authorized": self.authorized,
            "breached_floors": self.breached_floors,
            "directive": self.directive,
            "escalate_to_human": self.escalate_to_human,
        }


class ValueGovernor:
    """
    GAI value governor. Deterministic, auditable, value-floor enforcing.

    tier="SAI" reserved for the future autonomous re-allocation layer; in this
    build it behaves identically to GAI but never auto-executes (escalates).
    """

    def __init__(self, tier: str = "GAI", floors: dict[Dimension, float] | None = None):
        self.tier = "SAI" if str(tier).upper() == "SAI" else "GAI"
        self.floors = floors or VALUE_FLOORS

    def review(self, resonance: dict[str, Any]) -> GovernanceVerdict:
        dims = resonance.get("dimensions", {})
        verdict = resonance.get("verdict", "FRACTURED")
        R = float(resonance.get("system_resonance", 0.0))

        breached = []
        for dim, floor in self.floors.items():
            v = dims.get(dim.value)
            if v is not None and v < floor:
                breached.append(dim.value)

        critical = any(d in breached for d in ("planet", "knowledge", "health"))

        if verdict == "FRACTURED" or critical:
            decision = "HALT"
            authorized = False
            escalate = True
            if critical:
                directive = (
                    f"Critical value floor breached ({', '.join(breached)}). "
                    "Block resonance-lowering actions; escalate to human stewards."
                )
            else:
                directive = "System fractured — halt and rebuild coherence before proceeding."
        elif breached:
            decision = "REBALANCE"
            authorized = False
            escalate = False
            worst = resonance.get("binding_dimension", breached[0])
            directive = (
                f"Rebalance toward '{worst}' (and {', '.join(breached)}) before "
                f"authorizing actions that raise other dimensions."
            )
        else:
            decision = "PROCEED"
            authorized = True
            escalate = False
            directive = (
                f"System {verdict} at R={R:.2f}; all value floors held. "
                "Authorize within coupled constraints."
            )

        # SAI tier would auto-execute PROCEED; today it still defers to humans.
        if self.tier == "SAI" and decision == "PROCEED":
            escalate = True
            directive += " [SAI autonomous execution is ASPIRATIONAL — deferring to human authorization.]"

        return GovernanceVerdict(
            tier=self.tier,
            decision=decision,
            authorized=authorized,
            breached_floors=breached,
            directive=directive,
            escalate_to_human=escalate,
        )
