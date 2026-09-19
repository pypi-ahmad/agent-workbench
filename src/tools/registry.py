"""Central tool registry providing OpenAI tool definitions and dispatch."""

import json
from typing import Any, Dict, List, Optional
from src.tools.base import ToolDefinition
from src.tools.file_tools import list_dir, read_file, write_note
from src.tools.utility_tools import calc, now
from src.tools.web_tools import http_get


ALL_TOOLS: Dict[str, ToolDefinition] = {
    "list_dir": ToolDefinition(
        name="list_dir",
        description="List files and directories strictly inside workspace/ (default path is '.').",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path relative to workspace/ (default is '.').",
                    "default": ".",
                },
            },
            "required": [],
        },
        handler=list_dir,
    ),
    "read_file": ToolDefinition(
        name="read_file",
        description="Read contents of a text file strictly inside workspace/.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file inside workspace/.",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters to return (default 10000).",
                    "default": 10000,
                },
            },
            "required": ["path"],
        },
        handler=read_file,
    ),
    "write_note": ToolDefinition(
        name="write_note",
        description="Write or append text notes strictly inside workspace/.",
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Note title or filename (e.g. 'notes.md' or 'summary'). Stored in workspace/.",
                },
                "content": {
                    "type": "string",
                    "description": "Text content to write or append.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["append", "overwrite"],
                    "description": "Write mode: 'append' to add to existing note, or 'overwrite' to replace.",
                    "default": "append",
                },
            },
            "required": ["title", "content"],
        },
        handler=write_note,
    ),
    "calc": ToolDefinition(
        name="calc",
        description="Safely evaluate mathematical expressions using AST parser (no eval).",
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Arithmetic expression string (e.g. '17 * 19' or 'sqrt(144)').",
                },
            },
            "required": ["expression"],
        },
        handler=calc,
    ),
    "http_get": ToolDefinition(
        name="http_get",
        description="Perform an HTTPS GET request to an allowlisted hostname (HTTPS only).",
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Full HTTPS URL to fetch.",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Request timeout in seconds (default 10).",
                    "default": 10,
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters of response body to return (default 8000).",
                    "default": 8000,
                },
            },
            "required": ["url"],
        },
        handler=http_get,
    ),
    "now": ToolDefinition(
        name="now",
        description="Get current time and date in UTC and local timezone.",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        handler=now,
    ),
}


def get_openai_tools(enabled_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Return list of tool specifications formatted for OpenAI chat completions."""
    names = enabled_names if enabled_names is not None else list(ALL_TOOLS.keys())
    return [
        ALL_TOOLS[name].to_openai_schema()
        for name in names
        if name in ALL_TOOLS
    ]


def execute_tool_call(tool_name: str, arguments: Any) -> Dict[str, Any]:
    """Execute a registered tool by name with parsed or JSON-string arguments."""
    if tool_name not in ALL_TOOLS:
        return {"error": f"Tool '{tool_name}' is not registered."}

    tool = ALL_TOOLS[tool_name]

    if isinstance(arguments, str):
        try:
            kwargs = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse tool arguments JSON: {str(e)}"}
    elif isinstance(arguments, dict):
        kwargs = arguments
    else:
        kwargs = {}

    try:
        return tool.handler(**kwargs)
    except TypeError as e:
        return {"error": f"Invalid tool arguments provided to {tool_name}: {str(e)}"}
    except Exception as e:
        return {"error": f"Tool execution failed: {str(e)}"}
