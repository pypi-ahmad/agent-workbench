# Agent Workbench

Agent Workbench is a Windows 11 Streamlit application for interacting with LLM agents. It supports multi-turn chat, local tool execution, state inspection, and trace export.

## Quickstart

### 1. Run with run.cmd
Double-click `run.cmd` at the repository root:
```cmd
run.cmd
```
The script will:
- Check for `.env`. If missing, it copies `.env.example` to `.env` and opens Notepad.
- Create a `.venv` virtual environment if one does not exist.
- Install or update dependencies from `requirements.txt`.
- Start the Streamlit application.

### 2. Run manually
```powershell
uv venv .venv
uv pip install -r requirements.txt
streamlit run app.py
```

### 3. Environment variables
Configure keys in your user environment or in `.env`:
```ini
# Primary Provider: Agnes AI
AGNESAI_API_KEY=your_key_here
AGNESAI_BASE_URL=https://apihub.agnes-ai.com/v1
AGNESAI_MODEL=agnes-3.0-flash

# Optional Providers (shown in UI only when configured)
OPENAI_API_KEY=
OPENAI_BASE_URL=
GOOGLE_API_KEY=
```

## Threat model

The application restricts agent execution to safe operations:

- No shell execution: The agent cannot run system commands, cmd.exe, PowerShell, bash, or `subprocess`. Docker and WSL2 are not used.
- Safe math evaluation: The `calc` tool parses arithmetic with `ast.parse`. It evaluates basic math operations while rejecting `eval()`, `exec()`, imports, and dunder attributes.
- Constrained filesystem access: File tools (`read_file`, `list_dir`, `write_note`) operate strictly inside `workspace/`. Paths attempting to access files above `workspace/` are rejected.
- Outbound network allowlist: The `http_get` tool connects only to allowlisted HTTPS hostnames such as `api.github.com`, `httpbin.org`, and `wttr.in`. Plain HTTP requests and unlisted hosts are blocked.

- Credential safety: API keys remain in the process environment. The application checks whether an environment variable exists without logging or displaying its value. See `AGNESAI_API_KEY` configuration under Environment variables.

See [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) for full threat boundaries and security mitigations.


## How to add a tool

To register a new tool with the workbench:

### Step 1: Write the handler
Add a Python function in `src/tools/` or a new module:
```python
# src/tools/my_tool.py
from typing import Any, Dict

def reverse_text(text: str) -> Dict[str, Any]:
    """Reverse input text safely."""
    return {"reversed": text[::-1]}
```

### Step 2: Register the tool
Add the tool definition to `ALL_TOOLS` in `src/tools/registry.py`:
```python
from src.tools.base import ToolDefinition
from src.tools.my_tool import reverse_text

ALL_TOOLS["reverse_text"] = ToolDefinition(
    name="reverse_text",
    description="Reverse a given string.",
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The string to reverse.",
            },
        },
        "required": ["text"],
    },
    handler=reverse_text,
)
```

### Step 3: Export the tool
Add the function to `__all__` in `src/tools/__init__.py`:
```python
from src.tools.my_tool import reverse_text

__all__ = [
    ...,
    "reverse_text",
]
```

### Step 4: Verify the tool
Once registered:
- The sidebar displays a checkbox to toggle the tool on or off.
- The agent loop passes the tool schema to OpenAI-compatible models.
- The tool log records each invocation, arguments, result, and latency.

## Architecture and layout

For architectural details, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

The Streamlit UI uses a three-column layout:
- Left column: Tool execution log with step arguments, outputs, and latency.
- Center column: Chat dialogue showing user and agent messages.
- Right column: Live JSON inspector for session state, workspace files, and trace export.

- Workspace: The agent default working directory is [`workspace/`](workspace/).
