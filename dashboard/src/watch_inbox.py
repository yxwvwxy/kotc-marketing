#!/usr/bin/env python3
"""Watch inbox/ and auto-import Branch exports when new files appear.

Usage:
  ./scripts/watch_inbox.sh
  python -m src.watch_inbox
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

from src.import_file import DEFAULT_INBOX, EXPORT_SUFFIXES, ImportAborted, import_export

# Load .env if present (watcher may be started without the shell script)
ROOT = Path(__file__).resolve().parents[1]


def _applescript_quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def mac_notify(title: str, message: str, *, alert: bool = False) -> None:
    """Show a macOS notification; use alert=True for a hard-to-miss dialog."""
    title_q = _applescript_quote(title)
    # Keep message short enough for Notification Center / alert UI
    body = message.strip()
    if len(body) > 500:
        body = body[:500] + "…"
    msg_q = _applescript_quote(body)
    if alert:
        script = f"display alert {title_q} message {msg_q} as critical"
    else:
        script = (
            f"display notification {msg_q} with title {title_q} "
            f'sound name "Glass"'
        )
    try:
        # Non-blocking: a modal alert must not stall the import loop for 30s.
        subprocess.Popen(
            ["osascript", "-e", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        print(f"mac notify failed: {exc}", flush=True)


def reveal_in_finder(path: Path) -> None:
    try:
        subprocess.run(["open", "-R", str(path)], check=False, timeout=10)
    except Exception:
        pass


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        # Prefer .env values so LaunchAgent always picks up local credentials.
        if key:
            os.environ[key] = value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Auto-import files dropped into inbox/")
    p.add_argument("--inbox", default=None, help=f"Inbox dir (default: {DEFAULT_INBOX})")
    p.add_argument(
        "--poll-seconds",
        type=float,
        default=2.0,
        help="How often to scan inbox (default: 2)",
    )
    p.add_argument(
        "--stable-seconds",
        type=float,
        default=1.5,
        help="Wait until file size is unchanged this long before import",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Convert only; do not write BigQuery",
    )
    return p.parse_args()


def _write_error_note(export_path: Path, message: str) -> Path:
    """Leave a visible .ERROR.txt next to a failed export (no Terminal needed)."""
    note = export_path.with_name(f"{export_path.stem}.ERROR.txt")
    note.write_text(message.strip() + "\n", encoding="utf-8")
    print(f"已写入错误说明: {note.name}", flush=True)
    return note


def list_exports(inbox: Path) -> list[Path]:
    if not inbox.exists():
        return []
    return sorted(
        [
            p
            for p in inbox.iterdir()
            if p.is_file()
            and p.suffix.lower() in EXPORT_SUFFIXES
            and not p.name.startswith(".")
            and not p.name.startswith("~")
        ],
        key=lambda p: p.stat().st_mtime,
    )


def wait_until_stable(path: Path, stable_seconds: float, poll: float = 0.4) -> bool:
    """Return True if file stays same size for stable_seconds; False if it disappears."""
    try:
        last = path.stat().st_size
    except FileNotFoundError:
        return False
    stable_for = 0.0
    while stable_for < stable_seconds:
        time.sleep(poll)
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return False
        if size == last and size > 0:
            stable_for += poll
        else:
            last = size
            stable_for = 0.0
    return True


def main() -> None:
    _load_dotenv()
    args = parse_args()
    inbox = Path(args.inbox).expanduser().resolve() if args.inbox else DEFAULT_INBOX
    inbox.mkdir(parents=True, exist_ok=True)

    # fingerprint -> already attempted (avoid tight retry loops on bad files)
    attempted: dict[str, tuple[float, int]] = {}

    print(f"Watching inbox: {inbox}")
    print("Drop a Branch .xlsx / .xls / .csv here — import starts automatically.")
    print("缺字段时会在此打印提示，文件保留；成功后会删除文件。")
    print("Ctrl+C 停止。\n", flush=True)

    while True:
        try:
            for path in list_exports(inbox):
                try:
                    st = path.stat()
                except FileNotFoundError:
                    continue
                fp = (st.st_mtime, st.st_size)
                key = str(path.resolve())
                if attempted.get(key) == fp:
                    continue

                print(f"\n[{time.strftime('%H:%M:%S')}] 发现文件: {path.name} — 等待写入完成...", flush=True)
                if not wait_until_stable(path, args.stable_seconds):
                    continue

                try:
                    st = path.stat()
                    fp = (st.st_mtime, st.st_size)
                except FileNotFoundError:
                    continue

                print(f"[{time.strftime('%H:%M:%S')}] 开始导入: {path.name}", flush=True)
                try:
                    n = import_export(path, inbox=inbox, dry_run=args.dry_run)
                    print(f"[{time.strftime('%H:%M:%S')}] 完成 ({n} rows)\n", flush=True)
                    attempted.pop(key, None)
                    for note in inbox.glob(f"{path.stem}.ERROR*.txt"):
                        note.unlink(missing_ok=True)
                    mac_notify(
                        "Branch 导入成功",
                        f"{path.name}\n已写入 BigQuery：{n} 行",
                        alert=True,
                    )
                except ImportAborted as exc:
                    print(f"\n*** {exc}\n", flush=True)
                    attempted[key] = fp
                    note = _write_error_note(path, str(exc))
                    mac_notify("Branch 导入失败", str(exc), alert=True)
                    if note is not None:
                        reveal_in_finder(note)
                except Exception:
                    msg = traceback.format_exc()
                    print(f"\n*** 导入失败（文件保留）:\n{msg}", flush=True)
                    attempted[key] = fp
                    note = _write_error_note(path, f"导入失败（文件保留）:\n{msg}")
                    mac_notify(
                        "Branch 导入失败",
                        f"{path.name} 导入出错，详见 inbox 里的 .ERROR.txt",
                        alert=True,
                    )
                    if note is not None:
                        reveal_in_finder(note)

            # Drop attempted entries for files that were removed
            existing = {str(p.resolve()) for p in list_exports(inbox)}
            for k in list(attempted):
                if k not in existing:
                    attempted.pop(k, None)

            time.sleep(args.poll_seconds)
        except KeyboardInterrupt:
            print("\nStopped watching.", flush=True)
            sys.exit(0)


if __name__ == "__main__":
    main()
