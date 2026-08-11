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
from src.rankers.score_candidates import (
    score_candidates,
    score_velog_candidates,
    write_candidates_sqlite,
)


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
                output_path=base / "data" / "derived" / "2026-07-10" / "reference_targets.jsonl",
            )

            self.assertEqual(len(targets), 1)
            self.assertEqual(targets[0]["canonical_url"], "https://blog.naver.com/dev/1?a=1&b=2")
            target_text = (
                base / "data" / "derived" / "2026-07-10" / "reference_targets.jsonl"
            ).read_text(encoding="utf-8")
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
                output_path=base / "data" / "derived" / "2026-07-10" / "reference_targets.jsonl",
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

    def test_scores_velog_candidates_with_cohort_popularity_and_style_quality(self) -> None:
        candidates = score_velog_candidates(
            _velog_records(),
            _velog_body_records(),
            date_value="2026-08-11",
            scoring_config=_scoring_config(),
        )

        self.assertEqual([candidate["source"] for candidate in candidates], ["velog", "velog"])
        self.assertEqual(candidates[0]["author_name"], "technical-writer")
        self.assertGreater(
            candidates[0]["score_components"]["popularity_score"],
            candidates[1]["score_components"]["popularity_score"],
        )
        self.assertGreater(candidates[0]["style_quality_score"], 0.5)
        self.assertNotIn("body_text", candidates[0])

    def test_daily_report_includes_velog_source_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            raw_date = base / "raw" / "2026-08-11"
            write_jsonl(raw_date / "naver_search.jsonl", [])
            write_jsonl(raw_date / "naver_trend.jsonl", [])
            write_jsonl(raw_date / "velog_posts.jsonl", _velog_records())

            report_path = write_daily_collection_report(
                date_value="2026-08-11",
                raw_dir=base / "raw",
                report_dir=base / "reports",
                derived_dir=base / "derived",
            )
            report = report_path.read_text(encoding="utf-8")

            self.assertIn("# Daily Naver and Velog Tech Blog Signal Report", report)
            self.assertIn("- velog_candidates: 2", report)
            self.assertIn("| velog |", report)

    def test_reference_targets_apply_source_quotas_style_gate_and_round_robin(self) -> None:
        candidates = [
            _ranked_candidate("naver-a", "naver", 0.9, 0.8),
            _ranked_candidate("naver-b", "naver", 0.8, 0.7),
            _ranked_candidate("naver-shallow", "naver", 1.0, 0.1),
            _ranked_candidate("velog-a", "velog", 0.95, 0.9),
        ]

        targets = select_reference_targets(
            candidates,
            top_n=4,
            min_tech_relevance=0.3,
            min_style_quality=0.5,
            source_quotas={"naver": 2, "velog": 2},
        )

        self.assertEqual(
            [(target["source"], target["candidate_id"]) for target in targets],
            [("naver", "naver-a"), ("velog", "velog-a"), ("naver", "naver-b")],
        )
        self.assertEqual([target["rank_position"] for target in targets], [1, 2, 3])

    def test_velog_database_troubleshooting_title_is_technically_relevant(self) -> None:
        record = {
            **_velog_records()[0],
            "id": "n-plus-one",
            "canonical_url": "https://velog.io/@writer/n-plus-one",
            "title_clean": "N+1 문제 실측과 해결",
            "description_clean": "데이터베이스 쿼리 병목을 분석한 기록",
            "link": "https://velog.io/@writer/n-plus-one",
        }

        candidate = score_velog_candidates(
            [record],
            [],
            date_value="2026-08-11",
            scoring_config=_scoring_config(),
        )[0]

        self.assertGreaterEqual(
            candidate["score_components"]["tech_relevance_score"], 0.3
        )


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
            "naver": {
                "rank_score": 0.35,
                "popularity_score": 0.20,
                "recency_score": 0.15,
                "tech_relevance_score": 0.15,
                "source_repeat_score": 0.10,
                "novelty_score": 0.05,
            },
            "velog": {
                "rank_score": 0.25,
                "popularity_score": 0.20,
                "recency_score": 0.15,
                "tech_relevance_score": 0.20,
                "source_repeat_score": 0.10,
                "novelty_score": 0.10,
            },
        },
        "dedup": {"duplicate_penalty": 0.35},
        "recency": {"half_life_days": 45},
        "ranking": {"top_n_daily_report": 30},
    }


def _velog_records() -> list[dict[str, object]]:
    return [
        {
            "id": "velog-a",
            "source": "velog",
            "canonical_url": "https://velog.io/@technical-writer/migration",
            "title_clean": "Spring 마이그레이션 장애 해결 기록",
            "description_clean": "원인 분석과 배포 검증 과정을 정리한 기술 글",
            "author_name": "technical-writer",
            "author_url": "https://velog.io/@technical-writer",
            "postdate": "20260810",
            "best_rank": 1,
            "rank": 1,
            "tabs": ["trending_week", "curated"],
            "tab_ranks": {"trending_week": 1, "curated": 2},
            "likes": 20,
            "comments_count": 4,
            "link": "https://velog.io/@technical-writer/migration",
        },
        {
            "id": "velog-b",
            "source": "velog",
            "canonical_url": "https://velog.io/@another/dev-note",
            "title_clean": "개발 회고",
            "description_clean": "프로젝트에서 배운 점",
            "author_name": "another",
            "author_url": "https://velog.io/@another",
            "postdate": "20260809",
            "best_rank": 2,
            "rank": 2,
            "tabs": ["trending_week"],
            "tab_ranks": {"trending_week": 2},
            "likes": 1,
            "comments_count": 0,
            "link": "https://velog.io/@another/dev-note",
        },
    ]


def _velog_body_records() -> list[dict[str, object]]:
    structured_body = "\n".join(
        [
            "문제 상황과 원인을 확인했다.",
            "서버 배포 과정에서 장애가 발생했다.",
            "로그와 코드를 비교해 원인을 분석했다.",
            "첫 번째 해결 방법은 실패했다.",
            "설정을 변경하고 다시 배포했다.",
            "테스트와 모니터링으로 결과를 검증했다.",
        ]
        * 20
    )
    return [
        {
            "canonical_url": "https://velog.io/@technical-writer/migration",
            "source": "velog",
            "status": "ok",
            "body_path": "raw/2026-08-11/blog_bodies.jsonl",
            "body_text": structured_body,
        },
        {
            "canonical_url": "https://velog.io/@another/dev-note",
            "source": "velog",
            "status": "ok",
            "body_path": "raw/2026-08-11/blog_bodies.jsonl",
            "body_text": "짧은 개발 회고",
        },
    ]


def _ranked_candidate(
    candidate_id: str,
    source: str,
    total_score: float,
    style_quality_score: float,
) -> dict[str, object]:
    return {
        "date": "2026-08-11",
        "candidate_id": candidate_id,
        "source": source,
        "canonical_url": f"https://example.com/{candidate_id}",
        "title_clean": f"{candidate_id} 기술 개발 문제 해결",
        "author_name": f"author-{candidate_id}",
        "postdate": "20260810",
        "discovery_channel": source,
        "query_group": "technical",
        "query": "개발",
        "best_rank": 1,
        "has_body": True,
        "body_status": "ok",
        "body_path": "raw/body.jsonl",
        "total_score": total_score,
        "style_quality_score": style_quality_score,
        "score_components": {"tech_relevance_score": 0.8},
    }


if __name__ == "__main__":
    unittest.main()
