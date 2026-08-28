#!/usr/bin/env bash
set -euo pipefail
LABEL="com.kotc.branch-inbox-watch"
PLIST_DST="$HOME/Library/LaunchAgents/${LABEL}.plist"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$PLIST_DST"
echo "Stopped and removed $LABEL"
