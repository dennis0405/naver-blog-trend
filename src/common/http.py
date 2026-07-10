from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class HttpRequestError(RuntimeError):
    pass


def request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    retries: int = 3,
    timeout: int = 20,
) -> dict[str, Any]:
    encoded_body = None
    request_headers = dict(headers or {})
    if body is not None:
        encoded_body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request_headers.setdefault("Accept", "application/json")

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(url, data=encoded_body, headers=request_headers, method=method)
            with urlopen(request, timeout=timeout) as response:
                payload = response.read().decode("utf-8")
            parsed = json.loads(payload)
            if not isinstance(parsed, dict):
                raise HttpRequestError(f"JSON response is not an object: {url}")
            return parsed
        except HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            last_error = HttpRequestError(f"HTTP {exc.code} for {url}: {body_text[:300]}")
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
        if attempt < retries - 1:
            time.sleep(2**attempt)
    raise HttpRequestError(str(last_error))

