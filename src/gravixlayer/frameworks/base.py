"""Abstract base class for framework adapters."""

from __future__ import annotations

import abc
from typing import Any, AsyncIterator


class FrameworkAdapter(abc.ABC):
    """Interface that all framework adapters implement."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Framework name (e.g. 'langgraph')."""

    @abc.abstractmethod
    async def setup(self) -> None:
        """Called on app startup."""

    @abc.abstractmethod
    async def cleanup(self) -> None:
        """Called on app shutdown."""

    @abc.abstractmethod
    def get_routes(self) -> list:
        """Return additional Starlette Route objects."""

    @abc.abstractmethod
    async def handle_invoke(self, input_data: Any, config: Any) -> Any:
        """Handle a POST /invoke request."""

    async def handle_stream(
        self, input_data: Any, config: Any
    ) -> AsyncIterator[Any]:
        """Handle streaming — default falls back to invoke."""
        result = await self.handle_invoke(input_data, config)
        yield result

    def get_health_info(self) -> dict[str, Any]:
        """Return framework-specific health info."""
        return {"framework": self.name}


class BaseFrameworkAdapter(FrameworkAdapter):
    """Convenient base with defaults for setup/cleanup/routes."""

    def __init__(self, framework_app: Any, **kwargs: Any) -> None:
        self._app = framework_app
        self._kwargs = kwargs

    async def setup(self) -> None:
        pass

    async def cleanup(self) -> None:
        pass

    def get_routes(self) -> list:
        return []
