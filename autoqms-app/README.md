# AutoQMS Web App — Chapman Test Drive

Industrial-grade AI quality & compliance platform for **Chapman Nuclear x Green Horizon Innovation**.

## Quick Start (Joshua or Eric)

```bash
cd ~/QM2ARL
./scripts/run_autoqms.sh
```

Open **http://localhost:8502** → sidebar → **Chapman Test Drive**.

## 5-Minute Test Drive

1. **Chapman Test Drive** — click **Run Chapman NQA-1 Gap Analysis Now**
2. **Gap Analysis** — review NQA-1 findings (Req 3, 6, 16, 18 are the hot spots)
3. **CAPA Management** — create a CAR from a gap finding
4. **Document Library** — browse 30+ GHI controlled QMS/NQA-1 docs (Dragon Seal attested)
5. **Dragon Seal Signing** — verify QMS-003 attestation in history tab

## Demo vs. Real Data

| Mode | What it does |
|---|---|
| **Chapman Nuclear Pilot** | Uses 4 demo docs in `autoqms-app/demo/` — safe for test drive |
| **Upload Documents** | Eric can upload real Chapman QA manuals (stays local in browser session) |
| **Compliance Training** | Runs Division 10/11 agents via Master Console API (optional) |

## Optional: Master Console API

For live compliance agent training:

```bash
# Terminal 1
cd ~/QM2ARL/master-console && uvicorn server:app --port 8001 --reload

# Terminal 2
./scripts/run_autoqms.sh
```

Without the API, training shows the terminal command fallback.

## Document Sources

- **Primary:** `~/Documents/AutoQMS_Platform/QMS_Controlled_Documents/`
- **Repo sync:** `~/QM2ARL/qms/`
- **Demo corpus:** `~/QM2ARL/autoqms-app/demo/`

## Ports

| Service | Port |
|---|---|
| AutoQMS (this app) | 8502 |
| Master Console API | 8001 |
| Master Console UI | 8501 |

---

*Green Horizon Innovation LLC (SDVOSB) · Chapman Nuclear · AutoQMS Division 10 & 11*
