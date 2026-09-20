"""OpenAI SDK clients for Agnes and optional compatible providers."""

import os
import time
from typing import Any

from openai import OpenAI

from src.config import AGNES_BASE_URL, AGNES_MODEL


PROVIDER_DEFINITIONS: dict[str, dict[str, Any]] = {
    "Agnes AI": {
        "api_key_env": "AGNESAI_API_KEY",
        "base_url": AGNES_BASE_URL,
        "models": [AGNES_MODEL],
    },
    "OpenAI-compatible": {
        "api_key_env": "OPENAI_API_KEY",
        "base_url_env": "OPENAI_BASE_URL",
        "models": ["gpt-4.1-mini"],
    },
    "Google Gemini": {
        "api_key_env": "GOOGLE_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "models": ["gemini-2.5-flash"],
    },
}


def detect_available_providers() -> dict[str, dict[str, Any]]:
    """Return Agnes plus optional providers whose required variables exist."""
    available = {"Agnes AI": PROVIDER_DEFINITIONS["Agnes AI"]}
    if os.environ.get("OPENAI_API_KEY", "").strip() and os.environ.get(
        "OPENAI_BASE_URL", ""
    ).strip():
        available["OpenAI-compatible"] = PROVIDER_DEFINITIONS["OpenAI-compatible"]
    if os.environ.get("GOOGLE_API_KEY", "").strip():
        available["Google Gemini"] = PROVIDER_DEFINITIONS["Google Gemini"]
    return available


def get_client(provider_name: str = "Agnes AI") -> tuple[OpenAI | None, str | None]:
    """Create an SDK client without logging or persisting credential values."""
    config = detect_available_providers().get(provider_name)
    if config is None:
        return None, f"Provider is unavailable: {provider_name}"

    key_name = config["api_key_env"]
    api_key = os.environ.get(key_name, "").strip()
    if not api_key:
        return None, f"Required environment variable {key_name} is unavailable."

    base_url = config.get("base_url")
    if provider_name == "OpenAI-compatible":
        base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
    if not base_url:
        return None, f"Base URL is unavailable for provider: {provider_name}"

    return OpenAI(api_key=api_key, base_url=base_url), None


DEFAULT_AGNES_BASE_URL = AGNES_BASE_URL
DEFAULT_AGNES_MODEL = AGNES_MODEL


def chat_completion_with_429_retries(
    client: OpenAI,
    request: dict[str, Any],
    *,
    max_retries: int = 3,
    sleep: Any = time.sleep,
) -> Any:
    """Create a Chat Completion and retry only HTTP 429 responses."""
    for attempt in range(max_retries + 1):
        try:
            return client.chat.completions.create(**request)
        except Exception as exc:
            if getattr(exc, "status_code", None) != 429 or attempt == max_retries:
                raise
            sleep(min(2**attempt, 8))
    raise RuntimeError("Unreachable retry state.")
