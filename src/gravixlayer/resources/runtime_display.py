"""
Display plane — pixel-level control of the runtime's screen.

``client.runtime.display`` drives the virtual display shared by every headed
surface in the runtime (browser windows, file dialogs, native UI). Use it for
work the browser plane can't see — OS dialogs, canvas, WebGL, non-browser apps —
and for ``screenshot`` when pixels are the answer.

Browser-coordinate clicks/types belong on ``client.runtime.browser`` (they
settle against the DOM); display input is raw pixel input for everything else.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..types.runtime import _validate_runtime_id

if TYPE_CHECKING:
    from .runtime import Runtimes
    from .async_runtime import AsyncRuntimes


def _shot_body(format: str, region: Optional[Dict[str, int]], quality: int,
               scale_pct: int, wait_stable_ms: int, timeout_ms: int) -> Dict[str, Any]:
    body: Dict[str, Any] = {"format": format}
    if region is not None:
        body["region"] = region
    if quality:
        body["quality"] = quality
    if scale_pct:
        body["scale_pct"] = scale_pct
    if wait_stable_ms:
        body["wait_stable_ms"] = wait_stable_ms
        body["timeout_ms"] = timeout_ms or wait_stable_ms * 4
    return body


class RuntimeDisplayResource:
    """Display operations under ``client.runtime.display``."""

    __slots__ = ("_rt",)

    def __init__(self, runtimes: "Runtimes"):
        self._rt = runtimes

    def _j(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None):
        return self._rt._make_agents_request(method, endpoint, data).json()

    def enable(self, runtime_id: str, width: int = 1920, height: int = 1080,
               depth: int = 24, wm: str = "") -> Dict[str, Any]:
        """Enable the display; returns ``{enabled, width, height, display, …}``."""
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/display/enable",
                       {"width": width, "height": height, "depth": depth, "wm": wm})

    def disable(self, runtime_id: str) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/display/disable")

    def status(self, runtime_id: str) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return self._j("GET", f"runtime/{runtime_id}/display/status")

    def screenshot(self, runtime_id: str, format: str = "png",
                   region: Optional[Dict[str, int]] = None, quality: int = 0,
                   scale_pct: int = 0, wait_stable_ms: int = 0,
                   timeout_ms: int = 0) -> Dict[str, Any]:
        """Screenshot the display. ``wait_stable_ms`` blocks until pixel-stable.
        Data is base64."""
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/display/screenshot",
                       _shot_body(format, region, quality, scale_pct,
                                  wait_stable_ms, timeout_ms))

    def click(self, runtime_id: str, x: int, y: int, button: str = "left") -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/display/mouse/click",
                       {"x": x, "y": y, "button": button})

    def move(self, runtime_id: str, x: int, y: int) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/display/mouse/move",
                       {"x": x, "y": y})

    def scroll(self, runtime_id: str, x: int = 0, y: int = 0,
               dx: int = 0, dy: int = 0) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/display/mouse/scroll",
                       {"x": x, "y": y, "dx": dx, "dy": dy})

    def type(self, runtime_id: str, text: str, delay_ms: int = 0) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/display/keyboard/type",
                       {"text": text, "delay_ms": delay_ms})

    def press(self, runtime_id: str, key: str) -> Dict[str, Any]:
        """Press a named key (``enter``, ``tab``, ``escape``, ``f5``, …)."""
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/display/keyboard/press",
                       {"key": key})

    def hotkey(self, runtime_id: str, keys: List[str]) -> Dict[str, Any]:
        """Press a chord (``["ctrl","c"]``)."""
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/display/keyboard/hotkey",
                       {"keys": keys})

    def wait_stable(self, runtime_id: str, stable_ms: int = 300,
                    timeout_ms: int = 10_000) -> Dict[str, Any]:
        """Block until the framebuffer is pixel-stable for ``stable_ms``."""
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/display/wait_stable",
                       {"stable_ms": stable_ms, "timeout_ms": timeout_ms})

    def view(self, runtime_id: str, fps: int = 0, quality: int = 0) -> Dict[str, Any]:
        """Live view — returns a shareable watch URL a human can open
        (``url``/``browser_url`` carry the session's auth)."""
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/display/view",
                       {"fps": fps, "quality": quality})


class AsyncRuntimeDisplayResource:
    """Async display operations under ``client.runtime.display``."""

    __slots__ = ("_rt",)

    def __init__(self, runtimes: "AsyncRuntimes"):
        self._rt = runtimes

    async def _j(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None):
        r = await self._rt._make_agents_request(method, endpoint, data)
        return r.json()

    async def enable(self, runtime_id: str, width: int = 1920, height: int = 1080,
                     depth: int = 24, wm: str = "") -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/display/enable",
                             {"width": width, "height": height, "depth": depth, "wm": wm})

    async def disable(self, runtime_id: str) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/display/disable")

    async def status(self, runtime_id: str) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j("GET", f"runtime/{runtime_id}/display/status")

    async def screenshot(self, runtime_id: str, format: str = "png",
                         region: Optional[Dict[str, int]] = None, quality: int = 0,
                         scale_pct: int = 0, wait_stable_ms: int = 0,
                         timeout_ms: int = 0) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/display/screenshot",
                             _shot_body(format, region, quality, scale_pct,
                                        wait_stable_ms, timeout_ms))

    async def click(self, runtime_id: str, x: int, y: int, button: str = "left") -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/display/mouse/click",
                             {"x": x, "y": y, "button": button})

    async def move(self, runtime_id: str, x: int, y: int) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/display/mouse/move",
                             {"x": x, "y": y})

    async def scroll(self, runtime_id: str, x: int = 0, y: int = 0,
                     dx: int = 0, dy: int = 0) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/display/mouse/scroll",
                             {"x": x, "y": y, "dx": dx, "dy": dy})

    async def type(self, runtime_id: str, text: str, delay_ms: int = 0) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/display/keyboard/type",
                             {"text": text, "delay_ms": delay_ms})

    async def press(self, runtime_id: str, key: str) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/display/keyboard/press",
                             {"key": key})

    async def hotkey(self, runtime_id: str, keys: List[str]) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/display/keyboard/hotkey",
                             {"keys": keys})

    async def wait_stable(self, runtime_id: str, stable_ms: int = 300,
                          timeout_ms: int = 10_000) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/display/wait_stable",
                             {"stable_ms": stable_ms, "timeout_ms": timeout_ms})

    async def view(self, runtime_id: str, fps: int = 0, quality: int = 0) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/display/view",
                             {"fps": fps, "quality": quality})
