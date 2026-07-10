from __future__ import annotations

import unittest

from src.common.text import canonicalize_url, clean_html_text, extract_text_and_iframes


class TextCleaningTests(unittest.TestCase):
    def test_clean_html_text(self) -> None:
        self.assertEqual(clean_html_text("<b>Spring</b>&nbsp;Boot"), "Spring Boot")

    def test_canonicalize_url_removes_fragment_and_sorts_query(self) -> None:
        self.assertEqual(
            canonicalize_url("HTTPS://Blog.Naver.com/post?b=2&a=1#section"),
            "https://blog.naver.com/post?a=1&b=2",
        )

    def test_extract_text_and_iframes(self) -> None:
        text, iframes = extract_text_and_iframes(
            '<html><body><iframe src="/PostView.naver?x=1"></iframe><p>Hello</p></body></html>',
            "https://blog.naver.com/user/1",
        )
        self.assertIn("Hello", text)
        self.assertEqual(iframes[0], "https://blog.naver.com/PostView.naver?x=1")


if __name__ == "__main__":
    unittest.main()

