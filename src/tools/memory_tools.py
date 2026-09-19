"""JSON-backed persistent memory tool for notes."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_MEMORY_PATH = Path("data/notes_memory.json")


def _load_memory(file_path: Path) -> Dict[str, Any]:
    if not file_path.exists():
        return {}
    try:
        content = file_path.read_text(encoding="utf-8")
        return json.loads(content)
    except Exception:
        return {}


def _save_memory(file_path: Path, data: Dict[str, Any]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def notes_memory(
    action: str,
    key: Optional[str] = None,
    value: Optional[str] = None,
    memory_file: str = "data/notes_memory.json",
) -> Dict[str, Any]:
    """Store, retrieve, list, or delete notes in a persistent JSON file.
    
    Args:
        action: One of 'set', 'get', 'list', 'delete', 'search'.
        key: Note identifier/title (required for set, get, delete).
        value: Note body/content (required for set).
        memory_file: Target JSON file path (defaults to data/notes_memory.json).
    """
    path = Path(memory_file)
    action = action.lower().strip()
    data = _load_memory(path)

    if action == "set":
        if not key:
            return {"error": "Missing 'key' argument for action 'set'."}
        if value is None:
            return {"error": "Missing 'value' argument for action 'set'."}
        data[key] = value
        _save_memory(path, data)
        return {"status": "ok", "action": "set", "key": key, "message": f"Saved note '{key}'."}

    elif action == "get":
        if not key:
            return {"error": "Missing 'key' argument for action 'get'."}
        if key not in data:
            return {"error": f"Key '{key}' not found in notes.", "available_keys": list(data.keys())}
        return {"status": "ok", "action": "get", "key": key, "value": data[key]}

    elif action == "list":
        return {
            "status": "ok",
            "action": "list",
            "count": len(data),
            "keys": list(data.keys()),
            "items": data,
        }

    elif action == "delete":
        if not key:
            return {"error": "Missing 'key' argument for action 'delete'."}
        if key not in data:
            return {"error": f"Key '{key}' not found in notes."}
        del data[key]
        _save_memory(path, data)
        return {"status": "ok", "action": "delete", "key": key, "message": f"Deleted note '{key}'."}

    elif action == "search":
        query = (key or value or "").lower().strip()
        if not query:
            return {"error": "Missing search query in key or value argument."}
        matches = {
            k: v for k, v in data.items()
            if query in k.lower() or query in str(v).lower()
        }
        return {"status": "ok", "action": "search", "query": query, "matches": matches}

    else:
        return {
            "error": f"Invalid action '{action}'. Valid actions are 'set', 'get', 'list', 'delete', 'search'."
        }
