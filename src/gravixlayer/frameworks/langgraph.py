"""LangGraph framework adapter.

Wraps a compiled LangGraph StateGraph and exposes it via standard routes.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from .base import BaseFrameworkAdapter

logger = logging.getLogger("gravixlayer.frameworks.langgraph")


class LangGraphAdapter(BaseFrameworkAdapter):
    """Adapter for LangGraph compiled graphs."""

    @property
    def name(self) -> str:
        return "langgraph"

    async def handle_invoke(self, input_data: Any, config: Any) -> Any:
        graph = self._app
        result = await graph.ainvoke(input_data, config=config or None)
        return result

    async def handle_stream(
        self, input_data: Any, config: Any
    ) -> AsyncIterator[Any]:
        graph = self._app
        async for event in graph.astream(input_data, config=config or None):
            yield event

    def get_routes(self) -> list:
        from starlette.requests import Request
        from starlette.responses import JSONResponse, StreamingResponse
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
