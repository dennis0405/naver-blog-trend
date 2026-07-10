from __future__ import annotations

import hashlib
import html
import re
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse


def stable_id(*parts: object) -> str:
    joined = "|".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def clean_html_text(value: str | None) -> str:
    if not value:
        return ""
    without_tags = re.sub(r"<[^>]+>", "", value)
    return normalize_whitespace(html.unescape(without_tags))


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    query_pairs = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)]
    query = urlencode(sorted(query_pairs))
    return urlunparse((scheme, netloc, parsed.path, "", query, ""))


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0
        self.iframe_sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): value or "" for key, value in attrs}
        if tag in {"script", "style", "noscript"}:
            self.skip_depth += 1
        if tag == "iframe":
            src = attr_map.get("src", "")
            if src:
                self.iframe_sources.append(src)
        if tag in {"p", "br", "div", "section", "article", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self.skip_depth:
            self.skip_depth -= 1
        if tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        collapsed_lines = [
            normalize_whitespace(html.unescape(line))
            for line in "".join(self.parts).splitlines()
        ]
        return "\n".join(line for line in collapsed_lines if line)


def extract_text_and_iframes(html_text: str, base_url: str) -> tuple[str, list[str]]:
    parser = _TextExtractor()
    parser.feed(html_text)
    iframe_urls = [urljoin(base_url, src) for src in parser.iframe_sources]
    return parser.text(), iframe_urls

