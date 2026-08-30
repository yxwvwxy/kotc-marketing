#!/usr/bin/env bash
# Move files into project inbox/ (used by Finder Quick Action).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INBOX="$ROOT/inbox"
mkdir -p "$INBOX"

if [ "$#" -eq 0 ]; then
  osascript -e 'display alert "KOTC inbox" message "请先在 Finder 里选中要导入的文件，再使用此操作。" as warning' || true
  exit 1
fi

moved=0
for f in "$@"; do
  [ -e "$f" ] || continue
  base="$(basename "$f")"
  dest="$INBOX/$base"
  # Avoid overwrite: add timestamp if name exists
  if [ -e "$dest" ]; then
    stem="${base%.*}"
    ext="${base##*.}"
    if [ "$stem" = "$base" ]; then
      dest="$INBOX/${base}_$(date +%H%M%S)"
    else
      dest="$INBOX/${stem}_$(date +%H%M%S).${ext}"
    fi
  fi
  mv "$f" "$dest"
  moved=$((moved + 1))
done

osascript -e "display notification \"已移入 inbox：${moved} 个文件\" with title \"KOTC inbox\" sound name \"Glass\"" || true
