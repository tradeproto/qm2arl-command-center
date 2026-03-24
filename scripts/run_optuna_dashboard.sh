#!/usr/bin/env bash
# Start Optuna Dashboard — leave this terminal open, then open http://localhost:8080
# From repo root: ./scripts/run_optuna_dashboard.sh
set -e
cd "$(dirname "$0")/.."
DB="${1:-telpai_study.db}"
if [ ! -f "$DB" ]; then
  echo "No $DB found. Run tuning first: python3 scripts/tune.py --n-trials 1"
  exit 1
fi
echo "Starting Optuna Dashboard for sqlite:///$DB"
echo "  → Leave this terminal open, then open in browser: http://localhost:8080"
echo "  → Ctrl+C to stop"
exec optuna-dashboard "sqlite:///$DB" --host 127.0.0.1 --port 8080
