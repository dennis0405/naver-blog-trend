from __future__ import annotations

from pathlib import Path
from typing import Any

from src.common.storage import ensure_dir, read_jsonl


def write_daily_collection_report(
    *,
    date_value: str,
    raw_dir: str | Path = "raw",
    report_dir: str | Path = "data/reports/daily",
    deleted_dirs: list[str] | None = None,
) -> Path:
    raw_date = Path(raw_dir) / date_value
    search_path = raw_date / "naver_search.jsonl"
    trend_path = raw_date / "naver_trend.jsonl"
    bodies_path = raw_date / "blog_bodies.jsonl"
    manifest_path = raw_date / "body_manifest.json"

    search_records = list(read_jsonl(search_path))
    trend_records = list(read_jsonl(trend_path))
    body_records = list(read_jsonl(bodies_path))

    unique_links = {record.get("canonical_url") or record.get("link") for record in search_records}
    discovery_queries = {
        record.get("query") for record in search_records if record.get("search_layer") == "discovery"
    }
    target_queries = {
        record.get("query") for record in search_records if record.get("search_layer") == "target"
    }
    all_queries = {record.get("query") for record in search_records}

    deleted_dirs = deleted_dirs or []
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
        f"- raw_retention_deleted_dirs: {', '.join(deleted_dirs) if deleted_dirs else 'none'}",
        "- failed_queries: see errors report if present",
        "",
        "## Top Candidates",
        "",
        "| score | layer | query | rank | title | blogger | postdate | link |",
        "|---:|---|---|---:|---|---|---|---|",
    ]
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
