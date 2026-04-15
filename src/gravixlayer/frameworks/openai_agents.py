"""OpenAI Agents SDK framework adapter.

Wraps an OpenAI Agent and exposes it via standard routes.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from .base import BaseFrameworkAdapter

logger = logging.getLogger("gravixlayer.frameworks.openai_agents")


class OpenAIAgentsAdapter(BaseFrameworkAdapter):
    """Adapter for OpenAI Agents SDK."""

    @property
    def name(self) -> str:
        return "openai_agents"

    async def handle_invoke(self, input_data: Any, config: Any) -> Any:
        from agents import Runner

        agent = self._app
        user_input = input_data if isinstance(input_data, str) else str(input_data)
        result = await Runner.run(agent, input=user_input)
        return result.final_output

    async def handle_stream(
        self, input_data: Any, config: Any
    ) -> AsyncIterator[Any]:
        from agents import Runner

        agent = self._app
        user_input = input_data if isinstance(input_data, str) else str(input_data)
        result = Runner.run_streamed(agent, input=user_input)
        async for event in result.stream_events():
            yield {"event": str(event)}

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
