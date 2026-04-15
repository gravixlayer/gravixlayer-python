"""CrewAI framework adapter.

Wraps a CrewAI Crew object and exposes it via standard routes.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .base import BaseFrameworkAdapter

logger = logging.getLogger("gravixlayer.frameworks.crewai")


class CrewAIAdapter(BaseFrameworkAdapter):
    """Adapter for CrewAI Crew objects."""

    @property
    def name(self) -> str:
        return "crewai"

    async def handle_invoke(self, input_data: Any, config: Any) -> Any:
        crew = self._app
        # CrewAI kickoff() is synchronous — run in executor
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: crew.kickoff(inputs=input_data if isinstance(input_data, dict) else {"input": input_data})
        )
        # CrewOutput has .raw, .json_dict, .pydantic attributes
        if hasattr(result, "json_dict") and result.json_dict:
            return result.json_dict
        if hasattr(result, "raw"):
            return result.raw
        return str(result)

    def get_routes(self) -> list:
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        async def tasks_endpoint(request: Request) -> JSONResponse:
            crew = self._app
            tasks = []
            if hasattr(crew, "tasks"):
                for t in crew.tasks:
                    tasks.append({
                        "description": getattr(t, "description", ""),
                        "agent": getattr(t.agent, "role", "") if hasattr(t, "agent") and t.agent else "",
                    })
            return JSONResponse({"tasks": tasks})

        async def agents_endpoint(request: Request) -> JSONResponse:
            crew = self._app
            agents = []
            if hasattr(crew, "agents"):
                for a in crew.agents:
                    agents.append({
                        "role": getattr(a, "role", ""),
                        "goal": getattr(a, "goal", ""),
                    })
            return JSONResponse({"agents": agents})

        return [
            Route("/tasks", tasks_endpoint, methods=["GET"]),
            Route("/agents", agents_endpoint, methods=["GET"]),
        ]
