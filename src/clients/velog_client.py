from __future__ import annotations

import json
import re
import time
from datetime import datetime
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


FLIGHT_PUSH_RE = re.compile(
    r"self\.__next_f\.push\(\[1,(\"(?:\\.|[^\"\\])*\")\]\)"
)


class VelogClientError(RuntimeError):
    pass


class VelogPayloadError(ValueError):
    pass


class VelogClient:
    TAB_URLS = {
        "trending_week": "https://velog.io/trending/week",
        "curated": "https://velog.io/curated",
    }

    def __init__(self, *, timeout: int = 20, retries: int = 3, max_bytes: int = 5_000_000) -> None:
        self.timeout = timeout
        self.retries = retries
        self.max_bytes = max_bytes

    def fetch_tab_html(self, tab: str) -> str:
        try:
            url = self.TAB_URLS[tab]
        except KeyError as exc:
            raise ValueError(f"unsupported Velog tab: {tab}") from exc

        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                request = Request(
                    url,
                    headers={
                        "User-Agent": "naver-velog-blog-agent/0.2 (+https://github.com/)",
                        "Accept": "text/html,application/xhtml+xml",
                    },
                )
                with urlopen(request, timeout=self.timeout) as response:
                    raw = response.read(self.max_bytes + 1)
                    if len(raw) > self.max_bytes:
                        raise VelogClientError(f"Velog response exceeded {self.max_bytes} bytes")
                    charset = response.headers.get_content_charset() or "utf-8"
                    return raw.decode(charset, errors="replace")
            except (HTTPError, URLError, TimeoutError, UnicodeDecodeError, VelogClientError) as exc:
                last_error = exc
            if attempt < self.retries - 1:
                time.sleep(2**attempt)
        raise VelogClientError(f"failed to fetch public Velog tab {tab}: {type(last_error).__name__}")


def parse_velog_posts(
    html_text: str,
    *,
    tab: str,
    limit: int = 20,
) -> list[dict[str, object]]:
    """Return validated, ordered public Velog posts from a flight payload."""
    if tab not in VelogClient.TAB_URLS:
        raise ValueError(f"unsupported Velog tab: {tab}")
    if limit < 1:
        raise ValueError("limit must be >= 1")

    records: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    for segment in _flight_segments(html_text):
        for payload in _json_values(segment):
            for candidate in _walk_json(payload):
                record = _public_post_record(candidate, tab=tab, rank=len(records) + 1)
                if record is None:
                    continue
                post_id = str(record["id"])
                canonical_url = str(record["canonical_url"])
                if post_id in seen_ids or canonical_url in seen_urls:
                    continue
                records.append(record)
                seen_ids.add(post_id)
                seen_urls.add(canonical_url)
                if len(records) >= limit:
                    return records

    if not records:
        raise VelogPayloadError(f"no valid public posts found in Velog {tab} payload")
    return records


def _flight_segments(html_text: str) -> Iterator[str]:
    for match in FLIGHT_PUSH_RE.finditer(html_text):
        try:
            decoded = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, str):
            yield decoded


def _json_values(segment: str) -> Iterator[object]:
    decoder = json.JSONDecoder()
    index = 0
    while index < len(segment):
        if segment[index] not in "[{":
            index += 1
            continue
        try:
            value, end = decoder.raw_decode(segment, index)
        except json.JSONDecodeError:
            index += 1
            continue
        yield value
        index = end


def _walk_json(value: object) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _public_post_record(
    candidate: dict[str, Any],
    *,
    tab: str,
    rank: int,
) -> dict[str, object] | None:
    if candidate.get("is_private") is True:
        return None
    user = candidate.get("user")
    if not isinstance(user, dict):
        return None

    required = {
        "id": candidate.get("id"),
        "title": candidate.get("title"),
        "url_slug": candidate.get("url_slug") or candidate.get("urlSlug"),
        "released_at": candidate.get("released_at") or candidate.get("releasedAt"),
        "username": user.get("username"),
    }
    if any(not isinstance(value, str) or not value.strip() for value in required.values()):
        return None

    released_at = str(required["released_at"])
    try:
        postdate = datetime.fromisoformat(released_at.replace("Z", "+00:00")).strftime("%Y%m%d")
    except ValueError:
        return None

    username = str(required["username"]).strip()
    slug = str(required["url_slug"]).strip()
    canonical_url = f"https://velog.io/@{quote(username, safe='')}/{quote(slug, safe='-._~')}"
    return {
        "id": str(required["id"]).strip(),
        "tab": tab,
        "rank": rank,
        "canonical_url": canonical_url,
        "title_clean": str(required["title"]).strip(),
        "description_clean": str(
            candidate.get("short_description") or candidate.get("shortDescription") or ""
        ).strip(),
        "author_name": username,
        "author_url": f"https://velog.io/@{quote(username, safe='')}",
        "postdate": postdate,
        "released_at": released_at,
        "likes": _non_negative_int(candidate.get("likes")),
        "comments_count": _non_negative_int(
            candidate.get("comments_count", candidate.get("comments"))
        ),
    }


def _non_negative_int(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
