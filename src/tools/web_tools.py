"""HTTPS GET tool restricted by a fixed host allowlist."""

from typing import Any
from urllib.parse import urlparse

import httpx

from src.config import HTTP_ALLOWED_HOSTS


def get_allowed_hosts() -> list[str]:
    return sorted(HTTP_ALLOWED_HOSTS)


def http_get(
    url: str, timeout_seconds: int = 10, max_chars: int = 8_000
) -> dict[str, Any]:
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() != "https":
            return {"error": "Only https URLs are permitted."}
        if parsed.username or parsed.password:
            return {"error": "URLs containing credentials are not permitted."}

        host = (parsed.hostname or "").lower().rstrip(".")
        if host not in HTTP_ALLOWED_HOSTS:
            return {
                "error": f"Host '{host}' is not permitted by allowlist policy.",
                "allowed_hosts": get_allowed_hosts(),
            }

        timeout = min(max(int(timeout_seconds), 1), 30)
        limit = min(max(int(max_chars), 1), 20_000)
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            response = client.get(url, headers={"User-Agent": "AgentWorkbench/1.0"})
        body = response.text
        return {
            "status_code": response.status_code,
            "url": str(response.url),
            "content_type": response.headers.get("content-type", ""),
            "body": body[:limit],
            "truncated": len(body) > limit,
        }
    except (TypeError, ValueError) as exc:
        return {"error": f"Invalid request: {exc}"}
    except httpx.TimeoutException:
        return {"error": "HTTP request timed out."}
    except httpx.RequestError as exc:
        return {"error": f"HTTP request failed: {exc}"}
