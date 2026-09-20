# Tool-calling Agent Workbench

Windows 11 Streamlit app for chatting with `agnes-3.0-flash` through official
OpenAI Chat Completions tool calling. Each tool step shows its name, arguments,
truncated result, and latency.

## Run on Windows

1. Create the Windows User environment variable `AGNESAI_API_KEY`.
2. Relaunch the coding-agent host or Explorer after creating the variable.
3. Double-click `run.cmd`.

On the first run, `run.cmd` copies `.env.example` to `.env`, opens it in
Notepad, and exits. The file contains configuration names only. The app reads
credentials from the process environment and does not load secrets from
`.env`.

Double-click `run.cmd` again. It runs:

```bat
py -3 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\streamlit run app.py
```

## Workbench

- Default provider: Agnes AI at `https://apihub.agnes-ai.com/v1`
- Default model: `agnes-3.0-flash`
- Optional providers appear only when their required environment variables exist
- Maximum tool steps: 8 by default, 16 hard cap
- Tools can be enabled or disabled individually in the sidebar
- JSON and Markdown trace downloads are available in the sidebar

## Tools

| Tool | Purpose |
| --- | --- |
| `list_dir` | List a relative directory under `workspace/` |
| `read_file` | Read UTF-8 text under `workspace/`, up to 64 KiB |
| `write_note` | Write a simple filename under `workspace/notes/` |
| `calc` | Evaluate numbers with `+ - * / ** ()` only |
| `http_get` | Return status and 4,000 text characters from allowlisted HTTPS |
| `now` | Return local time as an ISO 8601 string |

File tools reject `..` traversal and paths outside `workspace/`.
`http_get` permits only `example.com` and `httpbin.org` by default. The app
contains no shell, subprocess, deletion, OCR, PDF, Qdrant, Docker, or WSL2
integration.

## Add a tool

1. Add the Python function under `src/tools/`. Return JSON-serializable data
   and return an `{"error": "..."}` object for expected failures.
2. Add its OpenAI function schema and handler to `ALL_TOOLS` in
   `src/tools/registry.py`. Schema property names must match the function
   parameters.
3. No separate UI code is required for a standard tool. The sidebar builds one
   checkbox per `ALL_TOOLS` entry and omits unchecked tools from the API
   `tools` array.

Run the offline and relevant scripted smokes after adding the function and
schema.

## Threat model

The model has no shell, subprocess, command runner, or deletion tool. File
operations stay under `workspace/`; outbound HTTP requires an allowlisted
HTTPS host; calculator input is interpreted through a restricted arithmetic
AST. Tool output is treated as data and never executed.

## Verify

```powershell
uv run python test_smoke.py
.venv\Scripts\python scripts\smoke_tools.py
```

The offline smoke writes `data/cache/smoke_trace.json`. The live smoke requires
`AGNESAI_API_KEY` in the current process and verifies real `tool_calls`.

See the [API reference](docs/API_REFERENCE.md),
[architecture](docs/ARCHITECTURE.md), and
[threat model](docs/THREAT_MODEL.md).
