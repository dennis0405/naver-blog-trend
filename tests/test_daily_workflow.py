from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DailyWorkflowContractTests(unittest.TestCase):
    def test_velog_collection_runs_before_shared_body_fetch(self) -> None:
        workflow = (ROOT / ".github/workflows/daily_collect.yml").read_text(encoding="utf-8")

        velog = "python3 -m src.collectors.collect_velog_posts"
        body_fetch = "python3 -m src.collectors.fetch_blog_bodies"
        self.assertIn(velog, workflow)
        self.assertLess(workflow.index(velog), workflow.index(body_fetch))

    def test_readme_documents_required_repository_secrets(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Repository secrets", readme)
        self.assertIn("NAVER_API_PROVIDER", readme)
        self.assertIn("NAVER_CLIENT_ID", readme)
        self.assertIn("NAVER_CLIENT_SECRET", readme)
        self.assertIn("Velog 공개 페이지 수집에는 secret이 필요하지 않다", readme)


if __name__ == "__main__":
    unittest.main()
