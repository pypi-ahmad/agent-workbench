"""Live scripted smoke for Agnes Chat Completions tool calling."""

import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent import DEFAULT_WORKSPACE_DIR, WorkbenchAgent
from src.agnes_client import DEFAULT_AGNES_MODEL, get_client
from src.export import export_trace_json, export_trace_markdown

PROMPT = "List files in the workspace, read sample.txt, and compute 17*19."


def run_smoke_tools() -> None:
    print("[1] Checking AGNESAI_API_KEY presence")
    if not os.environ.get("AGNESAI_API_KEY", "").strip():
        raise RuntimeError("AGNESAI_API_KEY is unavailable.")

    print("[2] Creating Agnes client")
    client, error = get_client("Agnes AI")
    if client is None:
        raise RuntimeError(error or "Agnes client is unavailable.")

    agent = WorkbenchAgent(
        client=client,
        model=DEFAULT_AGNES_MODEL,
        working_dir=DEFAULT_WORKSPACE_DIR,
        max_steps=8,
    )
    print(f"[3] Prompt: {PROMPT}")
    result = agent.run_turn(PROMPT)

    tool_names = [
        step["name"] for step in result["steps"] if step["kind"] == "tool"
    ]
    final_text = result["final_content"]
    print(f"Tools: {tool_names}")
    print(f"Final: {final_text}")

    assert any(name in {"list_dir", "read_file"} for name in tool_names), (
        "Trace requires list_dir or read_file."
    )
    assert "calc" in tool_names, "Trace requires calc."
    assert "323" in final_text, "Final assistant text must contain 323."
    assert "WORKBENCH_FIXTURE_OK" in final_text, (
        "Final assistant text must contain WORKBENCH_FIXTURE_OK."
    )

    cache_dir = Path("data/cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    json_path = cache_dir / "smoke_trace.json"
    markdown_path = cache_dir / "smoke_trace.md"
    json_path.write_text(
        export_trace_json(
            "Agnes AI",
            DEFAULT_AGNES_MODEL,
            str(agent.working_dir),
            result["messages"],
            result["steps"],
            result["total_latency"],
        ),
        encoding="utf-8",
    )
    markdown_path.write_text(
        export_trace_markdown(
            "Agnes AI",
            DEFAULT_AGNES_MODEL,
            str(agent.working_dir),
            result["messages"],
            result["steps"],
            result["total_latency"],
        ),
        encoding="utf-8",
    )
    assert json_path.exists()
    print(f"PASS: {json_path}")


if __name__ == "__main__":
    run_smoke_tools()
