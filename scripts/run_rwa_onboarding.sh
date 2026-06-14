#!/usr/bin/env bash
# Launch the TELPAI-Q × RWA Onboarding console.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${1:-8510}"
cd "$ROOT"
[[ -f .env ]] && set -a && . ./.env && set +a || true
echo "TELPAI-Q RWA Onboarding → http://localhost:${PORT}"
exec streamlit run rwa-onboarding/app.py --server.port "${PORT}" --server.headless true
