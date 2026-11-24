#!/usr/bin/env bash
# Start VitaLens on macOS / Linux: sets up Python, demo accounts, then opens http://localhost:8000
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "Setting up (first run only)..."
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
[ -f .env ] || cp .env.example .env
[ -f data/accounts.json ] || .venv/bin/python scripts/create_accounts.py --demo
echo ""
echo "VitaLens is running at http://localhost:8000"
echo "Demo sign-in: PC0989 / vitalens-demo   (also PC0387, PC0560)"
echo "Press Ctrl+C to stop."
( sleep 2; (command -v open >/dev/null && open http://localhost:8000) || (command -v xdg-open >/dev/null && xdg-open http://localhost:8000) ) >/dev/null 2>&1 &
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
