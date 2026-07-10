from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.common.text import extract_text_and_iframes


@dataclass(frozen=True)
class BodyFetchResult:
    requested_url: str
    fetched_url: str
    status: str
    body_text: str
    error: str = ""


class PublicBodyFetcher:
    def __init__(self, timeout: int = 20, max_bytes: int = 2_000_000) -> None:
        self.timeout = timeout
        self.max_bytes = max_bytes

    def fetch_text(self, url: str) -> BodyFetchResult:
        try:
            first_url, html_text = self._fetch_html(url)
            text, iframe_urls = extract_text_and_iframes(html_text, first_url)
            main_frame = self._select_naver_main_frame(iframe_urls)
            if main_frame:
                second_url, second_html = self._fetch_html(main_frame)
                second_text, _ = extract_text_and_iframes(second_html, second_url)
                if len(second_text) > len(text):
                    return BodyFetchResult(url, second_url, "ok", second_text)
            return BodyFetchResult(url, first_url, "ok", text)
        except (HTTPError, URLError, TimeoutError, UnicodeDecodeError, ValueError) as exc:
            return BodyFetchResult(url, url, "error", "", str(exc))

    def _fetch_html(self, url: str) -> tuple[str, str]:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError(f"Unsupported URL scheme: {url}")
        request = Request(
            url,
            headers={
                "User-Agent": "naver-tech-blog-agent/0.1 (+https://github.com/)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        with urlopen(request, timeout=self.timeout) as response:
            raw = response.read(self.max_bytes + 1)
            if len(raw) > self.max_bytes:
                raw = raw[: self.max_bytes]
            charset = response.headers.get_content_charset() or self._charset_from_html(raw)
            return response.geturl(), raw.decode(charset or "utf-8", errors="replace")

    @staticmethod
    def _charset_from_html(raw: bytes) -> str | None:
        prefix = raw[:2048].decode("ascii", errors="ignore")
        match = re.search(r"charset=['\"]?([A-Za-z0-9_\-]+)", prefix, re.IGNORECASE)
        return match.group(1) if match else None

    @staticmethod
    def _select_naver_main_frame(iframe_urls: list[str]) -> str | None:
        for iframe_url in iframe_urls:
            lower = iframe_url.lower()
            if "postview.naver" in lower or "blog.naver.com" in lower:
                return iframe_url
        return None

