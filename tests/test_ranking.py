from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.common.report import write_daily_collection_report
from src.common.storage import write_jsonl
from src.rankers.extract_reference_targets import (
    read_scored_candidates,
    select_reference_targets,
    write_reference_targets,
)
from src.rankers.score_candidates import score_candidates, write_candidates_sqlite


class RankingTests(unittest.TestCase):
    def test_score_candidates_deduplicates_and_prefers_body_available_technical_posts(self) -> None:
        candidates = score_candidates(
            _search_records(),
            _trend_records(),
            _body_records(),
            date_value="2026-07-10",
            scoring_config=_scoring_config(),
        )

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["canonical_url"], "https://blog.naver.com/dev/1?a=1&b=2")
        self.assertEqual(candidates[0]["query_count"], 2)
        self.assertTrue(candidates[0]["has_body"])
        self.assertGreater(candidates[0]["total_score"], candidates[1]["total_score"])
        self.assertGreater(
            candidates[0]["score_components"]["tech_relevance_score"],
            candidates[1]["score_components"]["tech_relevance_score"],
        )

    def test_writes_sqlite_and_reference_targets_without_body_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            db_path = base / "data" / "derived" / "candidates.sqlite"
            candidates = score_candidates(
                _search_records(),
                _trend_records(),
                _body_records(),
                date_value="2026-07-10",
                scoring_config=_scoring_config(),
            )
            write_candidates_sqlite(db_path, date_value="2026-07-10", candidates=candidates)

            stored = read_scored_candidates(db_path, date_value="2026-07-10")
            targets = select_reference_targets(stored, top_n=5, require_body=True)
            write_reference_targets(
                db_path,
                date_value="2026-07-10",
                targets=targets,
                output_path=base / "data" / "derived" / "reference_targets.jsonl",
            )

            self.assertEqual(len(targets), 1)
            self.assertEqual(targets[0]["canonical_url"], "https://blog.naver.com/dev/1?a=1&b=2")
            target_text = (base / "data" / "derived" / "reference_targets.jsonl").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("body_text", target_text)
            with sqlite3.connect(db_path) as connection:
                count = connection.execute("SELECT COUNT(*) FROM reference_targets").fetchone()[0]
            self.assertEqual(count, 1)

    def test_daily_report_uses_scored_candidates_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            raw_date = base / "raw" / "2026-07-10"
            write_jsonl(raw_date / "naver_search.jsonl", _search_records())
            write_jsonl(raw_date / "naver_trend.jsonl", _trend_records())
            write_jsonl(raw_date / "blog_bodies.jsonl", _body_records())

            candidates = score_candidates(
                _search_records(),
                _trend_records(),
                _body_records(),
                date_value="2026-07-10",
                scoring_config=_scoring_config(),
            )
            db_path = base / "data" / "derived" / "candidates.sqlite"
            write_candidates_sqlite(db_path, date_value="2026-07-10", candidates=candidates)
            targets = select_reference_targets(candidates, top_n=5, require_body=True)
            write_reference_targets(
                db_path,
                date_value="2026-07-10",
                targets=targets,
                output_path=base / "data" / "derived" / "reference_targets.jsonl",
            )

            report_path = write_daily_collection_report(
                date_value="2026-07-10",
                raw_dir=base / "raw",
                report_dir=base / "data" / "reports" / "daily",
                derived_dir=base / "data" / "derived",
            )
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("- ranked_candidates: 2", report)
            self.assertIn("- reference_targets: 1", report)
            self.assertIn("## Reference Targets", report)
            self.assertIn("JPA 성능 개선 트러블슈팅", report)


def _search_records() -> list[dict[str, object]]:
    return [
        {
            "id": "a1",
            "search_layer": "target",
            "query_group": "backend",
            "query": "JPA 성능 개선",
            "sort": "sim",
            "rank": 1,
            "title_clean": "JPA 성능 개선 트러블슈팅",
            "description_clean": "Spring Boot 프로젝트에서 쿼리 병목을 해결한 회고",
            "link": "https://blog.naver.com/dev/1?b=2&a=1",
            "canonical_url": "https://blog.naver.com/dev/1?a=1&b=2",
            "blogger_name": "dev",
            "blogger_link": "https://blog.naver.com/dev",
            "postdate": "20260709",
        },
        {
            "id": "a2",
            "search_layer": "discovery",
            "query_group": "troubleshooting",
            "query": "성능 개선",
            "sort": "sim",
            "rank": 2,
            "title_clean": "JPA 성능 개선 트러블슈팅",
            "description_clean": "장애 원인 분석과 해결 방법",
            "link": "https://blog.naver.com/dev/1?a=1&b=2#section",
            "canonical_url": "https://blog.naver.com/dev/1?a=1&b=2",
            "blogger_name": "dev",
            "blogger_link": "https://blog.naver.com/dev",
            "postdate": "20260709",
        },
        {
            "id": "b1",
            "search_layer": "discovery",
            "query_group": "domains",
            "query": "AI 개발",
            "sort": "sim",
            "rank": 1,
            "title_clean": "AI 개발 국비지원 교육 모집",
            "description_clean": "취업 대비 수강 과정 소개",
            "link": "https://blog.naver.com/academy/2",
            "canonical_url": "https://blog.naver.com/academy/2",
            "blogger_name": "academy",
            "blogger_link": "https://blog.naver.com/academy",
            "postdate": "20260101",
        },
    ]


def _trend_records() -> list[dict[str, object]]:
    return [
        {
            "topic_group": "target.backend",
            "values": [{"period": "2026-07-10", "ratio": 80}],
        },
        {
            "topic_group": "discovery.domains",
            "values": [{"period": "2026-07-10", "ratio": 100}],
        },
    ]


def _body_records() -> list[dict[str, object]]:
    return [
        {
            "canonical_url": "https://blog.naver.com/dev/1?a=1&b=2",
            "status": "ok",
            "body_path": "raw/2026-07-10/blog_bodies.jsonl",
            "body_text": "raw body should not be copied to derived target records",
        },
        {
            "canonical_url": "https://blog.naver.com/academy/2",
            "status": "ok",
            "body_path": "raw/2026-07-10/blog_bodies.jsonl",
            "body_text": "marketing body should not be copied or selected by default",
        }
    ]


def _scoring_config() -> dict[str, object]:
    return {
        "weights": {
            "search_rank_score": 0.35,
            "trend_score": 0.20,
            "recency_score": 0.15,
            "tech_relevance_score": 0.15,
            "source_repeat_score": 0.10,
            "novelty_score": 0.05,
        },
        "dedup": {"duplicate_penalty": 0.35},
        "recency": {"half_life_days": 45},
        "ranking": {"top_n_daily_report": 30},
    }


if __name__ == "__main__":
    unittest.main()
