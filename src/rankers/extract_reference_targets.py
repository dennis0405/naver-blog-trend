from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from src.common.storage import ensure_dir, write_jsonl
from src.common.text import stable_id
from src.common.time import now_kst_iso, resolve_date

LOW_SIGNAL_TARGET_KEYWORDS = {
    "국비",
    "학원",
    "교육",
    "취업",
    "수강",
    "업체",
    "매입",
    "세무",
    "뉴스",
    "보도",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract top reference targets from scored candidates.")
    parser.add_argument("--date", default="today")
    parser.add_argument("--derived-dir", default="data/derived")
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument("--min-tech-relevance", type=float, default=0.30)
    parser.add_argument("--include-without-body", action="store_true")
    parser.add_argument("--include-low-signal", action="store_true")
    args = parser.parse_args()

    date_value = resolve_date(args.date)
    db_path = Path(args.derived_dir) / "candidates.sqlite"
    candidates = read_scored_candidates(db_path, date_value=date_value)
    targets = select_reference_targets(
        candidates,
        top_n=args.top_n,
        min_tech_relevance=args.min_tech_relevance,
        require_body=not args.include_without_body,
        include_low_signal=args.include_low_signal,
    )
    write_reference_targets(
        db_path,
        date_value=date_value,
        targets=targets,
        output_path=ensure_dir(Path(args.derived_dir) / date_value) / "reference_targets.jsonl",
    )


def read_scored_candidates(db_path: str | Path, *, date_value: str) -> list[dict[str, Any]]:
    source = Path(db_path)
    if not source.exists():
        return []
    with sqlite3.connect(source) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
                date, candidate_id, canonical_url, title_clean, link, blogger_name,
                blogger_link, postdate, search_layer, query_group, query, best_rank,
                occurrence_count, query_count, trend_topic_group, trend_latest_ratio,
                has_body, body_status, body_path, total_score, tech_relevance_score,
                signals_json
            FROM candidates
            WHERE date = ?
            ORDER BY total_score DESC, best_rank ASC, canonical_url ASC
            """,
            (date_value,),
        ).fetchall()
    candidates: list[dict[str, Any]] = []
    for row in rows:
        candidate = dict(row)
        candidate["has_body"] = bool(candidate.get("has_body"))
        candidate["signals"] = json.loads(candidate.pop("signals_json") or "[]")
        candidates.append(candidate)
    return candidates


def select_reference_targets(
    candidates: list[dict[str, Any]],
    *,
    top_n: int,
    min_tech_relevance: float = 0.30,
    require_body: bool = True,
    include_low_signal: bool = False,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for candidate in sorted(
        candidates,
        key=lambda item: (
            -float(item.get("total_score", 0.0)),
            int(item.get("best_rank", 999999)),
            str(item.get("canonical_url", "")),
        ),
    ):
        if require_body and not candidate.get("has_body"):
            continue
        if _tech_relevance(candidate) < min_tech_relevance:
            continue
        if not include_low_signal and _is_low_signal_target(candidate):
            continue
        rank_position = len(selected) + 1
        selected.append(_target_record(candidate, rank_position=rank_position))
        if len(selected) >= top_n:
            break
    return selected


def write_reference_targets(
    db_path: str | Path,
    *,
    date_value: str,
    targets: list[dict[str, Any]],
    output_path: str | Path,
) -> None:
    target = Path(db_path)
    ensure_dir(target.parent)
    with sqlite3.connect(target) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reference_targets (
                date TEXT NOT NULL,
                target_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                rank_position INTEGER NOT NULL,
                total_score REAL NOT NULL,
                canonical_url TEXT NOT NULL,
                title_clean TEXT,
                blogger_name TEXT,
                postdate TEXT,
                search_layer TEXT,
                query_group TEXT,
                query TEXT,
                best_rank INTEGER,
                body_status TEXT,
                body_path TEXT,
                reason_codes_json TEXT,
                selected_at TEXT
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_reference_targets_date_rank ON reference_targets(date, rank_position)"
        )
        connection.execute("DELETE FROM reference_targets WHERE date = ?", (date_value,))
        connection.executemany(
            """
            INSERT INTO reference_targets (
                date, target_id, candidate_id, rank_position, total_score,
                canonical_url, title_clean, blogger_name, postdate, search_layer,
                query_group, query, best_rank, body_status, body_path,
                reason_codes_json, selected_at
            )
            VALUES (
                :date, :target_id, :candidate_id, :rank_position, :total_score,
                :canonical_url, :title_clean, :blogger_name, :postdate, :search_layer,
                :query_group, :query, :best_rank, :body_status, :body_path,
                :reason_codes_json, :selected_at
            )
            """,
            [_sqlite_target(target_record, date_value=date_value) for target_record in targets],
        )
    write_jsonl(output_path, targets)


def _target_record(candidate: dict[str, Any], *, rank_position: int) -> dict[str, Any]:
    reason_codes = ["high_total_score"]
    if candidate.get("has_body"):
        reason_codes.append("body_available")
    if candidate.get("search_layer") == "target":
        reason_codes.append("target_layer")
    if int(candidate.get("query_count", 0)) > 1:
        reason_codes.append("multi_query_signal")
    if _tech_relevance(candidate) >= 0.30:
        reason_codes.append("technical_relevance")
    return {
        "target_id": stable_id("reference_target", candidate.get("date", ""), candidate["candidate_id"]),
        "date": candidate.get("date", ""),
        "candidate_id": candidate["candidate_id"],
        "rank_position": rank_position,
        "total_score": candidate.get("total_score", 0.0),
        "canonical_url": candidate.get("canonical_url", ""),
        "title_clean": candidate.get("title_clean", ""),
        "link": candidate.get("link", ""),
        "blogger_name": candidate.get("blogger_name", ""),
        "postdate": candidate.get("postdate", ""),
        "search_layer": candidate.get("search_layer", ""),
        "query_group": candidate.get("query_group", ""),
        "query": candidate.get("query", ""),
        "best_rank": candidate.get("best_rank", ""),
        "body_status": candidate.get("body_status", ""),
        "body_path": candidate.get("body_path", ""),
        "reason_codes": reason_codes,
        "selected_at": now_kst_iso(),
    }


def _sqlite_target(target_record: dict[str, Any], *, date_value: str) -> dict[str, Any]:
    return {
        **target_record,
        "date": date_value,
        "reason_codes_json": json.dumps(
            target_record.get("reason_codes", []),
            ensure_ascii=False,
            sort_keys=True,
        ),
    }


def _tech_relevance(candidate: dict[str, Any]) -> float:
    if "tech_relevance_score" in candidate:
        return float(candidate.get("tech_relevance_score") or 0.0)
    score_components = candidate.get("score_components") or {}
    return float(score_components.get("tech_relevance_score") or 0.0)


def _is_low_signal_target(candidate: dict[str, Any]) -> bool:
    text = " ".join(
        str(candidate.get(field, ""))
        for field in ("title_clean", "query", "query_group", "blogger_name")
    ).lower()
    return any(keyword in text for keyword in LOW_SIGNAL_TARGET_KEYWORDS)


if __name__ == "__main__":
    main()
