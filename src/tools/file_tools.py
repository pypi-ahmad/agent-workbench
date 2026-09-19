"""Safe file and note tools strictly sandboxed to the workspace directory."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

DEFAULT_WORKSPACE_DIR = Path("D:/AI/Github/agent-workbench/workspace").resolve()
DEFAULT_WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
_active_workspace_dir: Path = DEFAULT_WORKSPACE_DIR


def set_working_dir(path: Union[str, Path]) -> Path:
    """Set active workspace directory (must be workspace root)."""
    global _active_workspace_dir
    p = Path(path).resolve()
    p.mkdir(parents=True, exist_ok=True)
    _active_workspace_dir = p
    return _active_workspace_dir


def get_working_dir() -> Path:
    """Retrieve active workspace directory."""
    return _active_workspace_dir


def resolve_in_workspace(path_str: str) -> Path:
    """Resolve a path strictly inside workspace/ directory.
    
    Rejects any attempt to read or access files above workspace/.
    """
    cleaned = path_str.strip().replace("\\", "/")

    # If path is empty, ".", or "workspace", point to root of workspace
    if cleaned in ("", ".", "workspace", "./workspace", "/workspace"):
        return _active_workspace_dir.resolve()

    # Strip leading "./" or "workspace/" prefixes
    if cleaned.startswith("./"):
        cleaned = cleaned[2:]
    if cleaned.startswith("workspace/"):
        cleaned = cleaned[len("workspace/"):]

    # Remove leading slashes so it is treated as relative to workspace
    cleaned = cleaned.lstrip("/")

    # Resolve target path relative to active workspace directory
    target = (_active_workspace_dir / cleaned).resolve()

    # Boundary enforcement: must be strictly inside _active_workspace_dir
    try:
        target.relative_to(_active_workspace_dir.resolve())
    except ValueError:
        raise PermissionError(f"Access denied: Path '{path_str}' resolves outside workspace boundary.")

    return target


def read_file(path: str, max_chars: int = 10000) -> Dict[str, Any]:
    """Read contents of a text file strictly inside the workspace.
    
    Args:
        path: Path to the file inside workspace/ to read.
        max_chars: Maximum characters to return to avoid token overflow.
    """
    try:
        target_path = resolve_in_workspace(path)
        if not target_path.exists():
            return {"error": f"File does not exist in workspace: {path}"}
        if not target_path.is_file():
            return {"error": f"Path is not a regular file: {path}"}
        
        try:
            content = target_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = target_path.read_text(encoding="latin-1", errors="replace")

        truncated = len(content) > max_chars
        output_content = content[:max_chars] if truncated else content

        rel_path = target_path.relative_to(_active_workspace_dir.resolve()).as_posix()
        return {
            "path": f"workspace/{rel_path}" if rel_path != "." else "workspace",
            "total_chars": len(content),
            "truncated": truncated,
            "content": output_content,
        }
    except PermissionError as pe:
        return {"error": str(pe)}
    except Exception as e:
        return {"error": f"Failed to read file: {str(e)}"}


def list_dir(path: str = ".") -> Dict[str, Any]:
    """List items inside a directory strictly within workspace/.
    
    Args:
        path: Directory path inside workspace/ to list (default is '.').
    """
    try:
        target_path = resolve_in_workspace(path)
        if not target_path.exists():
            return {"error": f"Directory does not exist in workspace: {path}"}
        if not target_path.is_dir():
            return {"error": f"Path is not a directory: {path}"}

        entries: List[Dict[str, Any]] = []
        for item in sorted(target_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            try:
                stat = item.stat()
                entries.append({
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "size_bytes": stat.st_size if item.is_file() else None,
                })
            except Exception:
                entries.append({
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "error": "Unable to read stat",
                })

        rel_path = target_path.relative_to(_active_workspace_dir.resolve()).as_posix()
        display_dir = f"workspace/{rel_path}" if rel_path != "." else "workspace"
        return {
            "directory": display_dir,
            "count": len(entries),
            "entries": entries,
        }
    except PermissionError as pe:
        return {"error": str(pe)}
    except Exception as e:
        return {"error": f"Failed to list directory: {str(e)}"}


def write_note(title: str, content: str, mode: str = "append") -> Dict[str, Any]:
    """Write or append text notes strictly inside the workspace directory.
    
    Args:
        title: Note title or filename (e.g. 'notes.md', 'summary', 'meeting_notes').
        content: Text content to write into the note.
        mode: Write mode: 'append' to add to existing note, or 'overwrite' to replace.
    """
    try:
        if not title or not title.strip():
            return {"error": "Note title cannot be empty."}

        clean_title = title.strip()
        if not any(clean_title.endswith(ext) for ext in (".md", ".txt", ".json", ".log")):
            clean_title = f"{clean_title}.md"

        target_path = resolve_in_workspace(clean_title)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        write_mode = mode.lower().strip()
        if write_mode not in ("append", "overwrite"):
            write_mode = "append"

        if write_mode == "append" and target_path.exists():
            existing = target_path.read_text(encoding="utf-8", errors="replace")
            separator = "\n" if existing and not existing.endswith("\n") else ""
            new_text = existing + separator + content
        else:
            new_text = content

        target_path.write_text(new_text, encoding="utf-8")

        rel_path = target_path.relative_to(_active_workspace_dir.resolve()).as_posix()
        return {
            "status": "ok",
            "file": target_path.name,
            "path": f"workspace/{rel_path}",
            "bytes_written": len(content.encode("utf-8")),
            "mode": write_mode,
            "total_bytes": target_path.stat().st_size,
        }
    except PermissionError as pe:
        return {"error": str(pe)}
    except Exception as e:
        return {"error": f"Failed to write note: {str(e)}"}
