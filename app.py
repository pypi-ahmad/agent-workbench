"""Streamlit Agent Workbench Application.

Layout:
- Left Column: Tool Execution Log (name, args, truncated result, ms)
- Center Column: Multi-turn Chat Conversation
- Right Column: Live State JSON Inspector & Trace Exporter
"""

import json
import os
from pathlib import Path
import platform
import sys
import streamlit as st

from src.agent import DEFAULT_WORKSPACE_DIR, WorkbenchAgent
from src.agnes_client import (
    detect_available_providers,
    get_client,
)
from src.export import export_trace_json, export_trace_markdown
from src.tools.file_tools import get_working_dir, list_dir
from src.tools.registry import ALL_TOOLS

# Configure wide layout
st.set_page_config(
    page_title="Agent Workbench",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

if "raw_messages" not in st.session_state:
    st.session_state.raw_messages = []

if "step_logs" not in st.session_state:
    st.session_state.step_logs = []

# Sidebar Configuration
with st.sidebar:
    st.title("⚙️ Workbench Config")

    # Detect providers strictly based on existing env variables (no secret leakage)
    available_providers = detect_available_providers()
    provider_names = list(available_providers.keys())

    selected_provider = st.selectbox(
        "Provider",
        options=provider_names,
        index=provider_names.index("Agnes AI") if "Agnes AI" in provider_names else 0,
        help="Providers appear only when their corresponding environment variables exist.",
    )

    prov_cfg = available_providers[selected_provider]
    models = prov_cfg.get("models", ["agnes-3.0-flash"])
    default_model = prov_cfg.get("default_model", models[0])

    selected_model = st.selectbox(
        "Model",
        options=models,
        index=models.index(default_model) if default_model in models else 0,
    )

    # Status check for API key
    required_env = prov_cfg.get("required_env", "AGNESAI_API_KEY")
    key_is_present = bool(os.environ.get(required_env, "").strip())

    if key_is_present:
        st.success(f"Key configured: `{required_env}`", icon="✅")
    else:
        st.warning(f"Missing `{required_env}`. Set it in environment or `.env`.", icon="⚠️")

    st.markdown("---")
    st.subheader("📁 Working Directory")
    st.caption("Filesystem sandbox root for file tools:")
    st.code(str(DEFAULT_WORKSPACE_DIR), language="text")

    st.markdown("---")
    st.subheader("⚙️ Execution Limits")
    max_steps = st.number_input(
        "Max Steps per Turn",
        min_value=1,
        max_value=20,
        value=8,
        step=1,
        help="Maximum tool execution steps allowed per agent turn (default 8).",
    )

    st.markdown("---")
    st.subheader("🛠️ Enable / Disable Tools")
    enabled_tools = []
    for tool_name in ALL_TOOLS.keys():
        if st.checkbox(tool_name, value=True, key=f"tool_toggle_{tool_name}"):
            enabled_tools.append(tool_name)

    st.markdown("---")
    st.subheader("📥 Export Trace")
    trace_json_sidebar = export_trace_json(
        provider_name=selected_provider,
        model=selected_model,
        working_dir=str(DEFAULT_WORKSPACE_DIR),
        messages=st.session_state.raw_messages,
        steps=st.session_state.step_logs,
    )
    trace_md_sidebar = export_trace_markdown(
        provider_name=selected_provider,
        model=selected_model,
        working_dir=str(DEFAULT_WORKSPACE_DIR),
        messages=st.session_state.raw_messages,
        steps=st.session_state.step_logs,
    )
    sb_exp1, sb_exp2 = st.columns(2)
    with sb_exp1:
        st.download_button(
            "💾 JSON",
            data=trace_json_sidebar,
            file_name="agent_trace.json",
            mime="application/json",
            use_container_width=True,
        )
    with sb_exp2:
        st.download_button(
            "📝 Markdown",
            data=trace_md_sidebar,
            file_name="agent_trace.md",
            mime="text/markdown",
            use_container_width=True,
        )

    st.markdown("---")
    if st.button("🧹 Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.session_state.raw_messages = []
        st.session_state.step_logs = []
        st.rerun()

# 3-Column Layout: Left = Tool Log, Center = Chat, Right = State JSON
col_left, col_center, col_right = st.columns([1, 1.8, 1.2], gap="medium")

# ----------------- Left Column: Tool Log -----------------
with col_left:
    st.subheader("🛠️ Tool Log")
    if not st.session_state.step_logs:
        st.info("No tool steps executed yet.")
    else:
        for idx, entry in enumerate(reversed(st.session_state.step_logs)):
            step_num = len(st.session_state.step_logs) - idx
            latency_ms = entry.get("latency_ms", int(entry.get("latency", 0) * 1000))
            header_label = f"#{step_num}: {entry.get('name')} ({latency_ms} ms)"
            with st.expander(header_label, expanded=idx == 0):
                st.caption(f"Call ID: `{entry.get('tool_call_id', 'n/a')}` | Latency: `{latency_ms} ms` ({entry.get('latency', 0)}s)")
                st.markdown("**Arguments:**")
                st.json(entry.get("args", {}))

                st.markdown("**Result (truncated):**")
                st.code(entry.get("result", ""), language="json")

                with st.expander("Raw Payload"):
                    st.json(entry.get("raw_result", {}))

# ----------------- Center Column: Chat -----------------
with col_center:
    st.subheader("💬 Chat")

    # Render past conversation messages
    for msg in st.session_state.messages:
        role = msg["role"]
        with st.chat_message(role):
            st.markdown(msg["content"])
            if "steps" in msg and msg["steps"]:
                with st.expander(f"Executed {len(msg['steps'])} step(s)"):
                    for s in msg["steps"]:
                        lat_ms = s.get("latency_ms", int(s.get("latency", 0) * 1000))
                        st.markdown(f"- `{s['name']}` ({lat_ms} ms)")

    # Chat Input
    user_prompt = st.chat_input("Ask a question or give a task...")
    if user_prompt:
        st.session_state.messages.append({"role": "user", "content": user_prompt})

        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant"):
            client, err = get_client(selected_provider)
            if err or client is None:
                err_msg = f"⚠️ Configuration Error: {err}"
                st.error(err_msg)
                st.session_state.messages.append({"role": "assistant", "content": err_msg})
            else:
                with st.spinner(f"Agent thinking with {selected_model}..."):
                    try:
                        agent = WorkbenchAgent(
                            client=client,
                            provider_name=selected_provider,
                            model=selected_model,
                            working_dir=DEFAULT_WORKSPACE_DIR,
                            enabled_tools=enabled_tools,
                            max_steps=int(max_steps),
                        )

                        if st.session_state.raw_messages:
                            agent.messages = list(st.session_state.raw_messages)

                        turn_steps_collected = []

                        def on_step_callback(step_data):
                            turn_steps_collected.append(step_data)
                            st.session_state.step_logs.append(step_data)

                        res = agent.run_turn(user_prompt, on_step=on_step_callback)
                        final_text = res.get("final_content", "")
                        st.session_state.raw_messages = res.get("messages", [])

                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": final_text,
                            "steps": turn_steps_collected,
                        })

                        st.markdown(final_text)
                        if turn_steps_collected:
                            with st.expander(f"Completed {len(turn_steps_collected)} tool step(s)"):
                                for s in turn_steps_collected:
                                    lat_ms = s.get("latency_ms", int(s.get("latency", 0) * 1000))
                                    st.write(f"- `{s['name']}`: {s['args']} ({lat_ms} ms)")

                    except Exception as ex:
                        error_text = f"Agent execution error: {str(ex)}"
                        st.error(error_text)
                        st.session_state.messages.append({"role": "assistant", "content": error_text})

        st.rerun()

# ----------------- Right Column: State JSON -----------------
with col_right:
    st.subheader("📊 State Inspector")

    workspace_listing = list_dir(".")

    inspector_state = {
        "provider": {
            "name": selected_provider,
            "model": selected_model,
            "key_configured": key_is_present,
        },
        "session": {
            "displayed_messages_count": len(st.session_state.messages),
            "raw_turns_count": len(st.session_state.raw_messages),
            "total_steps_executed": len(st.session_state.step_logs),
            "max_steps": int(max_steps),
            "active_tools": enabled_tools,
            "working_directory": str(DEFAULT_WORKSPACE_DIR),
        },
        "workspace_files": workspace_listing.get("entries", []),
        "system_environment": {
            "os": platform.platform(),
            "python_version": sys.version.split()[0],
            "cwd": str(Path.cwd()),
        },
        "latest_step": st.session_state.step_logs[-1] if st.session_state.step_logs else None,
    }

    st.json(inspector_state)

    st.markdown("---")
    st.subheader("📥 Export Trace")
    trace_json_inspector = export_trace_json(
        provider_name=selected_provider,
        model=selected_model,
        working_dir=str(DEFAULT_WORKSPACE_DIR),
        messages=st.session_state.raw_messages,
        steps=st.session_state.step_logs,
    )
    trace_md_inspector = export_trace_markdown(
        provider_name=selected_provider,
        model=selected_model,
        working_dir=str(DEFAULT_WORKSPACE_DIR),
        messages=st.session_state.raw_messages,
        steps=st.session_state.step_logs,
    )
    insp_col1, insp_col2 = st.columns(2)
    with insp_col1:
        st.download_button(
            "💾 Export JSON",
            data=trace_json_inspector,
            file_name="agent_trace.json",
            mime="application/json",
            use_container_width=True,
            key="insp_export_json",
        )
    with insp_col2:
        st.download_button(
            "📝 Export Markdown",
            data=trace_md_inspector,
            file_name="agent_trace.md",
            mime="text/markdown",
            use_container_width=True,
            key="insp_export_md",
        )
