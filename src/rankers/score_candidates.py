from __future__ import annotations

import argparse
import json
import math
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from src.common.config import load_yaml
from src.common.report import write_daily_collection_report
from src.common.storage import ensure_dir, read_jsonl
from src.common.text import canonicalize_url, stable_id
from src.common.time import now_kst_iso, resolve_date
from src.rankers.extract_reference_targets import (
    select_reference_targets,
    write_reference_targets,
)

TECH_KEYWORDS = {
    "개발",
    "기술",
    "트러블슈팅",
    "장애",
    "성능",
    "서버",
    "백엔드",
    "프론트엔드",
    "데이터",
    "인프라",
    "구현",
    "배포",
    "코드",
    "회고",
    "프로젝트",
    "ai",
    "llm",
    "rag",
    "spring",
    "jpa",
    "redis",
    "kubernetes",
    "langchain",
    "vector",
}

LOW_SIGNAL_KEYWORDS = {
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
    parser = argparse.ArgumentParser(description="Score deduplicated blog candidates.")
    parser.add_argument("--date", default="today")
    parser.add_argument("--raw-dir", default="raw")
    parser.add_argument("--derived-dir", default="data/derived")
    parser.add_argument("--report-dir", default="data/reports/daily")
    parser.add_argument("--scoring-config", default="configs/scoring.yaml")
    parser.add_argument("--target-top-n", type=int, default=None)
    parser.add_argument("--min-tech-relevance", type=float, default=0.30)
    parser.add_argument("--include-without-body", action="store_true")
    parser.add_argument("--include-low-signal", action="store_true")
    args = parser.parse_args()

    date_value = resolve_date(args.date)
    raw_path = Path(args.raw_dir) / date_value
    scoring_config = load_yaml(args.scoring_config)
    search_records = list(read_jsonl(raw_path / "naver_search.jsonl"))
    trend_records = list(read_jsonl(raw_path / "naver_trend.jsonl"))
    body_records = list(read_jsonl(raw_path / "blog_bodies.jsonl"))
    for body_record in body_records:
        body_record.setdefault("body_path", str(raw_path / "blog_bodies.jsonl"))

    candidates = score_candidates(
        search_records,
        trend_records,
        body_records,
        date_value=date_value,
        scoring_config=scoring_config,
    )
    db_path = ensure_dir(args.derived_dir) / "candidates.sqlite"
    write_candidates_sqlite(db_path, date_value=date_value, candidates=candidates)

    top_n = args.target_top_n or int(
        scoring_config.get("ranking", {}).get("top_n_daily_report", 30)
    )
    targets = select_reference_targets(
        candidates,
        top_n=top_n,
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
    write_daily_collection_report(
        date_value=date_value,
        raw_dir=args.raw_dir,
        report_dir=args.report_dir,
        derived_dir=args.derived_dir,
    )


def score_candidates(
    search_records: list[dict[str, Any]],
    trend_records: list[dict[str, Any]],
    body_records: list[dict[str, Any]],
    *,
    date_value: str,
    scoring_config: dict[str, Any],
) -> list[dict[str, Any]]:
    weights = scoring_config.get("weights", {})
    half_life_days = float(scoring_config.get("recency", {}).get("half_life_days", 45))
    duplicate_penalty = float(scoring_config.get("dedup", {}).get("duplicate_penalty", 0.35))
    trend_by_group = _trend_latest_ratios(trend_records)
    body_by_url = _body_by_canonical_url(body_records)
    blogger_counts = Counter(
        str(record.get("blogger_link") or record.get("blogger_name") or "")
        for record in search_records
        if record.get("blogger_link") or record.get("blogger_name")
    )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in search_records:
        canonical_url = _record_url(record)
        if canonical_url:
            grouped[canonical_url].append(record)

    max_query_count = max(
        (len({str(record.get("query", "")) for record in records}) for records in grouped.values()),
        default=1,
    )
    scored: list[dict[str, Any]] = []
    for canonical_url, records in grouped.items():
        representative = _representative_record(records)
        topic_group = f"{representative.get('search_layer')}.{representative.get('query_group')}"
        latest_ratio = trend_by_group.get(topic_group)
        query_count = len({str(record.get("query", "")) for record in records})
        occurrence_count = len(records)
        best_rank = min(int(record.get("rank", 999999)) for record in records)
        body = body_by_url.get(canonical_url, {})

        components = {
            "search_rank_score": _search_rank_score(best_rank),
            "trend_score": _trend_score(latest_ratio),
            "recency_score": _recency_score(
                str(representative.get("postdate", "")),
                date_value=date_value,
                half_life_days=half_life_days,
            ),
            "tech_relevance_score": _tech_relevance_score(records),
            "source_repeat_score": _source_repeat_score(query_count, max_query_count),
            "novelty_score": _novelty_score(representative, blogger_counts, duplicate_penalty),
        }
        total_score = sum(
            float(weights.get(name, 0.0)) * value for name, value in components.items()
        )
        candidate = {
            "date": date_value,
            "candidate_id": stable_id("candidate", canonical_url),
            "canonical_url": canonical_url,
            "representative_search_id": representative.get("id", ""),
            "title_clean": representative.get("title_clean", ""),
            "description_clean": representative.get("description_clean", ""),
            "link": representative.get("link", ""),
            "blogger_name": representative.get("blogger_name", ""),
            "blogger_link": representative.get("blogger_link", ""),
            "postdate": representative.get("postdate", ""),
            "search_layer": representative.get("search_layer", ""),
            "query_group": representative.get("query_group", ""),
            "query": representative.get("query", ""),
            "sort": representative.get("sort", ""),
            "best_rank": best_rank,
            "occurrence_count": occurrence_count,
            "query_count": query_count,
            "trend_topic_group": topic_group,
            "trend_latest_ratio": latest_ratio,
            "has_body": bool(body.get("status") == "ok"),
            "body_status": body.get("status", ""),
            "body_path": body.get("body_path", ""),
            "total_score": round(total_score, 6),
            "score_components": {name: round(value, 6) for name, value in components.items()},
            "signals": _candidate_signals(records),
            "created_at": now_kst_iso(),
        }
        scored.append(candidate)

    return sorted(
        scored,
        key=lambda item: (
            -float(item["total_score"]),
            int(item["best_rank"]),
            str(item["canonical_url"]),
        ),
    )


def write_candidates_sqlite(
    db_path: str | Path,
    *,
    date_value: str,
    candidates: list[dict[str, Any]],
) -> None:
    target = Path(db_path)
    ensure_dir(target.parent)
    with sqlite3.connect(target) as connection:
        _drop_incompatible_candidates_schema(connection)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                date TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                canonical_url TEXT NOT NULL,
                representative_search_id TEXT,
                title_clean TEXT,
                description_clean TEXT,
                link TEXT,
                blogger_name TEXT,
                blogger_link TEXT,
                postdate TEXT,
                search_layer TEXT,
                query_group TEXT,
                query TEXT,
                sort TEXT,
                best_rank INTEGER,
                occurrence_count INTEGER,
                query_count INTEGER,
                trend_topic_group TEXT,
                trend_latest_ratio REAL,
                has_body INTEGER,
                body_status TEXT,
                body_path TEXT,
                total_score REAL,
                search_rank_score REAL,
                trend_score REAL,
                recency_score REAL,
                tech_relevance_score REAL,
                source_repeat_score REAL,
                novelty_score REAL,
                signals_json TEXT,
                created_at TEXT,
                PRIMARY KEY (date, candidate_id)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_candidates_date_score ON candidates(date, total_score DESC)"
        )
        connection.execute("DELETE FROM candidates WHERE date = ?", (date_value,))
        connection.executemany(
            """
            INSERT INTO candidates (
                date, candidate_id, canonical_url, representative_search_id,
                title_clean, description_clean, link, blogger_name, blogger_link,
                postdate, search_layer, query_group, query, sort, best_rank,
                occurrence_count, query_count, trend_topic_group, trend_latest_ratio,
                has_body, body_status, body_path, total_score, search_rank_score,
                trend_score, recency_score, tech_relevance_score,
                source_repeat_score, novelty_score, signals_json, created_at
            )
            VALUES (
                :date, :candidate_id, :canonical_url, :representative_search_id,
                :title_clean, :description_clean, :link, :blogger_name, :blogger_link,
                :postdate, :search_layer, :query_group, :query, :sort, :best_rank,
                :occurrence_count, :query_count, :trend_topic_group, :trend_latest_ratio,
                :has_body, :body_status, :body_path, :total_score, :search_rank_score,
                :trend_score, :recency_score, :tech_relevance_score,
                :source_repeat_score, :novelty_score, :signals_json, :created_at
            )
            """,
            [_sqlite_candidate(candidate) for candidate in candidates],
        )


def _drop_incompatible_candidates_schema(connection: sqlite3.Connection) -> None:
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'candidates'"
    ).fetchone()
    if not row:
        return
    create_sql = str(row[0] or "")
    if "PRIMARY KEY (date, candidate_id)" in create_sql:
        return
    connection.execute("DROP TABLE IF EXISTS reference_targets")
    connection.execute("DROP TABLE IF EXISTS candidates")


def _sqlite_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    components = candidate["score_components"]
    return {
        **candidate,
        "has_body": 1 if candidate.get("has_body") else 0,
        "search_rank_score": components["search_rank_score"],
        "trend_score": components["trend_score"],
        "recency_score": components["recency_score"],
        "tech_relevance_score": components["tech_relevance_score"],
        "source_repeat_score": components["source_repeat_score"],
        "novelty_score": components["novelty_score"],
        "signals_json": json.dumps(candidate.get("signals", []), ensure_ascii=False, sort_keys=True),
    }


def _record_url(record: dict[str, Any]) -> str:
    url = str(record.get("canonical_url") or record.get("link") or "")
    return canonicalize_url(url) if url else ""


def _representative_record(records: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(
        records,
        key=lambda item: (
            int(item.get("rank", 999999)),
            0 if item.get("search_layer") == "target" else 1,
            str(item.get("query", "")),
        ),
    )[0]


def _trend_latest_ratios(trend_records: list[dict[str, Any]]) -> dict[str, float]:
    ratios: dict[str, float] = {}
    for record in trend_records:
        values = record.get("values") or []
        if not values:
            continue
        ratio = values[-1].get("ratio")
        if isinstance(ratio, (int, float)):
            ratios[str(record.get("topic_group", ""))] = float(ratio)
    return ratios


def _body_by_canonical_url(body_records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in body_records:
        canonical_url = str(record.get("canonical_url") or record.get("requested_url") or "")
        if not canonical_url:
            continue
        result[canonicalize_url(canonical_url)] = {
            "status": record.get("status", ""),
            "body_path": record.get("body_path", ""),
        }
    return result


def _search_rank_score(best_rank: int) -> float:
    if best_rank <= 0:
        return 0.0
    return max(0.0, min(1.0, (21 - best_rank) / 20))


def _trend_score(latest_ratio: float | None) -> float:
    if latest_ratio is None:
        return 0.0
    return max(0.0, min(1.0, latest_ratio / 100))


def _recency_score(postdate: str, *, date_value: str, half_life_days: float) -> float:
    try:
        posted = datetime.strptime(postdate, "%Y%m%d").date()
        reference = datetime.strptime(date_value, "%Y-%m-%d").date()
    except ValueError:
        return 0.0
    age_days = max(0, (reference - posted).days)
    if half_life_days <= 0:
        return 0.0
    return math.pow(0.5, age_days / half_life_days)


def _tech_relevance_score(records: list[dict[str, Any]]) -> float:
    best = 0.0
    for record in records:
        text = " ".join(
            str(record.get(field, ""))
            for field in ("title_clean", "description_clean", "query", "query_group")
        ).lower()
        hits = sum(1 for keyword in TECH_KEYWORDS if keyword in text)
        score = min(1.0, hits / 5)
        if str(record.get("search_layer")) == "target":
            score = min(1.0, score + 0.15)
        low_signal_hits = sum(1 for keyword in LOW_SIGNAL_KEYWORDS if keyword in text)
        score = max(0.0, score - (low_signal_hits * 0.18))
        best = max(best, score)
    return best


def _source_repeat_score(query_count: int, max_query_count: int) -> float:
    if max_query_count <= 1:
        return 0.0
    return max(0.0, min(1.0, (query_count - 1) / (max_query_count - 1)))


def _novelty_score(
    representative: dict[str, Any],
    blogger_counts: Counter[str],
    duplicate_penalty: float,
) -> float:
    blogger_key = str(representative.get("blogger_link") or representative.get("blogger_name") or "")
    count = max(1, blogger_counts.get(blogger_key, 1))
    penalty = min(duplicate_penalty, duplicate_penalty * math.log(count, 10)) if count > 1 else 0.0
    return max(0.0, 1.0 - penalty)


def _candidate_signals(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    signals = []
    for record in sorted(records, key=lambda item: int(item.get("rank", 999999))):
        signals.append(
            {
                "search_layer": record.get("search_layer", ""),
                "query_group": record.get("query_group", ""),
                "query": record.get("query", ""),
                "sort": record.get("sort", ""),
                "rank": record.get("rank", ""),
            }
        )
    return signals


if __name__ == "__main__":
    main()
