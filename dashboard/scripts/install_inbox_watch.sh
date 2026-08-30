#!/usr/bin/env bash
# Install a macOS LaunchAgent that watches inbox/ in the background.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.kotc.branch-inbox-watch"
PLIST_DST="$HOME/Library/LaunchAgents/${LABEL}.plist"
PYTHON="$ROOT/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
  echo "Missing $ROOT/.venv — run ./scripts/setup_local.sh first"
  exit 1
fi

mkdir -p "$ROOT/logs" "$ROOT/inbox" "$HOME/Library/LaunchAgents"

cat > "$PLIST_DST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>${LABEL}</string>
	<key>ProgramArguments</key>
	<array>
		<string>${PYTHON}</string>
		<string>-m</string>
		<string>src.watch_inbox</string>
	</array>
	<key>WorkingDirectory</key>
	<string>${ROOT}</string>
	<key>RunAtLoad</key>
	<true/>
	<key>KeepAlive</key>
	<true/>
	<key>LimitLoadToSessionType</key>
	<string>Aqua</string>
	<key>ProcessType</key>
	<string>Interactive</string>
	<key>StandardOutPath</key>
	<string>${ROOT}/logs/inbox-watch.log</string>
	<key>StandardErrorPath</key>
	<string>${ROOT}/logs/inbox-watch.err.log</string>
	<key>EnvironmentVariables</key>
	<dict>
		<key>PATH</key>
		<string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
	</dict>
</dict>
</plist>
EOF

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
