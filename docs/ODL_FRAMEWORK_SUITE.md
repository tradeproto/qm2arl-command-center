# Omni-Dimensional Ledger — Framework Suite

**What we need to build to run the Omni-Dimensional Ledger (ODL) operationally:
the Trinity Value Matrix, the zK-proof + data subsystems, the node network, the
hardware, and the cost to run it.**

Green Horizon Innovation LLC · QM2ARL Lab · v0.1
Companion to `docs/ODL_ARCHITECTURE.md` and the whitepaper.
Live status & cost: `python -m src.odl.nodes` (reads `configs/odl_framework_manifest.yaml`)

---

## 0. Honest taxonomy & cost discipline

Following the whitepaper's rule — aspiration is not dressed as accomplishment.

- **Build status:** `operational` (runs today) · `partial` (core built, hardening/scale left) · `to_build` (designed, not implemented).
- **Costs are AACE Class 5** (concept-screening) estimates, accuracy ≈ **−50% / +100%**. Quantum-cloud and zK-proving prices must be vendor-confirmed before commitment.
- **Engineering labor is the dominant real cost.** Infrastructure OpEx is comparatively small; do not read the infra rollup as the program budget.

**Current state (auto-computed): ~52% overall build completion.** The value,
AI, oracle, and gateway layers are mostly built; proof, ledger-consensus, and
storage layers are where the new work concentrates.

---

## 1. The eight-layer stack

| # | Layer | What it does | Completion |
|---|---|---|---|
| 1 | **Value & Resonance** | Trinity Value Matrix → N-dimensional value space; System Resonance kernel | ~75% |
| 2 | **Optimization & AI** | QM2ARL agents; Divisions 10–14; General AI governor; efficiency layer | ~88% |
| 3 | **Quantum Compute** | VQC kernel + annealing on BlueQubit / D-Wave / IBM ladder | ~38% |
| 4 | **Oracle & Verification** | TELPAI-Q verification + government/geo/AI data feeds | ~83% |
| 5 | **Proof** | zK proofs of the resonance computation + DragonSeal attestation | ~25% |
| 6 | **Ledger & Consensus** | Append-only hash-linked resonance chain; sealer/validator set | ~17% |
| 7 | **Storage & Data** | Postgres index, state DB, IPFS/Filecoin, data availability | ~12% |
| 8 | **Access & Gateway** | APIs, AutoQMS, RWA console, ODL dashboard | ~75% |

---

## 2. The Trinity Value Matrix → Omni-Dimensional value space

**Operational.** `src/odl/dimensions.py` + `resonance.py`. The whitepaper's
3-axis Trinity (economic · ecological · social) generalized to **6 measured
dimensions** — Prosperity, Planet, Equity, Health, Knowledge (Coherence),
Connection (Love). System Resonance `R = M·(½ρ + ½Q)` combines magnitude,
Kuramoto phase coherence ρ, and quantum-kernel coherence Q. The General AI
governor enforces per-dimension **value floors** (HALT/REBALANCE/PROCEED).

**To build:** broaden live coverage (Planet/Health/Equity telemetry), the
Super AI tier (ASPIRATIONAL), and the ODL dashboard.

---

## 3. zK proofs & the proof databases

**Goal:** prove that "this resonance / audit / reserve score was computed
honestly from this data, by this model" **without exposing the raw data** —
then anchor a succinct proof on-chain.

### Recommended proving stack (to_build)

| Choice | Recommendation | Why |
|---|---|---|
| **General-compute proofs** | **RISC Zero zkVM** or **SP1** (Rust zkVM) | Prove the actual Python/Rust resonance + audit computation as-is; no hand-written circuits. Best fit for our evolving math. |
| **Circuit-specific proofs** | Groth16 / PLONK / Halo2 (via `gnark`/`circom`) | If/when a hot path (e.g. Kuramoto order parameter, kernel) needs a tiny, cheap on-chain verifier. |
| **Alternative** | Cairo / StarkNet | If we move to a Starknet-native deployment. |
| **On-chain verifier** | Solidity verifier on **Base** (L2) | Cheap gas; DragonSeal already targets Ethereum/Base. |

**Proof databases / state:**

| Need | Choice |
|---|---|
| **Verifiable state root** | Merkle (or Verkle) trie over **RocksDB/LMDB** → one root hash per epoch the zK proof commits to |
| **Working index (queryable)** | **Postgres** feature store (migrate from current SQLite `autoqms-app/db.py`) + optional **The Graph** for epoch queries |
| **Blob / evidence permanence** | **IPFS + Filecoin via Lighthouse** (already integrated, `scripts/lighthouse_pin.py`) |
| **Data availability (optional, decentralized)** | **Celestia** or **EigenDA** |

**What's already real:** DragonSeal SHA-256 attestation (`partial` — local seal
ready, on-chain anchor pending) and Lighthouse pinning (`partial`). The zK layer
(`zk_prover`, `zk_verifier_contract`) is `to_build`.

---

## 4. Large data models & access

### Data feeds (operational — `src/telpai_rwa/telpai_feeds.py`, `api_server.py`)

Government/geophysical: **BOEM** (leases), **USGS** (seismic), **EIA** (prices),
**NOAA EMAG2** (magnetics), **NASA POWER/FIRMS** (irradiance/flares),
**ESA Swarm** (magnetics), **Curtin GGMplus** (gravity), Sentinel seepage, IHFC
heat flow.

### AI / model access

| Model class | Status | Access |
|---|---|---|
| QM2ARL multi-agent RL (Divisions 1–14) | operational | in-repo |
| Quantum kernel (8-wire VQC) | operational (sim) | `src/quantum_geospatial.py` |
| BlueQubit gate cloud | partial | `BLUEQUBIT_API_TOKEN` |
| LLM reasoning (xAI Grok — topology, assistant) | partial | API key |
| Domain corpora (SPE-PRMS, NI 43-101, GCP/ICH) | operational | configs + training summaries |

**To build:** a unified **Data Access Layer / feature store** (Postgres + object
store + a feed scheduler with retry/caching/signing) so every node reads a
consistent, versioned snapshot. Today feeds are pulled live per request.

---

## 5. Node network — what we program

Eight daemon types. Run-status from the manifest:

| Node | Role | Status |
|---|---|---|
| **Resonance node** | Compute System Resonance from signals | operational (`src/odl/engine.py`) |
| **Governor node** | General AI value-floor governance | operational (`src/odl/governance.py`) |
| **Gateway node** | Serve APIs + UIs | operational (`api_server.py`, AutoQMS, RWA console) |
| **Oracle node** | Ingest feeds, run TELPAI-Q verify, sign observations | partial |
| **Sealer/Validator node** | Validate, hash-link, DragonSeal, anchor on-chain | partial |
| **Archive node** | Pin epochs + evidence to IPFS/Filecoin | partial |
| **Prover node** | Generate zK proofs of computations | to_build |
| **Indexer node** | Index epochs/docs into Postgres/Graph for query | to_build |

**Minimum operational set (Phase 2):** resonance + governor + oracle + sealer +
archive + gateway on a single trusted operator (single-sequencer). Prover and a
second validator come with decentralization (Phase 3).

---

## 6. Hardware — what we run the ledger on

| Tier | Role | Status | Cost |
|---|---|---|---|
| **Dev workstation** (Linux main) | development, simulation, agent training | operational | CapEx ~$3k |
| **Office server** (Linux) | APIs, ledger, Postgres, oracle/sealer daemons | partial | CapEx ~$3k |
| **GPU prover/trainer node** | RL training, quantum sim, zK proving | to_build | CapEx ~$12k (or rent cloud GPU) |
| **Windows SolidWorks station** | Chapman engineering loop | partial | CapEx ~$2.8k + SW license ~$4k/yr |
| **Cloud VMs** (DigitalOcean, incl. `209.38.65.13`) | production nodes | operational | ~$150/mo |
| **Cloud GPU** (A100/H100 on-demand) | alternative to GPU CapEx | to_build | ~$900/mo |

**Quantum hardware:** the ledger's resonance kernel does **not** require quantum
hardware to run (it falls back to local simulation). The device ladder is:
**BlueQubit cloud** (primary gate path, `partial`) → **D-Wave Leap** (annealing,
optional `to_build`) → **IBM Quantum** (optional). Honest scope: at 6–8 qubits
the kernel is classically simulable — quantum is a scale-ready upgrade path, not
a present-day advantage claim.

**The three-machine office topology** (from earlier): Linux main (dev) + Linux
office server (services/ledger) + Windows box (SolidWorks), plus a GPU node for
proving/training. That is the minimal operational footprint.

---

## 7. Cost to run it (AACE Class 5 — estimates)

Auto-rolled from the manifest. **Infra only; labor separate.**

| | Monthly OpEx | One-time CapEx |
|---|---|---|
| **Component rollup** | ~$3,000 expected ($950–$14,750) | ~$20,800 expected ($14k–$37.5k) |

### Phased envelopes

| Phase | Scope | Monthly OpEx | CapEx |
|---|---|---|---|
| **1 — Pilot** | Resonance kernel + ledger + governor + RWA/clinical audits on existing cloud; local seal; quantum on sim/credits | **~$1,200** ($600–$2,500) | ~$0 (use existing) |
| **2 — Operational** | Postgres store, oracle daemon, sealer/validator, zK prover, on-chain anchor (Base), ODL dashboard | **~$5,000** ($2,500–$11,000) | **~$18,000** ($8k–$35k) |
| **3 — Scaled / decentralized** | Multi-validator or L2 rollup, data-availability layer, regional redundancy, edge TELPAI sensing | **~$25,000** ($12k–$60k) | **~$60,000** ($20k–$200k) |

### Cost drivers worth flagging

- **GPU/zK proving** is the single biggest swing — self-host (~$12k CapEx) vs cloud (~$900–$2,500/mo).
- **Quantum cloud (BlueQubit)** — confirm subscription/credit pricing; modeled $200–$2,500/mo.
- **On-chain anchoring on Base** is cheap when batched (~$30/mo); Ethereum L1 would be far more.
- **Labor dominates.** A Phase-2 build team (≈1 zK/protocol + 1 backend/infra + 1 ML/quantum + 0.5 frontend) is the real budget line — infra is a rounding error next to it.

---

## 8. Build roadmap (what to program, in order)

**Phase 1 — Pilot:**
1. ✅ Resonance kernel, ledger chain, General AI governor (`src/odl`)
2. ✅ Divisions 10–14 audit agents; RWA + clinical onboarding (Div 14 in Knowledge avg)
3. ✅ ODL dashboard — `streamlit run odl-app/app.py --server.port 8504` (pm2: `odl-dashboard`)
4. ✅ Anchor module — `src/odl/anchor.py` + `POST /odl/anchor` + `python -m src.odl --anchor-dry-run`
   (broadcast when `DRAGON_SEAL_*` env set; Sepolia or Base)

**Phase 2 — Operational:**
5. ◻ Postgres feature store + Data Access Layer + feed scheduler (oracle node hardening)
6. ◻ Sealer/validator node service (sign + hash-link + anchor)
7. ◻ **zK prover node** (RISC Zero zkVM/SP1) + on-chain verifier on Base
8. ◻ State DB (Merkle/Verkle trie) committing per-epoch roots
9. ◻ GPU node (or cloud) for training + proving

**Phase 3 — Scaled / decentralized:**
10. ◻ Multi-validator consensus **or** L2 rollup deployment
11. ◻ Data-availability layer (Celestia/EigenDA)
12. ◻ Regional redundancy, edge TELPAI sensing, Super AI governance research (with human oversight)

---

## 9. Run the status tool

```bash
python -m src.odl.nodes            # build completion + node inventory + cost rollup
python -m src.odl.nodes --json     # machine-readable
```

Edit `configs/odl_framework_manifest.yaml` to update build status or costs; the
tool re-rolls automatically — the framework reports its own readiness.

---

*Status, costs, and scope are screening-level and will tighten as vendors,
partners, and the Aqul/Chapman engineering team are confirmed. The kernel is
real today; this suite is the map from here to operational at scale.*
