"""Agnes AI and OpenAI-compatible multi-provider client with tool-calling support."""

import json
import os
from typing import Any, Callable, Dict, List, Optional, Tuple
from dotenv import load_dotenv
from openai import OpenAI

# Load local environment if present
load_dotenv()

DEFAULT_AGNES_BASE_URL = "https://apihub.agnes-ai.com/v1"
DEFAULT_AGNES_MODEL = "agnes-3.0-flash"

GOOGLE_OPENAI_COMPAT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

PROVIDER_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "Agnes AI": {
        "required_env": "AGNESAI_API_KEY",
        "default_base_url": DEFAULT_AGNES_BASE_URL,
        "base_url_env": "AGNESAI_BASE_URL",
        "models": ["agnes-3.0-flash"],
        "default_model": DEFAULT_AGNES_MODEL,
    },
    "OpenAI": {
        "required_env": "OPENAI_API_KEY",
        "default_base_url": None,  # Uses official OpenAI base URL
        "base_url_env": "OPENAI_BASE_URL",
        "models": ["gpt-5.6-luna", "gpt-5.6-terra"],
        "default_model": "gpt-5.6-luna",
    },
    "Google Gemini": {
        "required_env": "GOOGLE_API_KEY",
        "default_base_url": GOOGLE_OPENAI_COMPAT_BASE_URL,
        "base_url_env": "GOOGLE_BASE_URL",
        "models": ["gemini-3.5-flash-lite", "gemini-3.7-flash"],
        "default_model": "gemini-3.5-flash-lite",
    },
}


def detect_available_providers() -> Dict[str, Dict[str, Any]]:
    """Detect configured providers based strictly on presence of environment variables.
    
    Never exposes or logs secret values.
    """
    available = {}
    for name, config in PROVIDER_DEFINITIONS.items():
        env_name = config["required_env"]
        # Check presence only
        if bool(os.environ.get(env_name, "").strip()):
            available[name] = config
    
    # Agnes AI is always listed in definitions; if key is missing, UI can report prompt to set AGNESAI_API_KEY
    if "Agnes AI" not in available:
        available["Agnes AI"] = PROVIDER_DEFINITIONS["Agnes AI"]

    return available


def get_client(provider_name: str = "Agnes AI") -> Tuple[Optional[OpenAI], Optional[str]]:
    """Instantiate OpenAI client for the specified provider without exposing secrets.
    
    Returns (client, error_message).
    """
    if provider_name not in PROVIDER_DEFINITIONS:
        return None, f"Unknown provider: {provider_name}"

    conf = PROVIDER_DEFINITIONS[provider_name]
    env_name = conf["required_env"]
    api_key = os.environ.get(env_name, "").strip()

    if not api_key:
        return None, f"Environment variable '{env_name}' is not set or empty."

    # Determine base URL
    base_url_env = conf.get("base_url_env")
    custom_base = os.environ.get(base_url_env, "").strip() if base_url_env else None
    base_url = custom_base or conf.get("default_base_url")

    try:
        if base_url:
            client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            client = OpenAI(api_key=api_key)
        return client, None
    except Exception as e:
        return None, f"Failed to initialize client for {provider_name}: {str(e)}"


def run_chat_completion(
    client: OpenAI,
    model: str,
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    temperature: float = 0.2,
) -> Any:
    """Send chat completions request with optional tool definitions."""
    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    return client.chat.completions.create(**kwargs)


def run_agent_loop(
    client: OpenAI,
    model: str,
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]],
    tool_executor: Callable[[str, Any], Dict[str, Any]],
    max_turns: int = 5,
    on_tool_call: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """Execute conversational turn with automated tool execution loop.
    
    Returns structured results including tool call logs and final content.
    """
    turn_messages = list(messages)
    tool_executions: List[Dict[str, Any]] = []

    for _ in range(max_turns):
        response = run_chat_completion(
            client=client,
            model=model,
            messages=turn_messages,
            tools=tools,
        )

        choice = response.choices[0]
        message = choice.message

        # If no tool calls, conversation turn is complete
        if not message.tool_calls:
            turn_messages.append({"role": "assistant", "content": message.content or ""})
            return {
                "status": "completed",
                "final_content": message.content or "",
                "messages": turn_messages,
                "tool_executions": tool_executions,
                "usage": getattr(response, "usage", None),
            }

        # Model requested tool calls
        # Append assistant message with tool_calls in OpenAI format
        assistant_turn_msg: Dict[str, Any] = {
            "role": "assistant",
            "content": message.content or None,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ],
        }
        turn_messages.append(assistant_turn_msg)

        # Execute each requested tool call
        for tc in message.tool_calls:
            t_name = tc.function.name
            t_args_str = tc.function.arguments

            # Run execution
            result = tool_executor(t_name, t_args_str)
            exec_record = {
                "tool_call_id": tc.id,
                "tool_name": t_name,
                "arguments": t_args_str,
                "result": result,
            }
            tool_executions.append(exec_record)

            if on_tool_call:
                on_tool_call(exec_record)

            # Append tool response message
            turn_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": t_name,
                "content": json.dumps(result, ensure_ascii=False),
            })

    # Return if max turns reached without final content
    return {
        "status": "max_turns_reached",
        "final_content": "Maximum tool turn limit reached without final assistant text.",
        "messages": turn_messages,
        "tool_executions": tool_executions,
    }
