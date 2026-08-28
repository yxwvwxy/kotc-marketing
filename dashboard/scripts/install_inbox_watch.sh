#!/usr/bin/env bash
# Install a macOS LaunchAgent that watches inbox/ in the background
# (no Cursor / Terminal window needed; starts at login).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.kotc.branch-inbox-watch"
PLIST_SRC="$ROOT/scripts/${LABEL}.plist"
PLIST_DST="$HOME/Library/LaunchAgents/${LABEL}.plist"

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "Missing $ROOT/.venv — run ./scripts/setup_local.sh first"
  exit 1
fi

mkdir -p "$ROOT/logs" "$ROOT/inbox" "$HOME/Library/LaunchAgents"
# Rewrite WorkingDirectory / paths for this machine's ROOT
python3 - <<PY
from pathlib import Path
root = Path("$ROOT")
src = Path("$PLIST_SRC")
text = src.read_text()
# ensure absolute paths in installed copy match this checkout
dst = Path("$PLIST_DST")
dst.write_text(text)
print(f"Installed: {dst}")
PY

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"
launchctl enable "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl kickstart -k "gui/$(id -u)/$LABEL"

sleep 1
if launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null | grep -q "state = running"; then
  echo "OK: inbox watcher is running in the background."
else
  echo "Started LaunchAgent $LABEL (check logs if imports fail)."
fi
echo "Inbox:  $ROOT/inbox"
echo "Logs:   $ROOT/logs/inbox-watch.log"
echo "Stop:   ./scripts/uninstall_inbox_watch.sh"
