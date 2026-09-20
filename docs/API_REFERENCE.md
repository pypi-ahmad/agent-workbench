# Supported API reference

This reference describes the maintainer-facing surface used by the Streamlit
workbench. The source in `src/` is authoritative when this document and code
disagree.

## Configuration and providers

`src.config` defines the fixed repository `workspace/` root, the Agnes base
URL and model, the default HTTP host allowlist, and execution limits:

| Setting | Current value or behavior |
| --- | --- |
| `WORKSPACE_DIR` | Repository `workspace/` directory |
| `AGNES_BASE_URL` | `https://apihub.agnes-ai.com/v1` |
| `AGNES_MODEL` | `agnes-3.0-flash` |
| `HTTP_ALLOWED_HOSTS` | `example.com`, `httpbin.org` |
| `DEFAULT_MAX_STEPS` / `HARD_MAX_STEPS` | 8 / 16 tool calls |
| `TOOL_RESULT_MAX_CHARS` | 1,200 display characters |

`detect_available_providers()` always returns Agnes AI and adds optional
providers only when their required process environment variables exist:

| Provider | Required variables | Model exposed by the UI |
| --- | --- | --- |
| Agnes AI | `AGNESAI_API_KEY` | `agnes-3.0-flash` |
| OpenAI-compatible | `OPENAI_API_KEY`, `OPENAI_BASE_URL` | `gpt-4.1-mini` |
| Google Gemini | `GOOGLE_API_KEY` | `gemini-2.5-flash` |

`get_client(provider_name="Agnes AI")` returns `(OpenAI | None, error | None)`.
It reads credentials from the process environment and never persists them.
`chat_completion_with_429_retries(client, request)` retries only HTTP 429
responses, up to three retries with bounded exponential waits.

`AGNESAI_API_KEY` is not loaded from `.env`; it must be in the launching
process environment. The launcher creates `.env` only because its Windows
bootstrap contract requires that file to exist before it creates the virtual
environment and starts Streamlit.

## Agent interface

`WorkbenchAgent` in `src.agent` owns one conversation and its execution trace.
Its constructor accepts these supported parameters:

| Parameter | Meaning |
| --- | --- |
| `client` | Optional prebuilt OpenAI-compatible client; otherwise a provider client is created. |
| `provider_name` / `model` | Provider label and Chat Completions model. |
| `working_dir` | Must resolve to the repository `workspace/` root. |
| `enabled_tools` | Names from `ALL_TOOLS`; unknown names are ignored. |
| `max_steps` | Requested tool-call limit, clamped to 1 through 16. |
| `system_prompt` | Optional replacement for the default tool-use instruction. |

Call `run(user_message, on_step=None)` for one user turn. `run_turn` is the
underlying equivalent. The optional callback receives each step as it is
recorded. A successful result has this shape:

```json
{
  "status": "success",
  "final_content": "...",
  "steps": [],
  "messages": [],
  "total_latency": 0.0,
  "steps_count": 0,
  "tool_steps_count": 0
}
```

When the tool-call cap is exhausted, `status` is `"max_steps_reached"` and the
final text reports the limit. API errors are re-raised after a model error step
is recorded.

Every model or tool step has the same telemetry fields:

```json
{
  "i": 1,
  "kind": "model",
  "name": "agnes-3.0-flash",
  "args": {},
  "result_preview": "...",
  "ms": 0.0,
  "error": null
}
```

The agent sends official Chat Completions messages. It requests a tool on the
first model call whenever enabled tools exist, then uses automatic tool choice
on subsequent calls. Tool calls run sequentially. Malformed arguments and
disabled tools become error-valued `tool` messages so the next model call can
recover.

## Tool registry and schemas

`ToolDefinition` contains a tool `name`, `description`, JSON Schema
`parameters`, and callable `handler`. `to_openai_schema()` returns the official
Chat Completions function-tool object.

`ALL_TOOLS` is the supported registry. `get_openai_tools(enabled_names=None)`
returns schemas only for registered enabled names. `execute_tool_call(name,
arguments)` accepts either an argument object or JSON object string and returns
the handler result or an `{"error": "..."}` object for unknown, malformed, or
invalid calls.

| Tool | Arguments | Successful result | Boundaries |
| --- | --- | --- | --- |
| `list_dir` | `relative_path="."` | `path`, `entries` (`name`, `type`, `bytes`) | Existing directory under `workspace/` only. |
| `read_file` | `relative_path` | `path`, `bytes`, `text` | UTF-8 file under `workspace/`, maximum 64 KiB. |
| `write_note` | `name`, `text` | `path`, `bytes` | Simple non-reserved filename only; writes under `workspace/notes/`. |
| `calc` | `expression` | `expression`, `result` | Numbers, unary `+`/`-`, and `+ - * / **` only; 256-character input cap and exponent magnitude cap of 100. |
| `http_get` | `url` | `status`, `text` | HTTPS allowlisted host only; no URL credentials, redirects, or more than 4,000 response characters. |
| `now` | none | ISO 8601 local-time string | No external input or network request. |

Expected tool failures are data, not exceptions: handlers return
`{"error": "..."}`. Filesystem traversal, paths outside the workspace,
unlisted hosts, calculator names, imports, attributes, and function calls all
fail closed.

## Trace exports

`build_trace_payload(provider_name, model, working_dir, messages, steps,
total_latency=None)` returns a dictionary containing a UTC timestamp,
metadata, steps, and messages.

`export_trace_json(...)` returns that payload as formatted JSON.
`export_trace_markdown(...)` returns a human-readable execution trace with
tool arguments, result previews, errors, and conversation history. The
Streamlit sidebar exposes both outputs as downloads.

## Extension boundary

To add a model-callable tool, add a JSON-serializable handler, register its
matching JSON Schema and handler in `ALL_TOOLS`, then run the relevant smoke.
The sidebar automatically creates a checkbox for each registered tool and
passes only enabled schemas to the model.

`src.tools.file_tools` supplies workspace-resolution internals, and smoke
scripts verify behavior. They are not extension APIs. Do not expose a shell,
subprocess, file-deletion, OCR, PDF, Qdrant, Docker, or WSL2 tool through the
registry.
