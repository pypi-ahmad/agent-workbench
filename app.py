"""Windows-native Streamlit UI for the tool-calling agent workbench."""

import os

import streamlit as st

from src.agent import DEFAULT_WORKSPACE_DIR, WorkbenchAgent
from src.agnes_client import detect_available_providers, get_client
from src.config import DEFAULT_MAX_STEPS, HARD_MAX_STEPS
from src.export import export_trace_json, export_trace_markdown
from src.tools.fs_tools import list_dir
from src.tools.registry import ALL_TOOLS

st.set_page_config(page_title="Tool-calling Agent Workbench", layout="wide")

for key, default in {
    "chat_messages": [],
    "api_messages": [],
    "tool_steps": [],
}.items():
    st.session_state.setdefault(key, default)


def render_step(step: dict, *, live: bool = False) -> None:
    """Render all required tool telemetry."""
    label = f"#{step['i']} · {step['kind']} · {step['name']} · {step['ms']} ms"
    container = (
        st.status(label, state="complete", type="step")
        if live
        else st.expander(label, type="step")
    )
    with container:
        st.markdown("Arguments")
        st.json(step["args"])
        st.markdown("Result preview")
        st.code(step["result_preview"], language="text")
        if step["error"]:
            st.error(step["error"])


providers = detect_available_providers()

with st.sidebar:
    st.header("Workbench settings")
    provider_name = st.selectbox(
        "Provider",
        list(providers),
        index=list(providers).index("Agnes AI"),
        key="provider",
    )
    provider = providers[provider_name]
    model = st.selectbox("Model", provider["models"], key="model")
    key_name = provider["api_key_env"]
    key_available = bool(os.environ.get(key_name, "").strip())
    agnes_key_available = bool(os.environ.get("AGNESAI_API_KEY", "").strip())
    st.caption(f"AGNESAI_API_KEY set: {'yes' if agnes_key_available else 'no'}")
    if not agnes_key_available:
        st.error("Missing required environment variable: AGNESAI_API_KEY")
    if not key_available:
        st.warning(f"{key_name} is unavailable. Relaunch the host if recently configured.")

    max_steps = st.number_input(
        "Maximum tool steps",
        min_value=1,
        max_value=HARD_MAX_STEPS,
        value=DEFAULT_MAX_STEPS,
        step=1,
        help=f"Default {DEFAULT_MAX_STEPS}; hard cap {HARD_MAX_STEPS}.",
        key="max_steps",
    )

    st.subheader("Enabled tools")
    enabled_tools = [
        name
        for name in ALL_TOOLS
        if st.checkbox(name, value=True, key=f"tool_{name}")
    ]

    if st.button("Clear conversation", icon=":material/delete:", width="stretch"):
        st.session_state.chat_messages = []
        st.session_state.api_messages = []
        st.session_state.tool_steps = []
        st.rerun()

    trace_json = export_trace_json(
        provider_name,
        model,
        str(DEFAULT_WORKSPACE_DIR),
        st.session_state.api_messages,
        st.session_state.tool_steps,
    )
    trace_markdown = export_trace_markdown(
        provider_name,
        model,
        str(DEFAULT_WORKSPACE_DIR),
        st.session_state.api_messages,
        st.session_state.tool_steps,
    )
    st.download_button(
        "Download JSON trace",
        trace_json,
        "agent_trace.json",
        "application/json",
        icon=":material/download:",
        width="stretch",
    )
    st.download_button(
        "Download Markdown trace",
        trace_markdown,
        "agent_trace.md",
        "text/markdown",
        icon=":material/download:",
        width="stretch",
    )

st.title("Tool-calling Agent Workbench")
st.caption("Chat with Agnes 3.0 Flash and inspect every tool call.")

tool_column, chat_column, state_column = st.columns([1.1, 2, 1.1], gap="medium")

with tool_column:
    st.subheader("Tool timeline")
    if not st.session_state.tool_steps:
        st.info("No tool calls yet.")
    for saved_step in reversed(st.session_state.tool_steps):
        render_step(saved_step)

with chat_column:
    st.subheader("Chat")
    for chat_message in st.session_state.chat_messages:
        with st.chat_message(chat_message["role"]):
            st.markdown(chat_message["content"])
            for saved_step in chat_message.get("steps", []):
                render_step(saved_step)

    prompt = st.chat_input("Ask Agnes to inspect, calculate, fetch, or write a note.")
    if prompt:
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            if not agnes_key_available:
                client, error = (
                    None,
                    "Missing required environment variable: AGNESAI_API_KEY",
                )
            else:
                client, error = get_client(provider_name)
            if client is None:
                message = error or "Provider client is unavailable."
                st.error(message)
                st.session_state.chat_messages.append(
                    {"role": "assistant", "content": message}
                )
            else:
                turn_steps: list[dict] = []

                def show_step(step: dict) -> None:
                    turn_steps.append(step)
                    st.session_state.tool_steps.append(step)
                    render_step(step, live=True)

                try:
                    with st.spinner("Waiting for model"):
                        agent = WorkbenchAgent(
                            client=client,
                            provider_name=provider_name,
                            model=model,
                            enabled_tools=enabled_tools,
                            max_steps=int(max_steps),
                        )
                        if st.session_state.api_messages:
                            agent.messages = list(st.session_state.api_messages)
                        result = agent.run(prompt, on_step=show_step)
                    answer = result["final_content"]
                    st.markdown(answer)
                    st.session_state.api_messages = result["messages"]
                    st.session_state.chat_messages.append(
                        {
                            "role": "assistant",
                            "content": answer,
                            "steps": turn_steps,
                        }
                    )
                except Exception as exc:
                    message = f"Agent request failed: {exc}"
                    st.error(message)
                    st.session_state.chat_messages.append(
                        {"role": "assistant", "content": message, "steps": turn_steps}
                    )
        st.rerun()

with state_column:
    st.subheader("Live state")
    workspace = list_dir(".")
    st.json(
        {
            "provider": provider_name,
            "model": model,
            "credential_available": key_available,
            "enabled_tools": enabled_tools,
            "maximum_steps": int(max_steps),
            "tool_calls": sum(
                step["kind"] == "tool" for step in st.session_state.tool_steps
            ),
            "model_steps": sum(
                step["kind"] == "model" for step in st.session_state.tool_steps
            ),
            "messages": st.session_state.chat_messages,
            "api_messages": st.session_state.api_messages,
            "workspace": str(DEFAULT_WORKSPACE_DIR),
            "workspace_entries": workspace.get("entries", []),
        }
    )
