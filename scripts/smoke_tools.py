"""Scripted smoke test verifying live tool calling with Agnes AI."""

import json
import os
from pathlib import Path
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent import DEFAULT_WORKSPACE_DIR, WorkbenchAgent
from src.agnes_client import DEFAULT_AGNES_MODEL, get_client
from src.export import export_trace_json, export_trace_markdown


def run_smoke_tools():
    print("[1] Verifying AGNESAI_API_KEY...")
    if not os.environ.get("AGNESAI_API_KEY", "").strip():
        print("ERROR: AGNESAI_API_KEY is not configured in environment.")
        sys.exit(1)
    print("  OK: AGNESAI_API_KEY is configured.")

    print("[2] Initializing WorkbenchAgent...")
    client, err = get_client("Agnes AI")
    if err or client is None:
        print(f"ERROR initializing Agnes client: {err}")
        sys.exit(1)

    agent = WorkbenchAgent(
        client=client,
        provider_name="Agnes AI",
        model=DEFAULT_AGNES_MODEL,
        working_dir=DEFAULT_WORKSPACE_DIR,
        max_steps=8,
    )
    print(f"  OK: WorkbenchAgent ready with workspace at: {agent.working_dir}")

    prompt = "List workspace files and compute 17*19."
    print(f"[3] Running agent turn with prompt: '{prompt}'...")

    result = agent.run_turn(prompt)
    print(f"  Turn status: {result['status']}")
    print(f"  Steps executed: {result['steps_count']}")
    print(f"  Turn latency: {result['total_latency']}s")

    called_tool_names = [s["name"] for s in result["steps"]]
    print(f"  Tools called: {called_tool_names}")

    print("\n----- Agent Final Content -----")
    print(result["final_content"])
    print("--------------------------------\n")

    # Assertions: must use a file tool and calc
    has_file_tool = any(t in ("list_dir", "read_file") for t in called_tool_names)
    has_calc_tool = "calc" in called_tool_names

    if not has_file_tool:
        print("ERROR: Expected at least one call to 'list_dir' or 'read_file'.")
        sys.exit(1)

    if not has_calc_tool:
        print("ERROR: Expected at least one call to 'calc'.")
        sys.exit(1)

    print("  OK: File tool and calc successfully invoked.")

    # Save data/cache/smoke_trace.json
    cache_dir = Path("data/cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    trace_json_path = cache_dir / "smoke_trace.json"
    trace_md_path = cache_dir / "smoke_trace.md"

    trace_json_content = export_trace_json(
        provider_name="Agnes AI",
        model=DEFAULT_AGNES_MODEL,
        working_dir=str(agent.working_dir),
        messages=agent.messages,
        steps=result["steps"],
        total_latency=result["total_latency"],
    )
    trace_json_path.write_text(trace_json_content, encoding="utf-8")

    trace_md_content = export_trace_markdown(
        provider_name="Agnes AI",
        model=DEFAULT_AGNES_MODEL,
        working_dir=str(agent.working_dir),
        messages=agent.messages,
        steps=result["steps"],
        total_latency=result["total_latency"],
    )
    trace_md_path.write_text(trace_md_content, encoding="utf-8")

    print(f"[4] Trace saved to {trace_json_path}")

    # Verify trace file exists on disk and contains the required tools
    assert trace_json_path.exists(), f"Missing trace file: {trace_json_path}"
    saved_text = trace_json_path.read_text(encoding="utf-8")
    assert '"calc"' in saved_text, "Trace does not contain calc tool step"
    assert ('"list_dir"' in saved_text or '"read_file"' in saved_text), "Trace does not contain file tool step"

    print("  OK: Verified data/cache/smoke_trace.json exists and contains file tool and calc.")
    print("\nALL SMOKE_TOOLS CHECKS PASSED.")


if __name__ == "__main__":
    run_smoke_tools()
