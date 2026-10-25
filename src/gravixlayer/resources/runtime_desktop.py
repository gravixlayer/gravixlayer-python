"""
Desktop — the runtime's computer-use surface.

``client.runtime.desktop`` is the single entry point for driving a runtime's
desktop: pixel input and screenshots, windows, apps, clipboard, live view,
agent ``act`` batches, and the session plane (component lifecycle and journal
logs) on desktop-template images. ``client.runtime.browser`` stays the
semantic plane for in-page element work.

Browser-coordinate clicks/types belong on ``client.runtime.browser`` (they
settle against the DOM); desktop input is raw pixel input for everything else.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..types.runtime import _validate_runtime_id
from .runtime_display import RuntimeDisplayResource, AsyncRuntimeDisplayResource


def _logs_body(name: str, cursor: str, max_entries: int, priority: str) -> Dict[str, Any]:
    body: Dict[str, Any] = {"name": name}
    if cursor:
        body["cursor"] = cursor
    if max_entries:
        body["max"] = max_entries
    if priority:
        body["priority"] = priority
    return body


class RuntimeDesktopResource(RuntimeDisplayResource):
    """All desktop operations under ``client.runtime.desktop``.

    Inherits the pixel plane from the display implementation and adds the
    session plane (components, logs) plus simple button/scroll conveniences.
    """

    __slots__ = ()

    # ── session plane (desktop-template component lifecycle) ──────────────

    def components(self, runtime_id: str) -> Dict[str, Any]:
        """Component states: ``{present, display, user, components: [...]}``."""
        _validate_runtime_id(runtime_id)
        return self._j("GET", f"runtime/{runtime_id}/desktop/status")

    def component(self, runtime_id: str, name: str, op: str) -> Dict[str, Any]:
        """``op``: ``"start"`` | ``"stop"`` | ``"restart"`` — returns the
        component's post-op state."""
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/desktop/component",
                       {"name": name, "op": op})

    def start_component(self, runtime_id: str, name: str) -> Dict[str, Any]:
        return self.component(runtime_id, name, "start")

    def stop_component(self, runtime_id: str, name: str) -> Dict[str, Any]:
        return self.component(runtime_id, name, "stop")

    def restart_component(self, runtime_id: str, name: str) -> Dict[str, Any]:
        return self.component(runtime_id, name, "restart")

    def logs(self, runtime_id: str, name: str, cursor: str = "",
             max_entries: int = 0, priority: str = "") -> Dict[str, Any]:
        """Journal page for a component — pass the returned ``cursor`` back
        for the next page. ``priority="err"`` filters to errors."""
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/desktop/logs",
                       _logs_body(name, cursor, max_entries, priority))

    # ── simple mouse/keyboard conveniences ────────────────────────────────

    def left_click(self, runtime_id: str, x: Optional[int] = None,
                   y: Optional[int] = None, **kw: Any) -> Dict[str, Any]:
        return self.click(runtime_id, x, y, "left", **kw)

    def double_click(self, runtime_id: str, x: Optional[int] = None,
                     y: Optional[int] = None, **kw: Any) -> Dict[str, Any]:
        return self.click(runtime_id, x, y, "left", click_count=2, **kw)

    def right_click(self, runtime_id: str, x: Optional[int] = None,
                    y: Optional[int] = None, **kw: Any) -> Dict[str, Any]:
        return self.click(runtime_id, x, y, "right", **kw)

    def middle_click(self, runtime_id: str, x: Optional[int] = None,
                     y: Optional[int] = None, **kw: Any) -> Dict[str, Any]:
        return self.click(runtime_id, x, y, "middle", **kw)

    def mouse_press(self, runtime_id: str, button: str = "left",
                    x: Optional[int] = None, y: Optional[int] = None,
                    **kw: Any) -> Dict[str, Any]:
        return self.down(runtime_id, x, y, button, **kw)

    def mouse_release(self, runtime_id: str, button: str = "left",
                      x: Optional[int] = None, y: Optional[int] = None,
                      **kw: Any) -> Dict[str, Any]:
        return self.up(runtime_id, button, x, y, **kw)

    def move_mouse(self, runtime_id: str, x: int, y: int,
                   **kw: Any) -> Dict[str, Any]:
        return self.move(runtime_id, x, y, **kw)

    def write(self, runtime_id: str, text: str, delay_ms: int = 0,
              mode: str = "") -> Dict[str, Any]:
        """Type text — same as ``type`` without shadowing the builtin."""
        return self.type(runtime_id, text, delay_ms, mode)


class AsyncRuntimeDesktopResource(AsyncRuntimeDisplayResource):
    """Async desktop operations under ``client.runtime.desktop``."""

    __slots__ = ()

    # ── session plane ─────────────────────────────────────────────────────

    async def components(self, runtime_id: str) -> Dict[str, Any]:
        """Component states: ``{present, display, user, components: [...]}``."""
        _validate_runtime_id(runtime_id)
        return await self._j("GET", f"runtime/{runtime_id}/desktop/status")

    async def component(self, runtime_id: str, name: str, op: str) -> Dict[str, Any]:
        """``op``: ``"start"`` | ``"stop"`` | ``"restart"``."""
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/desktop/component",
                             {"name": name, "op": op})

    async def start_component(self, runtime_id: str, name: str) -> Dict[str, Any]:
        return await self.component(runtime_id, name, "start")

    async def stop_component(self, runtime_id: str, name: str) -> Dict[str, Any]:
        return await self.component(runtime_id, name, "stop")

    async def restart_component(self, runtime_id: str, name: str) -> Dict[str, Any]:
        return await self.component(runtime_id, name, "restart")

    async def logs(self, runtime_id: str, name: str, cursor: str = "",
                   max_entries: int = 0, priority: str = "") -> Dict[str, Any]:
        """Journal page for a component — pass the returned ``cursor`` back
        for the next page."""
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/desktop/logs",
                             _logs_body(name, cursor, max_entries, priority))

    # ── simple mouse/keyboard conveniences ────────────────────────────────

    async def left_click(self, runtime_id: str, x: Optional[int] = None,
                         y: Optional[int] = None, **kw: Any) -> Dict[str, Any]:
        return await self.click(runtime_id, x, y, "left", **kw)

    async def double_click(self, runtime_id: str, x: Optional[int] = None,
                           y: Optional[int] = None, **kw: Any) -> Dict[str, Any]:
        return await self.click(runtime_id, x, y, "left", click_count=2, **kw)

    async def right_click(self, runtime_id: str, x: Optional[int] = None,
                          y: Optional[int] = None, **kw: Any) -> Dict[str, Any]:
        return await self.click(runtime_id, x, y, "right", **kw)

    async def middle_click(self, runtime_id: str, x: Optional[int] = None,
                           y: Optional[int] = None, **kw: Any) -> Dict[str, Any]:
        return await self.click(runtime_id, x, y, "middle", **kw)

    async def mouse_press(self, runtime_id: str, button: str = "left",
                          x: Optional[int] = None, y: Optional[int] = None,
                          **kw: Any) -> Dict[str, Any]:
        return await self.down(runtime_id, x, y, button, **kw)

    async def mouse_release(self, runtime_id: str, button: str = "left",
                            x: Optional[int] = None, y: Optional[int] = None,
                            **kw: Any) -> Dict[str, Any]:
        return await self.up(runtime_id, button, x, y, **kw)

    async def move_mouse(self, runtime_id: str, x: int, y: int,
                         **kw: Any) -> Dict[str, Any]:
        return await self.move(runtime_id, x, y, **kw)

    async def write(self, runtime_id: str, text: str, delay_ms: int = 0,
                    mode: str = "") -> Dict[str, Any]:
        """Type text — same as ``type`` without shadowing the builtin."""
        return await self.type(runtime_id, text, delay_ms, mode)
