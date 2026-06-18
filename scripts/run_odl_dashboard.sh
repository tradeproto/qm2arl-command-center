#!/usr/bin/env bash
# ODL Dashboard — Live System Resonance + Ledger Explorer
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
export ODL_API_URL="${ODL_API_URL:-http://127.0.0.1:8000}"
exec streamlit run odl-app/app.py \
  --server.port "${ODL_DASHBOARD_PORT:-8504}" \
  --server.headless true \
  --server.address 0.0.0.0