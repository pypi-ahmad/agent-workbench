# Project status

- Timestamp: 2026-09-20 15:09:43 +05:30
- Platform: Windows 11 native
- Directory: `D:\AI\Github\agent-workbench`
- Status: implementation and named smoke complete

## Implemented

- Streamlit chat UI with provider, model, tool toggles, and 8-step default
- Official OpenAI SDK Chat Completions `tools` and `tool_calls` loop
- Model and tool steps with index, kind, name, arguments, result preview,
  latency, and error
- Six v1 tools: `list_dir`, `read_file`, `write_note`, `calc`, `http_get`, `now`
- Fixed `workspace/` file sandbox and HTTPS host allowlist
- JSON and Markdown trace downloads
- Chat input wired through `WorkbenchAgent.run()`
- Left step timeline and right raw messages/enabled-tools state
- Exact Windows `run.cmd` bootstrap and launch commands

## Verification

### Offline smoke

```text
Command: .venv\Scripts\python test_smoke.py
Result: ALL OFFLINE SMOKE CHECKS PASSED.
Checks: 14
```

The smoke verified schemas, calculator restrictions, filesystem traversal
blocks, network policy, optional provider visibility, official tool-message
flow, malformed argument recovery, 429 retry behavior, disabled-tool
enforcement, 16-step hard cap, forbidden execution APIs, Streamlit headless
rendering, and cache persistence.

### Live Agnes smoke

```text
Command: .venv\Scripts\python scripts\smoke_tools.py
Result: PASS: data\cache\smoke_trace.json
Prompt: List files in the workspace, read sample.txt, and compute 17*19.
Tools called: list_dir, read_file, calc
Final contains: WORKBENCH_FIXTURE_OK and 323
```

`data/cache/smoke_trace.json` contains 7 model/tool steps with every required
telemetry field.

### Import and UI smoke

```text
Command: .venv\Scripts\python scripts\smoke_import.py
Result: IMPORT_SMOKE_OK
Headless UI result: UI_SMOKE_OK
```

The import smoke imports `app` and `src.agent` without launching a server.
Schemas were unchanged, so the live Agnes smoke was not rerun. Its validated
trace remains in `data/cache/smoke_trace.json`.

### Sandbox smoke

```text
Command: .venv\Scripts\python scripts\smoke_sandbox.py
Result: PASS: data\cache\sandbox_check.json
Missing-key UI result: MISSING_KEY_UI_OK
```

Traversal reads returned error strings without file content. Note names with
slashes failed. Calculator import syntax failed closed. When
`AGNESAI_API_KEY` is missing, the UI shows that exact variable name and
blocks client creation before any API request.

## Cache-producing smokes

| Smoke | Cache output | Result |
| --- | --- | --- |
| `test_smoke.py` | Preliminary `smoke_trace.json` from fake client | Passed 14 checks |
| `scripts/smoke_tools.py` | `smoke_trace.json`, `smoke_trace.md` | Passed; replaced preliminary trace with live Agnes trace |
| `scripts/smoke_sandbox.py` | `sandbox_check.json` | Passed all fail-closed checks |

Current cache files:

- `data/cache/smoke_trace.json`: live steps for `list_dir`, `read_file`,
  and `calc`; final text contains `WORKBENCH_FIXTURE_OK` and `323`
- `data/cache/smoke_trace.md`: Markdown form of the same live trace
- `data/cache/sandbox_check.json`: traversal, note-name, and calculator
  rejection results

## Leftover failures

```text
None.
```

## Credential handling

Live-smoke verification used `AGNESAI_API_KEY` available to the process at the
timestamp above. Current credential availability is intentionally not recorded
here because it can change. No credential value was displayed or stored.
