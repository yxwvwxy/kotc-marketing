#!/usr/bin/env bash
# Keep this running; drop Branch exports into inbox/ and they import automatically.
#   ./scripts/watch_inbox.sh
#   ./scripts/watch_inbox.sh --dry-run
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

mkdir -p inbox
echo "Inbox: $ROOT/inbox"
exec python -m src.watch_inbox "$@"
