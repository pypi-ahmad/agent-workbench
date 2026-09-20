"""Offline smoke checks for product, security, agent loop, and Streamlit UI."""

import ast
from pathlib import Path
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

from src.agent import WorkbenchAgent
from src.agnes_client import chat_completion_with_429_retries, detect_available_providers
from src.config import HARD_MAX_STEPS, HTTP_ALLOWED_HOSTS, WORKSPACE_DIR
from src.export import export_trace_json
from src.tools.fs_tools import list_dir, read_file, write_note
from src.tools.misc_tools import calc, http_get, now
from src.tools.registry import get_openai_tools

ROOT = Path(__file__).resolve().parent


def _tool_call(index: int, name: str = "now", arguments: str = "{}") -> SimpleNamespace:
    return SimpleNamespace(
        id=f"call_{index}",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


class _FakeCompletions:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self.responses = responses
        self.requests: list[dict] = []

    def create(self, **request):
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _response(*, content: str = "", calls: list[SimpleNamespace] | None = None):
    message = SimpleNamespace(content=content, tool_calls=calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def run_smoke() -> None:
    print("[1] Product files and launcher")
    env_lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    assert env_lines == [
        "AGNESAI_API_KEY=",
        "AGNES_BASE_URL=https://apihub.agnes-ai.com/v1",
    ]
    launcher = (ROOT / "run.cmd").read_text(encoding="utf-8")
    for command in (
        "py -3 -m venv .venv",
        ".venv\\Scripts\\pip install -r requirements.txt",
        ".venv\\Scripts\\streamlit run app.py",
    ):
        assert command in launcher
    assert (ROOT / "workspace" / "sample.txt").read_text(encoding="utf-8").strip() == (
        "WORKBENCH_FIXTURE_OK"
    )
    assert "Workbench sandbox file." in (
        ROOT / "workspace" / "README.md"
    ).read_text(encoding="utf-8")
    assert (ROOT / "src" / "tools" / "fs_tools.py").exists()
    assert (ROOT / "src" / "tools" / "misc_tools.py").exists()

    print("[2] Six official tool schemas")
    names = {tool["function"]["name"] for tool in get_openai_tools()}
    assert names == {"list_dir", "read_file", "write_note", "calc", "http_get", "now"}
    assert {
        tool["function"]["name"] for tool in get_openai_tools(["calc", "now"])
    } == {"calc", "now"}

    print("[3] Calculator and time")
    assert calc("17 * 19")["result"] == 323
    assert "error" in calc("__import__('os').system('dir')")
    assert "T" in now()

    print("[4] Workspace file sandbox")
    assert list_dir(".")["path"] == "."
    assert "error" in read_file("../app.py")
    assert "error" in read_file(r"C:\Windows\win.ini")
    written = write_note("smoke.txt", "smoke")
    assert written["path"] == "notes/smoke.txt"
    assert read_file("notes/smoke.txt")["text"] == "smoke"
    assert "error" in write_note(r"C:\outside.txt", "blocked")

    print("[5] HTTPS host policy")
    assert HTTP_ALLOWED_HOSTS == {"example.com", "httpbin.org"}
    assert "error" in http_get("file:///etc/passwd")
    assert "error" in http_get("http://example.com")
    assert "error" in http_get("https://localhost/test")

    print("[6] Provider visibility")
    providers = detect_available_providers()
    assert providers["Agnes AI"]["models"] == ["agnes-3.0-flash"]

    print("[7] HTTP 429 retry")
    rate_limit = RuntimeError("rate limited")
    rate_limit.status_code = 429
    retry_completions = _FakeCompletions(
        [rate_limit, rate_limit, _response(content="recovered")]
    )
    retry_client = SimpleNamespace(
        chat=SimpleNamespace(completions=retry_completions)
    )
    waits: list[int] = []
    recovered = chat_completion_with_429_retries(
        retry_client, {"model": "test", "messages": []}, sleep=waits.append
    )
    assert recovered.choices[0].message.content == "recovered"
    assert waits == [1, 2]

    print("[8] Official Chat Completions tool loop")
    completions = _FakeCompletions(
        [
            _response(calls=[_tool_call(1, "calc", '{"expression":"6*7"}')]),
            _response(content="42"),
        ]
    )
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    agent = WorkbenchAgent(client=fake_client, enabled_tools=["calc"])
    result = agent.run("Calculate 6*7")
    assert result["final_content"] == "42"
    assert result["steps"][0]["kind"] == "model"
    assert result["steps"][1]["name"] == "calc"
    assert result["steps"][1]["kind"] == "tool"
    assert completions.requests[0]["tools"][0]["function"]["name"] == "calc"
    assert completions.requests[0]["tool_choice"] == "required"
    assert any(message["role"] == "tool" for message in result["messages"])

    print("[9] Disabled-tool enforcement")
    disabled_completions = _FakeCompletions(
        [
            _response(calls=[_tool_call(1, "calc", '{"expression":"1+1"}')]),
            _response(content="blocked"),
        ]
    )
    disabled_client = SimpleNamespace(
        chat=SimpleNamespace(completions=disabled_completions)
    )
    disabled = WorkbenchAgent(
        client=disabled_client, enabled_tools=["now"]
    ).run_turn("Use calc")
    assert "disabled" in disabled["steps"][1]["error"]

    print("[10] Malformed tool arguments")
    malformed_completions = _FakeCompletions(
        [
            _response(calls=[_tool_call(1, "calc", "{bad json")]),
            _response(content="argument error handled"),
        ]
    )
    malformed_client = SimpleNamespace(
        chat=SimpleNamespace(completions=malformed_completions)
    )
    malformed = WorkbenchAgent(
        client=malformed_client, enabled_tools=["calc"]
    ).run_turn("Calculate")
    assert "Malformed tool arguments" in malformed["steps"][1]["error"]
    assert malformed["final_content"] == "argument error handled"

    print("[11] Hard step cap")
    many_calls = [_tool_call(index) for index in range(20)]
    cap_completions = _FakeCompletions([_response(calls=many_calls)])
    cap_client = SimpleNamespace(chat=SimpleNamespace(completions=cap_completions))
    capped = WorkbenchAgent(client=cap_client, max_steps=999).run_turn("Run tools")
    assert capped["status"] == "max_steps_reached"
    assert capped["tool_steps_count"] == HARD_MAX_STEPS

    print("[12] Trace cache")
    cache = ROOT / "data" / "cache" / "smoke_trace.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        export_trace_json(
            "Agnes AI",
            "agnes-3.0-flash",
            str(WORKSPACE_DIR),
            result["messages"],
            result["steps"],
            result["total_latency"],
        ),
        encoding="utf-8",
    )
    assert cache.exists() and '"calc"' in cache.read_text(encoding="utf-8")

    print("[13] Forbidden execution APIs")
    for source_path in [ROOT / "app.py", *sorted((ROOT / "src").rglob("*.py"))]:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        assert not any(
            isinstance(node, (ast.Import, ast.ImportFrom))
            and any(alias.name == "subprocess" for alias in node.names)
            for node in ast.walk(tree)
        )
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"eval", "exec"}
            for node in ast.walk(tree)
        )

    print("[14] Streamlit headless render")
    app = AppTest.from_file("app.py", default_timeout=10).run()
    assert not app.exception
    assert app.number_input(key="max_steps").max == HARD_MAX_STEPS
    for name in names:
        assert app.checkbox(key=f"tool_{name}").value is True
    assert any(
        caption.value.startswith("AGNESAI_API_KEY set:")
        for caption in app.caption
    )

    print("ALL OFFLINE SMOKE CHECKS PASSED.")


if __name__ == "__main__":
    run_smoke()
