"""Google ADK framework adapter.

Wraps a Google ADK agent and exposes it via standard routes.
"""

from __future__ import annotations

import inspect
import json
import logging
from typing import Any, AsyncIterator

from .base import BaseFrameworkAdapter

logger = logging.getLogger("gravixlayer.frameworks.google_adk")


class GoogleADKAdapter(BaseFrameworkAdapter):
    """Adapter for Google Agent Development Kit (ADK)."""

    def __init__(self, framework_app: Any, **kwargs: Any) -> None:
        super().__init__(framework_app, **kwargs)
        self._runner = None
        self._session_service = None
        self._app_name = None

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
        from google.genai.types import Content, Part  # type: ignore[import-not-found]

        user_input = _extract_prompt(input_data)
        user_id = _config_value(config, "user_id", "gravix-user")
        session = await self._session_service.create_session(
            app_name=self._app_name or "adk-agent",
            user_id=user_id,
        )

        content = Content(parts=[_text_part(Part, user_input)], role="user")
        result_parts = []
        async for event in self._runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        result_parts.append(part.text)

        return "".join(result_parts)

    async def handle_stream(self, input_data: Any, config: Any) -> AsyncIterator[Any]:
        from google.genai.types import Content, Part  # type: ignore[import-not-found]

        user_input = _extract_prompt(input_data)
        user_id = _config_value(config, "user_id", "gravix-user")
        session = await self._session_service.create_session(
            app_name=self._app_name or "adk-agent",
            user_id=user_id,
        )

        content = Content(parts=[_text_part(Part, user_input)], role="user")
        async for event in self._runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        yield {"text": part.text}

    def get_routes(self) -> list:
        from starlette.requests import Request
        from starlette.responses import StreamingResponse
        from starlette.routing import Route

        async def stream_endpoint(request: Request) -> StreamingResponse:
            body = await request.json()
            input_data = body.get("input", body)
            config_data = body.get("config", {})

            async def event_stream():
                async for event in self.handle_stream(input_data, config_data):
                    yield f"data: {json.dumps(event, default=str)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(event_stream(), media_type="text/event-stream")

        return [Route("/stream", stream_endpoint, methods=["POST"])]


def _extract_prompt(input_data: Any) -> str:
    if isinstance(input_data, str):
        return input_data
    if isinstance(input_data, dict):
        for key in ("message", "prompt", "text"):
            value = input_data.get(key)
            if isinstance(value, str):
                return value
        messages = input_data.get("messages")
        if isinstance(messages, list) and messages:
            last_message = messages[-1]
            if isinstance(last_message, dict) and isinstance(last_message.get("content"), str):
                return last_message["content"]
            if hasattr(last_message, "content") and isinstance(last_message.content, str):
                return last_message.content
    return str(input_data)


def _config_value(config: Any, key: str, default: str) -> str:
    if isinstance(config, dict) and isinstance(config.get(key), str):
        return config[key]
    return default


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
