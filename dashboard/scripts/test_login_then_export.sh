#!/usr/bin/env bash
# Login once (headed), save session, then run Overview export dry-run.
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

echo "=== 1) Login test (saves session) ==="
python -m src.test_login

echo "=== 2) Export dry-run using saved session ==="
BRANCH_HEADED="${BRANCH_HEADED:-1}" python -m src.sync_daily --dry-run --lookback-days "${1:-7}"
