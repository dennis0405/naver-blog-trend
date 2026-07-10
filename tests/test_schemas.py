from __future__ import annotations

import unittest

from src.collectors.collect_naver_search import transform_search_items
from src.collectors.fetch_blog_bodies import select_body_candidates


class SchemaTests(unittest.TestCase):
    def test_search_item_transform(self) -> None:
        records = transform_search_items(
            [
                {
                    "title": "<b>JPA</b> 성능 개선",
                    "link": "https://blog.naver.com/example/1",
                    "description": "desc",
                    "bloggername": "dev",
                    "bloggerlink": "https://blog.naver.com/example",
                    "postdate": "20260709",
                }
            ],
            entry={"search_layer": "target", "query_group": "backend", "query": "JPA 성능 개선"},
            sort="sim",
            start=1,
            collected_at="2026-07-09T00:00:00+09:00",
        )
        self.assertEqual(records[0]["rank"], 1)
        self.assertEqual(records[0]["title_clean"], "JPA 성능 개선")
        self.assertTrue(records[0]["body_fetch_eligible"])

    def test_select_body_candidates_deduplicates(self) -> None:
        candidates = [
            {
                "id": "1",
                "search_layer": "discovery",
                "query": "기술 블로그",
                "sort": "sim",
                "rank": 1,
                "canonical_url": "https://blog.naver.com/a/1",
                "body_fetch_eligible": True,
            },
            {
                "id": "2",
                "search_layer": "discovery",
                "query": "기술 블로그",
                "sort": "sim",
                "rank": 2,
                "canonical_url": "https://blog.naver.com/a/1",
                "body_fetch_eligible": True,
            },
        ]
        selected = select_body_candidates(candidates, max_per_query=5, body_layers={"discovery"})
        self.assertEqual([item["id"] for item in selected], ["1"])


if __name__ == "__main__":
    unittest.main()

