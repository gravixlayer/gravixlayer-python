from google.protobuf import json_format
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
