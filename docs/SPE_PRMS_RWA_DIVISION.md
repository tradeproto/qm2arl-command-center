# Division 12 — SPE PRMS Geologist / RWA Reserves Audit

**Green Horizon Innovation LLC (SDVOSB)**  
**Product:** AutoQMS Division 12 — SPE PRMS Reserves Audit Agent  
**Use case:** Audit oil & gas reserves and resources per SPE global standards; support **RWA tokenization** with Dragon Seal + Trade Proto proof chain  
**Date:** 2026-06-06  
**Status:** Initial implementation

---

## 1. Why This Division Exists

The **Society of Petroleum Engineers (SPE)** sets the global standard for valuing and auditing oil and gas assets through:

- **Petroleum Resources Management System (PRMS)** — classification of reserves and resources
- **Standards Pertaining to the Estimating and Auditing of Oil and Gas Reserves Information** — audit procedures for reserves reports

Green Horizon's **RWA tokenization** platform (Trade Proto, ERC-3643, Dragon Seal) requires **auditable, third-party-defensible** reserves documentation before intrinsic asset value can be placed on-chain. Division 12 automates gap analysis, audit prep, and proof-chain packaging for tokenized petroleum assets.

---

## 2. Agent Roster (GEO-0 … GEO-7)

| Agent | Role | PRMS / SPE Domain |
|---|---|---|
| **GEO-0** | PRMS Framework Lead | Principles, definitions, scope, classification system |
| **GEO-1** | Reserves Classification | Proved / Probable / Possible (1P / 2P / 3P) |
| **GEO-2** | Contingent Resources | 1C / 2C / 3C, development status, commerciality |
| **GEO-3** | Prospective Resources | Exploration maturity, chance of development |
| **GEO-4** | Technical Evaluation | Volumetrics, simulation, material balance, decline analysis |
| **GEO-5** | Commercial Evaluation | Price deck, opex/capex, fiscal terms, economic limit |
| **GEO-6** | Uncertainty & Aggregation | P10/P50/P90, aggregation rules, determinism vs probabilistic |
| **GEO-7** | Audit & RWA Tokenization | SPE audit standards, third-party review, Dragon Seal attestation |

**Config:** `configs/compliance_spe_prms.yaml`  
**Training:** `python simulations/compliance_audit.py configs/compliance_spe_prms.yaml`

---

## 3. RWA Tokenization Workflow

```
Reserves report (PDF/DOCX) + technical data room
        │
        ▼
Division 12 agents — PRMS gap analysis
        │
        ├── GEO-1..6 — classification, technical, commercial, uncertainty scores
        │
        ▼
GEO-7 — Audit readiness + proof package
        │
        ├── SHA-256 reserves report + audit opinion
        ├── Dragon Seal on-chain attestation
        ├── Lighthouse IPFS pin (permanent)
        └── ERC-3643 / Trade Proto RWA metadata (volume class, P50, effective date)
```

**Qualified human authority:** Licensed Petroleum Engineer (PE) or Certified Petroleum Geologist signs reserves opinion — AI drafts and audits; humans certify per QMS-003.

---

## 4. Standards Corpus (ENGRAM reference set)

| Standard | Purpose |
|---|---|
| SPE-PRMS 2018 | Resources classification framework |
| SPE Reserves Definitions | Proved / probable / possible criteria |
| SPE/WPC/AAPG/SPEE Auditing Standards | Third-party reserves audit procedures |
| SEC S-X / S-K (optional) | US public reporting alignment |
| NI 51-101 (optional) | Canadian reserves disclosure |

---

## 5. Revenue / GTM

| Tier | What | Price | Target |
|---|---|---|---|
| **PRMS Gap Analysis** | Upload reserves report → PRMS compliance score | $8K–$15K | E&P operators, asset sellers |
| **RWA Audit Package** | Full audit prep + Dragon Seal + token metadata | $15K–$40K | RWA issuers, tokenization platforms |
| **Continuous Monitoring** | Re-audit on material change (price, production) | $3K–$8K/mo | Tokenized asset SPVs |

---

## 6. Integration with AutoQMS Live

- **Gap Analysis** — select **SPE PRMS 2018** standard
- **Compliance Training** — Division 12 preset `spe_prms`
- **QA Assistant** — ask about reserves classification, P50 disclosure, RWA readiness
- **Master Console** — `train_compliance` preset `spe_prms`

---

*GHI · AutoQMS Division 12 · SPE PRMS · RWA Tokenization*
