from __future__ import annotations

import json
import unittest

from src.clients.velog_client import VelogPayloadError, parse_velog_posts
from src.collectors.collect_velog_posts import collect_public_posts
from src.collectors.fetch_blog_bodies import select_body_candidates


class VelogCollectionTests(unittest.TestCase):
    def test_parses_ordered_public_posts_from_next_flight_payload(self) -> None:
        html = _flight_html(
            [
                _post("post-1", "첫 글", "writer", "first", likes=10, comments=2),
                _post("post-2", "둘째 글", "second", "second", likes=3, comments=0),
                {"id": "private", "title": "비공개", "is_private": True},
            ]
        )

        records = parse_velog_posts(html, tab="trending_week", limit=20)

        self.assertEqual([record["id"] for record in records], ["post-1", "post-2"])
        self.assertEqual(records[0]["rank"], 1)
        self.assertEqual(records[0]["canonical_url"], "https://velog.io/@writer/first")
        self.assertEqual(records[0]["author_name"], "writer")
        self.assertEqual(records[0]["postdate"], "20260810")

    def test_rejects_payload_without_valid_public_posts(self) -> None:
        with self.assertRaisesRegex(VelogPayloadError, "no valid public posts"):
            parse_velog_posts("<html><body>empty</body></html>", tab="curated")

    def test_parses_curated_camel_case_payload(self) -> None:
        html = _flight_html(
            [
                {
                    "id": "curated-1",
                    "title": "추천 글",
                    "urlSlug": "curated-post",
                    "shortDescription": "추천 설명",
                    "releasedAt": "2026-08-11T06:30:50.450Z",
                    "user": {"username": "curator"},
                    "likes": 4,
                    "comments": 2,
                }
            ]
        )

        records = parse_velog_posts(html, tab="curated")

        self.assertEqual(records[0]["canonical_url"], "https://velog.io/@curator/curated-post")
        self.assertEqual(records[0]["description_clean"], "추천 설명")
        self.assertEqual(records[0]["comments_count"], 2)

    def test_collects_and_merges_posts_seen_in_both_tabs(self) -> None:
        client = _FakeVelogClient(
            {
                "trending_week": _flight_html(
                    [_post("shared", "공통 글", "writer", "shared", likes=10, comments=2)]
                ),
                "curated": _flight_html(
                    [
                        _post("curated", "추천 글", "curator", "curated"),
                        _post("shared", "공통 글", "writer", "shared", likes=12, comments=3),
                    ]
                ),
            }
        )

        records = collect_public_posts(
            client=client,
            tabs=("trending_week", "curated"),
            limit_per_tab=20,
            collected_at="2026-08-11T09:00:00+09:00",
        )

        self.assertEqual(len(records), 2)
        shared = next(record for record in records if record["id"] == "shared")
        self.assertEqual(shared["tabs"], ["trending_week", "curated"])
        self.assertEqual(shared["tab_ranks"], {"trending_week": 1, "curated": 2})
        self.assertEqual(shared["likes"], 12)
        self.assertTrue(shared["body_fetch_eligible"])

    def test_body_selection_includes_velog_up_to_source_limit(self) -> None:
        candidates = [
            {
                "id": f"velog-{index}",
                "source": "velog",
                "search_layer": "velog",
                "canonical_url": f"https://velog.io/@writer/post-{index}",
                "rank": index,
                "body_fetch_eligible": True,
            }
            for index in range(1, 4)
        ]

        selected = select_body_candidates(
            candidates,
            max_per_query=1,
            body_layers={"discovery", "target", "velog"},
            source_limits={"velog": 2},
        )

        self.assertEqual([record["id"] for record in selected], ["velog-1", "velog-2"])


class _FakeVelogClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages

    def fetch_tab_html(self, tab: str) -> str:
        return self.pages[tab]


def _flight_html(posts: list[dict[str, object]]) -> str:
    flight_segment = "0:" + json.dumps({"posts": posts}, ensure_ascii=False)
    return (
        "<html><body><script>"
        f"self.__next_f.push([1,{json.dumps(flight_segment, ensure_ascii=False)}])"
        "</script></body></html>"
    )


def _post(
    post_id: str,
    title: str,
    username: str,
    slug: str,
    *,
    likes: int = 0,
    comments: int = 0,
) -> dict[str, object]:
    return {
        "id": post_id,
        "title": title,
        "url_slug": slug,
        "short_description": f"{title} 설명",
        "released_at": "2026-08-10T01:02:03.000Z",
        "is_private": False,
        "likes": likes,
        "comments_count": comments,
        "user": {"username": username},
    }


if __name__ == "__main__":
    unittest.main()
