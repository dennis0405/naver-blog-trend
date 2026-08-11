from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from src.common.config import load_yaml
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
    parser.add_argument("--scoring-config", default="configs/scoring.yaml")
    parser.add_argument("--min-style-quality", type=float, default=None)
    parser.add_argument("--include-without-body", action="store_true")
    parser.add_argument("--include-low-signal", action="store_true")
    args = parser.parse_args()

    date_value = resolve_date(args.date)
    ranking_config = load_yaml(args.scoring_config).get("ranking", {})
    source_quotas = {
        str(source): int(quota)
        for source, quota in (ranking_config.get("source_quotas", {}) or {}).items()
    }
    db_path = Path(args.derived_dir) / "candidates.sqlite"
    candidates = read_scored_candidates(db_path, date_value=date_value)
    targets = select_reference_targets(
        candidates,
        top_n=args.top_n,
        min_tech_relevance=args.min_tech_relevance,
        min_style_quality=(
            args.min_style_quality
            if args.min_style_quality is not None
            else float(ranking_config.get("min_style_quality", 0.0))
        ),
        require_body=not args.include_without_body,
        include_low_signal=args.include_low_signal,
        source_quotas=source_quotas or None,
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
                date, source, candidate_id, canonical_url, title_clean, link, blogger_name,
                blogger_link, author_name, author_url, postdate, search_layer,
                discovery_channel, query_group, query, best_rank,
                occurrence_count, query_count, trend_topic_group, trend_latest_ratio,
                has_body, body_status, body_path, total_score, tech_relevance_score,
                style_quality_score, signals_json
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
    min_style_quality: float = 0.0,
    require_body: bool = True,
    include_low_signal: bool = False,
    source_quotas: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    eligible = [
        candidate
        for candidate in candidates
        if _is_eligible(
            candidate,
            min_tech_relevance=min_tech_relevance,
            min_style_quality=min_style_quality,
            require_body=require_body,
            include_low_signal=include_low_signal,
        )
    ]
    ordered = sorted(
        eligible,
        key=lambda item: (
            -float(item.get("total_score", 0.0)),
            int(item.get("best_rank", 999999)),
            str(item.get("canonical_url", "")),
        ),
    )
    if source_quotas:
        buckets = {
            source: [candidate for candidate in ordered if _source(candidate) == source][:quota]
            for source, quota in source_quotas.items()
            if quota > 0
        }
        ordered = _round_robin(buckets, limit=top_n)

    return [
        _target_record(candidate, rank_position=index)
        for index, candidate in enumerate(ordered[:top_n], start=1)
    ]


def _is_eligible(
    candidate: dict[str, Any],
    *,
    min_tech_relevance: float,
    min_style_quality: float,
    require_body: bool,
    include_low_signal: bool,
) -> bool:
    if require_body and not candidate.get("has_body"):
        return False
    if _tech_relevance(candidate) < min_tech_relevance:
        return False
    if float(candidate.get("style_quality_score") or 0.0) < min_style_quality:
        return False
    if not include_low_signal and _is_low_signal_target(candidate):
        return False
    return True


def _round_robin(
    buckets: dict[str, list[dict[str, Any]]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    max_bucket_size = max((len(bucket) for bucket in buckets.values()), default=0)
    for index in range(max_bucket_size):
        for bucket in buckets.values():
            if index < len(bucket):
                selected.append(bucket[index])
                if len(selected) >= limit:
                    return selected
    return selected


def _source(candidate: dict[str, Any]) -> str:
    source = str(candidate.get("source") or "")
    return source if source in {"naver", "velog"} else "naver"


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
        columns = {
            str(info[1])
            for info in connection.execute("PRAGMA table_info(reference_targets)").fetchall()
        }
        if columns and "source" not in columns:
            connection.execute("DROP TABLE reference_targets")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reference_targets (
                date TEXT NOT NULL,
                target_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                source TEXT NOT NULL,
                rank_position INTEGER NOT NULL,
                total_score REAL NOT NULL,
                canonical_url TEXT NOT NULL,
                title_clean TEXT,
                blogger_name TEXT,
                author_name TEXT,
                postdate TEXT,
                search_layer TEXT,
                discovery_channel TEXT,
                query_group TEXT,
                query TEXT,
                best_rank INTEGER,
                body_status TEXT,
                body_path TEXT,
                style_quality_score REAL,
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
                date, target_id, candidate_id, source, rank_position, total_score,
                canonical_url, title_clean, blogger_name, author_name, postdate,
                search_layer, discovery_channel, query_group, query, best_rank,
                body_status, body_path, style_quality_score,
                reason_codes_json, selected_at
            )
            VALUES (
                :date, :target_id, :candidate_id, :source, :rank_position, :total_score,
                :canonical_url, :title_clean, :blogger_name, :author_name, :postdate,
                :search_layer, :discovery_channel, :query_group, :query, :best_rank,
                :body_status, :body_path, :style_quality_score,
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
    if float(candidate.get("style_quality_score") or 0.0) > 0:
        reason_codes.append("style_quality")
    return {
        "target_id": stable_id("reference_target", candidate.get("date", ""), candidate["candidate_id"]),
        "date": candidate.get("date", ""),
        "candidate_id": candidate["candidate_id"],
        "source": _source(candidate),
        "rank_position": rank_position,
        "total_score": candidate.get("total_score", 0.0),
        "canonical_url": candidate.get("canonical_url", ""),
        "title_clean": candidate.get("title_clean", ""),
        "link": candidate.get("link", ""),
        "blogger_name": candidate.get("blogger_name", ""),
        "author_name": candidate.get("author_name", candidate.get("blogger_name", "")),
        "postdate": candidate.get("postdate", ""),
        "search_layer": candidate.get("search_layer", ""),
        "discovery_channel": candidate.get(
            "discovery_channel", candidate.get("search_layer", "")
        ),
        "query_group": candidate.get("query_group", ""),
        "query": candidate.get("query", ""),
        "best_rank": candidate.get("best_rank", ""),
        "body_status": candidate.get("body_status", ""),
        "body_path": candidate.get("body_path", ""),
        "style_quality_score": candidate.get("style_quality_score", 0.0),
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
