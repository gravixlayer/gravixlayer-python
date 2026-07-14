from google.protobuf import json_format
import json
import pytest

pytest.importorskip("a2a")
pytest.importorskip("starlette")

from starlette.testclient import TestClient

from a2a.helpers.proto_helpers import new_text_message
from a2a.types.a2a_pb2 import Role, SendMessageConfiguration, SendMessageRequest

from gravixlayer.a2a import create_a2a_app, create_gravix_app_executor
from gravixlayer.runtime import GravixApp


def _agent_card() -> dict:
    return {
        "name": "Demo",
        "description": "Demo agent",
        "skills": [{"id": "default", "name": "Demo", "description": "Demo"}],
    }


class _State:
    values = {}
    next = ()
    tasks = ()


class _InterruptGraph:
    async def ainvoke(self, input_data, config=None, version=None):
        self.input_data = input_data
        self.config = config
        return {"__interrupt__": [{"value": "Approve send_email?"}]}

    def get_state(self, config):
        return _State()


class _ResumeGraph:
    def __init__(self) -> None:
        self.calls = 0

    async def ainvoke(self, input_data, config=None, version=None):
        self.calls += 1
        self.input_data = input_data
        self.config = config
        # First call interrupts; resume Command path completes.
        if hasattr(input_data, "resume"):
            return {"messages": [{"type": "ai", "content": "email sent"}]}
        return {"__interrupt__": [{"value": "Approve send_email?"}]}

    def get_state(self, config):
        return _State()


def test_platform_a2a_card_uses_public_rpc_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRAVIXLAYER_AGENT_ID", "demo-agent")
    app = GravixApp(name="demo")

    @app.entrypoint
    async def handle(payload: dict) -> str:
        return "ok"

    client = TestClient(create_a2a_app(create_gravix_app_executor(app), _agent_card()))

    response = client.get("/.well-known/agent-card.json")

    assert response.status_code == 200
    card = response.json()
    assert "url" not in card
    assert "protocolVersion" not in card
    assert card["supportedInterfaces"][0]["url"] == "https://demo-agent.agents.gravixlayer.ai/a2a"
    assert card["supportedInterfaces"][0]["protocolBinding"] == "JSONRPC"
    assert card["supportedInterfaces"][0]["protocolVersion"] == "1.0"


def test_platform_a2a_executor_delegates_to_gravix_app() -> None:
    app = GravixApp(name="demo")

    @app.entrypoint
    async def handle(payload: dict) -> dict:
        return {"echo": payload}

    client = TestClient(create_a2a_app(create_gravix_app_executor(app), _agent_card()))
    message = new_text_message("hello", context_id="ctx-1", role=Role.ROLE_USER)
    request = SendMessageRequest(message=message, configuration=SendMessageConfiguration())
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "SendMessage",
        "params": json_format.MessageToDict(request),
    }

    response = client.post("/a2a", json=payload, headers={"A2A-Version": "1.0"})

    assert response.status_code == 200
    body = response.json()
    assert "error" not in body
    task = body["result"]["task"]
    assert task["contextId"] == "ctx-1"
    assert task["status"]["state"] == "TASK_STATE_COMPLETED"
    assert "hello" in task["status"]["message"]["parts"][0]["text"]


def test_platform_a2a_langgraph_hitl_emits_input_required() -> None:
    """Single-agent HITL: interrupt → A2A TASK_STATE_INPUT_REQUIRED (prod path)."""
    app = GravixApp(name="hitl-demo", framework="langgraph")
    app.mount_framework("langgraph", _InterruptGraph())

    client = TestClient(create_a2a_app(create_gravix_app_executor(app), _agent_card()))
    message = new_text_message("send the email", context_id="ctx-hitl", role=Role.ROLE_USER)
    request = SendMessageRequest(message=message, configuration=SendMessageConfiguration())
    payload = {
        "jsonrpc": "2.0",
        "id": "hitl-1",
        "method": "SendMessage",
        "params": json_format.MessageToDict(request),
    }

    response = client.post("/a2a", json=payload, headers={"A2A-Version": "1.0"})

    assert response.status_code == 200
    body = response.json()
    assert "error" not in body, body
    task = body["result"]["task"]
    assert task["contextId"] == "ctx-hitl"
    assert task["status"]["state"] == "TASK_STATE_INPUT_REQUIRED"
    assert "Approve send_email?" in task["status"]["message"]["parts"][0]["text"]


@pytest.mark.asyncio
async def test_platform_http_langgraph_hitl_interrupt_and_resume() -> None:
    """Single-agent HITL over HTTP /invoke — same stack used by local autoserve + deploy."""
    graph = _ResumeGraph()
    app = GravixApp(name="hitl-http", framework="langgraph")
    app.mount_framework("langgraph", graph)

    class _Request:
        def __init__(self, body):
            self._body = body

        async def json(self):
            return self._body

    interrupted = await app._invoke_endpoint(
        _Request({"input": {"message": "send the email"}, "session_id": "thread-http-1"})
    )
    body = json.loads(interrupted.body)
    assert body["status"] == "interrupted"
    assert body["thread_id"] == "thread-http-1"
    assert "Approve send_email?" in body["prompt"]

    completed = await app._invoke_endpoint(
        _Request(
            {
                "resume": {"decisions": [{"type": "approve"}]},
                "session_id": "thread-http-1",
            }
        )
    )
    done = json.loads(completed.body)
    assert done["status"] == "completed"
    assert done["thread_id"] == "thread-http-1"
    assert hasattr(graph.input_data, "resume")
