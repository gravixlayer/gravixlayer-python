"""Strands Agents framework adapter."""

from __future__ import annotations

import inspect
from typing import Any

from .base import BaseFrameworkAdapter


class StrandsAdapter(BaseFrameworkAdapter):
    """Adapter for Strands Agent instances."""

    @property
    def name(self) -> str:
        return "strands"

    async def handle_invoke(self, input_data: Any, config: Any) -> Any:
        agent = self._app
        payload = input_data if isinstance(input_data, str) else str(input_data)

        if hasattr(agent, "invoke_async"):
            result = await agent.invoke_async(payload)
        elif callable(agent):
            result = agent(payload)
            if inspect.isawaitable(result):
                result = await result
        else:
            raise TypeError("Strands adapter requires a Strands Agent instance or callable")

        return _extract_output(result)



def _extract_output(result: Any) -> Any:
    if hasattr(result, "message"):
        return result.message
    if hasattr(result, "content"):
        return result.content
    return str(result)
