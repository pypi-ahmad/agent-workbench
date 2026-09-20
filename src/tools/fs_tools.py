"""Real filesystem tools confined to the repository workspace."""

from pathlib import PureWindowsPath
import re
from typing import Any

from src.tools.file_tools import get_working_dir, resolve_in_workspace

MAX_READ_BYTES = 64 * 1024
_SIMPLE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def list_dir(relative_path: str = ".") -> dict[str, Any]:
    """List one directory under workspace/."""
    try:
        target = resolve_in_workspace(relative_path)
        if not target.is_dir():
            return {"error": f"Directory does not exist: {relative_path}"}
        entries = [
            {
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "bytes": item.stat().st_size if item.is_file() else None,
            }
            for item in sorted(
                target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())
            )
        ]
        relative = target.relative_to(get_working_dir()).as_posix()
        return {
            "path": "." if relative == "." else relative,
            "entries": entries,
        }
    except (OSError, PermissionError, TypeError, ValueError) as exc:
        return {"error": str(exc)}


def read_file(relative_path: str) -> dict[str, Any]:
    """Read one UTF-8 text file under workspace/, capped at 64 KiB."""
    try:
        target = resolve_in_workspace(relative_path)
        if not target.is_file():
            return {"error": f"File does not exist: {relative_path}"}
        size = target.stat().st_size
        if size > MAX_READ_BYTES:
            return {
                "error": f"File exceeds 64 KiB limit: {relative_path}",
                "bytes": size,
            }
        try:
            text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return {"error": f"File is not valid UTF-8 text: {relative_path}"}
        return {
            "path": target.relative_to(get_working_dir()).as_posix(),
            "bytes": size,
            "text": text,
        }
    except (OSError, PermissionError, TypeError, ValueError) as exc:
        return {"error": str(exc)}


def write_note(name: str, text: str) -> dict[str, Any]:
    """Write one note using a simple filename under workspace/notes/."""
    try:
        if not isinstance(name, str) or not _SIMPLE_NAME.fullmatch(name):
            return {"error": "Note name must be a simple filename."}
        parsed = PureWindowsPath(name)
        stem = parsed.stem.upper()
        if parsed.name != name or stem in _WINDOWS_RESERVED or name.endswith((".", " ")):
            return {"error": "Note name must be a simple filename."}
        if not isinstance(text, str):
            return {"error": "Note text must be a string."}

        target = resolve_in_workspace(f"notes/{name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return {
            "path": target.relative_to(get_working_dir()).as_posix(),
            "bytes": len(text.encode("utf-8")),
        }
    except (OSError, PermissionError, TypeError, ValueError) as exc:
        return {"error": str(exc)}
