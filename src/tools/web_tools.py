"""HTTP GET tool with host allowlist enforcement using httpx."""

import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import httpx

DEFAULT_ALLOWLIST = {
    "api.github.com",
    "raw.githubusercontent.com",
    "httpbin.org",
    "en.wikipedia.org",
    "wttr.in",
    "dummyjson.com",
    "jsonplaceholder.typicode.com",
    "ipinfo.io",
    "api.coindesk.com",
}


def get_allowed_hosts() -> List[str]:
    """Retrieve combined allowed hosts from default and environment."""
    extra = os.environ.get("WORKBENCH_ALLOWED_HOSTS", "").strip()
    hosts = set(DEFAULT_ALLOWLIST)
    if extra:
        for host in extra.split(","):
            cleaned = host.strip().lower()
            if cleaned:
                hosts.add(cleaned)
    return sorted(hosts)


def http_get(url: str, timeout_seconds: int = 10, max_chars: int = 8000) -> Dict[str, Any]:
    """Perform an HTTP GET request to an allowed host using httpx.
    
    Args:
        url: Target HTTPS URL.
        timeout_seconds: Request timeout in seconds (max 30).
        max_chars: Maximum characters of response body to return.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return {"error": f"Invalid URL scheme '{parsed.scheme}'. Only https is permitted by policy."}

        host = (parsed.hostname or "").lower()
        allowed = get_allowed_hosts()

        if host not in allowed:
            return {
                "error": f"Host '{host}' is not permitted by allowlist policy.",
                "allowed_hosts": allowed,
            }

        timeout = min(max(1, timeout_seconds), 30)
        headers = {"User-Agent": "AgentWorkbench/1.0"}
        
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            text = response.text
            truncated = len(text) > max_chars
            content = text[:max_chars] if truncated else text

            return {
                "status_code": response.status_code,
                "url": str(response.url),
                "headers": dict(response.headers),
                "truncated": truncated,
                "body": content,
            }
    except httpx.TimeoutException:
        return {"error": f"Request timed out after {timeout_seconds} seconds."}
    except httpx.RequestError as e:
        return {"error": f"HTTP request failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error during HTTP GET: {str(e)}"}
