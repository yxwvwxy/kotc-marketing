#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f .venv/bin/activate ]; then
  echo "Missing .venv — run ./scripts/setup_local.sh first"
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

python -m playwright install chromium >/dev/null
python -m src.test_login
