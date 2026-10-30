"""
Pixel plane — implementation of the ``client.runtime.desktop`` surface.

``client.runtime.desktop`` drives the virtual display shared by every headed
surface in the runtime (browser windows, file dialogs, native UI). Use it for
work the browser plane can't see — OS dialogs, canvas, WebGL, non-browser apps —
and for ``screenshot`` when pixels are the answer.

Browser-coordinate clicks/types belong on ``client.runtime.browser`` (they
settle against the DOM); display input is raw pixel input for everything else.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..types.runtime import _validate_runtime_id
from .runtime_browser import _q

if TYPE_CHECKING:
    from .runtime import Runtimes
    from .async_runtime import AsyncRuntimes


def _shot_body(format: str, region: Optional[Dict[str, int]], quality: int,
               scale_pct: int, wait_stable_ms: int, timeout_ms: int,
               max_width: int, max_height: int, cursor: bool,
               if_rev: int = 0) -> Dict[str, Any]:
    body: Dict[str, Any] = {"format": format}
    if region is not None:
        # Wire shape is {x, y, w, h}; accept width/height as aliases.
        r = dict(region)
        if "w" not in r and "width" in r:
            r["w"] = r.pop("width")
        if "h" not in r and "height" in r:
            r["h"] = r.pop("height")
        body["region"] = r
    if quality:
        body["quality"] = quality
    if scale_pct:
        body["scale_pct"] = scale_pct
    if max_width:
        body["max_width"] = max_width
    if max_height:
        body["max_height"] = max_height
    if cursor:
        body["cursor"] = True
    if if_rev:
        body["if_rev"] = if_rev
    if wait_stable_ms:
        body["wait_stable_ms"] = wait_stable_ms
        body["timeout_ms"] = timeout_ms or wait_stable_ms * 4
    return body


def _put(body: Dict[str, Any], key: str, value: Any) -> None:
    """Attach ``value`` only when the caller set it — unset fields keep
    their server-side meaning (e.g. current pointer position)."""
    if value is not None:
        body[key] = value


def _with_watch_url(r: Dict[str, Any]) -> Dict[str, Any]:
    """Compose ``view_token`` into ``browser_url`` as ``watch_url`` — the
    ready-to-open link, so a shared URL can never arrive un-tokened."""
    url, vt = r.get("browser_url") or "", r.get("view_token") or ""
    r["watch_url"] = f"{url}{'&' if '?' in url else '?'}vt={vt}" if url and vt else url
    return r


class RuntimeDisplayResource:
    """Pixel-plane implementation — surfaced under ``client.runtime.desktop``."""

    __slots__ = ("_rt",)

    def __init__(self, runtimes: "Runtimes"):
        self._rt = runtimes

    def _j(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None):
        return self._rt._make_agents_request(method, endpoint, data).json()

    def enable(self, runtime_id: str, width: int = 0, height: int = 0,
               depth: int = 0, wm: str = "", display: str = "",
               mode: str = "") -> Dict[str, Any]:
        """Enable the display; returns ``{enabled, width, height, display, …}``.
        Zero/empty values defer to the platform defaults (1920×1080, depth 24).
        ``mode``: ``""``/``"auto"`` attaches to the session's display when the
        image ships one and spawns a virtual display otherwise; ``"spawn"``
        forces a new virtual display; ``"attach"`` requires a session display.
        """
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        if width:
            body["width"] = width
        if height:
            body["height"] = height
        if depth:
            body["depth"] = depth
        if wm:
            body["wm"] = wm
        if display:
            body["display"] = display
        if mode:
            body["mode"] = mode
        return self._j("POST", f"runtime/{runtime_id}/display/enable", body)

    def disable(self, runtime_id: str) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/display/disable")

    def status(self, runtime_id: str) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return self._j("GET", f"runtime/{runtime_id}/display/status")

    def info(self, runtime_id: str) -> Dict[str, Any]:
        """Live geometry as the display reports it now — ``status`` returns
        the enable-time config, ``info`` follows resizes."""
        _validate_runtime_id(runtime_id)
        return self._j("GET", f"runtime/{runtime_id}/display/info")

    def position(self, runtime_id: str) -> Dict[str, Any]:
        """Live pointer coordinates: ``{x, y}``."""
        _validate_runtime_id(runtime_id)
        return self._j("GET", f"runtime/{runtime_id}/display/position")

    def keys(self, runtime_id: str) -> Dict[str, Any]:
        """Key names ``press``/``hotkey`` accept: ``{keys: [...]}``."""
        _validate_runtime_id(runtime_id)
        return self._j("GET", f"runtime/{runtime_id}/display/keys")

    def screenshot(self, runtime_id: str, format: str = "png",
                   region: Optional[Dict[str, int]] = None, quality: int = 0,
                   scale_pct: int = 0, wait_stable_ms: int = 0,
                   timeout_ms: int = 0, max_width: int = 0, max_height: int = 0,
                   cursor: bool = False, if_rev: int = 0) -> Dict[str, Any]:
        """Screenshot the display. ``wait_stable_ms`` blocks until pixel-stable.
        ``region`` crops to ``{"x", "y", "w", "h"}`` (``width``/``height``
        accepted as aliases). ``max_width``/``max_height`` fit the image
        inside the bounds preserving aspect; the reply's ``scale`` reports
        the applied factor — pass ``coordinate_space="screenshot"`` on input
        calls to address coordinates in delivered pixels. ``cursor``
        composites the pointer into the shot. Data is base64.
        ``if_rev`` skips encode+transfer when the frame is unchanged —
        feed a previous reply's ``rev`` back; ``unchanged`` is then true
        and ``data`` empty."""
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/display/screenshot",
                       _shot_body(format, region, quality, scale_pct,
                                  wait_stable_ms, timeout_ms,
                                  max_width, max_height, cursor, if_rev))

    def click(self, runtime_id: str, x: Optional[int] = None,
              y: Optional[int] = None, button: str = "left",
              click_count: int = 0,
              modifiers: Optional[List[str]] = None,
              coordinate_space: str = "") -> Dict[str, Any]:
        """Click at ``(x, y)`` — unset axes keep the current pointer position.
        ``click_count`` 2 is a double-click. ``modifiers`` (``["ctrl"]`` …)
        are held during the click."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"button": button}
        _put(body, "x", x)
        _put(body, "y", y)
        _put(body, "click_count", click_count or None)
        _put(body, "modifiers", modifiers)
        _put(body, "coordinate_space", coordinate_space or None)
        return self._j("POST", f"runtime/{runtime_id}/display/mouse/click", body)

    def down(self, runtime_id: str, x: Optional[int] = None,
             y: Optional[int] = None, button: str = "left",
             modifiers: Optional[List[str]] = None,
             coordinate_space: str = "") -> Dict[str, Any]:
        """Press a mouse button (compose with ``up`` or ``drag``)."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"button": button}
        _put(body, "x", x)
        _put(body, "y", y)
        _put(body, "modifiers", modifiers)
        _put(body, "coordinate_space", coordinate_space or None)
        return self._j("POST", f"runtime/{runtime_id}/display/mouse/down", body)

    def up(self, runtime_id: str, button: str = "left",
           x: Optional[int] = None, y: Optional[int] = None,
           modifiers: Optional[List[str]] = None,
           coordinate_space: str = "") -> Dict[str, Any]:
        """Release a mouse button — ``x``/``y`` move the pointer first."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"button": button}
        _put(body, "x", x)
        _put(body, "y", y)
        _put(body, "modifiers", modifiers)
        _put(body, "coordinate_space", coordinate_space or None)
        return self._j("POST", f"runtime/{runtime_id}/display/mouse/up", body)

    def drag(self, runtime_id: str, to_x: int, to_y: int,
             x: Optional[int] = None, y: Optional[int] = None,
             button: str = "left", steps: int = 0, duration_ms: int = 0,
             modifiers: Optional[List[str]] = None,
             coordinate_space: str = "") -> Dict[str, Any]:
        """Drag from ``(x, y)`` (or the current position) to ``(to_x, to_y)``
        with ``button`` held, interpolated over ``steps`` inside
        ``duration_ms``."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"to_x": to_x, "to_y": to_y, "button": button}
        _put(body, "x", x)
        _put(body, "y", y)
        _put(body, "steps", steps or None)
        _put(body, "duration_ms", duration_ms or None)
        _put(body, "modifiers", modifiers)
        _put(body, "coordinate_space", coordinate_space or None)
        return self._j("POST", f"runtime/{runtime_id}/display/mouse/drag", body)

    def move(self, runtime_id: str, x: int, y: int,
             coordinate_space: str = "") -> Dict[str, Any]:
        """Move the pointer — ``coordinate_space="screenshot"`` maps
        delivered screenshot pixels back to display coordinates."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"x": x, "y": y}
        _put(body, "coordinate_space", coordinate_space or None)
        return self._j("POST", f"runtime/{runtime_id}/display/mouse/move", body)

    def scroll(self, runtime_id: str, x: Optional[int] = None,
               y: Optional[int] = None, dx: int = 0, dy: int = 0,
               modifiers: Optional[List[str]] = None,
               coordinate_space: str = "") -> Dict[str, Any]:
        """Scroll the wheel ``dx``/``dy`` units. ``x``/``y`` position the
        pointer first — the wheel lands under the pointer; an unset axis
        keeps the current one."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"dx": dx, "dy": dy}
        _put(body, "x", x)
        _put(body, "y", y)
        _put(body, "modifiers", modifiers)
        _put(body, "coordinate_space", coordinate_space or None)
        return self._j("POST", f"runtime/{runtime_id}/display/mouse/scroll", body)

    def type(self, runtime_id: str, text: str, delay_ms: int = 0,
             mode: str = "") -> Dict[str, Any]:
        """Type text as synthetic keystrokes. ``mode="paste"`` stages the
        text on the clipboard and sends ctrl+v — faster and lossless for
        large blocks."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"text": text, "delay_ms": delay_ms}
        _put(body, "mode", mode or None)
        return self._j("POST", f"runtime/{runtime_id}/display/keyboard/type", body)

    def press(self, runtime_id: str, key: str,
              modifiers: Optional[List[str]] = None) -> Dict[str, Any]:
        """Press a named key (``enter``, ``tab``, ``escape``, ``f5``, …),
        optionally with modifiers held."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"key": key}
        _put(body, "modifiers", modifiers)
        return self._j("POST", f"runtime/{runtime_id}/display/keyboard/press", body)

    def hotkey(self, runtime_id: str, keys: List[str],
               modifiers: Optional[List[str]] = None) -> Dict[str, Any]:
        """Press a chord (``["ctrl","c"]``)."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"keys": keys}
        _put(body, "modifiers", modifiers)
        return self._j("POST", f"runtime/{runtime_id}/display/keyboard/hotkey", body)

    def get_clipboard(self, runtime_id: str) -> str:
        """Read the display clipboard contents."""
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/display/clipboard",
                       {"op": "get"}).get("text", "")

    def set_clipboard(self, runtime_id: str, text: str) -> Dict[str, Any]:
        """Own the display clipboard — subsequent pastes yield ``text``."""
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/display/clipboard",
                       {"op": "set", "text": text})

    def wait_stable(self, runtime_id: str, stable_ms: int = 300,
                    timeout_ms: int = 10_000) -> Dict[str, Any]:
        """Block until the framebuffer is pixel-stable for ``stable_ms``."""
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/display/wait_stable",
                       {"stable_ms": stable_ms, "timeout_ms": timeout_ms})

    def view(self, runtime_id: str, fps: int = 0, quality: int = 0,
             rotate_token: bool = False, role: str = "",
             window_id: int = 0) -> Dict[str, Any]:
        """Live view — returns the watch record. ``browser_url`` carries the
        auth token and is what a human opens; it is minted on the first call
        for a port, so a repeat call returns a token-less URL unless
        ``rotate_token=True`` (fresh token — invalidates the previous URL).
        ``role="watch"`` mints a view-only link (no input injection).
        ``watch_url`` is ``browser_url`` with the role token already
        composed — the ready-to-open link. ``window_id`` streams just that
        window's pixels."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"fps": fps, "quality": quality}
        if rotate_token:
            body["rotate_token"] = True
        if role:
            body["role"] = role
        if window_id:
            body["window_id"] = window_id
        r = self._j("POST", f"runtime/{runtime_id}/display/view", body)
        return _with_watch_url(r)

    def stop_view(self, runtime_id: str) -> Dict[str, Any]:
        """Stop the live view server and free its port."""
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/display/view/stop")

    # -- agent step ---------------------------------------------------------

    def act(self, runtime_id: str, actions: List[Dict[str, Any]],
            settle_ms: int = 0, timeout_ms: int = 0,
            observe: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """One agent step in one call: run ``actions`` in order, wait for
        the screen to settle, return the observation.

        ``actions`` are input bodies — either nested
        (``{"kind": "click", "mouse": {"x": 10, "y": 20}}``) or the flat
        per-verb shape the input methods take
        (``{"kind": "click", "x": 10, "y": 20, "button": "left"}``);
        ``kind`` decides which fields apply. ``{"kind": "wait",
        "ms": 300}`` (or ``duration_ms``) pauses the batch for a fixed
        interval. ``observe`` is a screenshot options dict (``format``,
        ``region``, ``quality``, ``scale_pct``/``max_width``/
        ``max_height``, ``cursor``, ``if_rev``); omit it for no image.
        Returns ``{settled, rev, screenshot}`` — ``screenshot.rev`` feeds
        the next call's ``if_rev`` to skip unchanged frames."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"actions": actions}
        if settle_ms:
            body["settle_ms"] = settle_ms
        if timeout_ms:
            body["timeout_ms"] = timeout_ms
        if observe:
            body["observe"] = observe
        return self._j("POST", f"runtime/{runtime_id}/display/act", body)

    # -- geometry / windows / apps ------------------------------------------

    def resize(self, runtime_id: str, width: int, height: int) -> Dict[str, Any]:
        """Live-resize the display; returns the new live geometry."""
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/display/resize",
                       {"width": width, "height": height})

    def windows(self, runtime_id: str, window_class: str = "") -> Dict[str, Any]:
        """Top-level windows ``{windows: [...], focused}`` — each entry
        carries id/geometry/title/class/instance/desktop/focused/states."""
        _validate_runtime_id(runtime_id)
        params = {"window_class": window_class} if window_class else None
        return self._rt._make_agents_request(
            "GET", f"runtime/{runtime_id}/display/windows", params=params
        ).json()

    def window_op(self, runtime_id: str, window_id: int, op: str,
                  x: int = 0, y: int = 0, w: int = 0, h: int = 0) -> Dict[str, Any]:
        """Window op: ``focus`` | ``close`` | ``raise`` | ``lower`` |
        ``move`` (x,y) | ``resize`` (w,h) | ``maximize`` | ``unmaximize`` |
        ``minimize`` | ``fullscreen`` | ``unfullscreen``.
        Returns the window's post-op record."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"id": window_id, "op": op}
        if x or y:
            body["x"], body["y"] = x, y
        if w or h:
            body["w"], body["h"] = w, h
        return self._j("POST", f"runtime/{runtime_id}/display/windows/op", body)

    def focus_window(self, runtime_id: str, window_id: int) -> Dict[str, Any]:
        return self.window_op(runtime_id, window_id, "focus")

    def close_window(self, runtime_id: str, window_id: int) -> Dict[str, Any]:
        return self.window_op(runtime_id, window_id, "close")

    def move_window(self, runtime_id: str, window_id: int,
                    x: int, y: int) -> Dict[str, Any]:
        return self.window_op(runtime_id, window_id, "move", x=x, y=y)

    def resize_window(self, runtime_id: str, window_id: int,
                      w: int, h: int) -> Dict[str, Any]:
        return self.window_op(runtime_id, window_id, "resize", w=w, h=h)

    def apps(self, runtime_id: str) -> Dict[str, Any]:
        """Installed applications ``{apps: [{id, name, exec, icon, …}]}``."""
        _validate_runtime_id(runtime_id)
        return self._j("GET", f"runtime/{runtime_id}/display/apps")

    def launch_app(self, runtime_id: str, app: str, uri: str = "",
                   wait_window: bool = False,
                   timeout_ms: int = 0) -> Dict[str, Any]:
        """Launch an installed app by its ``apps()`` id. ``wait_window``
        blocks until a new top-level window maps; returns
        ``{pid, window_id, app}``."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"app": app}
        if uri:
            body["uri"] = uri
        if wait_window:
            body["wait_window"] = True
            body["timeout_ms"] = timeout_ms or 10_000
        return self._j("POST", f"runtime/{runtime_id}/display/apps/launch", body)

    def open(self, runtime_id: str, target: str, wait_window: bool = False,
             timeout_ms: int = 0) -> Dict[str, Any]:
        """Open a file path or URL with its registered handler. Returns
        ``{pid, window_id, app, mime}``."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"target": target}
        if wait_window:
            body["wait_window"] = True
            body["timeout_ms"] = timeout_ms or 10_000
        return self._j("POST", f"runtime/{runtime_id}/display/open", body)

    # -- clipboard (image) ---------------------------------------------------

    def clipboard_image(self, runtime_id: str) -> bytes:
        """Clipboard image payload as PNG bytes (``b""`` when the
        clipboard holds no image)."""
        _validate_runtime_id(runtime_id)
        import base64
        r = self._j("POST", f"runtime/{runtime_id}/display/clipboard",
                    {"op": "get"})
        return base64.b64decode(r.get("png") or b"")

    def set_clipboard_image(self, runtime_id: str, png: bytes) -> Dict[str, Any]:
        """Own the display clipboard with a PNG image — subsequent pastes
        yield it."""
        _validate_runtime_id(runtime_id)
        import base64
        return self._j("POST", f"runtime/{runtime_id}/display/clipboard",
                       {"op": "set", "png": base64.b64encode(png).decode()})

    # -- accessibility plane --------------------------------------------------

    def a11y_snapshot(self, runtime_id: str, scope: str = "", app: str = "",
                      pid: int = 0, max_depth: int = 0, limit: int = 0,
                      visible_only: Optional[bool] = None,
                      roles: Optional[List[str]] = None, name: str = "",
                      diff: bool = False, rev: int = 0) -> Dict[str, Any]:
        """Flat accessibility digest of the desktop tree → ``{rev, elements,
        truncated}``. Elements carry a ``d{n}`` ref (stable within a
        revision), role/name/value/bounds/states/actions, parent ref, app,
        pid and depth.

        ``scope``: ``""``/``"full"`` every application, ``"app"`` narrows to
        one app matched by ``app`` (name substring) or ``pid``, ``"focus"``
        the subtree holding keyboard focus. The server returns only
        showing+visible elements unless ``visible_only`` is ``False``;
        ``diff=True`` returns nodes changed since ``rev`` (or the last-known
        tree when ``rev`` is 0)."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        _put(body, "scope", scope or None)
        _put(body, "app", app or None)
        if pid:
            body["pid"] = pid
        if max_depth:
            body["max_depth"] = max_depth
        if limit:
            body["limit"] = limit
        _put(body, "visible_only", visible_only)
        _put(body, "roles", roles)
        _put(body, "name", name or None)
        if diff:
            body["diff"] = True
            if rev:
                body["rev"] = rev
        return self._j("POST", f"runtime/{runtime_id}/display/a11y/snapshot", body)

    def a11y_find(self, runtime_id: str, role: str = "", name: str = "",
                  ref: str = "", max: int = 0) -> Dict[str, Any]:
        """Search the accessibility tree → ``{elements, rev}``. ``role`` and
        ``name`` (case-insensitive substring) combine; ``ref`` scopes the
        search below one element (``""`` = whole tree); ``max`` caps
        results."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        _put(body, "role", role or None)
        _put(body, "name", name or None)
        _put(body, "ref", ref or None)
        if max:
            body["max"] = max
        return self._j("POST", f"runtime/{runtime_id}/display/a11y/find", body)

    def a11y_action(self, runtime_id: str, op: str, ref: str, action: str = "",
                    action_index: int = 0, text: str = "",
                    value: Optional[float] = None,
                    timeout_ms: int = 0) -> Dict[str, Any]:
        """Ref-addressed accessibility action → ``{ok, settled, rev}``.

        ``op``: ``click`` | ``focus`` | ``invoke`` | ``set_value`` |
        ``type``. ``invoke`` names an ``action`` (e.g. ``"press"``) or falls
        back to ``action_index``; ``type``/``set_value`` take ``text``;
        ``set_value`` may also take a numeric ``value``. The reply settles
        damage-driven like :meth:`act`, bounded by ``timeout_ms``."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"op": op, "ref": ref}
        _put(body, "action", action or None)
        if action_index:
            body["action_index"] = action_index
        _put(body, "text", text or None)
        _put(body, "value", value)
        if timeout_ms:
            body["timeout_ms"] = timeout_ms
        return self._j("POST", f"runtime/{runtime_id}/display/a11y/action", body)

    # -- recordings + takeover -------------------------------------------------

    def start_recording(self, runtime_id: str,
                        include: Optional[List[str]] = None,
                        label: str = "", window_id: int = 0) -> Dict[str, Any]:
        """Start a display recording → ``{rec_id, path, trajectory_path,
        status, ...}``.

        ``include`` selects components — ``"video"`` (MP4), ``"input"``
        (pointer/keyboard trajectory), ``"window"`` (lifecycle),
        ``"app"`` (launches); empty/``None`` records everything.
        ``window_id`` scopes capture to one window's rect. The returned
        paths are guest files readable through the files plane."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        _put(body, "include", include)
        _put(body, "label", label or None)
        if window_id:
            body["window_id"] = window_id
        return self._j("POST", f"runtime/{runtime_id}/display/recordings", body)

    def recordings(self, runtime_id: str) -> Dict[str, Any]:
        """List recordings → ``{recordings}`` (active first, then completed
        newest-first)."""
        _validate_runtime_id(runtime_id)
        return self._j("GET", f"runtime/{runtime_id}/display/recordings")

    def recording(self, runtime_id: str, rec_id: str) -> Dict[str, Any]:
        """One recording's metadata with live progress merged in."""
        _validate_runtime_id(runtime_id)
        return self._j("GET", f"runtime/{runtime_id}/display/recordings/{_q(rec_id)}")

    def stop_recording(self, runtime_id: str, rec_id: str) -> Dict[str, Any]:
        """Finalize the MP4 and seal the trajectory → ``{status}``."""
        _validate_runtime_id(runtime_id)
        return self._j("POST",
                       f"runtime/{runtime_id}/display/recordings/{_q(rec_id)}/stop", {})

    def mark_recording(self, runtime_id: str, rec_id: str,
                       label: str) -> Dict[str, Any]:
        """Stamp a named mark into the recording's metadata + trajectory."""
        _validate_runtime_id(runtime_id)
        return self._j("POST",
                       f"runtime/{runtime_id}/display/recordings/{_q(rec_id)}/mark",
                       {"label": label})

    def delete_recording(self, runtime_id: str, rec_id: str) -> Dict[str, Any]:
        """Delete a recording's artifacts → ``{deleted}`` (rejects while
        recording)."""
        _validate_runtime_id(runtime_id)
        return self._j("DELETE",
                       f"runtime/{runtime_id}/display/recordings/{_q(rec_id)}")

    def set_control_mode(self, runtime_id: str, mode: str) -> Dict[str, Any]:
        """Live-view takeover mode ``shared`` | ``human`` | ``agent`` →
        ``{mode}``. Under ``human`` the pixel plane keeps answering
        screenshots/status but rejects agent input until the mode returns
        to ``shared``/``agent``."""
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/display/view/control",
                       {"mode": mode})

    def recording_video(self, runtime_id: str, rec_id: str) -> bytes:
        """The recording's MP4 bytes. fMP4 fragments decode as a prefix, so
        a still-running recording downloads a playable file. 404 when the
        artifact is not on disk."""
        _validate_runtime_id(runtime_id)
        r = self._rt._make_agents_request(
            "GET",
            f"runtime/{runtime_id}/display/recordings/{_q(rec_id)}/video")
        return r.content

    def recording_trajectory(self, runtime_id: str, rec_id: str) -> bytes:
        """The recording's event trajectory (ndjson lines) as bytes."""
        _validate_runtime_id(runtime_id)
        r = self._rt._make_agents_request(
            "GET",
            f"runtime/{runtime_id}/display/recordings/{_q(rec_id)}/trajectory")
        return r.content


class AsyncRuntimeDisplayResource:
    """Async pixel-plane implementation — surfaced under ``client.runtime.desktop``."""

    __slots__ = ("_rt",)

    def __init__(self, runtimes: "AsyncRuntimes"):
        self._rt = runtimes

    async def _j(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None):
        r = await self._rt._make_agents_request(method, endpoint, data)
        return r.json()

    async def enable(self, runtime_id: str, width: int = 0, height: int = 0,
                     depth: int = 0, wm: str = "", display: str = "",
                     mode: str = "") -> Dict[str, Any]:
        """Enable the display. Zero/empty values defer to the platform
        defaults (1920×1080, depth 24). ``mode``: ``"spawn"`` forces a new
        virtual display, ``"attach"`` requires a session display."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        if width:
            body["width"] = width
        if height:
            body["height"] = height
        if depth:
            body["depth"] = depth
        if wm:
            body["wm"] = wm
        if display:
            body["display"] = display
        if mode:
            body["mode"] = mode
        return await self._j("POST", f"runtime/{runtime_id}/display/enable", body)

    async def disable(self, runtime_id: str) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/display/disable")

    async def status(self, runtime_id: str) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j("GET", f"runtime/{runtime_id}/display/status")

    async def info(self, runtime_id: str) -> Dict[str, Any]:
        """Live geometry as the display reports it now."""
        _validate_runtime_id(runtime_id)
        return await self._j("GET", f"runtime/{runtime_id}/display/info")

    async def position(self, runtime_id: str) -> Dict[str, Any]:
        """Live pointer coordinates: ``{x, y}``."""
        _validate_runtime_id(runtime_id)
        return await self._j("GET", f"runtime/{runtime_id}/display/position")

    async def keys(self, runtime_id: str) -> Dict[str, Any]:
        """Key names ``press``/``hotkey`` accept."""
        _validate_runtime_id(runtime_id)
        return await self._j("GET", f"runtime/{runtime_id}/display/keys")

    async def screenshot(self, runtime_id: str, format: str = "png",
                         region: Optional[Dict[str, int]] = None, quality: int = 0,
                         scale_pct: int = 0, wait_stable_ms: int = 0,
                         timeout_ms: int = 0, max_width: int = 0,
                         max_height: int = 0, cursor: bool = False,
                         if_rev: int = 0) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/display/screenshot",
                             _shot_body(format, region, quality, scale_pct,
                                        wait_stable_ms, timeout_ms,
                                        max_width, max_height, cursor, if_rev))

    async def click(self, runtime_id: str, x: Optional[int] = None,
                    y: Optional[int] = None, button: str = "left",
                    click_count: int = 0,
                    modifiers: Optional[List[str]] = None,
                    coordinate_space: str = "") -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"button": button}
        _put(body, "x", x)
        _put(body, "y", y)
        _put(body, "click_count", click_count or None)
        _put(body, "modifiers", modifiers)
        _put(body, "coordinate_space", coordinate_space or None)
        return await self._j("POST", f"runtime/{runtime_id}/display/mouse/click", body)

    async def down(self, runtime_id: str, x: Optional[int] = None,
                   y: Optional[int] = None, button: str = "left",
                   modifiers: Optional[List[str]] = None,
                   coordinate_space: str = "") -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"button": button}
        _put(body, "x", x)
        _put(body, "y", y)
        _put(body, "modifiers", modifiers)
        _put(body, "coordinate_space", coordinate_space or None)
        return await self._j("POST", f"runtime/{runtime_id}/display/mouse/down", body)

    async def up(self, runtime_id: str, button: str = "left",
                 x: Optional[int] = None, y: Optional[int] = None,
                 modifiers: Optional[List[str]] = None,
                 coordinate_space: str = "") -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"button": button}
        _put(body, "x", x)
        _put(body, "y", y)
        _put(body, "modifiers", modifiers)
        _put(body, "coordinate_space", coordinate_space or None)
        return await self._j("POST", f"runtime/{runtime_id}/display/mouse/up", body)

    async def drag(self, runtime_id: str, to_x: int, to_y: int,
                   x: Optional[int] = None, y: Optional[int] = None,
                   button: str = "left", steps: int = 0, duration_ms: int = 0,
                   modifiers: Optional[List[str]] = None,
                   coordinate_space: str = "") -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"to_x": to_x, "to_y": to_y, "button": button}
        _put(body, "x", x)
        _put(body, "y", y)
        _put(body, "steps", steps or None)
        _put(body, "duration_ms", duration_ms or None)
        _put(body, "modifiers", modifiers)
        _put(body, "coordinate_space", coordinate_space or None)
        return await self._j("POST", f"runtime/{runtime_id}/display/mouse/drag", body)

    async def move(self, runtime_id: str, x: int, y: int,
                   coordinate_space: str = "") -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"x": x, "y": y}
        _put(body, "coordinate_space", coordinate_space or None)
        return await self._j("POST", f"runtime/{runtime_id}/display/mouse/move",
                             body)

    async def scroll(self, runtime_id: str, x: Optional[int] = None,
                     y: Optional[int] = None, dx: int = 0, dy: int = 0,
                     modifiers: Optional[List[str]] = None,
                     coordinate_space: str = "") -> Dict[str, Any]:
        """Scroll the wheel ``dx``/``dy`` units. ``x``/``y`` position the
        pointer first — the wheel lands under the pointer; an unset axis
        keeps the current one."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"dx": dx, "dy": dy}
        _put(body, "x", x)
        _put(body, "y", y)
        _put(body, "modifiers", modifiers)
        _put(body, "coordinate_space", coordinate_space or None)
        return await self._j("POST", f"runtime/{runtime_id}/display/mouse/scroll", body)

    async def type(self, runtime_id: str, text: str, delay_ms: int = 0,
                   mode: str = "") -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"text": text, "delay_ms": delay_ms}
        _put(body, "mode", mode or None)
        return await self._j("POST", f"runtime/{runtime_id}/display/keyboard/type", body)

    async def press(self, runtime_id: str, key: str,
                    modifiers: Optional[List[str]] = None) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"key": key}
        _put(body, "modifiers", modifiers)
        return await self._j("POST", f"runtime/{runtime_id}/display/keyboard/press", body)

    async def hotkey(self, runtime_id: str, keys: List[str],
                     modifiers: Optional[List[str]] = None) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"keys": keys}
        _put(body, "modifiers", modifiers)
        return await self._j("POST", f"runtime/{runtime_id}/display/keyboard/hotkey", body)

    async def get_clipboard(self, runtime_id: str) -> str:
        """Read the display clipboard contents."""
        _validate_runtime_id(runtime_id)
        r = await self._j("POST", f"runtime/{runtime_id}/display/clipboard",
                          {"op": "get"})
        return r.get("text", "")

    async def set_clipboard(self, runtime_id: str, text: str) -> Dict[str, Any]:
        """Own the display clipboard — subsequent pastes yield ``text``."""
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/display/clipboard",
                             {"op": "set", "text": text})

    async def wait_stable(self, runtime_id: str, stable_ms: int = 300,
                          timeout_ms: int = 10_000) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/display/wait_stable",
                             {"stable_ms": stable_ms, "timeout_ms": timeout_ms})

    async def view(self, runtime_id: str, fps: int = 0, quality: int = 0,
                   rotate_token: bool = False, role: str = "",
                   window_id: int = 0) -> Dict[str, Any]:
        """Live view — returns the watch record. ``browser_url`` carries the
        auth token and is what a human opens; it is minted on the first call
        for a port, so a repeat call returns a token-less URL unless
        ``rotate_token=True`` (fresh token — invalidates the previous URL).
        ``role="watch"`` mints a view-only link (no input injection).
        ``watch_url`` is ``browser_url`` with the role token already
        composed — the ready-to-open link. ``window_id`` streams just that
        window's pixels."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"fps": fps, "quality": quality}
        if rotate_token:
            body["rotate_token"] = True
        if role:
            body["role"] = role
        if window_id:
            body["window_id"] = window_id
        r = await self._j("POST", f"runtime/{runtime_id}/display/view", body)
        return _with_watch_url(r)

    async def stop_view(self, runtime_id: str) -> Dict[str, Any]:
        """Stop the live view server and free its port."""
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/display/view/stop")

    # -- agent step ---------------------------------------------------------

    async def act(self, runtime_id: str, actions: List[Dict[str, Any]],
                  settle_ms: int = 0, timeout_ms: int = 0,
                  observe: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """One agent step in one call: run ``actions`` in order, wait for
        the screen to settle, return the observation. ``actions`` are input
        bodies; ``observe`` is a screenshot options dict. Returns
        ``{settled, rev, screenshot}``."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"actions": actions}
        if settle_ms:
            body["settle_ms"] = settle_ms
        if timeout_ms:
            body["timeout_ms"] = timeout_ms
        if observe:
            body["observe"] = observe
        return await self._j("POST", f"runtime/{runtime_id}/display/act", body)

    # -- geometry / windows / apps ------------------------------------------

    async def resize(self, runtime_id: str, width: int, height: int) -> Dict[str, Any]:
        """Live-resize the display; returns the new live geometry."""
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/display/resize",
                             {"width": width, "height": height})

    async def windows(self, runtime_id: str, window_class: str = "") -> Dict[str, Any]:
        """Top-level windows ``{windows: [...], focused}``."""
        _validate_runtime_id(runtime_id)
        params = {"window_class": window_class} if window_class else None
        r = await self._rt._make_agents_request(
            "GET", f"runtime/{runtime_id}/display/windows", params=params
        )
        return r.json()

    async def window_op(self, runtime_id: str, window_id: int, op: str,
                        x: int = 0, y: int = 0, w: int = 0,
                        h: int = 0) -> Dict[str, Any]:
        """Window op: ``focus`` | ``close`` | ``raise`` | ``lower`` |
        ``move`` (x,y) | ``resize`` (w,h) | ``maximize`` | ``unmaximize`` |
        ``minimize`` | ``fullscreen`` | ``unfullscreen``."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"id": window_id, "op": op}
        if x or y:
            body["x"], body["y"] = x, y
        if w or h:
            body["w"], body["h"] = w, h
        return await self._j("POST", f"runtime/{runtime_id}/display/windows/op", body)

    async def focus_window(self, runtime_id: str, window_id: int) -> Dict[str, Any]:
        return await self.window_op(runtime_id, window_id, "focus")

    async def close_window(self, runtime_id: str, window_id: int) -> Dict[str, Any]:
        return await self.window_op(runtime_id, window_id, "close")

    async def move_window(self, runtime_id: str, window_id: int,
                          x: int, y: int) -> Dict[str, Any]:
        return await self.window_op(runtime_id, window_id, "move", x=x, y=y)

    async def resize_window(self, runtime_id: str, window_id: int,
                            w: int, h: int) -> Dict[str, Any]:
        return await self.window_op(runtime_id, window_id, "resize", w=w, h=h)

    async def apps(self, runtime_id: str) -> Dict[str, Any]:
        """Installed applications ``{apps: [{id, name, exec, icon, …}]}``."""
        _validate_runtime_id(runtime_id)
        return await self._j("GET", f"runtime/{runtime_id}/display/apps")

    async def launch_app(self, runtime_id: str, app: str, uri: str = "",
                         wait_window: bool = False,
                         timeout_ms: int = 0) -> Dict[str, Any]:
        """Launch an installed app by id; ``wait_window`` blocks until its
        window maps. Returns ``{pid, window_id, app}``."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"app": app}
        if uri:
            body["uri"] = uri
        if wait_window:
            body["wait_window"] = True
            body["timeout_ms"] = timeout_ms or 10_000
        return await self._j("POST", f"runtime/{runtime_id}/display/apps/launch", body)

    async def open(self, runtime_id: str, target: str, wait_window: bool = False,
                   timeout_ms: int = 0) -> Dict[str, Any]:
        """Open a file path or URL with its registered handler."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"target": target}
        if wait_window:
            body["wait_window"] = True
            body["timeout_ms"] = timeout_ms or 10_000
        return await self._j("POST", f"runtime/{runtime_id}/display/open", body)

    # -- clipboard (image) ---------------------------------------------------

    async def clipboard_image(self, runtime_id: str) -> bytes:
        """Clipboard image payload as PNG bytes (``b""`` when no image)."""
        _validate_runtime_id(runtime_id)
        import base64
        r = await self._j("POST", f"runtime/{runtime_id}/display/clipboard",
                          {"op": "get"})
        return base64.b64decode(r.get("png") or b"")

    async def set_clipboard_image(self, runtime_id: str, png: bytes) -> Dict[str, Any]:
        """Own the display clipboard with a PNG image."""
        _validate_runtime_id(runtime_id)
        import base64
        return await self._j("POST", f"runtime/{runtime_id}/display/clipboard",
                             {"op": "set", "png": base64.b64encode(png).decode()})

    # -- accessibility plane --------------------------------------------------

    async def a11y_snapshot(self, runtime_id: str, scope: str = "", app: str = "",
                            pid: int = 0, max_depth: int = 0, limit: int = 0,
                            visible_only: Optional[bool] = None,
                            roles: Optional[List[str]] = None, name: str = "",
                            diff: bool = False, rev: int = 0) -> Dict[str, Any]:
        """Flat accessibility digest → ``{rev, elements, truncated}`` —
        async variant of the sync method (same scope/filters/diff)."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        _put(body, "scope", scope or None)
        _put(body, "app", app or None)
        if pid:
            body["pid"] = pid
        if max_depth:
            body["max_depth"] = max_depth
        if limit:
            body["limit"] = limit
        _put(body, "visible_only", visible_only)
        _put(body, "roles", roles)
        _put(body, "name", name or None)
        if diff:
            body["diff"] = True
            if rev:
                body["rev"] = rev
        return await self._j("POST", f"runtime/{runtime_id}/display/a11y/snapshot", body)

    async def a11y_find(self, runtime_id: str, role: str = "", name: str = "",
                        ref: str = "", max: int = 0) -> Dict[str, Any]:
        """Search the accessibility tree → ``{elements, rev}``."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        _put(body, "role", role or None)
        _put(body, "name", name or None)
        _put(body, "ref", ref or None)
        if max:
            body["max"] = max
        return await self._j("POST", f"runtime/{runtime_id}/display/a11y/find", body)

    async def a11y_action(self, runtime_id: str, op: str, ref: str,
                          action: str = "", action_index: int = 0,
                          text: str = "", value: Optional[float] = None,
                          timeout_ms: int = 0) -> Dict[str, Any]:
        """Ref-addressed action ``click`` | ``focus`` | ``invoke`` |
        ``set_value`` | ``type`` → ``{ok, settled, rev}``."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"op": op, "ref": ref}
        _put(body, "action", action or None)
        if action_index:
            body["action_index"] = action_index
        _put(body, "text", text or None)
        _put(body, "value", value)
        if timeout_ms:
            body["timeout_ms"] = timeout_ms
        return await self._j("POST", f"runtime/{runtime_id}/display/a11y/action", body)

    # -- recordings + takeover -------------------------------------------------

    async def start_recording(self, runtime_id: str,
                              include: Optional[List[str]] = None,
                              label: str = "", window_id: int = 0) -> Dict[str, Any]:
        """Start a display recording → ``{rec_id, path, trajectory_path,
        status, ...}``. ``include``: ``"video"`` | ``"input"`` |
        ``"window"`` | ``"app"``; empty records everything."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        _put(body, "include", include)
        _put(body, "label", label or None)
        if window_id:
            body["window_id"] = window_id
        return await self._j("POST", f"runtime/{runtime_id}/display/recordings", body)

    async def recordings(self, runtime_id: str) -> Dict[str, Any]:
        """List recordings → ``{recordings}``."""
        _validate_runtime_id(runtime_id)
        return await self._j("GET", f"runtime/{runtime_id}/display/recordings")

    async def recording(self, runtime_id: str, rec_id: str) -> Dict[str, Any]:
        """One recording's metadata with live progress."""
        _validate_runtime_id(runtime_id)
        return await self._j("GET", f"runtime/{runtime_id}/display/recordings/{_q(rec_id)}")

    async def stop_recording(self, runtime_id: str, rec_id: str) -> Dict[str, Any]:
        """Finalize the MP4 and seal the trajectory."""
        _validate_runtime_id(runtime_id)
        return await self._j("POST",
                             f"runtime/{runtime_id}/display/recordings/{_q(rec_id)}/stop", {})

    async def mark_recording(self, runtime_id: str, rec_id: str,
                             label: str) -> Dict[str, Any]:
        """Stamp a named mark into the recording."""
        _validate_runtime_id(runtime_id)
        return await self._j("POST",
                             f"runtime/{runtime_id}/display/recordings/{_q(rec_id)}/mark",
                             {"label": label})

    async def delete_recording(self, runtime_id: str, rec_id: str) -> Dict[str, Any]:
        """Delete a recording's artifacts (rejects while recording)."""
        _validate_runtime_id(runtime_id)
        return await self._j("DELETE",
                             f"runtime/{runtime_id}/display/recordings/{_q(rec_id)}")

    async def set_control_mode(self, runtime_id: str, mode: str) -> Dict[str, Any]:
        """Takeover mode ``shared`` | ``human`` | ``agent`` → ``{mode}``."""
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/display/view/control",
                             {"mode": mode})

    async def recording_video(self, runtime_id: str, rec_id: str) -> bytes:
        """The recording's MP4 bytes — playable while still recording."""
        _validate_runtime_id(runtime_id)
        r = await self._rt._make_agents_request(
            "GET",
            f"runtime/{runtime_id}/display/recordings/{_q(rec_id)}/video")
        return r.content

    async def recording_trajectory(self, runtime_id: str, rec_id: str) -> bytes:
        """The recording's event trajectory (ndjson lines) as bytes."""
        _validate_runtime_id(runtime_id)
        r = await self._rt._make_agents_request(
            "GET",
            f"runtime/{runtime_id}/display/recordings/{_q(rec_id)}/trajectory")
        return r.content
