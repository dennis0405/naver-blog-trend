from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / ".agents"
    / "skills"
    / "review-draft"
    / "scripts"
    / "render_naver_post.py"
)
SPEC = importlib.util.spec_from_file_location("render_naver_post", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"failed to load renderer: {SCRIPT_PATH}")
RENDERER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RENDERER)


class RenderNaverPostTests(unittest.TestCase):
    def test_renders_markdown_as_naver_friendly_plain_text(self) -> None:
        source = """# Apple 계정 이전

## 확인 범위

본문의 `sub`와 **Team ID**를 확인했다.

| 구분 | 준비한 정보 |
|---|---|
| 기존 팀 | Team ID, `.p8` |
| 새 팀 | 새 profile |

```sql
SELECT id
FROM account;
```

- [Apple 문서](https://example.com/docs)
"""

        self.assertEqual(
            RENDERER.render_naver_post(source),
            """Apple 계정 이전

확인 범위

본문의 sub와 Team ID를 확인했다.

구분: 기존 팀
준비한 정보: Team ID, .p8

구분: 새 팀
준비한 정보: 새 profile

SELECT id
FROM account;

- Apple 문서 (https://example.com/docs)
""",
        )

    def test_normalizes_non_breaking_spaces_only_outside_code(self) -> None:
        source = """# 제목

본문\u00a0문장

```text
code\u00a0value
```
"""

        rendered = RENDERER.render_naver_post(source)

        self.assertIn("본문 문장", rendered)
        self.assertIn("code\u00a0value", rendered)

    def test_supports_escaped_table_pipes_and_local_images(self) -> None:
        source = """# 제목

| 구분 | 값 |
|---|---|
| 연산 | A \\| B |

![구조도](images/architecture.png)
"""

        rendered = RENDERER.render_naver_post(source)

        self.assertIn("A | B", rendered)
        self.assertIn("[이미지: 구조도]", rendered)
        self.assertNotIn("images/architecture.png", rendered)
        self.assertNotIn("![", rendered)

    def test_rejects_unclosed_code_fence(self) -> None:
        with self.assertRaisesRegex(RENDERER.NaverRenderError, "unclosed"):
            RENDERER.render_naver_post("# 제목\n\n```text\nvalue\n")

    def test_omits_naver_ui_placeholders_and_normalizes_common_syntax(self) -> None:
        source = """# 제목

AI 활용 설정
사진 설명을 입력하세요.

- [ ] 이전 전 확인
- [x] 이전 완료

~~취소선~~과 _강조_, <https://example.com>을 확인했다.
"""

        rendered = RENDERER.render_naver_post(source)

        self.assertNotIn("AI 활용 설정", rendered)
        self.assertNotIn("사진 설명을 입력하세요.", rendered)
        self.assertIn("□ 이전 전 확인", rendered)
        self.assertIn("☑ 이전 완료", rendered)
        self.assertIn("취소선과 강조, https://example.com을 확인했다.", rendered)

    def test_supports_tilde_fences_and_tables_without_outer_pipes(self) -> None:
        source = """# 제목

구분 | 값
--- | ---
기존 팀 | Team ID
새 팀 | profile

~~~text
literal **text**
~~~
"""

        self.assertEqual(
            RENDERER.render_naver_post(source),
            """제목

구분: 기존 팀
값: Team ID

구분: 새 팀
값: profile

literal **text**
""",
        )

    def test_requires_exactly_one_leading_h1(self) -> None:
        with self.assertRaisesRegex(RENDERER.NaverRenderError, "begin with one H1"):
            RENDERER.render_naver_post("본문부터 시작한다.\n")

        with self.assertRaisesRegex(RENDERER.NaverRenderError, "exactly one H1"):
            RENDERER.render_naver_post("# 첫 제목\n\n# 둘째 제목\n")


if __name__ == "__main__":
    unittest.main()
