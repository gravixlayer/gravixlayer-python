"""Google ADK framework adapter.

Wraps a Google ADK agent and exposes it via:

* GravixLayer canonical routes (``/invoke``, ``/stream``) used by the
  platform's framework-agnostic invoke pipeline.
* The ADK REST contract (``/list-apps``, sessions CRUD,
  ``/run``, ``/run_sse``) so existing clients written against
  ``adk api_server`` work against a deployed agent unchanged.

This is what makes any ``adk-samples`` project deploy out of the box.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from typing import Any, AsyncIterator

from .base import BaseFrameworkAdapter

logger = logging.getLogger("gravixlayer.frameworks.google_adk")

_DEFAULT_USER_ID = "gravix-user"


class GoogleADKAdapter(BaseFrameworkAdapter):
    """Adapter for Google Agent Development Kit (ADK)."""

    def __init__(self, framework_app: Any, **kwargs: Any) -> None:
        super().__init__(framework_app, **kwargs)
        self._runner = None
        self._session_service = None
        self._app_name = None
        self._session_locks: dict[tuple[str, str, str], asyncio.Lock] = {}

    @property
    def name(self) -> str:
        return "google_adk"

    async def setup(self) -> None:
        from google.adk.runners import Runner  # type: ignore[import-not-found]

        try:
            from google.adk.sessions import InMemorySessionService  # type: ignore[import-not-found]
        except ImportError:
            from google.adk.sessions.in_memory_session_service import (  # type: ignore[import-not-found]
                InMemorySessionService,
            )

        self._session_service = InMemorySessionService()
        service_kwargs = _build_runner_service_kwargs()
        root_agent = getattr(self._app, "root_agent", None)
        self._app_name = (
            self._kwargs.get("app_name")
            or getattr(self._app, "name", None)
            or getattr(root_agent, "name", None)
            or "adk-agent"
        )
        runner_params = inspect.signature(Runner).parameters
        if root_agent is not None and "app" in runner_params:
            self._runner = Runner(
                app=self._app,
                app_name=self._app_name,
                session_service=self._session_service,
                **service_kwargs,
            )
        else:
            self._runner = Runner(
                agent=root_agent or self._app,
                app_name=self._app_name,
                session_service=self._session_service,
                **service_kwargs,
            )

    async def handle_invoke(self, input_data: Any, config: Any) -> Any:
        user_input = _extract_prompt(input_data)
        user_id = _config_value(config, "user_id", _DEFAULT_USER_ID)
        session_id = _config_value(config, "session_id", "")
        session = await self._get_or_create_session(user_id, session_id or None)

        text_parts: list[str] = []
        async for event in self._run_agent(user_id, session.id, user_input):
            text_parts.extend(_iter_text_parts(event))
        return "".join(text_parts)

    async def handle_stream(self, input_data: Any, config: Any) -> AsyncIterator[Any]:
        user_input = _extract_prompt(input_data)
        user_id = _config_value(config, "user_id", _DEFAULT_USER_ID)
        session_id = _config_value(config, "session_id", "")
        session = await self._get_or_create_session(user_id, session_id or None)

        async for event in self._run_agent(user_id, session.id, user_input):
            for part_text in _iter_text_parts(event):
                yield {"text": part_text}

    def get_routes(self) -> list:
        from starlette.requests import Request
        from starlette.responses import JSONResponse, Response, StreamingResponse
        from starlette.routing import Route

        async def stream_endpoint(request: Request) -> StreamingResponse:
            body = await request.json()
            input_data = body.get("input", body)
            config_data = body.get("config", {})

            async def event_stream() -> AsyncIterator[bytes]:
                async for event in self.handle_stream(input_data, config_data):
                    yield f"data: {json.dumps(event, default=str)}\n\n".encode("utf-8")
                yield b"data: [DONE]\n\n"

            return StreamingResponse(event_stream(), media_type="text/event-stream")

        async def list_apps(_: Request) -> JSONResponse:
            return JSONResponse([self._app_name or "adk-agent"])

        async def create_session(request: Request) -> JSONResponse:
            self._guard_app_path(request)
            user_id = request.path_params["user_id"]
            session_id = request.path_params["session_id"]
            body = await _request_json_or_empty(request)
            state = body.get("state") if isinstance(body.get("state"), dict) else body
            session = await self._create_session(
                user_id,
                session_id,
                state=state if isinstance(state, dict) else {},
                fail_if_exists=True,
            )
            if session is None:
                return JSONResponse({"detail": f"Session already exists: {session_id}"}, status_code=409)
            await self._append_initial_events(session, body.get("events") if isinstance(body, dict) else None)
            return JSONResponse(_session_to_dict(session))

        async def create_session_without_id(request: Request) -> JSONResponse:
            self._guard_app_path(request)
            user_id = request.path_params["user_id"]
            body = await _request_json_or_empty(request)
            session_id = None
            state = {}
            events = None
            if isinstance(body, dict):
                session_id = body.get("sessionId") or body.get("session_id")
                state = body.get("state") if isinstance(body.get("state"), dict) else {}
                events = body.get("events")
            if session_id:
                session = await self._create_session(
                    user_id,
                    str(session_id),
                    state=state,
                    fail_if_exists=True,
                )
                if session is None:
                    return JSONResponse({"detail": f"Session already exists: {session_id}"}, status_code=409)
            else:
                session = await self._session_service.create_session(  # type: ignore[union-attr]
                    app_name=self._app_name or "adk-agent",
                    user_id=user_id,
                    state=state,
                )
            await self._append_initial_events(session, events)
            return JSONResponse(_session_to_dict(session))

        async def list_sessions(request: Request) -> JSONResponse:
            self._guard_app_path(request)
            sessions = await self._list_sessions(request.path_params["user_id"])
            return JSONResponse([_session_to_dict(session) for session in sessions])

        async def get_session(request: Request) -> Response:
            self._guard_app_path(request)
            session = await self._safe_get_session(
                request.path_params["user_id"], request.path_params["session_id"]
            )
            if session is None:
                return JSONResponse({"detail": "Session not found"}, status_code=404)
            return JSONResponse(_session_to_dict(session))

        async def delete_session(request: Request) -> Response:
            self._guard_app_path(request)
            try:
                await self._session_service.delete_session(  # type: ignore[union-attr]
                    app_name=self._app_name or "adk-agent",
                    user_id=request.path_params["user_id"],
                    session_id=request.path_params["session_id"],
                )
            except Exception:  # noqa: BLE001
                pass
            return Response(status_code=204)

        async def run_endpoint(request: Request) -> JSONResponse:
            payload = await request.json()
            self._guard_app_body(payload)
            run_request = _parse_run_request(payload)
            user_id = run_request["user_id"]
            session_id = run_request["session_id"]
            session = await self._get_or_create_session(user_id, session_id)
            events = [
                _event_to_dict(event)
                async for event in self._run_agent(
                    user_id,
                    session.id,
                    content=run_request["content"],
                    state_delta=run_request["state_delta"],
                    invocation_id=run_request["invocation_id"],
                )
            ]
            return JSONResponse(events)

        async def run_sse_endpoint(request: Request) -> StreamingResponse:
            payload = await request.json()
            self._guard_app_body(payload)
            run_request = _parse_run_request(payload)
            user_id = run_request["user_id"]
            session_id = run_request["session_id"]
            session = await self._get_or_create_session(user_id, session_id)

            async def event_stream() -> AsyncIterator[bytes]:
                async for event in self._run_agent(
                    user_id,
                    session.id,
                    content=run_request["content"],
                    state_delta=run_request["state_delta"],
                    invocation_id=run_request["invocation_id"],
                ):
                    payload_json = json.dumps(_event_to_dict(event), default=str)
                    yield f"data: {payload_json}\n\n".encode("utf-8")

            return StreamingResponse(event_stream(), media_type="text/event-stream")

        session_path = "/apps/{app_name}/users/{user_id}/sessions/{session_id}"
        sessions_path = "/apps/{app_name}/users/{user_id}/sessions"
        return [
            Route("/stream", stream_endpoint, methods=["POST"]),
            Route("/list-apps", list_apps, methods=["GET"]),
            Route(sessions_path, create_session_without_id, methods=["POST"]),
            Route(sessions_path, list_sessions, methods=["GET"]),
            Route(session_path, create_session, methods=["POST"]),
            Route(session_path, get_session, methods=["GET"]),
            Route(session_path, delete_session, methods=["DELETE"]),
            Route("/run", run_endpoint, methods=["POST"]),
            Route("/run_sse", run_sse_endpoint, methods=["POST"]),
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _guard_app_path(self, request: Any) -> None:
        requested = request.path_params.get("app_name")
        self._raise_if_unknown_app(requested)

    def _guard_app_body(self, payload: dict[str, Any]) -> None:
        requested = payload.get("appName") or payload.get("app_name")
        self._raise_if_unknown_app(requested)

    def _raise_if_unknown_app(self, requested: str | None) -> None:
        if requested and self._app_name and requested != self._app_name:
            from starlette.exceptions import HTTPException

            raise HTTPException(
                status_code=404,
                detail=f"App '{requested}' not found. Available: {self._app_name}",
            )

    async def _safe_get_session(self, user_id: str, session_id: str) -> Any | None:
        try:
            return await self._session_service.get_session(  # type: ignore[union-attr]
                app_name=self._app_name or "adk-agent",
                user_id=user_id,
                session_id=session_id,
            )
        except Exception:  # noqa: BLE001
            return None

    async def _get_or_create_session(self, user_id: str, session_id: str | None) -> Any:
        if session_id:
            session = await self._create_session(user_id, session_id, fail_if_exists=False)
            if session is not None:
                return session
        return await self._session_service.create_session(  # type: ignore[union-attr]
            app_name=self._app_name or "adk-agent",
            user_id=user_id,
        )

    async def _list_sessions(self, user_id: str) -> list[Any]:
        response = await self._session_service.list_sessions(  # type: ignore[union-attr]
            app_name=self._app_name or "adk-agent",
            user_id=user_id,
        )
        sessions = getattr(response, "sessions", response)
        return list(sessions or [])

    async def _append_initial_events(self, session: Any, events: Any) -> None:
        if not events or not hasattr(self._session_service, "append_event"):
            return
        for event in events:
            await self._session_service.append_event(session=session, event=event)  # type: ignore[union-attr]

    async def _create_session(
        self,
        user_id: str,
        session_id: str,
        *,
        state: dict[str, Any] | None = None,
        fail_if_exists: bool = False,
    ) -> Any | None:
        app_name = self._app_name or "adk-agent"
        async with self._session_lock(app_name, user_id, session_id):
            existing = await self._safe_get_session(user_id, session_id)
            if existing is not None:
                return None if fail_if_exists else existing
            try:
                return await self._session_service.create_session(  # type: ignore[union-attr]
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    state=state or {},
                )
            except Exception:
                existing = await self._safe_get_session(user_id, session_id)
                if existing is not None and not fail_if_exists:
                    return existing
                raise

    def _session_lock(self, app_name: str, user_id: str, session_id: str) -> asyncio.Lock:
        key = (app_name, user_id, session_id)
        lock = self._session_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._session_locks[key] = lock
        return lock

    async def _run_agent(
        self,
        user_id: str,
        session_id: str,
        user_input: str | None = None,
        *,
        content: Any | None = None,
        state_delta: dict[str, Any] | None = None,
        invocation_id: str | None = None,
    ) -> AsyncIterator[Any]:
        from google.genai.types import Content, Part  # type: ignore[import-not-found]

        native_content = content or Content(parts=[_text_part(Part, user_input or "")], role="user")
        kwargs: dict[str, Any] = {
            "user_id": user_id,
            "session_id": session_id,
            "new_message": native_content,
        }
        if state_delta is not None:
            kwargs["state_delta"] = state_delta
        if invocation_id is not None:
            kwargs["invocation_id"] = invocation_id
        async for event in _call_runner_async(self._runner, kwargs):  # type: ignore[arg-type]
            yield event


def _extract_prompt(input_data: Any) -> str:
    if isinstance(input_data, str):
        return input_data
    if isinstance(input_data, dict):
        for key in ("message", "prompt", "text"):
            value = input_data.get(key)
            if isinstance(value, str):
                return value
        new_message = input_data.get("newMessage") or input_data.get("new_message")
        if isinstance(new_message, dict):
            return _extract_prompt_from_message(new_message)
        messages = input_data.get("messages")
        if isinstance(messages, list) and messages:
            last_message = messages[-1]
            if isinstance(last_message, dict) and isinstance(last_message.get("content"), str):
                return last_message["content"]
            if hasattr(last_message, "content") and isinstance(last_message.content, str):
                return last_message.content
    return str(input_data)


def _extract_prompt_from_message(message: Any) -> str:
    if not isinstance(message, dict):
        return str(message)
    parts = message.get("parts") or []
    if isinstance(parts, list):
        texts = [
            part.get("text")
            for part in parts
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ]
        if texts:
            return "".join(texts)
    text = message.get("text")
    return text if isinstance(text, str) else ""


def _parse_run_payload(payload: dict[str, Any]) -> tuple[str, str | None, str]:
    user_id = payload.get("userId") or payload.get("user_id") or _DEFAULT_USER_ID
    session_id = payload.get("sessionId") or payload.get("session_id")
    new_message = payload.get("newMessage") or payload.get("new_message") or {}
    return user_id, session_id, _extract_prompt_from_message(new_message)


def _parse_run_request(payload: dict[str, Any]) -> dict[str, Any]:
    user_id, session_id, _ = _parse_run_payload(payload)
    new_message = payload.get("newMessage") or payload.get("new_message") or {}
    return {
        "user_id": user_id,
        "session_id": session_id,
        "content": _content_from_message(new_message),
        "state_delta": payload.get("stateDelta") or payload.get("state_delta"),
        "invocation_id": payload.get("invocationId") or payload.get("invocation_id"),
    }


def _content_from_message(message: Any) -> Any:
    from google.genai.types import Content, Part  # type: ignore[import-not-found]

    if isinstance(message, Content):
        return message
    if isinstance(message, dict):
        for validator in (getattr(Content, "model_validate", None), getattr(Content, "parse_obj", None)):
            if callable(validator):
                try:
                    return validator(message)
                except Exception:  # noqa: BLE001
                    pass
        role = message.get("role") or "user"
        parts = [_part_from_payload(Part, part) for part in (message.get("parts") or [])]
        if not parts:
            prompt = _extract_prompt_from_message(message)
            if prompt:
                parts = [_text_part(Part, prompt)]
        return Content(parts=parts, role=role)
    return Content(parts=[_text_part(Part, str(message))], role="user")


def _part_from_payload(part_cls: Any, payload: Any) -> Any:
    if isinstance(payload, part_cls):
        return payload
    if isinstance(payload, dict):
        for validator in (getattr(part_cls, "model_validate", None), getattr(part_cls, "parse_obj", None)):
            if callable(validator):
                try:
                    return validator(payload)
                except Exception:  # noqa: BLE001
                    pass
        text = payload.get("text")
        if isinstance(text, str):
            return _text_part(part_cls, text)
        try:
            return part_cls(**payload)
        except Exception:  # noqa: BLE001
            return _text_part(part_cls, str(payload))
    return _text_part(part_cls, str(payload))


async def _call_runner_async(runner: Any, kwargs: dict[str, Any]) -> AsyncIterator[Any]:
    run_async = runner.run_async
    signature = inspect.signature(run_async)
    accepts_kwargs = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values())
    supported_kwargs = {
        key: value
        for key, value in kwargs.items()
        if accepts_kwargs or key in signature.parameters
    }
    async for event in run_async(**supported_kwargs):
        yield event


async def _request_json_or_empty(request: Any) -> Any:
    try:
        body = await request.body()
    except Exception:  # noqa: BLE001
        body = b""
    if not body:
        return {}
    try:
        return await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        return {}


def _config_value(config: Any, key: str, default: str) -> str:
    if isinstance(config, dict):
        for candidate in (key, _camel_case(key)):
            value = config.get(candidate)
            if isinstance(value, str):
                return value
    return default


def _camel_case(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


def _iter_text_parts(event: Any) -> list[str]:
    parts = getattr(getattr(event, "content", None), "parts", None) or []
    out: list[str] = []
    for part in parts:
        text = getattr(part, "text", None)
        if isinstance(text, str) and text:
            out.append(text)
    return out


def _session_to_dict(session: Any) -> dict[str, Any]:
    return {
        "id": getattr(session, "id", None),
        "appName": getattr(session, "app_name", None),
        "userId": getattr(session, "user_id", None),
        "state": getattr(session, "state", {}) or {},
        "events": [_event_to_dict(event) for event in (getattr(session, "events", None) or [])],
        "lastUpdateTime": getattr(session, "last_update_time", None),
    }


def _event_to_dict(event: Any) -> dict[str, Any]:
    """Convert an ADK Event to the JSON shape produced by ``adk api_server``."""
    to_dict = getattr(event, "model_dump", None) or getattr(event, "dict", None)
    if callable(to_dict):
        try:
            return to_dict(by_alias=True, exclude_none=True)  # type: ignore[call-arg]
        except TypeError:
            try:
                return to_dict()
            except Exception:  # noqa: BLE001
                pass
    return {
        "id": getattr(event, "id", None),
        "author": getattr(event, "author", None),
        "invocationId": getattr(event, "invocation_id", None),
        "content": _content_to_dict(getattr(event, "content", None)),
        "timestamp": getattr(event, "timestamp", None),
    }


def _content_to_dict(content: Any) -> dict[str, Any] | None:
    if content is None:
        return None
    parts_out: list[dict[str, Any]] = []
    for part in getattr(content, "parts", None) or []:
        text = getattr(part, "text", None)
        if isinstance(text, str):
            parts_out.append({"text": text})
    return {"role": getattr(content, "role", None), "parts": parts_out}


def _text_part(part_cls: Any, text: str) -> Any:
    from_text = getattr(part_cls, "from_text", None)
    if callable(from_text):
        return from_text(text=text)
    return part_cls(text=text)


def _build_runner_service_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    try:
        from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService  # type: ignore[import-not-found]

        kwargs["artifact_service"] = InMemoryArtifactService()
    except Exception:
        pass

    try:
        from google.adk.memory.in_memory_memory_service import InMemoryMemoryService  # type: ignore[import-not-found]

        kwargs["memory_service"] = InMemoryMemoryService()
    except Exception:
        pass

    try:
        from google.adk.auth.credential_service.in_memory_credential_service import (  # type: ignore[import-not-found]
            InMemoryCredentialService,
        )

        kwargs["credential_service"] = InMemoryCredentialService()
    except Exception:
        pass

    return kwargs
