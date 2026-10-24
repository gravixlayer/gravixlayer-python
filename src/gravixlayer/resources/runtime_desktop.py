"""
Desktop session plane — component lifecycle on desktop-template runtimes.

``client.runtime.desktop`` inspects and controls the components a desktop
image declares (the display server, the session, the window manager) and
reads their journal logs. On runtimes without a desktop image the calls
return not-found errors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from ..types.runtime import _validate_runtime_id

if TYPE_CHECKING:
    from .runtime import Runtimes
    from .async_runtime import AsyncRuntimes


def _logs_body(name: str, cursor: str, max_entries: int, priority: str) -> Dict[str, Any]:
    body: Dict[str, Any] = {"name": name}
    if cursor:
        body["cursor"] = cursor
    if max_entries:
        body["max"] = max_entries
    if priority:
        body["priority"] = priority
    return body


class RuntimeDesktopResource:
    """Desktop session operations under ``client.runtime.desktop``."""

    __slots__ = ("_rt",)

    def __init__(self, runtimes: "Runtimes"):
        self._rt = runtimes

    def _j(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None):
        return self._rt._make_agents_request(method, endpoint, data).json()

    def status(self, runtime_id: str) -> Dict[str, Any]:
        """Component states: ``{present, display, user, components: [...]}``."""
        _validate_runtime_id(runtime_id)
        return self._j("GET", f"runtime/{runtime_id}/desktop/status")

    def component(self, runtime_id: str, name: str, op: str) -> Dict[str, Any]:
        """``op``: ``"start"`` | ``"stop"`` | ``"restart"`` — returns the
        component's post-op state."""
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/desktop/component",
                       {"name": name, "op": op})

    def start(self, runtime_id: str, name: str) -> Dict[str, Any]:
        return self.component(runtime_id, name, "start")

    def stop(self, runtime_id: str, name: str) -> Dict[str, Any]:
        return self.component(runtime_id, name, "stop")

    def restart(self, runtime_id: str, name: str) -> Dict[str, Any]:
        return self.component(runtime_id, name, "restart")

    def logs(self, runtime_id: str, name: str, cursor: str = "",
             max_entries: int = 0, priority: str = "") -> Dict[str, Any]:
        """Journal page for a component — pass the returned ``cursor`` back
        for the next page. ``priority="err"`` filters to errors."""
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/desktop/logs",
                       _logs_body(name, cursor, max_entries, priority))


class AsyncRuntimeDesktopResource:
    """Async desktop session operations under ``client.runtime.desktop``."""

    __slots__ = ("_rt",)

    def __init__(self, runtimes: "AsyncRuntimes"):
        self._rt = runtimes

    async def _j(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None):
        r = await self._rt._make_agents_request(method, endpoint, data)
        return r.json()

    async def status(self, runtime_id: str) -> Dict[str, Any]:
        """Component states: ``{present, display, user, components: [...]}``."""
        _validate_runtime_id(runtime_id)
        return await self._j("GET", f"runtime/{runtime_id}/desktop/status")

    async def component(self, runtime_id: str, name: str, op: str) -> Dict[str, Any]:
        """``op``: ``"start"`` | ``"stop"`` | ``"restart"``."""
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/desktop/component",
                             {"name": name, "op": op})

    async def start(self, runtime_id: str, name: str) -> Dict[str, Any]:
        return await self.component(runtime_id, name, "start")

    async def stop(self, runtime_id: str, name: str) -> Dict[str, Any]:
        return await self.component(runtime_id, name, "stop")

    async def restart(self, runtime_id: str, name: str) -> Dict[str, Any]:
        return await self.component(runtime_id, name, "restart")

    async def logs(self, runtime_id: str, name: str, cursor: str = "",
                   max_entries: int = 0, priority: str = "") -> Dict[str, Any]:
        """Journal page for a component — pass the returned ``cursor`` back
        for the next page."""
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/desktop/logs",
                             _logs_body(name, cursor, max_entries, priority))
