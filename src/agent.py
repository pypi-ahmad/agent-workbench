"""Official Chat Completions loop with sequential tool execution."""

import json
from pathlib import Path
import time
from typing import Any, Callable

from openai import OpenAI

from src.agnes_client import (
    DEFAULT_AGNES_MODEL,
    chat_completion_with_429_retries,
    get_client,
)
from src.config import HARD_MAX_STEPS, TOOL_RESULT_MAX_CHARS, WORKSPACE_DIR
from src.tools.file_tools import set_working_dir
from src.tools.registry import ALL_TOOLS, execute_tool_call, get_openai_tools

DEFAULT_WORKSPACE_DIR = WORKSPACE_DIR


def _preview(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    if len(text) <= TOOL_RESULT_MAX_CHARS:
        return text
    return f"{text[:TOOL_RESULT_MAX_CHARS]}... [truncated]"


def _arguments(raw_arguments: Any) -> tuple[dict[str, Any], str | None]:
    if not isinstance(raw_arguments, str):
        return {}, "Tool arguments are not a JSON string."
    try:
        parsed = json.loads(raw_arguments) if raw_arguments.strip() else {}
    except json.JSONDecodeError as exc:
        return {"raw": raw_arguments}, f"Malformed tool arguments: {exc}"
    if not isinstance(parsed, dict):
        return {"raw": raw_arguments}, "Tool arguments must decode to a JSON object."
    return parsed, None


class WorkbenchAgent:
    """Run model and tool steps until final text or the tool-step cap."""

    def __init__(
        self,
        client: OpenAI | None = None,
        provider_name: str = "Agnes AI",
        model: str = DEFAULT_AGNES_MODEL,
        working_dir: str | Path = DEFAULT_WORKSPACE_DIR,
        enabled_tools: list[str] | None = None,
        max_steps: int = 8,
        system_prompt: str | None = None,
    ) -> None:
        self.provider_name = provider_name
        self.model = model
        self.max_steps = min(max(int(max_steps), 1), HARD_MAX_STEPS)
        self.working_dir = set_working_dir(working_dir)
        self.enabled_tools = [
            name
            for name in (enabled_tools if enabled_tools is not None else ALL_TOOLS)
            if name in ALL_TOOLS
        ]
        if client is None:
            client, error = get_client(provider_name)
            if client is None:
                raise ValueError(error or "Provider client is unavailable.")
        self.client = client
        self.messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": system_prompt
                or (
                    "Use the supplied tools to complete every requested operation. "
                    "For file questions, inspect files instead of guessing. "
                    "For arithmetic, use calc. After all tool results arrive, give a "
                    "concise final answer containing the relevant results."
                ),
            }
        ]
        self.steps: list[dict[str, Any]] = []

    def _add_step(
        self,
        turn_steps: list[dict[str, Any]],
        *,
        kind: str,
        name: str,
        args: Any,
        result: Any,
        ms: float,
        error: str | None,
        on_step: Callable[[dict[str, Any]], None] | None,
    ) -> None:
        step = {
            "i": len(self.steps) + 1,
            "kind": kind,
            "name": name,
            "args": args,
            "result_preview": _preview(result),
            "ms": round(ms, 2),
            "error": error,
        }
        self.steps.append(step)
        turn_steps.append(step)
        if on_step:
            on_step(step)

    def run_turn(
        self,
        user_message: str,
        on_step: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        self.messages.append({"role": "user", "content": user_message})
        turn_steps: list[dict[str, Any]] = []
        turn_started = time.perf_counter()
        tool_count = 0
        first_model_call = True

        while tool_count < self.max_steps:
            tools = get_openai_tools(self.enabled_tools)
            request: dict[str, Any] = {
                "model": self.model,
                "messages": self.messages,
            }
            if tools:
                request["tools"] = tools
                request["tool_choice"] = "required" if first_model_call else "auto"

            model_started = time.perf_counter()
            try:
                response = chat_completion_with_429_retries(self.client, request)
            except Exception as exc:
                self._add_step(
                    turn_steps,
                    kind="model",
                    name=self.model,
                    args={"message_count": len(self.messages)},
                    result="",
                    ms=(time.perf_counter() - model_started) * 1000,
                    error=str(exc),
                    on_step=on_step,
                )
                raise
            first_model_call = False

            message = response.choices[0].message
            requested_calls = list(message.tool_calls or [])
            model_result = message.content or ""
            if requested_calls:
                names = ", ".join(call.function.name for call in requested_calls)
                model_result = f"tool_calls: {names}"
            self._add_step(
                turn_steps,
                kind="model",
                name=self.model,
                args={"message_count": len(self.messages), "tools": self.enabled_tools},
                result=model_result,
                ms=(time.perf_counter() - model_started) * 1000,
                error=None,
                on_step=on_step,
            )

            if not requested_calls:
                final_content = message.content or ""
                self.messages.append({"role": "assistant", "content": final_content})
                return self._result(
                    "success",
                    final_content,
                    turn_steps,
                    tool_count,
                    time.perf_counter() - turn_started,
                )

            requested_calls = requested_calls[: self.max_steps - tool_count]
            self.messages.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments,
                            },
                        }
                        for call in requested_calls
                    ],
                }
            )

            for call in requested_calls:
                tool_count += 1
                name = call.function.name
                args, argument_error = _arguments(call.function.arguments)
                tool_started = time.perf_counter()
                if argument_error:
                    result: Any = {"error": argument_error}
                elif name not in self.enabled_tools:
                    result = {"error": f"Tool is disabled: {name}"}
                else:
                    result = execute_tool_call(name, args)
                error = result.get("error") if isinstance(result, dict) else None
                self._add_step(
                    turn_steps,
                    kind="tool",
                    name=name,
                    args=args,
                    result=result,
                    ms=(time.perf_counter() - tool_started) * 1000,
                    error=error,
                    on_step=on_step,
                )
                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": name,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

        final_content = f"Stopped after the {self.max_steps}-tool limit."
        self.messages.append({"role": "assistant", "content": final_content})
        return self._result(
            "max_steps_reached",
            final_content,
            turn_steps,
            tool_count,
            time.perf_counter() - turn_started,
        )

    def run(
        self,
        user_message: str,
        on_step: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Run one user turn through the Chat Completions tool loop."""
        return self.run_turn(user_message, on_step=on_step)

    def _result(
        self,
        status: str,
        final_content: str,
        turn_steps: list[dict[str, Any]],
        tool_count: int,
        latency: float,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "final_content": final_content,
            "steps": turn_steps,
            "messages": self.messages,
            "total_latency": round(latency, 3),
            "steps_count": len(turn_steps),
            "tool_steps_count": tool_count,
        }
