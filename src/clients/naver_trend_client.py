from __future__ import annotations

from src.common.config import ConfigError, require_env
from src.common.http import request_json


class NaverTrendClient:
    DEVELOPERS_ENDPOINT = "https://openapi.naver.com/v1/datalab/search"

    def __init__(self, provider: str = "developers") -> None:
        self.provider = provider
        if provider != "developers":
            raise ConfigError(
                "NAVER_API_PROVIDER=api_hub is configured, but API HUB endpoints are not implemented yet."
            )
        self.client_id = require_env("NAVER_CLIENT_ID")
        self.client_secret = require_env("NAVER_CLIENT_SECRET")

    def get_search_trend(
        self,
        topic_group: dict,
        start_date: str,
        end_date: str,
        time_unit: str,
    ) -> dict:
        body = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
            "keywordGroups": [topic_group],
        }
        return request_json(
            self.DEVELOPERS_ENDPOINT,
            method="POST",
            headers={
                "X-Naver-Client-Id": self.client_id,
                "X-Naver-Client-Secret": self.client_secret,
            },
            body=body,
        )

