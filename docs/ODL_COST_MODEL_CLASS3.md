# Omni-Dimensional Ledger (ODL) — Class-3 Cost Model

**Green Horizon Innovation LLC (GHI) · QM2ARL Lab · SDVOSB**
Companion to `configs/odl_framework_manifest.yaml`, `docs/ODL_FRAMEWORK_SUITE.md`, and `docs/ODL_CAPITAL_PLAN.md`.
CSV companion: `docs/odl_cost_model.csv`.

> **Estimate class — AACE Class 3 (budget authorization).** Accuracy band **−20% / +30%**.
> This tightens the prior **Class-5** (concept-screening, −50%/+100%) estimate in the manifest. It is definitive enough to authorize a budget and to anchor an investor / program-office conversation. It is **not** a Class-1 detailed-design estimate.
>
> **Honesty taxonomy (carried from source docs):** every figure is an **ESTIMATE**. Build status is `operational` / `partial` / `to_build`. Quantum-cloud (BlueQubit, D-Wave, IBM) and zK-proving-service prices are flagged **`[vendor-confirmation required]`**. **Engineering labor is the dominant cost** and is modeled explicitly; infra OpEx is comparatively small.

---

## 0. Assumptions block (read first)

| # | Assumption | Value | Type | Basis |
|---|---|---|---|---|
| A1 | Estimate class / accuracy | AACE Class 3, −20% / +30% | known (method) | AACE 18R-97 |
| A2 | Program horizon | 36 months | assumed-base | 3-phase build |
| A3 | Phase 1 (Pilot) duration | Months 1–9 (9 mo) | assumed-base | simulator-first scope |
| A4 | Phase 2 (Operational) duration | Months 10–24 (15 mo) | assumed-base | multi-node hardening |
| A5 | Phase 3 (Scaled) duration | Months 25–36 (12 mo) | assumed-base | decentralization |
| A6 | Currency | USD, nominal 2026 | known | — |
| A7 | Labor burden multiplier (fully-loaded) | **1.40×** base salary | assumed-base | US startup fringe+G&A+equip+SW+recruiting; range 1.30–1.50× |
| A8 | Wage escalation | Not separately escalated within 36 mo | assumed-base | within Class-3 band; flagged in caveats |
| A9 | Contingency at Class 3 | **15%** (recommend 10–15%) | recommended | AACE typical at this maturity |
| A10 | Quantum/zK/cloud vendor prices | `[vendor-confirmation required]` | estimated | manifest disclaimer |
| A11 | Founder / PI labor | Tracked separately; may be grant-covered or uncompensated in Phase 1 | assumed-base | see §3 note |
| A12 | On-chain anchoring path | Base L2 (batched), **not** Ethereum L1 | assumed-base | manifest `anchor_base` |

All infra low/expected/high values are taken directly from `odl_framework_manifest.yaml`. Labor low/high apply a rate + headcount band (≈ −20% / +25%).

---

## 1. Work Breakdown Structure (WBS)

WBS is organized by the 8 architecture layers (Level 2) → components / node types (Level 3). Build status drives **remaining build effort** (labor); the cost columns below are recurring infra (OpEx) and one-time infra (CapEx). **Labor is NOT in this table** — see §3.

### Level 1 — Program: ODL Operational Build

| WBS | Layer / element | Key components | Status mix | Drives |
|---|---|---|---|---|
| 1.0 | **Value & Resonance** | resonance_kernel, value_dimensions, value_governor_gai (op); value_governor_sai (to_build, ASPIRATIONAL) | mostly operational | labor only |
| 2.0 | **Optimization & AI** | qm2arl_agents, divisions_10_14, efficiency_layer (op); llm_reasoning_access (partial) | operational | LLM OpEx |
| 3.0 | **Quantum Compute** | quantum_kernel_sim (op); bluequbit_cloud (partial); dwave_annealing, ibm_quantum (to_build) | partial | quantum cloud OpEx `[vendor]` |
| 4.0 | **Oracle & Verification** | telpai_q_verify, data_feeds (op); oracle_node_service (partial) | operational | oracle OpEx + labor |
| 5.0 | **Proof** | dragon_seal, odl_anchor, lighthouse_ipfs (partial); zk_prover, zk_verifier_contract (to_build) | partial→build | zK proving OpEx `[vendor]` + heavy labor |
| 6.0 | **Ledger & Consensus** | odl_chain (partial); sealer_validator_node, consensus_layer (to_build) | partial→build | validator OpEx + labor |
| 7.0 | **Storage & Data** | object_store (partial); working_index_postgres, state_db, data_availability (to_build) | to_build | Postgres/object/DA OpEx + labor |
| 8.0 | **Access & Gateway** | api_server, autoqms_app, rwa_onboarding_console, odl_dashboard, odl_api (op) | operational | labor only |
| 9.0 | **Hardware** | dev_workstation, office_server (have); gpu_prover_trainer, windows_solidworks (build) | mixed | CapEx |
| 10.0 | **On-chain & Monitoring** | anchor_base (to_build), monitoring_misc (partial) | build | OpEx |
| 11.0 | **Labor** (see §3) | Phase team (zK / backend / ML-quantum / frontend / SRE / PM) | — | **dominant cost** |

### Node-type build status (effort concentration for §3 labor)

| Node | Status | Remaining-build weight |
|---|---|---|
| resonance, governor, gateway | operational | low (maintain) |
| oracle, sealer/validator, archive | partial | medium (harden) |
| **prover (zK)**, **indexer**, **consensus** | to_build | **high (new build)** |

> **Where the labor goes:** Layers 5 (Proof/zK), 6 (Ledger/Consensus), and 7 (Storage) are the least complete (manifest completion ~25% / ~17% / ~12%). They drive the protocol/zK and backend/infra engineering headcount in §3.

---

## 2. Infrastructure — CapEx & OpEx (no labor)

### 2.1 Recurring OpEx (monthly USD), by category

| WBS | Line item | Status | Low | Expected | High | Flag |
|---|---|---|---:|---:|---:|---|
| 2.0 | LLM reasoning (Grok, pluggable) | partial | 50 | 200 | 800 | |
| 3.0 | BlueQubit gate cloud | partial | 200 | 600 | 2,500 | `[vendor]` |
| 3.0 | D-Wave Leap (annealing, optional) | to_build | 0 | 0 | 2,000 | `[vendor]` |
| 3.0 | IBM Quantum (optional eval) | to_build | 0 | 0 | 1,500 | `[vendor]` |
| 4.0 | Oracle node service | partial | 24 | 60 | 200 | |
| 5.0 | Lighthouse IPFS/Filecoin | partial | 50 | 150 | 400 | |
| 5.0 | zK prover (RISC Zero/SP1 service) | to_build | 100 | 500 | 2,000 | `[vendor]` |
| 6.0 | Sealer/validator node | to_build | 48 | 120 | 400 | |
| 7.0 | Working index (Postgres) | to_build | 50 | 120 | 400 | |
| 7.0 | Object store | partial | 20 | 80 | 300 | |
| 7.0 | Data availability (Celestia/EigenDA) | to_build | 0 | 0 | 600 | `[vendor]` |
| 9.0 | Cloud VMs (DigitalOcean prod) | operational | 48 | 150 | 600 | |
| 9.0 | Cloud GPU (on-demand, alt to CapEx) | to_build | 300 | 900 | 2,500 | `[vendor]` |
| 10.0 | On-chain anchor (Base L2, batched) | to_build | 10 | 30 | 150 | |
| 10.0 | Monitoring / logging / backups / TLS | partial | 50 | 120 | 400 | |
| | **Infra OpEx rollup (monthly)** | | **950** | **3,030** | **14,750** | |

> Reconciles exactly to the Class-5 manifest rollup (~$3,030/mo expected; $950–$14,750). At **Class 3** we hold the expected steady but tighten the working band per phase (§4) — the all-categories-maxed $14,750 high only occurs if every optional path (D-Wave + IBM + DA + heavy zK + heavy quantum + cloud GPU) is simultaneously live, which the phased plan avoids.

### 2.2 Annual software licenses (OpEx)

| Line item | Annual USD | Note |
|---|---:|---|
| SolidWorks (Chapman engineering loop) | 4,000 | per manifest `labor.software_licenses` |
| Misc dev tools (IDEs, CI, monitoring SaaS) | 1,500 | |
| **Licenses total** | **5,500 / yr** (~$458/mo) | |

### 2.3 One-time CapEx (hardware/setup)

| WBS | Line item | Status | Low | Expected | High | Note |
|---|---|---|---:|---:|---:|---|
| 9.0 | Dev workstation (Linux main) | operational | 2,000 | 3,000 | 5,000 | likely sunk/owned |
| 9.0 | Office server (Linux services) | partial | 2,000 | 3,000 | 6,000 | |
| 9.0 | GPU prover/trainer node | to_build | 8,000 | 12,000 | 22,000 | **swing item** — vs cloud GPU OpEx |
| 9.0 | Windows SolidWorks station | partial | 2,000 | 2,800 | 4,500 | |
| | **CapEx rollup (one-time)** | | **14,000** | **20,800** | **37,500** | |

> Reconciles to the Class-5 manifest (~$20,800 expected; $14k–$37.5k). **Decision point:** self-host GPU (~$12k CapEx once) **vs** cloud GPU (~$900/mo). See sensitivity §6.

---

## 3. Fully-loaded labor model — *the dominant cost*

**Method.** Per-role US base salary (2026 nominal) × **1.40 fully-loaded burden** (A7: payroll tax, benefits, equipment, software seat, facilities/G&A, recruiting). Headcount ramps by phase per the manifest's suggested Phase-2 team, extended for Phase 1 (lean) and Phase 3 (scale).

### 3.1 Role rate card (fully-loaded annual, USD)

| Role | Base (exp) | ×1.40 loaded (exp) | Loaded low | Loaded high | Scarcity note |
|---|---:|---:|---:|---:|---|
| zK / protocol engineer (Rust, RISC Zero/SP1) | 200,000 | **280,000** | 245,000 | 330,000 | scarce skill → premium |
| Backend / infra engineer (FastAPI, Postgres, nodes, devops) | 165,000 | **231,000** | 200,000 | 275,000 | |
| ML / quantum engineer (QM2ARL, PennyLane/BlueQubit) | 190,000 | **266,000** | 235,000 | 315,000 | |
| Frontend engineer (dashboards/consoles) | 150,000 | **210,000** | 180,000 | 245,000 | |
| SRE / devops (Phase 3) | 165,000 | **231,000** | 200,000 | 275,000 | |
| PM / ops (Phase 3, 0.5) | 150,000 | **210,000** | 180,000 | 245,000 | |

### 3.2 Headcount by phase (FTE) and labor run-rate

| Role | Phase 1 (Pilot) | Phase 2 (Operational) | Phase 3 (Scaled) |
|---|:--:|:--:|:--:|
| zK / protocol | — | 1.0 | 1.0 |
| Backend / infra | 1.0 | 1.0 | 2.0 |
| ML / quantum | 0.5 | 1.0 | 1.0 |
| Frontend | — | 0.5 | 1.0 |
| SRE / devops | — | — | 1.0 |
| PM / ops | — | — | 0.5 |
| **Total FTE** | **1.5** | **3.5** | **6.5** |
| **Annual labor run-rate (expected)** | **$364k** | **$882k** | **$1,554k** |
| Annual labor — low | $290k | $705k | $1,245k |
| Annual labor — high | $455k | $1,100k | $1,945k |
| **Monthly labor (expected)** | **$30.3k** | **$73.5k** | **$129.5k** |

> **Note on founder/PI labor (A11).** Phase-1 founder/principal engineering may be uncompensated or covered by an SBIR/STTR award. If a market-rate PI salary (~$210k loaded) is added, Phase-1 labor rises accordingly — modeled in the high case.

**Labor vs infra (expected monthly):** Phase 1 = $30.3k labor vs $1.2k infra (**96% labor**); Phase 2 = $73.5k vs $5.0k (**94%**); Phase 3 = $129.5k vs $25.0k (**84%**). Labor dominates every phase.

---

## 4. 3-Year Total Cost of Ownership (TCO) by phase

Each phase = (labor run-rate × duration) + (infra OpEx × months) + licenses (prorated) + one-time CapEx.

### 4.1 Phase 1 — Pilot (9 months)

| Category | Low | Expected | High |
|---|---:|---:|---:|
| Labor (1.5 FTE) | 217.5 | 273.0 | 341.3 |
| Infra OpEx ($0.6/1.2/2.5k/mo × 9) | 5.4 | 10.8 | 22.5 |
| Licenses (prorated 0.75 yr) | 3.0 | 4.1 | 4.1 |
| CapEx (use existing) | 0.0 | 0.0 | 3.0 |
| **Phase 1 total ($k)** | **225.9** | **287.9** | **370.9** |

### 4.2 Phase 2 — Operational (15 months)

| Category | Low | Expected | High |
|---|---:|---:|---:|
| Labor (3.5 FTE) | 881.3 | 1,102.5 | 1,375.0 |
| Infra OpEx ($2.5/5.0/11.0k/mo × 15) | 37.5 | 75.0 | 165.0 |
| Licenses (prorated 1.25 yr) | 6.9 | 6.9 | 6.9 |
| CapEx (GPU node, server, SW station) | 8.0 | 18.0 | 35.0 |
| **Phase 2 total ($k)** | **933.7** | **1,202.4** | **1,581.9** |

### 4.3 Phase 3 — Scaled (12 months)

| Category | Low | Expected | High |
|---|---:|---:|---:|
| Labor (6.5 FTE) | 1,245.0 | 1,554.0 | 1,945.0 |
| Infra OpEx ($12/25/60k/mo × 12) | 144.0 | 300.0 | 720.0 |
| Licenses (1 yr) | 5.5 | 5.5 | 5.5 |
| CapEx (scale/redundancy) | 20.0 | 60.0 | 200.0 |
| **Phase 3 total ($k)** | **1,414.5** | **1,919.5** | **2,870.5** |

### 4.4 Program 3-year TCO

| | Low | Expected | High |
|---|---:|---:|---:|
| Phase 1 — Pilot | $0.23M | $0.29M | $0.37M |
| Phase 2 — Operational | $0.93M | $1.20M | $1.58M |
| Phase 3 — Scaled | $1.41M | $1.92M | $2.87M |
| **Base TCO (3 yr)** | **$2.58M** | **$3.41M** | **$4.82M** |
| Contingency @ 15% (on expected) | — | $0.51M | — |
| **Contingency-loaded TCO (expected)** | | **$3.92M** | |
| **AACE Class-3 band on loaded (−20% / +30%)** | **$3.14M** | **$3.92M** | **$5.10M** |

> **How to read the two bands.** The **component envelope** ($2.58M–$4.82M) is built bottom-up from the manifest's own low/high triplets and is slightly *wider* than the formal Class-3 band because it lets the optional Phase-3 scaling and every quantum/DA path run hot simultaneously. For **budget authorization**, use the contingency-loaded expected **$3.92M** with the formal Class-3 band **$3.14M–$5.10M**. Labor is ~75% of every scenario.

---

## 5. Cost composition (contingency-loaded, expected $3.92M)

| Category | $M | % of program |
|---|---:|---:|
| **Labor** | $2.93M | **~75%** |
| Infra OpEx (cloud/quantum/zK/storage/onchain/monitoring) | $0.39M | ~10% |
| Contingency (15%) | $0.51M | ~13% |
| CapEx (hardware) | $0.08M | ~2% |
| Licenses | $0.02M | <1% |
| **Total** | **$3.92M** | 100% |

---

## 6. Sensitivity analysis — top cost drivers

Single-variable swing on the **3-year base TCO** ($3.41M expected). Ordered tornado (largest first).

| Rank | Driver | Low case | High case | ~Swing on 3-yr TCO | Note |
|---|---|---|---|---:|---|
| 1 | **Engineering headcount / wage** (Phase 2–3) | −1 FTE & low rates | +1–2 FTE & high rates | **±$0.9M** | by far the biggest lever; labor = 75% of program |
| 2 | **Phase-3 scaling intensity** (infra) | $12k/mo | $60k/mo | **±$0.29M** | $144k vs $720k over 12 mo |
| 3 | **GPU / zK proving path** | self-host $12k CapEx | cloud $900–$2,500/mo | **±$0.05–0.07M** | `[vendor]`; CapEx vs OpEx tradeoff |
| 4 | **Quantum cloud usage** (BlueQubit/D-Wave/IBM) | $200/mo | $2,500+/mo | **±$0.06M** | `[vendor]`; kernel runs on sim, so optional |
| 5 | **On-chain path** | Base L2 ~$30/mo | Ethereum L1 ~$1,500/mo | **±$0.04M** | stay on Base unless settlement demands L1 |

### 6.1 Two-variable scenario table — Headcount × Infra path (3-yr TCO, $M, base before contingency)

| | Lean infra (cloud-min, Base L2, low quantum) | Expected infra | Heavy infra (self-host + DA + heavy quantum/zK) |
|---|:--:|:--:|:--:|
| **Lean team** (−1 FTE) | **$2.58M** | $2.85M | $3.25M |
| **Expected team** | $3.10M | **$3.41M** | $3.95M |
| **Scaled team** (+1–2 FTE) | $3.80M | $4.25M | **$4.82M** |

> The matrix confirms: you can move the program by ~$0.7M with infra choices, but ~$1.2M+ with team-size choices. **Manage headcount first.**

---

## 7. Notes, caveats & limitations

- **What this model does NOT capture:** revenue/offsetting income; SBIR/STTR indirect-rate accounting (uses commercial 1.40× loading, not a negotiated NICRA); equity/dilution (see capital plan); wage escalation beyond 36 mo; legal/IP/patent, insurance, audit/certification (ISO/NQA-1) program costs unless folded into labor; partner cost-share inflows.
- **Vendor-confirmation required** on all `[vendor]`-flagged lines (BlueQubit, D-Wave, IBM, zK proving service, cloud GPU, Celestia/EigenDA). These are screening estimates until quoted.
- **Labor is the estimate's center of gravity.** A ±15% miss on blended rate or a single mis-timed hire moves the program more than any infra decision. Tighten this first when moving to Class 2/1.
- **Phase 3 is the widest band** ($1.41M–$2.87M) because decentralization scope (multi-validator vs L2 rollup, DA layer) is still a design decision (`to_build`).
- **Sufficiency:** adequate for **budget authorization, internal planning, and investor discussion**. For **federal submission** (SBIR/STTR), re-cast labor on the negotiated/forward indirect rates and DOE RR 5-year budget format. For **counsel/contract**, pair with the capital plan's dilution and tranche terms.

---

*All figures ESTIMATE · AACE Class 3 (−20%/+30%) · USD 2026 nominal · GHI / QM2ARL. Source of truth: `configs/odl_framework_manifest.yaml`.*
