from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from src.clients.naver_search_client import NaverSearchClient
from src.common.config import collection_config, iter_search_queries, load_dotenv, load_yaml
from src.common.storage import raw_date_dir, write_jsonl
from src.common.text import canonicalize_url, clean_html_text, stable_id
from src.common.time import now_kst_iso, resolve_date


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Naver blog search metadata.")
    parser.add_argument("--date", default="today")
    parser.add_argument("--layers", default="all")
    parser.add_argument("--config", default="configs/search_layers.yaml")
    parser.add_argument("--raw-dir", default="raw")
    args = parser.parse_args()

    load_dotenv()
    date_value = resolve_date(args.date)
    config = load_yaml(args.config)
    collection = collection_config(config)
    entries = iter_search_queries(config, args.layers)
    display = int(collection.get("display", 20))
    sort_modes = [str(sort) for sort in collection.get("sort_modes", ["sim", "date"])]
    start_positions = [int(start) for start in collection.get("start_positions", [1])]

    provider = os.environ.get("NAVER_API_PROVIDER", "developers")
    client = NaverSearchClient(provider=provider)
    records: list[dict[str, Any]] = []
    errors: list[str] = []

    for entry in entries:
        for sort in sort_modes:
            for start in start_positions:
                try:
                    response = client.search_blog(entry["query"], display, start, sort)
                    records.extend(
                        transform_search_items(
                            response.get("items", []),
                            entry=entry,
                            sort=sort,
                            start=start,
                            collected_at=now_kst_iso(),
                        )
                    )
                except Exception as exc:  # noqa: BLE001 - keep batch collection running.
                    errors.append(
                        f"- layer={entry['search_layer']} group={entry['query_group']} "
                        f"query={entry['query']} sort={sort} start={start}: {exc}"
                    )

    output_dir = raw_date_dir(args.raw_dir, date_value)
    write_jsonl(output_dir / "naver_search.jsonl", records)
    if errors:
        report_dir = Path("data/reports/daily")
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / f"{date_value}.errors.md").write_text(
            f"# Daily Collection Errors - {date_value}\n\n" + "\n".join(errors) + "\n",
            encoding="utf-8",
        )


def transform_search_items(
    items: list[dict[str, Any]],
    *,
    entry: dict[str, str],
    sort: str,
    start: int,
    collected_at: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for offset, item in enumerate(items):
        link = str(item.get("link", ""))
        canonical_url = canonicalize_url(link) if link else ""
        rank = start + offset
        title_raw = str(item.get("title", ""))
        description_raw = str(item.get("description", ""))
        records.append(
            {
                "id": stable_id(entry["search_layer"], entry["query"], sort, link),
                "collected_at": collected_at,
                "search_layer": entry["search_layer"],
                "query_group": entry["query_group"],
                "query": entry["query"],
                "sort": sort,
                "rank": rank,
                "title_raw": title_raw,
                "title_clean": clean_html_text(title_raw),
                "link": link,
                "description_raw": description_raw,
                "description_clean": clean_html_text(description_raw),
                "blogger_name": clean_html_text(str(item.get("bloggername", ""))),
                "blogger_link": str(item.get("bloggerlink", "")),
                "postdate": str(item.get("postdate", "")),
                "source": "naver_blog_search_api",
                "canonical_url": canonical_url,
                "body_fetch_eligible": bool(canonical_url),
            }
        )
    return records


if __name__ == "__main__":
    main()

