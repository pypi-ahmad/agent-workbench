"""File tools confined to this repository's workspace directory."""

from pathlib import Path, PureWindowsPath
from typing import Any

from src.config import WORKSPACE_DIR

DEFAULT_WORKSPACE_DIR = WORKSPACE_DIR
DEFAULT_WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
_active_workspace_dir = DEFAULT_WORKSPACE_DIR


def set_working_dir(path: str | Path) -> Path:
    """Select the fixed repository workspace and reject every other root."""
    global _active_workspace_dir
    candidate = Path(path).resolve()
    if candidate != DEFAULT_WORKSPACE_DIR:
        raise PermissionError("Working directory must be this repository's workspace directory.")
    candidate.mkdir(parents=True, exist_ok=True)
    _active_workspace_dir = candidate
    return candidate


def get_working_dir() -> Path:
    return _active_workspace_dir


def resolve_in_workspace(path_str: str) -> Path:
    """Resolve a user path and reject traversal or paths outside workspace."""
    if not isinstance(path_str, str):
        raise TypeError("Path must be a string.")

    cleaned = path_str.strip().replace("\\", "/") or "."
    if ".." in PureWindowsPath(cleaned).parts:
        raise PermissionError("Access denied: '..' path traversal is not allowed.")

    if cleaned in {".", "workspace", "./workspace"}:
        return _active_workspace_dir
    if cleaned.startswith("./"):
        cleaned = cleaned[2:]
    if cleaned.startswith("workspace/"):
        cleaned = cleaned[len("workspace/") :]

    windows_path = PureWindowsPath(cleaned)
    if windows_path.is_absolute() or windows_path.drive:
        target = Path(str(windows_path)).resolve()
    else:
        target = (_active_workspace_dir / cleaned).resolve()

    try:
        target.relative_to(_active_workspace_dir)
    except ValueError as exc:
        raise PermissionError("Access denied: path resolves outside workspace.") from exc
    return target


def read_file(path: str, max_chars: int = 10_000) -> dict[str, Any]:
    try:
        target = resolve_in_workspace(path)
        if not target.is_file():
            return {"error": f"File does not exist in workspace: {path}"}
        limit = min(max(int(max_chars), 1), 50_000)
        content = target.read_text(encoding="utf-8", errors="replace")
        relative = target.relative_to(_active_workspace_dir).as_posix()
        return {
            "path": f"workspace/{relative}",
            "content": content[:limit],
            "total_chars": len(content),
            "truncated": len(content) > limit,
        }
    except (PermissionError, TypeError, ValueError) as exc:
        return {"error": str(exc)}
    except OSError as exc:
        return {"error": f"Failed to read file: {exc}"}


def list_dir(path: str = ".") -> dict[str, Any]:
    try:
        target = resolve_in_workspace(path)
        if not target.is_dir():
            return {"error": f"Directory does not exist in workspace: {path}"}
        entries = [
            {
                "name": item.name,
                "is_dir": item.is_dir(),
                "size_bytes": item.stat().st_size if item.is_file() else None,
            }
            for item in sorted(
                target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())
            )
        ]
        relative = target.relative_to(_active_workspace_dir).as_posix()
        return {
            "directory": "workspace" if relative == "." else f"workspace/{relative}",
            "entries": entries,
            "count": len(entries),
        }
    except (PermissionError, TypeError, ValueError) as exc:
        return {"error": str(exc)}
    except OSError as exc:
        return {"error": f"Failed to list directory: {exc}"}


def write_note(title: str, content: str, mode: str = "append") -> dict[str, Any]:
    """Write a UTF-8 note under workspace/notes/."""
    try:
        if not title.strip():
            return {"error": "Note title cannot be empty."}
        title_path = PureWindowsPath(title.replace("\\", "/"))
        if ".." in title_path.parts:
            return {"error": "Access denied: '..' path traversal is not allowed."}
        if title_path.is_absolute() or title_path.drive:
            return {"error": "Access denied: absolute note paths are not allowed."}

        filename = Path(title).name
        if not Path(filename).suffix:
            filename += ".md"
        target = resolve_in_workspace(f"notes/{filename}")
        target.parent.mkdir(parents=True, exist_ok=True)

        if mode not in {"append", "overwrite"}:
            return {"error": "Mode must be 'append' or 'overwrite'."}
        existing = (
            target.read_text(encoding="utf-8")
            if mode == "append" and target.exists()
            else ""
        )
        separator = "\n" if existing and not existing.endswith("\n") else ""
        target.write_text(existing + separator + content, encoding="utf-8")
        relative = target.relative_to(_active_workspace_dir).as_posix()
        return {
            "status": "ok",
            "path": f"workspace/{relative}",
            "mode": mode,
            "bytes_written": len(content.encode("utf-8")),
        }
    except (PermissionError, TypeError, ValueError) as exc:
        return {"error": str(exc)}
    except OSError as exc:
        return {"error": f"Failed to write note: {exc}"}
