"""Workbench Agent implementation with robust tool execution and step persistence."""

import ast
import json
from pathlib import Path
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from openai import OpenAI

from src.agnes_client import DEFAULT_AGNES_MODEL, get_client
from src.tools.file_tools import get_working_dir, set_working_dir
from src.tools.registry import ALL_TOOLS, execute_tool_call, get_openai_tools

DEFAULT_WORKSPACE_DIR = Path("D:/AI/Github/agent-workbench/workspace").resolve()
MAX_RESULT_CHARS = 1000


def clean_argument_string(raw_str: str) -> str:
    """Strip markdown code blocks or wrapping quotes."""
    s = raw_str.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if len(lines) >= 2 and lines[-1].strip().startswith("```"):
            s = "\n".join(lines[1:-1]).strip()
        elif s.startswith("```json"):
            s = s[7:].strip()
        elif s.startswith("```"):
            s = s[3:].strip()
        if s.endswith("```"):
            s = s[:-3].strip()
    return s


def parse_tool_arguments(tool_name: str, raw_args: Any) -> Dict[str, Any]:
    """Parse tool arguments defensively against unexpected model output shapes."""
    if raw_args is None:
        return {}

    if isinstance(raw_args, dict):
        return raw_args

    if not isinstance(raw_args, str):
        try:
            return dict(raw_args)
        except Exception:
            return {"value": raw_args}

    cleaned = clean_argument_string(raw_args)
    if not cleaned or cleaned in ("{}", "[]"):
        return {}

    # 1. Attempt standard JSON decoding
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
        elif isinstance(parsed, (int, float, bool, list)):
            return _heuristic_single_arg_map(tool_name, parsed)
    except json.JSONDecodeError:
        pass

    # 2. Attempt Python literal parsing (single quotes or unescaped strings)
    try:
        parsed = ast.literal_eval(cleaned)
        if isinstance(parsed, dict):
            return parsed
        elif isinstance(parsed, (int, float, bool, list)):
            return _heuristic_single_arg_map(tool_name, parsed)
    except Exception:
        pass

    # 3. Fallback heuristic mapping for single argument string outputs
    return _heuristic_single_arg_map(tool_name, cleaned)


def _heuristic_single_arg_map(tool_name: str, val: Any) -> Dict[str, Any]:
    """Map a bare value to expected parameter name based on tool registry schema."""
    if tool_name == "calc":
        return {"expression": str(val)}
    elif tool_name == "read_file":
        return {"path": str(val)}
    elif tool_name == "list_dir":
        return {"path": str(val)}
    elif tool_name == "write_note":
        return {"title": "notes.md", "content": str(val)}
    elif tool_name == "http_get":
        return {"url": str(val)}
    return {"input": val}



def truncate_result(result: Any, max_chars: int = MAX_RESULT_CHARS) -> str:
    """Format and truncate tool execution result for logging."""
    if isinstance(result, str):
        s = result
    else:
        try:
            s = json.dumps(result, ensure_ascii=False)
        except Exception:
            s = str(result)
    
    if len(s) > max_chars:
        return s[:max_chars] + f"... [truncated, total {len(s)} chars]"
    return s


class WorkbenchAgent:
    """Agent coordinator managing conversation history, tool definitions, and step loops."""

    def __init__(
        self,
        client: Optional[OpenAI] = None,
        provider_name: str = "Agnes AI",
        model: str = DEFAULT_AGNES_MODEL,
        working_dir: Union[str, Path] = DEFAULT_WORKSPACE_DIR,
        enabled_tools: Optional[List[str]] = None,
        max_steps: int = 8,
        system_prompt: Optional[str] = None,
    ):
        self.provider_name = provider_name
        self.model = model
        self.max_steps = max_steps
        self.working_dir = set_working_dir(working_dir)

        if client is not None:
            self.client = client
        else:
            c, err = get_client(provider_name)
            if err or c is None:
                raise ValueError(f"Failed to initialize client for {provider_name}: {err}")
            self.client = c

        self.enabled_tools = enabled_tools if enabled_tools is not None else list(ALL_TOOLS.keys())
        self.system_prompt = system_prompt or (
            f"You are a helpful coding assistant operating on Windows 11. "
            f"Your sole accessible filesystem directory is the workspace at: {self.working_dir}. "
            "All file operations (list_dir, read_file, write_note) are strictly confined to this workspace. "
            "Use available tools (list_dir, read_file, write_note, calc, http_get, now) to solve tasks. "
            "Never guess file contents or mathematical computations; invoke the appropriate tools."
        )


        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt}
        ]
        self.steps: List[Dict[str, Any]] = []

    def set_enabled_tools(self, tools: List[str]) -> None:
        """Update enabled tools list."""
        self.enabled_tools = [t for t in tools if t in ALL_TOOLS]

    def get_tool_schemas(self) -> Optional[List[Dict[str, Any]]]:
        """Return OpenAI-formatted tool schemas for enabled tools."""
        if not self.enabled_tools:
            return None
        return get_openai_tools(self.enabled_tools)

    def run_turn(
        self,
        user_message: str,
        on_step: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Execute agent turn until no tool calls or max_steps reached."""
        self.messages.append({"role": "user", "content": user_message})

        step_count = 0
        turn_start_time = time.perf_counter()
        turn_steps: List[Dict[str, Any]] = []

        while step_count < self.max_steps:
            tool_schemas = self.get_tool_schemas()

            req_kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": self.messages,
                "temperature": 0.1,
            }
            if tool_schemas:
                req_kwargs["tools"] = tool_schemas
                req_kwargs["tool_choice"] = "auto"

            max_retries = 3
            backoff_base = 4.0
            response = None

            for attempt in range(max_retries + 1):
                try:
                    response = self.client.chat.completions.create(**req_kwargs)
                    break
                except Exception as ex:
                    err_str = str(ex).lower()
                    if attempt < max_retries and ("rate limit" in err_str or "429" in err_str or "timeout" in err_str):
                        wait_sec = backoff_base * (attempt + 1)
                        time.sleep(wait_sec)
                    else:
                        raise ex

            choice = response.choices[0]
            message = choice.message


            # Check if model made tool calls
            raw_tool_calls = getattr(message, "tool_calls", None)

            if not raw_tool_calls:
                final_text = message.content or ""
                self.messages.append({"role": "assistant", "content": final_text})
                total_latency = time.perf_counter() - turn_start_time
                return {
                    "status": "success",
                    "final_content": final_text,
                    "steps": turn_steps,
                    "messages": self.messages,
                    "total_latency": round(total_latency, 3),
                    "steps_count": len(turn_steps),
                }

            # 1. Parse all tool calls in this turn
            parsed_calls = []
            for tc in raw_tool_calls:
                step_count += 1
                tc_id = getattr(tc, "id", f"call_{step_count}")
                func = getattr(tc, "function", None)
                if func is not None:
                    t_name = getattr(func, "name", "")
                    raw_args = getattr(func, "arguments", "{}")
                elif isinstance(tc, dict):
                    f_dict = tc.get("function", {})
                    t_name = f_dict.get("name", "")
                    raw_args = f_dict.get("arguments", "{}")
                else:
                    t_name = str(tc)
                    raw_args = "{}"

                parsed_args = parse_tool_arguments(t_name, raw_args)
                parsed_calls.append((tc_id, t_name, parsed_args))

            # 2. Append assistant turn entry
            assistant_turn_entry = {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc_id,
                        "type": "function",
                        "function": {
                            "name": t_name,
                            "arguments": json.dumps(parsed_args, ensure_ascii=False),
                        },
                    }
                    for tc_id, t_name, parsed_args in parsed_calls
                ],
            }
            self.messages.append(assistant_turn_entry)

            # 3. Execute each tool and append tool messages
            for tc_id, t_name, parsed_args in parsed_calls:
                exec_start = time.perf_counter()
                tool_result = execute_tool_call(t_name, parsed_args)
                exec_latency = time.perf_counter() - exec_start
                truncated = truncate_result(tool_result, max_chars=MAX_RESULT_CHARS)
                latency_ms = int(round(exec_latency * 1000))


                step_record = {
                    "step_index": len(self.steps) + 1,
                    "name": t_name,
                    "args": parsed_args,
                    "result": truncated,
                    "raw_result": tool_result,
                    "latency": round(exec_latency, 4),
                    "latency_ms": latency_ms,
                    "tool_call_id": tc_id,
                }

                self.steps.append(step_record)
                turn_steps.append(step_record)

                if on_step:
                    on_step(step_record)

                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "name": t_name,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                })

        # Max steps reached
        total_latency = time.perf_counter() - turn_start_time
        fallback_msg = "Maximum tool step limit reached."
        self.messages.append({"role": "assistant", "content": fallback_msg})

        return {
            "status": "max_steps_reached",
            "final_content": fallback_msg,
            "steps": turn_steps,
            "messages": self.messages,
            "total_latency": round(total_latency, 3),
            "steps_count": len(turn_steps),
        }
