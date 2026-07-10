from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from src.common.storage import ensure_dir, read_jsonl


def write_daily_collection_report(
    *,
    date_value: str,
    raw_dir: str | Path = "raw",
    report_dir: str | Path = "data/reports/daily",
    derived_dir: str | Path = "data/derived",
    deleted_dirs: list[str] | None = None,
    deleted_report_files: list[str] | None = None,
) -> Path:
    raw_date = Path(raw_dir) / date_value
    search_path = raw_date / "naver_search.jsonl"
    trend_path = raw_date / "naver_trend.jsonl"
    bodies_path = raw_date / "blog_bodies.jsonl"
    manifest_path = raw_date / "body_manifest.json"

    search_records = list(read_jsonl(search_path))
    trend_records = list(read_jsonl(trend_path))
    body_records = list(read_jsonl(bodies_path))
    ranked_candidates = _read_ranked_candidates(derived_dir, date_value, limit=30)
    reference_targets = _read_reference_targets(derived_dir, date_value, limit=30)
    ranked_candidate_count = _count_derived_rows(derived_dir, "candidates", date_value)
    reference_target_count = _count_derived_rows(derived_dir, "reference_targets", date_value)

    unique_links = {record.get("canonical_url") or record.get("link") for record in search_records}
    discovery_queries = {
        record.get("query") for record in search_records if record.get("search_layer") == "discovery"
    }
    target_queries = {
        record.get("query") for record in search_records if record.get("search_layer") == "target"
    }
    all_queries = {record.get("query") for record in search_records}

    deleted_dirs = deleted_dirs or []
    deleted_report_files = deleted_report_files or []
    lines = [
        f"# Daily Naver Tech Blog Signal Report - {date_value}",
        "",
        "## Summary",
        f"- collected_queries: {len(all_queries)}",
        f"- discovery_queries: {len(discovery_queries)}",
        f"- target_queries: {len(target_queries)}",
        f"- total_candidates: {len(search_records)}",
        f"- unique_candidates: {len(unique_links)}",
        f"- body_fetch_candidates: {len(body_records)}",
        f"- ranked_candidates: {ranked_candidate_count}",
        f"- reference_targets: {reference_target_count}",
        f"- raw_retention_deleted_dirs: {', '.join(deleted_dirs) if deleted_dirs else 'none'}",
        f"- report_retention_deleted_files: {', '.join(deleted_report_files) if deleted_report_files else 'none'}",
        "- failed_queries: see errors report if present",
        "",
        "## Top Candidates",
        "",
        "| score | layer | query | rank | title | blogger | postdate | link |",
        "|---:|---|---|---:|---|---|---|---|",
    ]
    if ranked_candidates:
        for record in ranked_candidates:
            lines.append(
                "| {score:.3f} | {layer} | {query} | {rank} | {title} | {blogger} | {postdate} | {link} |".format(
                    score=float(record.get("total_score") or 0),
                    layer=record.get("search_layer", ""),
                    query=_escape_table(record.get("query", "")),
                    rank=record.get("best_rank", ""),
                    title=_escape_table(record.get("title_clean", "")),
                    blogger=_escape_table(record.get("blogger_name", "")),
                    postdate=record.get("postdate", ""),
                    link=record.get("canonical_url", ""),
                )
            )
    else:
        for record in sorted(
            search_records,
            key=lambda item: (
                str(item.get("search_layer", "")),
                str(item.get("query", "")),
                int(item.get("rank", 999999)),
            ),
        )[:30]:
            lines.append(
                "| - | {layer} | {query} | {rank} | {title} | {blogger} | {postdate} | {link} |".format(
                    layer=record.get("search_layer", ""),
                    query=_escape_table(record.get("query", "")),
                    rank=record.get("rank", ""),
                    title=_escape_table(record.get("title_clean", "")),
                    blogger=_escape_table(record.get("blogger_name", "")),
                    postdate=record.get("postdate", ""),
                    link=record.get("link", ""),
                )
            )

    if reference_targets:
        lines.extend(
            [
                "",
                "## Reference Targets",
                "",
                "| position | score | layer | query | title | reasons | body_status | link |",
                "|---:|---:|---|---|---|---|---|---|",
            ]
        )
        for target_record in reference_targets:
            lines.append(
                "| {position} | {score:.3f} | {layer} | {query} | {title} | {reasons} | {body_status} | {link} |".format(
                    position=target_record.get("rank_position", ""),
                    score=float(target_record.get("total_score") or 0),
                    layer=target_record.get("search_layer", ""),
                    query=_escape_table(target_record.get("query", "")),
                    title=_escape_table(target_record.get("title_clean", "")),
                    reasons=_escape_table(", ".join(target_record.get("reason_codes", []))),
                    body_status=target_record.get("body_status", ""),
                    link=target_record.get("canonical_url", ""),
                )
            )

    lines.extend(
        [
            "",
            "## Topic Trends",
            "| topic_group | latest_ratio | 7d_delta | 30d_delta | note |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for record in trend_records:
        values = record.get("values") or []
        latest_ratio = values[-1].get("ratio") if values else ""
        lines.append(
            f"| {_escape_table(record.get('topic_group', ''))} | {latest_ratio} |  |  | relative trend value |"
        )

    lines.extend(
        [
            "",
            "## Raw Storage",
            f"- raw_dir: {raw_date}",
            f"- naver_search_jsonl: {search_path}",
            f"- naver_trend_jsonl: {trend_path}",
            f"- blog_bodies_jsonl: {bodies_path}",
            f"- body_manifest_json: {manifest_path}",
        ]
    )

    target = ensure_dir(report_dir) / f"{date_value}.md"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def _escape_table(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _read_ranked_candidates(
    derived_dir: str | Path,
    date_value: str,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    db_path = Path(derived_dir) / "candidates.sqlite"
    if not db_path.exists():
        return []
    try:
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT total_score, search_layer, query, best_rank, title_clean,
                       blogger_name, postdate, canonical_url
                FROM candidates
                WHERE date = ?
                ORDER BY total_score DESC, best_rank ASC, canonical_url ASC
                LIMIT ?
                """,
                (date_value, limit),
            ).fetchall()
    except sqlite3.Error:
        return []
    return [dict(row) for row in rows]


def _read_reference_targets(
    derived_dir: str | Path,
    date_value: str,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    db_path = Path(derived_dir) / "candidates.sqlite"
    if not db_path.exists():
        return []
    try:
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT rank_position, total_score, search_layer, query, title_clean,
                       reason_codes_json, body_status, canonical_url
                FROM reference_targets
                WHERE date = ?
                ORDER BY rank_position ASC
                LIMIT ?
                """,
                (date_value, limit),
            ).fetchall()
    except sqlite3.Error:
        return []
    targets: list[dict[str, Any]] = []
    for row in rows:
        target = dict(row)
        target["reason_codes"] = json.loads(target.pop("reason_codes_json") or "[]")
        targets.append(target)
    return targets


def _count_derived_rows(derived_dir: str | Path, table_name: str, date_value: str) -> int:
    if table_name not in {"candidates", "reference_targets"}:
        return 0
    db_path = Path(derived_dir) / "candidates.sqlite"
    if not db_path.exists():
        return 0
    try:
        with sqlite3.connect(db_path) as connection:
            return int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {table_name} WHERE date = ?",
                    (date_value,),
                ).fetchone()[0]
            )
    except sqlite3.Error:
        return 0
