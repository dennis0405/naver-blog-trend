from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta
from typing import Any

from src.clients.naver_trend_client import NaverTrendClient
from src.common.config import collection_config, iter_search_queries, load_dotenv, load_yaml
from src.common.storage import raw_date_dir, write_jsonl
from src.common.text import stable_id
from src.common.time import now_kst_iso, resolve_date


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Naver DataLab search trends.")
    parser.add_argument("--date", default="today")
    parser.add_argument("--config", default="configs/search_layers.yaml")
    parser.add_argument("--raw-dir", default="raw")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--time-unit", default="date")
    args = parser.parse_args()

    load_dotenv()
    date_value = resolve_date(args.date)
    config = load_yaml(args.config)
    collection_config(config)
    groups = trend_groups(config)
    end_date = datetime.strptime(date_value, "%Y-%m-%d").date()
    start_date = end_date - timedelta(days=args.days)

    provider = os.environ.get("NAVER_API_PROVIDER", "developers")
    client = NaverTrendClient(provider=provider)
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for group in groups:
        topic_group = {
            "groupName": group["topic_group"],
            "keywords": group["keywords"][:20],
        }
        try:
            response = client.get_search_trend(
                topic_group,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                time_unit=args.time_unit,
            )
            records.append(
                transform_trend_response(
                    response,
                    search_layer=group["search_layer"],
                    topic_group=group["topic_group"],
                    keywords=topic_group["keywords"],
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                    time_unit=args.time_unit,
                    collected_at=now_kst_iso(),
                )
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"- topic_group={group['topic_group']}: {exc}")

    output_dir = raw_date_dir(args.raw_dir, date_value)
    write_jsonl(output_dir / "naver_trend.jsonl", records)
    if errors:
        report_dir = "data/reports/daily"
        from pathlib import Path

        Path(report_dir).mkdir(parents=True, exist_ok=True)
        Path(report_dir, f"{date_value}.trend.errors.md").write_text(
            f"# Daily Trend Collection Errors - {date_value}\n\n" + "\n".join(errors) + "\n",
            encoding="utf-8",
        )


def trend_groups(config: dict[str, Any]) -> list[dict[str, Any]]:
    entries = iter_search_queries(config, "all")
    grouped: dict[tuple[str, str], list[str]] = {}
    for entry in entries:
        grouped.setdefault((entry["search_layer"], entry["query_group"]), []).append(entry["query"])
    return [
        {
            "search_layer": search_layer,
            "topic_group": f"{search_layer}.{query_group}",
            "keywords": keywords,
        }
        for (search_layer, query_group), keywords in grouped.items()
    ]


def transform_trend_response(
    response: dict[str, Any],
    *,
    search_layer: str,
    topic_group: str,
    keywords: list[str],
    start_date: str,
    end_date: str,
    time_unit: str,
    collected_at: str,
) -> dict[str, Any]:
    result = (response.get("results") or [{}])[0]
    values = result.get("data") or []
    return {
        "id": stable_id(topic_group, start_date, end_date, time_unit),
        "collected_at": collected_at,
        "search_layer": search_layer,
        "topic_group": topic_group,
        "keywords": keywords,
        "start_date": start_date,
        "end_date": end_date,
        "time_unit": time_unit,
        "values": values,
        "source": "naver_datalab_or_api_hub",
        "raw_response": response,
    }


if __name__ == "__main__":
    main()

