"""Application constants and security policy."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = (REPO_ROOT / "workspace").resolve()

AGNES_BASE_URL = "https://apihub.agnes-ai.com/v1"
AGNES_MODEL = "agnes-3.0-flash"

HTTP_ALLOWED_HOSTS = frozenset({"example.com", "httpbin.org"})

DEFAULT_MAX_STEPS = 8
HARD_MAX_STEPS = 16
TOOL_RESULT_MAX_CHARS = 1_200
