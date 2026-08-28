#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env — fill BRANCH_EMAIL, BRANCH_PASSWORD, GOOGLE_APPLICATION_CREDENTIALS"
else
  echo ".env already exists"
fi

echo "Setup done."
echo "  1) Edit $ROOT/.env (BRANCH_EMAIL / BRANCH_PASSWORD)"
echo "  2) Optional: set BRANCH_SUMMARY_URL and BRANCH_HEADED=1 for first run"
echo "  3) Run: ./scripts/dry_run.sh"
