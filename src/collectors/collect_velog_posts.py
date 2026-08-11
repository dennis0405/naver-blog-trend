from __future__ import annotations

import argparse
from typing import Protocol

from src.clients.velog_client import VelogClient, parse_velog_posts
from src.common.storage import raw_date_dir, write_jsonl
from src.common.time import now_kst_iso, resolve_date


DEFAULT_TABS = ("trending_week", "curated")


class VelogPageClient(Protocol):
    def fetch_tab_html(self, tab: str) -> str: ...


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect public Velog post metadata.")
    parser.add_argument("--date", default="today")
    parser.add_argument("--raw-dir", default="raw")
    parser.add_argument("--limit-per-tab", type=int, default=20)
    args = parser.parse_args()

    if args.limit_per_tab < 1:
        raise SystemExit("--limit-per-tab must be >= 1")

    date_value = resolve_date(args.date)
    records = collect_public_posts(
        client=VelogClient(),
        tabs=DEFAULT_TABS,
        limit_per_tab=args.limit_per_tab,
        collected_at=now_kst_iso(),
    )
    write_jsonl(raw_date_dir(args.raw_dir, date_value) / "velog_posts.jsonl", records)


def collect_public_posts(
    *,
    client: VelogPageClient,
    tabs: tuple[str, ...],
    limit_per_tab: int,
    collected_at: str,
) -> list[dict[str, object]]:
    if limit_per_tab < 1:
        raise ValueError("limit_per_tab must be >= 1")

    merged: dict[str, dict[str, object]] = {}
    order: list[str] = []
    for tab in tabs:
        posts = parse_velog_posts(client.fetch_tab_html(tab), tab=tab, limit=limit_per_tab)
        for post in posts:
            canonical_url = str(post["canonical_url"])
            if canonical_url not in merged:
                order.append(canonical_url)
                merged[canonical_url] = {
                    **post,
                    "source": "velog",
                    "collected_at": collected_at,
                    "tabs": [],
                    "tab_ranks": {},
                    "search_layer": "velog",
                    "query_group": "public",
                    "sort": "rank",
                    "link": canonical_url,
                    "blogger_name": post["author_name"],
                    "blogger_link": post["author_url"],
                    "body_fetch_eligible": True,
                }
            record = merged[canonical_url]
            tabs_value = record["tabs"]
            tab_ranks_value = record["tab_ranks"]
            assert isinstance(tabs_value, list)
            assert isinstance(tab_ranks_value, dict)
            tabs_value.append(tab)
            tab_ranks_value[tab] = int(post["rank"])
            record["best_rank"] = min(tab_ranks_value.values())
            record["rank"] = record["best_rank"]
            record["likes"] = max(int(record.get("likes", 0)), int(post.get("likes", 0)))
            record["comments_count"] = max(
                int(record.get("comments_count", 0)), int(post.get("comments_count", 0))
            )
            record["query"] = ",".join(tabs_value)
            record.pop("tab", None)

    return [merged[url] for url in order]


if __name__ == "__main__":
    main()
