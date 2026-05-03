"""Tests for native Google ADK support.

Covers the gaps that make adk-samples projects deploy out of the box:

* Auto-discovery of the ADK package directory (any folder with
  ``__init__.py`` containing ``agent.py`` exporting ``root_agent``).
* ``.env`` autoloading from the project root and the package directory.
* Propagation of the package directory name as the ADK ``app_name``.
* ADK-compatible REST endpoints (``/list-apps``, sessions CRUD, ``/run``,
  ``/run_sse``).
"""

from __future__ import annotations

import asyncio
import os
import sys
import types

import pytest

from gravixlayer.frameworks.google_adk import (
    GoogleADKAdapter,
    _event_to_dict,
    _extract_prompt,
    _extract_prompt_from_message,
    _parse_run_payload,
    _session_to_dict,
)
from gravixlayer.runtime.autoserve import (
    _autoload_env_files,
    _derive_adk_agent_card,
    _load_google_adk_with_meta,
)


# ---------------------------------------------------------------------------
# autoserve discovery + .env autoload
# ---------------------------------------------------------------------------


def test_load_google_adk_with_meta_returns_package_app_name(tmp_path):
    project = tmp_path / "software_bug_assistant_sample"
    package = project / "software_bug_assistant"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "agent.py").write_text(
        "root_agent = {'name': 'software-bug-assistant'}\n",
        encoding="utf-8",
    )

    obj, app_name = _load_google_adk_with_meta(project)
    assert obj == {"name": "software-bug-assistant"}
    assert app_name == "software_bug_assistant"


def test_load_google_adk_with_meta_handles_top_level_agent_module(tmp_path):
    project = tmp_path / "flat_adk_sample"
    project.mkdir()
    (project / "agent.py").write_text("root_agent = {'name': 'flat'}\n", encoding="utf-8")

    obj, app_name = _load_google_adk_with_meta(project)
    assert obj == {"name": "flat"}
    # Flat layout falls back to the project root directory name.
    assert app_name == "flat_adk_sample"


def test_autoload_env_files_loads_root_and_package_envs(tmp_path, monkeypatch):
    project = tmp_path / "adk_env_sample"
    package = project / "trip_planner"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "agent.py").write_text("root_agent = object()\n", encoding="utf-8")

    (project / ".env").write_text("ROOT_ONLY=root-value\n", encoding="utf-8")
    (package / ".env").write_text(
        'GOOGLE_API_KEY="abc-123"\nexport GOOGLE_GENAI_USE_VERTEXAI=FALSE\n# comment\n',
        encoding="utf-8",
    )

    for key in ("ROOT_ONLY", "GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI"):
        monkeypatch.delenv(key, raising=False)

    _autoload_env_files(project)

    assert os.environ.get("ROOT_ONLY") == "root-value"
    assert os.environ.get("GOOGLE_API_KEY") == "abc-123"
    assert os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") == "FALSE"


def test_autoload_env_files_does_not_override_existing_env(tmp_path, monkeypatch):
    package = tmp_path / "agent_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "agent.py").write_text("root_agent = object()\n", encoding="utf-8")
    (package / ".env").write_text("GOOGLE_API_KEY=from-file\n", encoding="utf-8")

    monkeypatch.setenv("GOOGLE_API_KEY", "from-environment")
    _autoload_env_files(tmp_path)

    assert os.environ.get("GOOGLE_API_KEY") == "from-environment"


def test_derive_adk_agent_card_uses_agent_tools():
    def get_current_time():
        """Return the current time."""
        return "now"

    agent = types.SimpleNamespace(
        name="time_agent",
        description="Answers time questions.",
        tools=[get_current_time],
    )

    card = _derive_adk_agent_card(agent, "time_agent")

    assert card["name"] == "time_agent"
    assert card["description"] == "Answers time questions."
    assert card["capabilities"]["streaming"] is True
    assert card["skills"] == [
        {
            "id": "get-current-time",
            "name": "Get Current Time",
            "description": "Return the current time.",
            "tags": ["google-adk", "tool"],
        }
    ]


def test_derive_adk_agent_card_falls_back_to_agent_skill():
    agent = types.SimpleNamespace(name="simple_agent", instruction="Answer clearly.")

    card = _derive_adk_agent_card(agent, "simple_agent")

    assert card["name"] == "simple_agent"
    assert card["description"] == "Answer clearly."
    assert card["skills"] == [
        {
            "id": "default",
            "name": "Agent",
            "description": "Answer clearly.",
            "tags": ["google-adk", "agent"],
        }
    ]


# ---------------------------------------------------------------------------
# Adapter input parsing
# ---------------------------------------------------------------------------


def test_extract_prompt_from_message_concatenates_text_parts():
    message = {"role": "user", "parts": [{"text": "hello "}, {"text": "world"}]}
    assert _extract_prompt_from_message(message) == "hello world"


def test_extract_prompt_handles_adk_run_payload_shape():
    payload = {
        "appName": "agent",
        "userId": "u",
        "sessionId": "s",
        "newMessage": {"role": "user", "parts": [{"text": "ping"}]},
    }
    assert _extract_prompt(payload) == "ping"


def test_parse_run_payload_camel_case():
    payload = {
        "appName": "agent",
        "userId": "user-1",
        "sessionId": "abc",
        "newMessage": {"role": "user", "parts": [{"text": "hi"}]},
    }
    user_id, session_id, prompt = _parse_run_payload(payload)
    assert (user_id, session_id, prompt) == ("user-1", "abc", "hi")


def test_parse_run_payload_falls_back_to_default_user():
    payload = {"newMessage": {"parts": [{"text": "hi"}]}}
    user_id, session_id, prompt = _parse_run_payload(payload)
    assert user_id == "gravix-user"
    assert session_id is None
    assert prompt == "hi"


# ---------------------------------------------------------------------------
# Event / session serialization
# ---------------------------------------------------------------------------


class _FakeContent:
    def __init__(self, role, texts):
        self.role = role
        self.parts = [types.SimpleNamespace(text=t) for t in texts]


class _FakeEvent:
    def __init__(self, eid, author, texts):
        self.id = eid
        self.author = author
        self.invocation_id = "inv-1"
        self.content = _FakeContent("model", texts)
        self.timestamp = 0.0


def test_event_to_dict_falls_back_when_no_pydantic_dump():
    event = _FakeEvent("e1", "agent", ["hello"])
    out = _event_to_dict(event)
    assert out["id"] == "e1"
    assert out["author"] == "agent"
    assert out["content"] == {"role": "model", "parts": [{"text": "hello"}]}


def test_session_to_dict_uses_camel_case():
    session = types.SimpleNamespace(
        id="sid",
        app_name="bugbot",
        user_id="uid",
        state={"k": "v"},
        events=[_FakeEvent("e1", "agent", ["x"])],
        last_update_time=1.0,
    )
    out = _session_to_dict(session)
    assert out["appName"] == "bugbot"
    assert out["userId"] == "uid"
    assert out["lastUpdateTime"] == 1.0
    assert out["events"][0]["id"] == "e1"


# ---------------------------------------------------------------------------
# Adapter REST routes — exercised against a fake Runner / SessionService
# ---------------------------------------------------------------------------


pytest.importorskip("starlette")


class _FakeSession:
    def __init__(self, app_name, user_id, session_id, state=None):
        self.id = session_id
        self.app_name = app_name
        self.user_id = user_id
        self.state = state or {}
        self.events: list = []
        self.last_update_time = 0.0


class _FakeSessionService:
    def __init__(self):
        self._sessions: dict[tuple[str, str, str], _FakeSession] = {}
        self._counter = 0

    async def create_session(self, *, app_name, user_id, session_id=None, state=None):
        if session_id is None:
            self._counter += 1
            session_id = f"auto-{self._counter}"
        key = (app_name, user_id, session_id)
        if key in self._sessions:
            raise ValueError(f"Session already exists: {session_id}")
        session = _FakeSession(app_name, user_id, session_id, state or {})
        self._sessions[key] = session
        return session

    async def get_session(self, *, app_name, user_id, session_id):
        return self._sessions.get((app_name, user_id, session_id))

    async def list_sessions(self, *, app_name, user_id):
        sessions = [
            session
            for (stored_app_name, stored_user_id, _), session in self._sessions.items()
            if stored_app_name == app_name and stored_user_id == user_id
        ]
        return types.SimpleNamespace(sessions=sessions)

    async def delete_session(self, *, app_name, user_id, session_id):
        self._sessions.pop((app_name, user_id, session_id), None)

    async def append_event(self, *, session, event):
        session.events.append(event)
        return event


class _FakeRunner:
    def __init__(self, replies):
        self._replies = list(replies)
        self.calls: list[dict] = []

    async def run_async(self, *, user_id, session_id, new_message, state_delta=None, invocation_id=None):
        self.calls.append(
            {
                "user_id": user_id,
                "session_id": session_id,
                "message": new_message,
                "state_delta": state_delta,
                "invocation_id": invocation_id,
            }
        )
        for idx, text in enumerate(self._replies):
            yield _FakeEvent(f"e{idx}", "agent", [text])


def _install_fake_genai_types(monkeypatch):
    """Provide a minimal ``google.genai.types`` so tests don't need google-genai."""

    google_pkg = sys.modules.get("google") or types.ModuleType("google")
    google_pkg.__path__ = getattr(google_pkg, "__path__", [])  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", google_pkg)

    genai_pkg = types.ModuleType("google.genai")
    genai_pkg.__path__ = []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google.genai", genai_pkg)

    types_mod = types.ModuleType("google.genai.types")

    class _Part:
        def __init__(self, *, text=None):
            self.text = text

        @classmethod
        def from_text(cls, *, text):
            return cls(text=text)

    class _Content:
        def __init__(self, *, parts, role):
            self.parts = list(parts)
            self.role = role

    types_mod.Part = _Part
    types_mod.Content = _Content
    monkeypatch.setitem(sys.modules, "google.genai.types", types_mod)


def _build_adapter(monkeypatch, replies=("hi",), app_name="bugbot"):
    _install_fake_genai_types(monkeypatch)
    adapter = GoogleADKAdapter(types.SimpleNamespace(name=app_name), app_name=app_name)
    adapter._session_service = _FakeSessionService()
    adapter._runner = _FakeRunner(replies)
    adapter._app_name = app_name
    return adapter


def _route_map(adapter):
    """Index routes by (path, method) — Starlette adds HEAD for GET routes."""
    out: dict[tuple[str, str], object] = {}
    for route in adapter.get_routes():
        for method in route.methods or []:
            if method == "HEAD":
                continue
            out[(route.path, method)] = route
    return out


def _run(coro):
    return asyncio.run(coro)


def test_handle_invoke_uses_persistent_session(monkeypatch):
    adapter = _build_adapter(monkeypatch, replies=["hello", " world"])
    config = {"user_id": "u1", "session_id": "s1"}

    first = _run(adapter.handle_invoke("hi", config))
    second = _run(adapter.handle_invoke("hi again", config))

    assert first == "hello world"
    assert second == "hello world"
    # Both calls used the same persisted session id.
    assert {call["session_id"] for call in adapter._runner.calls} == {"s1"}


def test_list_apps_route_returns_configured_app_name(monkeypatch):
    adapter = _build_adapter(monkeypatch)
    routes = _route_map(adapter)
    list_apps = routes[("/list-apps", "GET")].endpoint

    response = _run(list_apps(_FakeRequest()))

    import json as _json

    assert _json.loads(response.body) == ["bugbot"]


class _FakeRequest:
    def __init__(self, path_params=None, body=b"", json_payload=None):
        self.path_params = path_params or {}
        self._body = body
        self._json = json_payload

    async def body(self):
        return self._body

    async def json(self):
        if self._json is not None:
            return self._json
        if not self._body:
            raise ValueError("no body")
        import json as _json

        return _json.loads(self._body)


def test_create_and_get_session_round_trip(monkeypatch):
    adapter = _build_adapter(monkeypatch)
    routes = _route_map(adapter)
    create = routes[
        ("/apps/{app_name}/users/{user_id}/sessions/{session_id}", "POST")
    ].endpoint
    fetch = routes[
        ("/apps/{app_name}/users/{user_id}/sessions/{session_id}", "GET")
    ].endpoint

    path_params = {"app_name": "bugbot", "user_id": "u", "session_id": "s"}
    create_resp = _run(create(_FakeRequest(path_params=path_params, json_payload={"k": "v"}, body=b"{}")))

    import json as _json

    body = _json.loads(create_resp.body)
    assert body["id"] == "s"
    assert body["appName"] == "bugbot"
    assert body["state"] == {"k": "v"}

    get_resp = _run(fetch(_FakeRequest(path_params=path_params)))
    assert _json.loads(get_resp.body)["id"] == "s"


def test_create_session_rejects_duplicate(monkeypatch):
    adapter = _build_adapter(monkeypatch)
    routes = _route_map(adapter)
    create = routes[
        ("/apps/{app_name}/users/{user_id}/sessions/{session_id}", "POST")
    ].endpoint

    path_params = {"app_name": "bugbot", "user_id": "u", "session_id": "dup"}
    _run(create(_FakeRequest(path_params=path_params, body=b"{}")))
    second = _run(create(_FakeRequest(path_params=path_params, body=b"{}")))

    assert second.status_code == 409


def test_create_session_without_id_and_list_sessions(monkeypatch):
    adapter = _build_adapter(monkeypatch)
    routes = _route_map(adapter)
    create = routes[("/apps/{app_name}/users/{user_id}/sessions", "POST")].endpoint
    list_sessions = routes[("/apps/{app_name}/users/{user_id}/sessions", "GET")].endpoint

    path_params = {"app_name": "bugbot", "user_id": "u"}
    create_resp = _run(create(_FakeRequest(path_params=path_params, body=b"{}")))
    list_resp = _run(list_sessions(_FakeRequest(path_params=path_params)))

    import json as _json

    created = _json.loads(create_resp.body)
    listed = _json.loads(list_resp.body)
    assert created["id"] == "auto-1"
    assert [session["id"] for session in listed] == ["auto-1"]


def test_run_endpoint_camel_case_payload(monkeypatch):
    adapter = _build_adapter(monkeypatch, replies=["pong"])
    routes = _route_map(adapter)
    run = routes[("/run", "POST")].endpoint

    payload = {
        "appName": "bugbot",
        "userId": "u",
        "sessionId": "s-run",
        "newMessage": {"role": "user", "parts": [{"text": "ping"}]},
    }
    response = _run(run(_FakeRequest(json_payload=payload)))

    import json as _json

    events = _json.loads(response.body)
    assert events[0]["author"] == "agent"
    assert events[0]["content"]["parts"][0]["text"] == "pong"
    assert adapter._runner.calls[0]["session_id"] == "s-run"
    assert adapter._runner.calls[0]["message"].parts[0].text == "ping"


def test_run_endpoint_forwards_state_delta_and_invocation_id(monkeypatch):
    adapter = _build_adapter(monkeypatch, replies=["pong"])
    routes = _route_map(adapter)
    run = routes[("/run", "POST")].endpoint

    payload = {
        "appName": "bugbot",
        "userId": "u",
        "sessionId": "s-run",
        "stateDelta": {"ticket": "TG-1"},
        "invocationId": "inv-1",
        "newMessage": {"role": "user", "parts": [{"text": "ping"}]},
    }
    _run(run(_FakeRequest(json_payload=payload)))

    call = adapter._runner.calls[0]
    assert call["state_delta"] == {"ticket": "TG-1"}
    assert call["invocation_id"] == "inv-1"


def test_run_endpoint_rejects_unknown_app(monkeypatch):
    adapter = _build_adapter(monkeypatch)
    routes = _route_map(adapter)
    run = routes[("/run", "POST")].endpoint

    from starlette.exceptions import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        _run(
            run(
                _FakeRequest(
                    json_payload={
                        "appName": "wrong-name",
                        "userId": "u",
                        "newMessage": {"parts": [{"text": "hi"}]},
                    }
                )
            )
        )

    assert exc_info.value.status_code == 404
