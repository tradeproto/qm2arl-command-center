# The Omni-Dimensional Ledger (ODL)
## System Resonance on Quantum Hardware — Engineering Architecture

**Green Horizon Innovation LLC · QM2ARL Lab**
**Status:** v0.1 — conceptual architecture with an OPERATIONAL kernel
**Companion to:** `docs/WHITEPAPER_QM2ARL_OMNIDIRECTIONAL_LEDGER.md`, `VALUES.md`

---

## 0. Honest phase taxonomy (read this first)

This document follows the same discipline as the whitepaper — aspiration is not
dressed as accomplishment.

| Label | Meaning | Applies to |
|---|---|---|
| **OPERATIONAL** | Runs today, reproducible in-repo | Resonance kernel, ledger chain, governor, signal ingestion |
| **SIMULATED** | Demonstrated in software, quantum on simulator | Quantum coherence term (BlueQubit-ready, sim today) |
| **ASPIRATIONAL** | Destination; components exist in pieces | Planetary-scale instrumentation, SAI autonomous tier |

The mathematics, the ledger, and the governor are real and runnable today
(`python -m src.odl`). Planet-scale data coverage and the SAI tier are
explicitly future — the architecture is built so they slot in without redesign.

---

## 1. Why an Omni-Dimensional Ledger

The whitepaper's **OmniDirectional Ledger** records value on 3 Trinity axes
(economic · ecological · social). The **Omni-Dimensional Ledger** generalizes
that to an **N-dimensional value space** and adds a **System Resonance** kernel:
the ledger no longer asks "did one number go up?" but "is the whole system both
*elevated* and *coherent* — with nothing sacrificed for anything else?"

This is the infrastructure layer beneath the vision: a world economy, planetary
health, wealth, and human connection recorded **together**, verifiably, so that
**cooperation becomes the rational strategy** rather than a hope.

---

## 2. The six value dimensions

`src/odl/dimensions.py`. Each is a measurable scalar in [0,1] with a target and
weight. "Coherence" and "Love" are concrete proxies, not mysticism.

| Dimension | Trinity pillar | Proxy (how measured) |
|---|---|---|
| **Prosperity** (Wealth) | economic | prosperity-equilibrium, RWA value, economic audit scores |
| **Planet** (Ecology) | ecological | CO₂ intensity, regeneration, materials lifecycle |
| **Equity** (Society) | social | coupling fairness, access, ISO 42001 AI governance |
| **Health** (Vitality) | social | human/system health & resilience, safety compliance |
| **Knowledge** (Coherence) | governance | verifiable-information integrity, audit %, proof-chain completeness |
| **Connection** (Love) | social | cooperative alignment Hμ, relational coherence across agents |

The set is extensible — add a dimension spec and the kernel, ledger, and
governor pick it up automatically.

---

## 3. The System Resonance kernel

`src/odl/resonance.py`. A flourishing system is **high** *and* **synchronized**.

**Magnitude** — how high overall:
\[ M = \sum_i w_i a_i \]

**Phase coherence** ρ — the **Kuramoto order parameter**, the same quantity that
measures synchronization in coupled-oscillator physics. Each dimension is an
oscillator with amplitude \(a_i\) and phase \(\theta_i = \pi(a_i - \text{target}_i)\):
\[ \rho = \frac{\left| \sum_i a_i e^{i\theta_i} \right|}{\sum_i a_i} \in [0,1] \]
ρ → 1 when dimensions sit at their targets in phase; ρ falls when some race ahead
while others collapse.

**Quantum coherence** Q — the QM2ARL quantum kernel \(K(a,\text{target}) =
|\langle\phi(a)|\phi(\text{target})\rangle|^2\) from `src/quantum_geospatial.py`,
run on the **same backend ladder** as the rest of the stack.

**System Resonance:**
\[ R = M \cdot \left(\tfrac{1}{2}\rho + \tfrac{1}{2}Q\right) \in [0,1] \]
optionally fused with the live Harmony Metric Hμ the agents already optimize.

| R | Verdict |
|---|---|
| ≥ 0.80 (and ρ ≥ 0.85) | **RESONANT** |
| ≥ 0.65 | **COHERENT** |
| ≥ 0.45 | **DISSONANT** |
| < 0.45 | **FRACTURED** |

### Quantum-hardware execution

Q is computed on the QM2ARL device ladder (`docs/QUANTUM_STACK.md`):

| Priority | Backend | Role |
|---|---|---|
| 1 | **BlueQubit** cloud (`BLUEQUBIT_API_TOKEN`, `bluequbit.cpu/gpu`) | Primary gate cloud / hardware path |
| 2 | `lightning.qubit` | Fast local/GPU simulation |
| 3 | `default.qubit` | Always-available fallback |

Select with `ODL_QUANTUM_BACKEND` or `vqc_backend`. **Honest scope:** at
N=6 wires the kernel is classically simulable — the value is a backend-agnostic,
scale-ready architecture, not a quantum-advantage claim today.

---

## 4. The ledger — hash-linked and sealable

`src/odl/ledger.py`. Append-only chain of **resonance epochs**; each carries
`prev_hash`, so any tampering breaks the chain (verified: editing one epoch
flips `verify_chain()` to `BROKEN`). Any epoch is **Dragon Seal-ready** and
pins to Lighthouse via the existing `src/telpai_rwa/dragon_seal.py` — the same
proof chain that seals RWA oracle epochs and QMS documents.

```
epoch_n = { index, timestamp, subject, prev_hash,
            resonance{R, M, ρ, Q, verdict, dimensions…},
            sources{…}, governance{…}, sha256 }
```

Persistence: `data/odl_ledger.jsonl`.

---

## 5. Governance — the GAI → SAI value governor

`src/odl/governance.py`. The ledger records; the governor decides under **value
floors**. It will not authorize an action that lifts one dimension by collapsing
another below its floor — cooperation is enforced **structurally**.

Two intelligence tiers (acronyms spelled out):

- **GAI — General AI** (artificial *general* intelligence; human-level breadth)
- **SAI — Super AI** (artificial *super*intelligence; beyond human capability)

| Tier | Status | Behavior |
|---|---|---|
| **GAI — General AI** | OPERATIONAL | Transparent rule + agent-collective policy; reviews resonance, checks floors, returns verdict; human-in-the-loop |
| **SAI — Super AI** | ASPIRATIONAL | Future autonomous re-allocation across the coupled system; present as an interface + mode flag; still escalates to humans today |

**Why the value floors matter more as intelligence scales:** a General AI
advising humans is bounded by human review; a Super AI acting at machine speed
and scale is not. The value floors and the HALT/escalate path are the
**alignment harness** — encoded *now*, in the General AI tier, so the same
structural constraints are already load-bearing if/when a Super AI tier is ever
switched on. We build the guardrail before the road.

| Decision | Trigger | Effect |
|---|---|---|
| **PROCEED** | resonant/coherent, no floor breached | authorize within coupled constraints |
| **REBALANCE** | a dimension below floor | corrective directive toward the binding dimension |
| **HALT** | FRACTURED or critical floor (planet/knowledge/health) breached | block + escalate to human stewards |

**Demonstrated:** an extractive scenario (Prosperity 0.95, Planet 0.20) →
DISSONANT → **HALT**. The ledger refuses to let the system win economically
while losing ecologically — the whitepaper's thesis made executable.

---

## 6. The engine — unifying everything built

`src/odl/engine.py`. `SystemResonanceEngine.step()` auto-assembles value-
dimension signals from real in-repo artifacts, computes resonance, records the
epoch, and runs the governor.

| Dimension | Live signal source |
|---|---|
| Knowledge | mean audit % across **Divisions 10–13** (`results/autoqms_*_training_summary.json`) |
| Connection | best **Hμ** from QM2ARL training |
| Prosperity | registered **RWA assets** + tokenizable share (`data/rwa_assets.json`) |
| Planet / Equity / Health | (uncovered today — reported, defaulted to target) |

Coverage is reported honestly (today ~50%). As engineering domains (CO₂,
geothermal footprint, safety) and social signals come online, coverage rises
without code changes.

```
signals (RWA · Div 10-13 · TELPAI-Q · Hμ)
  → value dimensions
  → compute_resonance()      [quantum-hardware-ready]
  → ledger.append()          [hash-linked, DragonSeal-ready]
  → ValueGovernor.review()   [GAI now, SAI later]
```

---

## 7. How it connects to the rest of QM2ARL

| Built component | Role in the ODL |
|---|---|
| QM2ARL agents + Hμ (`qm2arl_trainer.py`) | Connection dimension; dynamical resonance |
| Quantum kernel (`quantum_geospatial.py`) | Quantum coherence term Q |
| Divisions 10–13 (compliance/audit) | Knowledge dimension (verifiable integrity) |
| TELPAI-Q (`telpai_rwa/quantum_verify.py`) | Asset-level verification feeding Prosperity |
| RWA onboarding (`telpai_rwa/onboarding.py`) | Asset value → Prosperity; sealed epochs |
| DragonSeal + Lighthouse | Ledger epoch attestation & permanence |
| Efficient models (`efficient_models.py`) | Lets the resonance loop run at scale/edge |

One architecture; the ODL is the layer where all directions are recorded in one
coherent, verifiable state.

---

## 8. Roadmap

| Phase | Milestone |
|---|---|
| **Now (OPERATIONAL)** | Resonance kernel, ledger chain, GAI governor, signal ingestion, demo (`python -m src.odl`) |
| **Near** | Streamlit ODL dashboard; broaden dimension coverage (CO₂, safety, social); seal epochs on-chain |
| **Mid** | Live coupling of engineering-domain telemetry into Planet/Health; multi-subject ledgers (per asset, per program) |
| **Long (ASPIRATIONAL)** | Continental/planetary resonance; SAI autonomous re-allocation under value floors with human oversight |

---

## 9. Run it

```bash
python -m src.odl                      # System Resonance cycle from live platform signals
python -m src.odl --seal               # also Dragon Seal the head epoch
python -m src.odl --backend bluequbit.cpu   # quantum coherence on BlueQubit cloud
```

```python
from src.odl import SystemResonanceEngine, Dimension
eng = SystemResonanceEngine()
out = eng.step()
print(out["resonance"]["verdict"], out["resonance"]["system_resonance"])
```

---

*This is where it begins — the conceptual phase made executable. The kernel is
real; the vision is the direction it scales. Same agents, same code, an honest
ledger across every dimension that matters.*
