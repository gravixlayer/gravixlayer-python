"""Google ADK framework adapter.

Wraps a Google ADK agent and exposes it via standard routes.
"""

from __future__ import annotations

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

    @property
    def name(self) -> str:
        return "google_adk"

    async def setup(self) -> None:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService

        self._session_service = InMemorySessionService()
        self._runner = Runner(
            agent=self._app,
            app_name=getattr(self._app, "name", "adk-agent"),
            session_service=self._session_service,
        )

    async def handle_invoke(self, input_data: Any, config: Any) -> Any:
        from google.genai.types import Content, Part

        user_input = input_data if isinstance(input_data, str) else str(input_data)
        session = await self._session_service.create_session(
            app_name=getattr(self._app, "name", "adk-agent"),
            user_id="gravix-user",
        )

        content = Content(parts=[Part(text=user_input)], role="user")
        result_parts = []
        async for event in self._runner.run_async(
            user_id="gravix-user",
            session_id=session.id,
            new_message=content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        result_parts.append(part.text)

        return "".join(result_parts)

    async def handle_stream(
        self, input_data: Any, config: Any
    ) -> AsyncIterator[Any]:
        from google.genai.types import Content, Part

        user_input = input_data if isinstance(input_data, str) else str(input_data)
        session = await self._session_service.create_session(
            app_name=getattr(self._app, "name", "adk-agent"),
            user_id="gravix-user",
        )

        content = Content(parts=[Part(text=user_input)], role="user")
        async for event in self._runner.run_async(
            user_id="gravix-user",
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

            return StreamingResponse(
                event_stream(), media_type="text/event-stream"
            )

        return [Route("/stream", stream_endpoint, methods=["POST"])]
