"""OpenAI tool schemas and sequential dispatch."""

import json
from typing import Any

from src.tools.base import ToolDefinition
from src.tools.fs_tools import list_dir, read_file, write_note
from src.tools.misc_tools import calc, http_get, now


ALL_TOOLS: dict[str, ToolDefinition] = {
    "list_dir": ToolDefinition(
        "list_dir",
        "List files and directories inside workspace only.",
        {
            "type": "object",
            "properties": {
                "relative_path": {
                    "type": "string",
                    "description": "Directory path relative to workspace.",
                    "default": ".",
                }
            },
            "additionalProperties": False,
        },
        list_dir,
    ),
    "read_file": ToolDefinition(
        "read_file",
        "Read a UTF-8 text file under workspace, up to 64 KiB.",
        {
            "type": "object",
            "properties": {
                "relative_path": {
                    "type": "string",
                    "description": "File path relative to workspace.",
                }
            },
            "required": ["relative_path"],
            "additionalProperties": False,
        },
        read_file,
    ),
    "write_note": ToolDefinition(
        "write_note",
        "Write text to a simple filename under workspace/notes.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Simple note filename."},
                "text": {"type": "string", "description": "Complete note text."},
            },
            "required": ["name", "text"],
            "additionalProperties": False,
        },
        write_note,
    ),
    "calc": ToolDefinition(
        "calc",
        "Evaluate arithmetic containing only numbers and + - * / ** parentheses.",
        {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Arithmetic expression."}
            },
            "required": ["expression"],
            "additionalProperties": False,
        },
        calc,
    ),
    "http_get": ToolDefinition(
        "http_get",
        "GET an allowlisted HTTPS URL and return status plus up to 4000 characters.",
        {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Allowlisted HTTPS URL."}
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        http_get,
    ),
    "now": ToolDefinition(
        "now",
        "Return local time as an ISO 8601 string.",
        {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        now,
    ),
}


def get_openai_tools(enabled_names: list[str] | None = None) -> list[dict[str, Any]]:
    names = enabled_names if enabled_names is not None else list(ALL_TOOLS)
    return [ALL_TOOLS[name].to_openai_schema() for name in names if name in ALL_TOOLS]


def execute_tool_call(tool_name: str, arguments: str | dict[str, Any]) -> Any:
    if tool_name not in ALL_TOOLS:
        return {"error": f"Tool is not registered: {tool_name}"}
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError as exc:
            return {"error": f"Malformed tool arguments: {exc}"}
    elif isinstance(arguments, dict):
        parsed = arguments
    else:
        return {"error": "Tool arguments must be a JSON object."}
    if not isinstance(parsed, dict):
        return {"error": "Tool arguments must decode to a JSON object."}
    try:
        return ALL_TOOLS[tool_name].handler(**parsed)
    except TypeError as exc:
        return {"error": f"Invalid tool arguments: {exc}"}
    except Exception as exc:
        return {"error": f"Tool failed: {exc}"}
