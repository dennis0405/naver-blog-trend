from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from src.common.report import write_daily_collection_report
from src.common.time import resolve_date


def main() -> None:
    parser = argparse.ArgumentParser(description="Prune raw date directories older than retention.")
    parser.add_argument("--raw-dir", default="raw")
    parser.add_argument("--keep-days", type=int, default=7)
    parser.add_argument("--date", default="today")
    args = parser.parse_args()

    date_value = resolve_date(args.date)
    deleted = prune_raw_directories(args.raw_dir, date_value=date_value, keep_days=args.keep_days)
    write_daily_collection_report(date_value=date_value, raw_dir=args.raw_dir, deleted_dirs=deleted)


def prune_raw_directories(raw_dir: str | Path, *, date_value: str, keep_days: int) -> list[str]:
    if keep_days < 1:
        raise ValueError("keep_days must be >= 1")
    base = Path(raw_dir)
    if not base.exists():
        return []

    today = datetime.strptime(date_value, "%Y-%m-%d").date()
    cutoff = today - timedelta(days=keep_days - 1)
    deleted: list[str] = []
    for child in base.iterdir():
        if not child.is_dir():
            continue
        try:
            child_date = datetime.strptime(child.name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if child_date < cutoff:
            shutil.rmtree(child)
            deleted.append(child.name)
    return sorted(deleted)


if __name__ == "__main__":
    main()

