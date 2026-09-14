#!/usr/bin/env python3
"""Import a manually downloaded Branch Summary Excel/CSV into BigQuery.

Cleans the file and APPENDS all rows — does not delete existing BigQuery data.
Example: table ends at 8/5, file has 8/5–8/10 → those rows are appended as-is.

Usage:
  ./scripts/import_inbox.sh
  ./scripts/import_inbox.sh ~/Downloads/summary-table-export.xlsx
  ./scripts/import_inbox.sh --dry-run
  ./scripts/watch_inbox.sh          # auto-import when files appear in inbox/
  python -m src.import_file
  python -m src.import_file path/to/export.xlsx --dry-run
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

from src.config import Settings

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INBOX = ROOT / "inbox"
EXPORT_SUFFIXES = {".xlsx", ".xls", ".csv"}


class ImportAborted(Exception):
    """Raised when import is stopped before writing BigQuery (e.g. missing columns)."""


def _load_convert_module():
    path = ROOT / "bigquery" / "convert_branch_export.py"
    spec = importlib.util.spec_from_file_location("convert_branch_export", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load converter at {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Clean a Branch export and APPEND rows into BigQuery"
    )
    p.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Excel/CSV path. If omitted, use newest file in inbox/",
    )
    p.add_argument(
        "--inbox",
        default=None,
        help=f"Inbox directory (default: {DEFAULT_INBOX})",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Convert only; do not write BigQuery",
    )
    return p.parse_args()


def resolve_export_path(path_arg: str | None, inbox: Path) -> Path:
    if path_arg:
        path = Path(path_arg).expanduser().resolve()
        if not path.exists():
            raise ImportAborted(f"File not found: {path}")
        if path.suffix.lower() not in EXPORT_SUFFIXES:
            raise ImportAborted(
                f"Unsupported file type {path.suffix!r}. Use .xlsx, .xls, or .csv"
            )
        return path

    inbox.mkdir(parents=True, exist_ok=True)
    candidates = [
        p
        for p in inbox.iterdir()
        if p.is_file() and p.suffix.lower() in EXPORT_SUFFIXES and not p.name.startswith(".")
    ]
    if not candidates:
        raise ImportAborted(
            f"No .xlsx/.xls/.csv in {inbox}\n"
            "Drop your Branch Summary export there, then re-run:\n"
            "  ./scripts/import_inbox.sh"
        )
    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    print(f"Using newest inbox file: {newest.name}")
    return newest.resolve()


def import_export(
    export_path: Path,
    *,
    inbox: Path | None = None,
    dry_run: bool = False,
) -> int:
    """Convert and append one export file. Returns rows written (0 on dry-run).

    On success, deletes the file if it lives under inbox/.
    Raises ImportAborted for validation failures (file is kept).
    """
    inbox = (inbox or DEFAULT_INBOX).resolve()
    export_path = export_path.expanduser().resolve()
    settings = Settings.from_env(require_branch_login=False)
    convert_mod = _load_convert_module()

    missing = convert_mod.missing_required_columns(export_path)
    if missing:
        raise ImportAborted(
            f"文件: {export_path.name}\n"
            "导入中止：导出文件缺少必填字段，未写入 BigQuery，inbox 文件保留。\n"
            f"缺少: {', '.join(missing)}\n"
            "请在 Branch Customize Columns / Compare by 补齐后再导出。"
        )

    optional_missing = convert_mod.missing_optional_columns(export_path)
    if optional_missing:
        print(
            "Optional columns missing in export (written as null): "
            + ", ".join(optional_missing)
        )

    print(f"Importing: {export_path}")

    rows, skipped = convert_mod.convert_to_rows(export_path)
    upload_csv = convert_mod.convert(export_path)
    print(f"Converted rows: {len(rows)} (skipped {skipped})")
    print(f"Upload CSV: {upload_csv}")

    if not rows:
        raise ImportAborted(
            "导入中止：转换后 0 行，未写入 BigQuery，inbox 文件保留。\n"
            "请确认导出包含 date 列，且是按天明细（不只是合计）。"
        )

    dates = sorted({r["date"] for r in rows})
    print(f"Dates in file: {dates[0]} -> {dates[-1]} ({len(dates)} distinct days)")
    print("Sample row:", rows[0])

    if dry_run:
        print("Dry run complete — BigQuery not modified.")
        return 0

    from src.bigquery_loader import BigQueryLoader

    loader = BigQueryLoader(settings.table_id)
    n = loader.append_rows(rows)
    print(f"Done. Appended {n} rows to {settings.table_id}")

    try:
        export_path.relative_to(inbox)
    except ValueError:
        pass
    else:
        export_path.unlink(missing_ok=True)
        print(f"Removed inbox file: {export_path.name}")
    return n


def main() -> None:
    args = parse_args()
    inbox = Path(args.inbox).expanduser().resolve() if args.inbox else DEFAULT_INBOX
    try:
        export_path = resolve_export_path(args.path, inbox)
        import_export(export_path, inbox=inbox, dry_run=args.dry_run)
    except ImportAborted as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
