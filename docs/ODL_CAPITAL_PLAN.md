# Omni-Dimensional Ledger (ODL) — Capital Plan

**Green Horizon Innovation LLC (GHI) · QM2ARL Lab · SDVOSB**
Companion to `docs/ODL_COST_MODEL_CLASS3.md` (AACE Class-3 cost model) and `configs/odl_framework_manifest.yaml`.

> **All figures are ESTIMATES at AACE Class 3 (−20% / +30%).** This plan derives directly from the Class-3 cost model. Funding sources below are **OPTIONS, not commitments**. No vendor, investor, or program has been secured by this document.

---

## 1. Assumptions & basis

| # | Assumption | Value | Basis |
|---|---|---|---|
| B1 | Program horizon | 36 months | 3-phase build |
| B2 | Phase durations | P1 = 9 mo · P2 = 15 mo · P3 = 12 mo | cost model A3–A5 |
| B3 | Currency | USD, 2026 nominal | — |
| B4 | Base 3-yr TCO (expected) | **$3.41M** | cost model §4.4 |
| B5 | Contingency-loaded TCO (expected) | **$3.92M** (15% contingency) | cost model §4.4 |
| B6 | Labor share of program | **~75%** | cost model §5 |
| B7 | Capital raised with per-tranche buffer | ~10–15% above phase need | runway protection |
| B8 | Recommended total capital | **~$4.4M** across 3 tranches | §3 |

---

## 2. Monthly burn schedule & cumulative capital / runway

**Expected monthly burn (labor + infra + licenses), with one-time CapEx at phase start:**

| Phase | Months | Labor/mo | Infra/mo | Licenses/mo | **Total burn/mo** | CapEx (one-time) |
|---|---|---:|---:|---:|---:|---:|
| 1 — Pilot | 1–9 | $30.3k | $1.2k | $0.46k | **~$32.0k** | $0 |
| 2 — Operational | 10–24 | $73.5k | $5.0k | $0.46k | **~$79.0k** | $18.0k (mo 10) |
| 3 — Scaled | 25–36 | $129.5k | $25.0k | $0.46k | **~$155.0k** | $60.0k (mo 25) |

### 2.1 Cumulative capital deployed (expected, $k) — quarterly

| Month | Phase | Burn this qtr | CapEx this qtr | **Cumulative capital** | Runway note |
|---:|---|---:|---:|---:|---|
| 3 | P1 | 96 | 0 | **96** | |
| 6 | P1 | 96 | 0 | **192** | |
| 9 | P1 | 96 | 0 | **288** | ← Gate A (Pilot complete) |
| 12 | P2 | 237 | 18 | **543** | Tranche B should be in hand by mo 9–10 |
| 15 | P2 | 237 | 0 | **780** | |
| 18 | P2 | 237 | 0 | **1,017** | |
| 21 | P2 | 237 | 0 | **1,254** | |
| 24 | P2 | 237 | 0 | **1,491** | ← Gate B (Operational complete) |
| 27 | P3 | 465 | 60 | **2,016** | Tranche C should be in hand by mo 22–24 |
| 30 | P3 | 465 | 0 | **2,481** | |
| 33 | P3 | 465 | 0 | **2,946** | |
| 36 | P3 | 465 | 0 | **3,411** | ← end of horizon (= base TCO) |

> **Runway rule:** each tranche must close **~2–3 months before** the prior tranche is exhausted (B7). Burn nearly **doubles at the Phase-1→2 step (~$32k→$79k/mo)** and nearly **doubles again at Phase-2→3 (~$79k→$155k/mo)** — the hiring ramp is the runway risk, not infra.

---

## 3. Recommended raise / tranche structure

Phased, milestone-gated. Raise to reach the **next** gate plus buffer; do not raise the full $4.4M up front (avoids over-dilution before de-risking).

| Tranche | Funds the phase | Phase need (expected) | **Recommended raise** | Cumulative raised | Buffer/contingency included |
|---|---|---:|---:|---:|---|
| **A — Pilot** | Phase 1 (mo 1–9) | $0.29M | **$0.40M** | $0.40M | ~$0.11M (pilot overrun + bridge) |
| **B — Operational** | Phase 2 (mo 10–24) | $1.20M | **$1.50M** | $1.90M | ~$0.30M (zK/vendor variance) |
| **C — Scaled** | Phase 3 (mo 25–36) | $1.92M | **$2.50M** | $4.40M | ~$0.58M (Phase-3 scope band) |
| | **Total** | **$3.41M** | **~$4.40M** | | vs $3.92M contingency-loaded TCO |

### 3.1 Milestone gates (release conditions for the next tranche)

- **Gate A → unlocks Tranche B (≈ month 9):**
  - Resonance kernel + ledger chain + General AI governor running reproducibly (already `operational`).
  - Divisions 10–14 audit agents + RWA/clinical onboarding demoed.
  - DragonSeal anchor on **testnet** (Sepolia/Base) via `src/odl/anchor.py`.
  - ≥ 1–2 design-partner LOIs or a federal award (SBIR Phase I).
- **Gate B → unlocks Tranche C (≈ month 24):**
  - zK prover node (RISC Zero/SP1) live + on-chain verifier on **Base mainnet**.
  - Postgres feature store + sealer/validator + hardened oracle daemon in production.
  - ≥ 1 paying engagement or binding partner commitment; uptime/SLO evidence.
- **Gate C (≈ month 36):**
  - Multi-validator or L2-rollup deployment + data-availability layer; regional redundancy.
  - Revenue traction sufficient to approach default-alive or Series A on metrics.

---

## 4. Use of funds

### 4.1 Program-level (contingency-loaded, expected $3.92M)

| Category | $M | % |
|---|---:|---:|
| **Labor** | $2.93M | **~75%** |
| Infra OpEx (cloud/quantum/zK/storage/onchain/monitoring) | $0.39M | ~10% |
| Contingency (15%) | $0.51M | ~13% |
| CapEx (hardware) | $0.08M | ~2% |
| Licenses | $0.02M | <1% |
| **Total** | **$3.92M** | 100% |

### 4.2 By tranche (recommended raise, approximate allocation $k)

| Category | Tranche A ($400k) | Tranche B ($1,500k) | Tranche C ($2,500k) |
|---|---:|---:|---:|
| Labor | 273 | 1,103 | 1,554 |
| Infra OpEx | 11 | 75 | 300 |
| CapEx | 0 | 18 | 60 |
| Licenses | 4 | 7 | 6 |
| Contingency / buffer | 112 | 297 | 580 |
| **Total** | **400** | **1,500** | **2,500** |

---

## 5. Funding-source options (SDVOSB) — *options, not commitments*

GHI's **SDVOSB** status and the QM2ARL portfolio (existing DOE Sea Horse award; TELPAI-QUANTUM FOA-3472) make a **non-dilutive-first** strategy realistic.

| Source | Fit / vehicle | Typical size | Dilution | Best applied to |
|---|---|---|---|---|
| **SBIR/STTR Phase I** (DOE, NSF, DoD, DARPA) | quantum-ledger / verifiable-compute topics | $150k–$300k | none | **Tranche A** (Pilot) |
| **SBIR/STTR Phase II** | follow-on to Phase I | $1.0M–$2.0M | none | **Tranche B** (Operational) |
| **SDVOSB set-aside / sole-source contracts** | SBA sole-source up to ~$4.5M | varies | none | Tranches B–C (services revenue) |
| **Strategic / partner capital** | RANK Quantum & design-partner prepay / co-dev | $0.1M–$1M+ | low/none | Tranches A–B |
| **Federal program / direct grant** | DOE/DARPA program funding | varies | none | Tranches B–C |
| **Seed equity** (deep-tech / quantum VCs) | priced round or SAFE | $0.5M–$3M | yes | Tranche B gap-fill |
| **Series A equity** | growth round on milestones | $3M+ | yes | **Tranche C** (Scaled) |
| **Customer revenue** | AutoQMS / RWA / audit engagements | recurring | none | offsets Tranche C burn |

**Recommended posture:**
- **Tranche A:** SBIR/STTR Phase I + strategic/partner — keep it non-dilutive; reserve equity.
- **Tranche B:** SBIR Phase II as the anchor, topped up by seed equity or partner prepay only if needed.
- **Tranche C:** blend Series A equity + strategic + first revenue; non-dilutive set-aside contracts reduce the equity ask.

---

## 6. Key assumptions & risks

| Risk | Driver | Mitigation |
|---|---|---|
| **Labor overrun / mis-hire** (largest) | 75% of program is labor; +1 FTE ≈ +$0.25M/yr | phase-gated hiring; contractors before FTEs; do not pre-hire ahead of gates |
| **Hiring-ramp runway gap** | burn ~doubles at each phase step | close each tranche 2–3 mo early; bridge buffer in every tranche |
| **Vendor price variance** | quantum-cloud, zK-proving, cloud-GPU prices `[vendor-confirmation required]` | get quotes before Gate B; prefer Base L2 + self-host GPU to cap OpEx |
| **Non-dilutive timing** | SBIR cycles are slow (6–9 mo) | start Phase I application now; keep a small equity/partner bridge ready |
| **Phase-3 scope uncertainty** | multi-validator vs L2 rollup undecided (`to_build`) | defer the decision to Gate B; widest cost band sits here ($1.41M–$2.87M) |
| **Quantum-advantage scope creep** | kernel is classically simulable at 6–8 qubits | keep quantum as optional upgrade path; do not fund hardware ahead of need |
| **Estimate maturity** | Class 3 = −20%/+30% | re-baseline to Class 2 before committing Tranche C |

---

## 7. Headline summary

- **3-year program need (expected):** base **$3.41M**; with 15% contingency **$3.92M**; AACE Class-3 band **$3.14M–$5.10M**.
- **Per-phase capital required (expected):** Pilot **$0.29M** · Operational **$1.20M** · Scaled **$1.92M**.
- **Recommended raise:** **3 tranches ≈ $4.4M total** — A $0.40M (Pilot) → B $1.50M (Operational) → C $2.50M (Scaled), each milestone-gated with buffer.
- **Use of funds:** ~75% labor, ~13% contingency, ~10% infra OpEx, ~2% CapEx.
- **Strategy:** non-dilutive-first (SBIR/STTR + SDVOSB set-asides + strategic/partner) for Tranches A–B; equity for Tranche C scale.

---

*All figures ESTIMATE · AACE Class 3 (−20%/+30%) · USD 2026 nominal · GHI / QM2ARL. Funding sources are options, not commitments.*
