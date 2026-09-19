"""Scripted smoke test verifying live agent turn against Agnes AI."""

import json
import os
from pathlib import Path
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent import DEFAULT_WORKSPACE_DIR, WorkbenchAgent
from src.agnes_client import DEFAULT_AGNES_MODEL, get_client


def run_live_smoke():
    print("[1] Verifying AGNESAI_API_KEY...")
    if not os.environ.get("AGNESAI_API_KEY", "").strip():
        print("ERROR: AGNESAI_API_KEY environment variable is missing.")
        sys.exit(1)
    print("  OK: AGNESAI_API_KEY is configured.")

    print("[2] Initializing WorkbenchAgent...")
    client, err = get_client("Agnes AI")
    if err or client is None:
        print(f"ERROR initializing client: {err}")
        sys.exit(1)

    agent = WorkbenchAgent(
        client=client,
        provider_name="Agnes AI",
        model=DEFAULT_AGNES_MODEL,
        working_dir=DEFAULT_WORKSPACE_DIR,
        max_steps=8,
    )
    print(f"  OK: WorkbenchAgent initialized with working_dir={agent.working_dir}")

    question = "What files are in workspace and what is 17*19?"
    print(f"[3] Running agent turn with prompt: '{question}'...")

    result = agent.run_turn(question)
    print(f"  Agent turn finished with status: {result['status']}")
    print(f"  Steps executed: {result['steps_count']}")
    print(f"  Total turn latency: {result['total_latency']}s")

    called_tool_names = [s["name"] for s in result["steps"]]
    print(f"  Tools called: {called_tool_names}")

    print("\n----- Agent Final Content -----")
    print(result["final_content"])
    print("--------------------------------\n")

    # Assertions required by prompt:
    # "must call list_dir or read_file and calc"
    has_file_tool = any(t in ("list_dir", "read_file") for t in called_tool_names)
    has_calc_tool = "calc" in called_tool_names

    if not has_file_tool:
        print("ERROR: Expected at least one call to 'list_dir' or 'read_file'.")
        sys.exit(1)

    if not has_calc_tool:
        print("ERROR: Expected at least one call to 'calc'.")
        sys.exit(1)

    print("  OK: Required tools (list_dir/read_file AND calc) were successfully invoked!")

    # Save to data/cache/smoke_trace.json and smoke_trace.md
    from src.export import export_trace_json, export_trace_markdown
    cache_dir = Path("data/cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    trace_json_file = cache_dir / "smoke_trace.json"
    trace_md_file = cache_dir / "smoke_trace.md"

    trace_json_str = export_trace_json(
        provider_name="Agnes AI",
        model=DEFAULT_AGNES_MODEL,
        working_dir=str(agent.working_dir),
        messages=agent.messages,
        steps=result["steps"],
        total_latency=result["total_latency"],
    )
    trace_json_file.write_text(trace_json_str, encoding="utf-8")

    trace_md_str = export_trace_markdown(
        provider_name="Agnes AI",
        model=DEFAULT_AGNES_MODEL,
        working_dir=str(agent.working_dir),
        messages=agent.messages,
        steps=result["steps"],
        total_latency=result["total_latency"],
    )
    trace_md_file.write_text(trace_md_str, encoding="utf-8")

    print(f"[4] Successfully saved smoke trace to {trace_json_file} and {trace_md_file}")
    print("\nALL SCRIPTED SMOKE ASSERTIONS PASSED.")



if __name__ == "__main__":
    run_live_smoke()
