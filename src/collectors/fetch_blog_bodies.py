from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.clients.body_fetcher import PublicBodyFetcher
from src.common.config import collection_config, load_yaml
from src.common.storage import raw_date_dir, read_jsonl, write_json, write_jsonl
from src.common.time import now_kst_iso, resolve_date, retained_until


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch public body text for top candidates.")
    parser.add_argument("--date", default="today")
    parser.add_argument("--config", default="configs/search_layers.yaml")
    parser.add_argument("--raw-dir", default="raw")
    args = parser.parse_args()

    date_value = resolve_date(args.date)
    config = load_yaml(args.config)
    collection = collection_config(config)
    max_per_query = int(collection.get("max_body_fetch_per_query", 5))
    max_velog = int(collection.get("max_velog_body_fetch", 20))
    body_layers = {str(layer) for layer in collection.get("body_fetch_layers", ["discovery", "target"])}
    raw_path = raw_date_dir(args.raw_dir, date_value)
    candidates = [
        *read_jsonl(raw_path / "naver_search.jsonl"),
        *read_jsonl(raw_path / "velog_posts.jsonl"),
    ]
    selected = select_body_candidates(
        candidates,
        max_per_query=max_per_query,
        body_layers=body_layers,
        source_limits={"velog": max_velog},
    )

    fetcher = PublicBodyFetcher()
    body_records: list[dict[str, Any]] = []
    manifest_items: list[dict[str, Any]] = []
    for candidate in selected:
        result = fetcher.fetch_text(str(candidate.get("canonical_url") or candidate.get("link")))
        body_record = {
            "candidate_id": candidate.get("id"),
            "search_layer": candidate.get("search_layer"),
            "query_group": candidate.get("query_group"),
            "query": candidate.get("query"),
            "sort": candidate.get("sort"),
            "rank": candidate.get("rank"),
            "title_clean": candidate.get("title_clean"),
            "canonical_url": candidate.get("canonical_url"),
            "requested_url": result.requested_url,
            "fetched_url": result.fetched_url,
            "fetched_at": now_kst_iso(),
            "status": result.status,
            "error": result.error,
            "body_text": result.body_text,
            "text_length": len(result.body_text),
            "source": _candidate_source(candidate),
            "fetch_source": "public_blog_body_fetch",
        }
        body_records.append(body_record)
        manifest_items.append(
            {
                "candidate_id": candidate.get("id"),
                "canonical_url": candidate.get("canonical_url"),
                "fetched_at": body_record["fetched_at"],
                "status": result.status,
                "source": body_record["source"],
                "body_path": str(Path(args.raw_dir) / date_value / "blog_bodies.jsonl"),
                "retained_until": retained_until(date_value, int(collection.get("raw_retention_days", 7))),
            }
        )

    write_jsonl(raw_path / "blog_bodies.jsonl", body_records)
    write_json(
        raw_path / "body_manifest.json",
        {
            "raw_dir": str(raw_path),
            "created_at": now_kst_iso(),
            "retention_days": int(collection.get("raw_retention_days", 7)),
            "items": manifest_items,
        },
    )


def select_body_candidates(
    candidates: list[dict[str, Any]],
    *,
    max_per_query: int,
    body_layers: set[str],
    source_limits: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    source_limits = source_limits or {}
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        if not candidate.get("body_fetch_eligible"):
            continue
        if candidate.get("search_layer") not in body_layers:
            continue
        source = _candidate_source(candidate)
        if source in source_limits:
            group_key = (source, "", "")
        else:
            group_key = (
                str(candidate.get("search_layer")),
                str(candidate.get("query")),
                str(candidate.get("sort")),
            )
        grouped[group_key].append(candidate)

    selected: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for group_key, group_candidates in grouped.items():
        group_limit = source_limits.get(group_key[0], max_per_query)
        selected_from_group = 0
        for candidate in sorted(group_candidates, key=lambda item: int(item.get("rank", 999999))):
            canonical_url = str(candidate.get("canonical_url") or candidate.get("link"))
            if canonical_url in seen_urls:
                continue
            selected.append(candidate)
            seen_urls.add(canonical_url)
            selected_from_group += 1
            if selected_from_group >= group_limit:
                break
    return selected


def _candidate_source(candidate: dict[str, Any]) -> str:
    source = str(candidate.get("source", ""))
    return "velog" if source == "velog" else "naver"


if __name__ == "__main__":
    main()
