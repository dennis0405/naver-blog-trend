from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from src.common.report import write_daily_collection_report
from src.common.time import resolve_date


def main() -> None:
    parser = argparse.ArgumentParser(description="Prune date-based raw data and daily reports.")
    parser.add_argument("--raw-dir", default="raw")
    parser.add_argument("--report-dir", default="data/reports/daily")
    parser.add_argument("--keep-days", type=int, default=7)
    parser.add_argument("--date", default="today")
    args = parser.parse_args()

    date_value = resolve_date(args.date)
    deleted_raw_dirs = prune_raw_directories(
        args.raw_dir,
        date_value=date_value,
        keep_days=args.keep_days,
    )
    deleted_report_files = prune_daily_reports(
        args.report_dir,
        date_value=date_value,
        keep_days=args.keep_days,
    )
    write_daily_collection_report(
        date_value=date_value,
        raw_dir=args.raw_dir,
        report_dir=args.report_dir,
        deleted_dirs=deleted_raw_dirs,
        deleted_report_files=deleted_report_files,
    )


def prune_raw_directories(raw_dir: str | Path, *, date_value: str, keep_days: int) -> list[str]:
    if keep_days < 1:
        raise ValueError("keep_days must be >= 1")
    base = Path(raw_dir)
    if not base.exists():
        return []

    cutoff = _retention_cutoff(date_value, keep_days)
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


def prune_daily_reports(
    report_dir: str | Path,
    *,
    date_value: str,
    keep_days: int,
) -> list[str]:
    if keep_days < 1:
        raise ValueError("keep_days must be >= 1")
    base = Path(report_dir)
    if not base.exists():
        return []

    cutoff = _retention_cutoff(date_value, keep_days)
    deleted: list[str] = []
    for child in base.iterdir():
        if not child.is_file():
            continue
        child_date = _parse_leading_date(child.name)
        if child_date is None:
            continue
        if child_date < cutoff:
            child.unlink()
            deleted.append(child.name)
    return sorted(deleted)


def _retention_cutoff(date_value: str, keep_days: int):
    today = datetime.strptime(date_value, "%Y-%m-%d").date()
    return today - timedelta(days=keep_days - 1)


def _parse_leading_date(file_name: str):
    if len(file_name) < 10:
        return None
    if len(file_name) > 10 and file_name[10] not in {".", "_", "-"}:
        return None
    try:
        return datetime.strptime(file_name[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


if __name__ == "__main__":
    main()
