"""Offline smoke test verifying tool execution, schemas, and workspace sandbox."""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from src.agnes_client import detect_available_providers
from src.tools.file_tools import list_dir, read_file, write_note, DEFAULT_WORKSPACE_DIR
from src.tools.registry import ALL_TOOLS, execute_tool_call, get_openai_tools
from src.tools.utility_tools import calc, now
from src.tools.web_tools import get_allowed_hosts, http_get
from src.export import export_trace_json, export_trace_markdown


def run_smoke():
    print("[1] Checking Tool Registry...")
    tools = get_openai_tools()
    expected_tools = {"list_dir", "read_file", "write_note", "calc", "http_get", "now"}
    registered_names = {t["function"]["name"] for t in tools}
    assert registered_names == expected_tools, f"Expected {expected_tools}, got {registered_names}"
    for t in tools:
        assert t["type"] == "function"
        assert "name" in t["function"]
        assert "description" in t["function"]
    print(f"  OK: 6 v1 tools registered with valid OpenAI schemas: {sorted(registered_names)}.")

    print("[2] Testing calc tool...")
    c1 = calc("10 * (5 + 3)")
    assert c1.get("result") == 80, f"Unexpected calc result: {c1}"
    c2 = calc("sqrt(256) + 4")
    assert c2.get("result") == 20.0, f"Unexpected calc result: {c2}"
    c_err = calc("__import__('os').system('dir')")
    assert "error" in c_err, "Calc security check failed; should reject dunder/import"
    print("  OK: calc passed evaluation and security boundaries.")

    print("[3] Testing now tool...")
    n = now()
    assert "utc_iso" in n and "local_iso" in n
    print(f"  OK: now returned {n['local_iso']}")

    print("[4] Testing write_note tool...")
    wn = write_note("smoke_test_note.txt", "Initial smoke note line.\n", mode="overwrite")
    assert wn.get("status") == "ok", f"write_note failed: {wn}"
    assert "workspace" in wn.get("path", "")

    # Append
    wn_app = write_note("smoke_test_note.txt", "Second line appended.\n", mode="append")
    assert wn_app.get("status") == "ok"

    # Read back through read_file
    rf = read_file("smoke_test_note.txt")
    assert "Initial smoke note line." in rf.get("content", "")
    assert "Second line appended." in rf.get("content", "")
    print(f"  OK: write_note created and appended to note successfully.")

    print("[5] Testing workspace filesystem sandbox...")
    ld = list_dir(".")
    assert ld.get("count", 0) > 0, "Workspace directory listing should not be empty"
    
    # Boundary violation test: reading outside workspace must be blocked
    above_read = read_file("../app.py")
    assert "error" in above_read and ("outside workspace" in above_read["error"].lower() or "denied" in above_read["error"].lower()), (
        f"Path traversal above workspace was not blocked: {above_read}"
    )

    above_list = list_dir("../src")
    assert "error" in above_list and ("outside workspace" in above_list["error"].lower() or "denied" in above_list["error"].lower()), (
        f"Directory listing above workspace was not blocked: {above_list}"
    )
    print(f"  OK: workspace/ sandbox strictly enforced (traversal attempts rejected).")

    print("[6] Testing web_tools HTTPS allowlist...")
    http_attempt = http_get("http://api.github.com")
    assert "error" in http_attempt and "https is permitted" in http_attempt["error"].lower()

    untrusted_domain = http_get("https://untrusted-external-domain.org")
    assert "error" in untrusted_domain and "not permitted by allowlist policy" in untrusted_domain["error"]
    print("  OK: http_get strictly enforces HTTPS and domain allowlist.")

    print("[7] Testing provider detection...")
    providers = detect_available_providers()
    assert "Agnes AI" in providers
    print(f"  OK: Providers detected cleanly: {list(providers.keys())}")

    print("[8] Testing tool dispatcher...")
    dispatch_calc = execute_tool_call("calc", '{"expression": "40 + 2"}')
    assert dispatch_calc.get("result") == 42
    dispatch_note = execute_tool_call("write_note", '{"title": "dispatch_test", "content": "hello"}')
    assert dispatch_note.get("status") == "ok"
    print("  OK: execute_tool_call dispatch succeeded for calc and write_note.")

    print("[9] Testing trace export (JSON and Markdown)...")
    sample_steps = [{
        "step_index": 1,
        "name": "calc",
        "args": {"expression": "2+2"},
        "result": "4",
        "latency": 0.001,
        "latency_ms": 1,
        "tool_call_id": "call_1",
    }]
    sample_msgs = [
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "content": "It is 4."},
    ]
    t_json = export_trace_json("Agnes AI", "agnes-3.0-flash", str(DEFAULT_WORKSPACE_DIR), sample_msgs, sample_steps)
    assert '"calc"' in t_json and '"total_steps": 1' in t_json
    t_md = export_trace_markdown("Agnes AI", "agnes-3.0-flash", str(DEFAULT_WORKSPACE_DIR), sample_msgs, sample_steps)
    assert "# Agent Workbench Execution Trace" in t_md and "### Step 1: `calc`" in t_md
    print("  OK: Trace JSON and Markdown exports generated successfully.")

    print("\nALL OFFLINE SMOKE CHECKS PASSED.")


if __name__ == "__main__":
    run_smoke()
