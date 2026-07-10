from __future__ import annotations

from urllib.parse import urlencode

from src.common.config import ConfigError, require_env
from src.common.http import request_json


class NaverSearchClient:
    DEVELOPERS_ENDPOINT = "https://openapi.naver.com/v1/search/blog.json"

    def __init__(self, provider: str = "developers") -> None:
        self.provider = provider
        if provider != "developers":
            raise ConfigError(
                "NAVER_API_PROVIDER=api_hub is configured, but API HUB endpoints are not implemented yet."
            )
        self.client_id = require_env("NAVER_CLIENT_ID")
        self.client_secret = require_env("NAVER_CLIENT_SECRET")

    def search_blog(self, query: str, display: int, start: int, sort: str) -> dict:
        params = urlencode(
            {
                "query": query,
                "display": display,
                "start": start,
                "sort": sort,
            }
        )
        return request_json(
            f"{self.DEVELOPERS_ENDPOINT}?{params}",
            headers={
                "X-Naver-Client-Id": self.client_id,
                "X-Naver-Client-Secret": self.client_secret,
            },
        )

