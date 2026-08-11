from __future__ import annotations

import unittest
from pathlib import Path


SKILL_PATH = (
    Path(__file__).resolve().parents[1]
    / ".agents"
    / "skills"
    / "review-draft"
    / "SKILL.md"
)


class ReviewDraftSkillContractTests(unittest.TestCase):
    def test_contract_requires_independent_platform_outputs(self) -> None:
        skill = SKILL_PATH.read_text(encoding="utf-8")

        self.assertIn("posts/final/{draft_stem}/post.velog.md", skill)
        self.assertIn("posts/final/{draft_stem}/post.naver.txt", skill)
        self.assertIn("knowledge/style/platforms/naver.md", skill)
        self.assertIn("knowledge/style/platforms/velog.md", skill)
        self.assertIn("Never derive one platform's prose from the other", skill)
        self.assertIn("_workspace/{run_id}/common.structure.md", skill)
        self.assertIn("Apply humanize-korean twice", skill)
        self.assertIn("install_final_artifacts.py", skill)
        self.assertNotIn("posts/final/{draft_stem}/post.final.md", skill)

    def test_contract_requires_cross_platform_factual_parity(self) -> None:
        skill = SKILL_PATH.read_text(encoding="utf-8")

        self.assertIn("## Cross-Platform Factual Parity", skill)
        self.assertIn("## Platform Verdicts", skill)
        self.assertIn("cross-platform factual contradiction", skill)


if __name__ == "__main__":
    unittest.main()
