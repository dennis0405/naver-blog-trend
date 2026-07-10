from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Any


def ensure_dir(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def raw_date_dir(raw_dir: str | Path, date_value: str) -> Path:
    return ensure_dir(Path(raw_dir) / date_value)


def write_jsonl(path: str | Path, records: Iterable[Mapping[str, Any]]) -> int:
    target = Path(path)
    ensure_dir(target.parent)
    count = 0
    with target.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
            count += 1
    return count


def read_jsonl(path: str | Path) -> Iterator[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return
    with source.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                yield json.loads(stripped)


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    ensure_dir(target.parent)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

