"""Anthropic Claude Agent SDK adapter."""

from __future__ import annotations

import inspect
from typing import Any

from .base import BaseFrameworkAdapter


class AnthropicAdapter(BaseFrameworkAdapter):
    """Adapter for Claude Agent SDK query functions and options."""

    @property
    def name(self) -> str:
        return "anthropic"

    async def handle_invoke(self, input_data: Any, config: Any) -> Any:
        payload = input_data if isinstance(input_data, str) else str(input_data)
        target = self._app

        if callable(target):
            result = target(payload)
            if inspect.isawaitable(result):
                return await result
            return result

        from claude_agent_sdk import ClaudeAgentOptions, query

        options = target if isinstance(target, ClaudeAgentOptions) else ClaudeAgentOptions()
        chunks: list[str] = []
        async for event in query(prompt=payload, options=options):
            if hasattr(event, "result") and event.result:
                chunks.append(event.result)
            elif hasattr(event, "text") and event.text:
                chunks.append(event.text)
        return "".join(chunks)
