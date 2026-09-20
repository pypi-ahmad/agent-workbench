"""Export utilities for agent traces in JSON and Markdown formats."""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional


def build_trace_payload(
    provider_name: str,
    model: str,
    working_dir: str,
    messages: List[Dict[str, Any]],
    steps: List[Dict[str, Any]],
    total_latency: Optional[float] = None,
) -> Dict[str, Any]:
    """Assemble structured trace payload."""
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "timestamp_utc": now_iso,
        "metadata": {
            "provider": provider_name,
            "model": model,
            "working_directory": working_dir,
            "total_messages": len(messages),
            "total_steps": len(steps),
            "total_latency_seconds": total_latency,
        },
        "steps": steps,
        "messages": messages,
    }


def export_trace_json(
    provider_name: str,
    model: str,
    working_dir: str,
    messages: List[Dict[str, Any]],
    steps: List[Dict[str, Any]],
    total_latency: Optional[float] = None,
    indent: int = 2,
) -> str:
    """Export conversation and execution trace as formatted JSON string."""
    payload = build_trace_payload(
        provider_name=provider_name,
        model=model,
        working_dir=working_dir,
        messages=messages,
        steps=steps,
        total_latency=total_latency,
    )
    return json.dumps(payload, indent=indent, ensure_ascii=False)


def export_trace_markdown(
    provider_name: str,
    model: str,
    working_dir: str,
    messages: List[Dict[str, Any]],
    steps: List[Dict[str, Any]],
    total_latency: Optional[float] = None,
) -> str:
    """Export conversation and execution trace as human-readable Markdown."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: List[str] = [
        "# Agent Workbench Execution Trace",
        "",
        f"- **Generated**: {now_str}",
        f"- **Provider**: `{provider_name}`",
        f"- **Model**: `{model}`",
        f"- **Working Directory**: `{working_dir}`",
        f"- **Total Steps Executed**: {len(steps)}",
    ]
    if total_latency is not None:
        lines.append(f"- **Total Latency**: `{total_latency:.3f}s`")
    
    lines.extend([
        "",
        "## Tool execution steps",
        "",
    ])

    if not steps:
        lines.append("No tools were executed during this session.\n")
    else:
        for idx, step in enumerate(steps, 1):
            name = step.get("name", "unknown")
            latency_ms = step.get("ms", "n/a")
            args = step.get("args", {})
            result = step.get("result_preview", "")

            lines.append(
                f"### Step {step.get('i', idx)}: "
                f"`{step.get('kind', 'unknown')}` / `{name}` ({latency_ms} ms)"
            )
            if step.get("error"):
                lines.append(f"- Error: `{step['error']}`")
            lines.append("")
            lines.append("Arguments:")
            lines.append("```json")
            lines.append(json.dumps(args, indent=2, ensure_ascii=False) if isinstance(args, dict) else str(args))
            lines.append("```")
            lines.append("")
            lines.append("Result (truncated):")
            lines.append("```json")
            lines.append(result if isinstance(result, str) else json.dumps(result, indent=2, ensure_ascii=False))
            lines.append("```")
            lines.append("")

    lines.extend([
        "## Conversation history",
        "",
    ])


    for msg in messages:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content")
        if content:
            lines.append(f"### {role}")
            lines.append("")
            lines.append(content)
            lines.append("")
        elif msg.get("tool_calls"):
            calls_summary = [f"`{tc['function']['name']}`" for tc in msg.get("tool_calls", [])]
            lines.append(f"### {role} (Tool Calls Requested: {', '.join(calls_summary)})")
            lines.append("")

    return "\n".join(lines)
