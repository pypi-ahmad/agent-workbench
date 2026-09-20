"""Standalone fail-closed checks for workspace and calculator boundaries."""

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.tools.fs_tools import read_file, write_note  # noqa: E402
from src.tools.misc_tools import calc  # noqa: E402


def require_error(result: object, check: str) -> str:
    assert isinstance(result, dict), f"{check}: expected error object"
    error = result.get("error")
    assert isinstance(error, str) and error, f"{check}: expected error string"
    assert "bytes" not in result, f"{check}: returned file bytes"
    assert "text" not in result, f"{check}: returned file text"
    return error


def run() -> None:
    checks = {
        "relative_escape": require_error(read_file("../.env"), "relative escape"),
        "absolute_escape": require_error(
            read_file(r"C:\Windows\win.ini"), "absolute escape"
        ),
        "slash_note_name": require_error(
            write_note("nested/note.txt", "blocked"), "slash note name"
        ),
        "backslash_note_name": require_error(
            write_note(r"nested\note.txt", "blocked"), "backslash note name"
        ),
        "calc_import": require_error(
            calc("__import__('os')"), "calculator import"
        ),
    }
    output = {
        "status": "passed",
        "checks": checks,
    }
    cache_path = REPO_ROOT / "data" / "cache" / "sandbox_check.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"PASS: {cache_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    run()
