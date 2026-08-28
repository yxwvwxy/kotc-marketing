#!/usr/bin/env bash
# Drop a Branch Summary Excel/CSV into inbox/, then run:
#   ./scripts/import_inbox.sh
# Or pass a file path:
#   ./scripts/import_inbox.sh ~/Downloads/summary-table-export.xlsx
# Dry-run (convert only):
#   ./scripts/import_inbox.sh --dry-run
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
python -m src.import_file "$@"
