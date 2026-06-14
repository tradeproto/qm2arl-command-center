# TELPAI-Q × RWA Onboarding Console

One platform to onboard, **quantum-verify**, classify, **Dragon Seal**, and gate
in-ground real-world assets — **natural gas (SPE-PRMS)** and **gold (NI 43-101 / CIM)**.

## Pipeline

```
intake → TELPAI survey → TELPAI-Q quantum verify → classify (PRMS | NI 43-101)
       → QRE/QP package → oracle epoch → Dragon Seal (+ Lighthouse) → Reg D 506 gate
```

The commodity-agnostic spine lives in `src/telpai_rwa/onboarding.py` and is shared
by this UI and the FastAPI `/rwa/*` endpoints, so behavior is identical on both.

## Run

```bash
chmod +x scripts/run_rwa_onboarding.sh
./scripts/run_rwa_onboarding.sh           # http://localhost:8510
./scripts/run_rwa_onboarding.sh 8511      # custom port
```

## Quantum hardware (TELPAI-Q)

Verification runs on a PennyLane VQC kernel. Backend selection:

| Backend | Notes |
|---|---|
| `default.qubit` | Local simulator (default, no setup) |
| `lightning.qubit` | Faster local/GPU sim |
| `bluequbit.cpu` / `bluequbit.gpu` | **Quantum cloud** — set `BLUEQUBIT_API_TOKEN` |

If a BlueQubit backend is selected without a token, it falls back to the local
simulator and notes it in the result.

## Example assets

- Gas: `configs/rwa_rivers_bend_gas.example.json` (Rivers Bend, Upper Houston Embayment)
- Gold: `configs/rwa_gold_mine_ni43101.example.json`

## API equivalents

| Endpoint | Purpose |
|---|---|
| `POST /rwa/onboard` | Full commodity-agnostic spine (this UI's engine) |
| `POST /rwa/verify` | TELPAI-Q quantum verification only |
| `POST /rwa/minerals/classify` | NI 43-101 / CIM classification |
| `POST /rwa/oracle/seal` | Seal an oracle epoch → `.dragon` (+ Lighthouse) |

## Compliance guardrail

TELPAI-Q verification is **supplementary** geophysical evidence. Independent
**QRE** (oil & gas) or **QP** (NI 43-101 minerals) sign-off remains mandatory
before any Reg D 506(c) offering. Inferred resources and prospective resources
cannot be the basis of a primary reserve token.
