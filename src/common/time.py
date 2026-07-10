from __future__ import annotations

from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    return datetime.now(KST)


def now_kst_iso() -> str:
    return now_kst().isoformat(timespec="seconds")


def resolve_date(value: str) -> str:
    if value == "today":
        return now_kst().date().isoformat()
    datetime.strptime(value, "%Y-%m-%d")
    return value


def retained_until(date_value: str, keep_days: int) -> str:
    base = datetime.strptime(date_value, "%Y-%m-%d").date()
    return (base + timedelta(days=keep_days)).isoformat()

