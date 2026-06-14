# TELPAI × RWA — Live Integration Guide
**Date:** 2026-06-06 · **Stack:** SPE PRMS · SEC Reg D 506 · TradeProto · DragonSeal · ERC-3643

## What is live now

| Component | Path | Status |
|-----------|------|--------|
| SPE PRMS classification engine | `src/telpai_rwa/prms_engine.py` | **LIVE** |
| Reg D 506(b)/(c) checklist + validator | `src/telpai_rwa/reg_d_506.py` | **LIVE** |
| Reserve oracle epoch (SHA-256 → Dragon Seal) | `src/telpai_rwa/reserve_oracle.py` | **LIVE** |
| QRE data package generator | `src/telpai_rwa/qre_package.py` | **LIVE** |
| RWA API routes | `src/telpai_rwa/api_routes.py` | **LIVE** (mounted on `api_server.py`) |
| Division 12 QM2ARL agents | `configs/compliance_spe_prms.yaml` | **READY TO TRAIN** |
| TELPAI data feeds | `api_server.py` `/data/*` | **LIVE** (USGS, BOEM, EIA, seepage, swarm, etc.) |
| Master framework doc | `~/Documents/.../TELPAI_RWA_Tokenization_Master_Framework.md` | Reference |

## Start the stack

```bash
cd ~/QM2ARL
source .venv/bin/activate   # if using venv
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

## API quick test

```bash
# Health
curl -s http://localhost:8000/rwa/health | jq

# SPE PRMS framework
curl -s http://localhost:8000/rwa/prms/framework | jq

# Classify reserves (PDP example)
curl -s -X POST http://localhost:8000/rwa/prms/classify \
  -H 'Content-Type: application/json' \
  -d '{
    "technical": {"volumetric_confidence":0.85,"seismic_interpretation_confidence":0.80,"magnetometry_anomaly_strength":0.75,"production_history_months":36,"analog_match_score":0.70,"simulation_quality":0.72},
    "commercial": {"price_deck_current":0.82,"opex_breakeven_ratio":0.35,"fiscal_terms_certainty":0.78,"development_plan_approved":true,"regulatory_approval":0.80},
    "is_producing": true
  }' | jq

# Full pipeline (pilot asset)
curl -s -X POST http://localhost:8000/rwa/pipeline/evaluate \
  -H 'Content-Type: application/json' \
  -d @configs/rwa_pilot_asset.example.yaml | jq

# Reg D 506(c) checklist
curl -s 'http://localhost:8000/rwa/regd506/checklist?rule=506c' | jq
```

## Train Division 12 SPE PRMS agents

```bash
python simulations/compliance_audit.py configs/compliance_spe_prms.yaml
```

Eight agents map to SPE PRMS domains:

| Agent | Domain | Role |
|-------|--------|------|
| PRMS-0 | prms_framework_definitions | Geologist — framework & scope |
| PRMS-1 | reserves_classification | Reserves Engineer — 1P/2P/3P |
| PRMS-2 | contingent_resources | Geologist — 1C/2C/3C |
| PRMS-3 | prospective_resources | Prospector — exploration |
| PRMS-4 | technical_evaluation | Petroleum Engineer — volumetrics |
| PRMS-5 | commercial_evaluation | Reserves Economist — commerciality |
| PRMS-6 | uncertainty_aggregation | Geostatistician — P10/P50/P90 |
| PRMS-7 | audit_rwa_tokenization | Audit — SPE standards + on-chain |

## Engineer / Prospector task list

### Week 1 — Wire live feeds to oracle
- [x] On `/rwa/pipeline/evaluate`, `collect_telpai_survey()` pulls BOEM, GGMplus, EMAG2, EIA, USGS, Swarm, FIRMS, POWER (`src/telpai_rwa/telpai_feeds.py`)
- [ ] Store epoch JSON in `data/rwa_epochs/`
- [ ] Anchor SHA-256 on dragonseal.io (Sepolia)

### Week 2 — QRE handoff
- [ ] Export `/rwa/qre/package` JSON → PDF template for QRE firms
- [ ] Engage Ryder Scott / DeGolyer pilot review of package format

### Week 3 — Reg D 506(c) gate
- [ ] Complete checklist in TradeProto compliance module
- [ ] PPM draft with SEC Rule 4-10 reserve definitions
- [ ] Accredited investor verification path (ERC-3643 ModularCompliance)

### Week 4 — First asset tokenization path
- [ ] Delaware SPV formation
- [ ] VPP smart contract test on Sepolia (from Master Framework §5.1)
- [ ] Investor portal MVP — reserve status + oracle feed

## SEC / SPE guardrails (non-negotiable)

1. **Only Proved (1P)** as primary Reg D offering basis — 2P/3P supplemental only
2. **PUD** requires 5-year development plan (SEC Rule 4-10)
3. **Contingent / Prospective** — convertible or exploration tokens, not reserve tokens
4. **QRE independence** — TELPAI generates data package; QRE signs report
5. **Token** = enterprise + verified data + supply agreement — never naked in-ground claim

## Related docs

- `TELPAI_RWA_Tokenization_Master_Framework.md` (QMind_Labs/NotebookLM_Sources)
- `TELPAI_API_Integration_Map.md` (~/Documents)
- `compliance_spe_prms.yaml` — agent training config