"""
Browser plane — semantic control of the runtime's browser.

``client.runtime.browser`` drives the browser that lives inside the runtime.
Actions are element-first: pass a ref from ``snapshot()`` (``"e3"``) or a
``{"by": ..., "value": ...}`` selector, and the runtime resolves, checks
actionability, dispatches, and waits for the page to settle before returning.
Coordinates work too when the surface isn't an element (canvas, WebGL).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, Iterator, List, Optional, Tuple
from urllib.parse import quote

from ..types.runtime import _validate_runtime_id

if TYPE_CHECKING:
    from .runtime import Runtimes
    from .async_runtime import AsyncRuntimes


def _q(seg: Any) -> str:
    """Percent-encode one URL path segment — caller-supplied ids (browser,
    target, download) must never carry ``/``, ``?`` or ``#`` into a path."""
    return quote(str(seg), safe="-_.")


def _iter_event_frames(lines: Any) -> Iterator[Dict[str, Any]]:
    """Fold an SSE line iterator into ``{seq, kind, data}`` dicts.

    Each frame is ``id: {seq}`` + ``event: {kind}`` + ``data: {entry}``;
    comment keep-alives and blank lines are skipped. ``data`` is JSON
    decoded when it parses, otherwise carried verbatim."""
    seq: Optional[int] = None
    kind = "message"
    for raw in lines:
        if not raw:
            continue
        line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        value = value.lstrip(" ")
        if field == "id":
            try:
                seq = int(value)
            except ValueError:
                pass
        elif field == "event":
            kind = value or "message"
        elif field == "data":
            try:
                data: Any = json.loads(value)
            except json.JSONDecodeError:
                data = value
            yield {"seq": seq, "kind": kind, "data": data}
            seq = None
            kind = "message"


async def _aiter_event_frames(lines: Any) -> AsyncIterator[Dict[str, Any]]:
    """Async counterpart of :func:`_iter_event_frames`."""
    seq: Optional[int] = None
    kind = "message"
    async for raw in lines:
        if not raw:
            continue
        line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        value = value.lstrip(" ")
        if field == "id":
            try:
                seq = int(value)
            except ValueError:
                pass
        elif field == "event":
            kind = value or "message"
        elif field == "data":
            try:
                data: Any = json.loads(value)
            except json.JSONDecodeError:
                data = value
            yield {"seq": seq, "kind": kind, "data": data}
            seq = None
            kind = "message"


def _target(target: Any) -> Optional[Dict[str, Any]]:
    """Normalize an element target: a ref string, an (x, y) coords pair, or the
    full ``{by, value, attrs, exact, pierce, inner}`` selector dict."""
    if target is None:
        return None
    if isinstance(target, str):
        return {"by": "ref", "value": target}
    if isinstance(target, (tuple, list)) and len(target) == 2:
        return {"by": "coords", "attrs": {"x": str(target[0]), "y": str(target[1])}}
    return dict(target)


_COMMAND_VERBS = frozenset({"back", "forward", "reload", "activate"})


def _open_body(engine: str, headless: bool, profile_dir: str, args: Optional[List[str]], url: str) -> Dict[str, Any]:
    body: Dict[str, Any] = {"engine": engine, "headless": headless}
    if profile_dir:
        body["profile_dir"] = profile_dir
    if args:
        body["args"] = args
    if url:
        body["url"] = url
    return body


def _shot_body(
    target_id: str, format: str, full_page: bool, element: Any, quality: int, wait_stable_ms: int, timeout_ms: int
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"target_id": target_id, "format": format, "full_page": full_page}
    if element is not None:
        body["element"] = _target(element)
    if quality:
        body["quality"] = quality
    if wait_stable_ms:
        body["wait_stable_ms"] = wait_stable_ms
        body["timeout_ms"] = timeout_ms or wait_stable_ms * 4
    return body


def _act(
    verb: str,
    target_id: str,
    target: Any,
    settle: bool,
    extra: Dict[str, Any],
    force: bool = False,
    settle_timeout_ms: int = 0,
    target_timeout_ms: int = 0,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "verb": verb,
        "target_id": target_id,
        "settle": settle,
        "force": force,
        "settle_timeout_ms": settle_timeout_ms,
        "target_timeout_ms": target_timeout_ms,
    }
    if target is not None:
        body["target"] = _target(target)
    body.update(extra)
    return body


class RuntimeBrowserResource:
    """Browser operations under ``client.runtime.browser``."""

    __slots__ = ("_rt", "_default")

    def __init__(self, runtimes: "Runtimes"):
        self._rt = runtimes
        self._default: Dict[str, str] = {}

    def _ensure(self, runtime_id: str) -> str:
        """The default browser for a runtime — opened on first use."""
        bid = self._default.get(runtime_id)
        if not bid:
            bid = self.open(runtime_id)["browser_id"]
            self._default[runtime_id] = bid
        return bid

    def goto(
        self, runtime_id: str, url: str, target_id: str = "", wait_until: str = "load", timeout_ms: int = 30_000
    ) -> Dict[str, Any]:
        """Auto-opens a browser if needed and navigates it — the simple path.
        If the remembered browser died, reopen and retry once."""
        _validate_runtime_id(runtime_id)
        from gravixlayer.types.exceptions import GravixLayerError

        bid = self._ensure(runtime_id)
        try:
            return self.navigate(
                runtime_id, bid, url, target_id=target_id, wait_until=wait_until, timeout_ms=timeout_ms
            )
        except GravixLayerError as e:
            if e.status != 404 or self._default.get(runtime_id) != bid:
                raise
            self._default.pop(runtime_id, None)
            return self.navigate(
                runtime_id,
                self._ensure(runtime_id),
                url,
                target_id=target_id,
                wait_until=wait_until,
                timeout_ms=timeout_ms,
            )

    def _j(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None):
        return self._rt._make_agents_request(method, endpoint, data).json()

    def _action(self, runtime_id: str, browser_id: str, verb: str, body: Dict[str, Any]) -> Dict[str, Any]:
        return self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/actions/{verb}", body)

    # -- lifecycle -------------------------------------------------------------

    def open(
        self,
        runtime_id: str,
        engine: str = "chromium",
        headless: bool = False,
        profile_dir: str = "",
        args: Optional[List[str]] = None,
        url: str = "",
    ) -> Dict[str, Any]:
        """Open a browser. Headed by default — the window is on the runtime's
        display, so ``view()`` and pixel actions work on it."""
        _validate_runtime_id(runtime_id)
        return self._j(
            "POST", f"runtime/{runtime_id}/browser/open", _open_body(engine, headless, profile_dir, args, url)
        )

    def close(self, runtime_id: str, browser_id: str) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        if self._default.get(runtime_id) == browser_id:
            self._default.pop(runtime_id, None)
        return self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/close")

    def list(self, runtime_id: str) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return self._j("GET", f"runtime/{runtime_id}/browser")

    def status(self, runtime_id: str, browser_id: str) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return self._j("GET", f"runtime/{runtime_id}/browser/{_q(browser_id)}/status")

    # -- navigation -------------------------------------------------------------

    def navigate(
        self,
        runtime_id: str,
        browser_id: str,
        url: str,
        target_id: str = "",
        wait_until: str = "load",
        timeout_ms: int = 30_000,
    ) -> Dict[str, Any]:
        """Navigate a target; returns once the page settles."""
        _validate_runtime_id(runtime_id)
        return self._j(
            "POST",
            f"runtime/{runtime_id}/browser/{_q(browser_id)}/navigate",
            {"target_id": target_id, "url": url, "wait_until": wait_until, "timeout_ms": timeout_ms},
        )

    def _command(self, runtime_id: str, browser_id: str, verb: str, target_id: str) -> Dict[str, Any]:
        return self._j(
            "POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/{verb}", {"target_id": target_id, "verb": verb}
        )

    def command(self, runtime_id: str, browser_id: str, verb: str, target_id: str = "") -> Dict[str, Any]:
        """Generic target verb — ``back``/``forward``/``reload``/``activate``.
        The named methods cover the same set; this is the escape hatch."""
        _validate_runtime_id(runtime_id)
        if verb not in _COMMAND_VERBS:
            raise ValueError(f"verb must be one of {sorted(_COMMAND_VERBS)}")
        return self._command(runtime_id, browser_id, verb, target_id)

    def activate(self, runtime_id: str, browser_id: str, target_id: str) -> Dict[str, Any]:
        """Bring a target (tab) to the front."""
        _validate_runtime_id(runtime_id)
        return self._command(runtime_id, browser_id, "activate", target_id)

    def back(self, runtime_id: str, browser_id: str, target_id: str = "") -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return self._command(runtime_id, browser_id, "back", target_id)

    def forward(self, runtime_id: str, browser_id: str, target_id: str = "") -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return self._command(runtime_id, browser_id, "forward", target_id)

    def reload(self, runtime_id: str, browser_id: str, target_id: str = "") -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return self._command(runtime_id, browser_id, "reload", target_id)

    # -- observation -------------------------------------------------------------

    def screenshot(
        self,
        runtime_id: str,
        browser_id: str,
        target_id: str = "",
        format: str = "png",
        full_page: bool = False,
        element: Any = None,
        quality: int = 0,
        wait_stable_ms: int = 0,
        timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        """Page screenshot — viewport default; ``full_page`` or ``element`` for a
        scoped clip. ``quality`` applies to JPEG (0–100). Data is base64."""
        _validate_runtime_id(runtime_id)
        return self._j(
            "POST",
            f"runtime/{runtime_id}/browser/{_q(browser_id)}/screenshot",
            _shot_body(target_id, format, full_page, element, quality, wait_stable_ms, timeout_ms),
        )

    def snapshot(
        self,
        runtime_id: str,
        browser_id: str,
        target_id: str = "",
        viewport_only: bool = True,
        diff: str = "",
        filter_role: str = "",
        filter_name: str = "",
    ) -> Dict[str, Any]:
        """Interactable-element digest ``{ref, role, name, rect, ...}`` — the
        model's ground truth for targeting."""
        _validate_runtime_id(runtime_id)
        return self._j(
            "POST",
            f"runtime/{runtime_id}/browser/{_q(browser_id)}/snapshot",
            {
                "target_id": target_id,
                "viewport_only": viewport_only,
                "diff": diff,
                "filter_role": filter_role,
                "filter_name": filter_name,
            },
        )

    def evaluate(
        self,
        runtime_id: str,
        browser_id: str,
        expression: str,
        target_id: str = "",
        await_promise: bool = True,
        timeout_ms: int = 30_000,
        world: str = "isolated",
    ) -> Dict[str, Any]:
        """The escape hatch: run JavaScript in the page, get the JSON result.
        ``world`` selects the isolated world (default) or the page's main world."""
        _validate_runtime_id(runtime_id)
        return self._j(
            "POST",
            f"runtime/{runtime_id}/browser/{_q(browser_id)}/evaluate",
            {
                "target_id": target_id,
                "expression": expression,
                "await_promise": await_promise,
                "timeout_ms": timeout_ms,
                "world": world,
            },
        )

    # -- actions -------------------------------------------------------------

    def click(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        target_id: str = "",
        button: str = "left",
        click_count: int = 1,
        settle: bool = True,
        settle_timeout_ms: int = 0,
        force: bool = False,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        """Click an element (ref/selector/coords) — resolve, actionability,
        dispatch, settle."""
        _validate_runtime_id(runtime_id)
        return self._action(
            runtime_id,
            browser_id,
            "click",
            _act(
                "click",
                target_id,
                target,
                settle,
                {"button": button, "click_count": click_count},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    def dblclick(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        target_id: str = "",
        button: str = "left",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        """Double-click an element."""
        _validate_runtime_id(runtime_id)
        return self._action(
            runtime_id,
            browser_id,
            "dblclick",
            _act(
                "dblclick",
                target_id,
                target,
                settle,
                {"button": button},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    def hover(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        target_id: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        """Move the pointer onto an element (triggers :hover / tooltips)."""
        _validate_runtime_id(runtime_id)
        return self._action(
            runtime_id,
            browser_id,
            "hover",
            _act(
                "hover",
                target_id,
                target,
                settle,
                {},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    def fill(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        text: str = "",
        target_id: str = "",
        secret_ref: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        """Clear + insert text. ``secret_ref`` types from the secrets store so the
        value never crosses the client."""
        _validate_runtime_id(runtime_id)
        extra: Dict[str, Any] = {"secret_ref": secret_ref} if secret_ref else {"text": text}
        return self._action(
            runtime_id,
            browser_id,
            "fill",
            _act(
                "fill",
                target_id,
                target,
                settle,
                extra,
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    def type(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        text: str,
        target_id: str = "",
        delay_ms: int = 0,
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return self._action(
            runtime_id,
            browser_id,
            "type",
            _act(
                "type",
                target_id,
                target,
                settle,
                {"text": text, "delay_ms": delay_ms},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    def press(
        self,
        runtime_id: str,
        browser_id: str,
        key: str,
        target: Any = None,
        target_id: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return self._action(
            runtime_id,
            browser_id,
            "press",
            _act(
                "press",
                target_id,
                target,
                settle,
                {"key": key},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    def hotkey(
        self,
        runtime_id: str,
        browser_id: str,
        keys: List[str],
        target_id: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return self._action(
            runtime_id,
            browser_id,
            "hotkey",
            _act(
                "hotkey",
                target_id,
                None,
                settle,
                {"keys": keys},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    def scroll(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any = None,
        target_id: str = "",
        dx: int = 0,
        dy: int = 0,
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        """Scroll — page-level by default, or the element's box when targeted."""
        _validate_runtime_id(runtime_id)
        return self._action(
            runtime_id,
            browser_id,
            "scroll",
            _act(
                "scroll",
                target_id,
                target,
                settle,
                {"dx": dx, "dy": dy},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    # -- dialogs / downloads / pdf / view -------------------------------------------------------------

    def dialog(
        self,
        runtime_id: str,
        browser_id: str,
        accept: bool = True,
        prompt_text: str = "",
        auto_dismiss: bool = False,
        target_id: str = "",
    ) -> Dict[str, Any]:
        """Answer a pending alert/confirm/prompt (``prompt_text`` fills prompt
        dialogs). ``auto_dismiss=True`` instead restores auto-dismiss policy
        and clears any pending dialog."""
        _validate_runtime_id(runtime_id)
        return self._j(
            "POST",
            f"runtime/{runtime_id}/browser/{_q(browser_id)}/dialog",
            {"target_id": target_id, "accept": accept, "prompt_text": prompt_text, "auto_dismiss": auto_dismiss},
        )

    def targets(
        self, runtime_id: str, browser_id: str, url: str = "", activate: bool = True, context_id: str = ""
    ) -> Dict[str, Any]:
        """List targets, or open one (``url`` non-empty → new tab).
        ``context_id`` opens the target inside an isolated context from
        :meth:`create_context` — ``""`` is the default context."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"url": url, "activate": activate}
        if context_id:
            body["context_id"] = context_id
        return self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/targets", body)

    def downloads(self, runtime_id: str, browser_id: str, wait_name: str = "", timeout_ms: int = 0) -> Dict[str, Any]:
        """List downloads; ``wait_name`` blocks until that file lands."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        if wait_name:
            body["wait_name"] = wait_name
            body["timeout_ms"] = timeout_ms or 30_000
        return self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/downloads", body)

    def download(self, runtime_id: str, browser_id: str, download_id: str, meta_only: bool = False) -> Dict[str, Any]:
        """Entry + file bytes (base64). ``meta_only`` returns the entry only."""
        _validate_runtime_id(runtime_id)
        ep = f"runtime/{runtime_id}/browser/{_q(browser_id)}/downloads/{_q(download_id)}"
        if meta_only:
            ep += "?meta_only=true"
        return self._j("GET", ep)

    def pdf(
        self,
        runtime_id: str,
        browser_id: str,
        target_id: str,
        landscape: bool = False,
        print_background: bool = True,
        page_ranges: str = "",
        paper_width_in: float = 0.0,
        paper_height_in: float = 0.0,
        margins_in: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Render a target to PDF. Data is base64.

        ``margins_in``: ``{"top": 0.4, "bottom": ..., "left": ..., "right": ...}`` inches.
        """
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {
            "landscape": landscape,
            "print_background": print_background,
            "page_ranges": page_ranges,
            "paper_width_in": paper_width_in,
            "paper_height_in": paper_height_in,
        }
        if margins_in:
            for k in ("top", "bottom", "left", "right"):
                if k in margins_in:
                    body[f"margin_{k}_in"] = margins_in[k]
        return self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/targets/{_q(target_id)}/pdf", body)

    def view(
        self,
        runtime_id: str,
        browser_id: str,
        target_id: str = "",
        fps: int = 0,
        quality: int = 0,
        role: str = "",
        rotate_token: bool = False,
    ) -> Dict[str, Any]:
        """Live view — returns the watch record. ``browser_url`` carries a
        fresh auth token and is what a human opens; every call mints one, so
        repeat calls always return a working link (each mint invalidates the
        previous token — already-open viewers keep their live sockets).
        ``rotate_token`` is accepted but no longer needed. ``role="watch"``
        mints a view-only link: ``view_token``/``watch_url`` carry a ``vt=``
        capability that sees frames but can never inject input. Headed
        browsers stream through the display's token-gated view where ``vt=``
        is required."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"target_id": target_id, "fps": fps, "quality": quality}
        if role:
            body["role"] = role
        if rotate_token:
            body["rotate_token"] = True
        from gravixlayer.resources.runtime_display import _with_watch_url

        return _with_watch_url(self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/view", body))

    # -- events, contexts, storage state --------------------------------------

    def events(self, runtime_id: str, browser_id: str, since: int = 0, wait_ms: int = 0) -> Iterator[Dict[str, Any]]:
        """Yield browser events ``{seq, kind, data}`` until the current
        long-poll page ends.

        ``since`` resumes strictly after that sequence number (sent as the
        ``Last-Event-ID`` header); ``wait_ms`` bounds the page (server
        default 25 s, cap 30 s). An idle page ends after one keep-alive.
        Chain pages by passing the last yielded ``seq`` back as ``since`` —
        a fabric error arrives as a terminal ``kind="error"`` frame."""
        _validate_runtime_id(runtime_id)
        params: Dict[str, Any] = {}
        if since:
            params["since"] = since
        if wait_ms:
            params["wait_ms"] = wait_ms
        headers = {"Accept": "text/event-stream"}
        if since:
            headers["Last-Event-ID"] = str(since)
        response = self._rt._make_agents_request(
            "GET", f"runtime/{runtime_id}/browser/{_q(browser_id)}/events", params=params, stream=True, headers=headers
        )
        try:
            yield from _iter_event_frames(response.iter_lines())
        finally:
            response.close()

    def create_context(
        self, runtime_id: str, browser_id: str, proxy: str = "", storage_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Open an isolated browser context (separate cookie/storage jars)
        → ``{context_id}``. ``proxy`` is a proxy server URL;
        ``storage_state`` seeds the context's cookies and origins in the
        Playwright-compatible export shape."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        if proxy:
            body["proxy"] = proxy
        if storage_state is not None:
            body["storage_state"] = storage_state
        return self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/context", body)

    def contexts(self, runtime_id: str, browser_id: str) -> Dict[str, Any]:
        """Caller-created contexts → ``{contexts: [...]}``; the implicit
        default context does not list."""
        _validate_runtime_id(runtime_id)
        return self._j("GET", f"runtime/{runtime_id}/browser/{_q(browser_id)}/contexts")

    def delete_context(self, runtime_id: str, browser_id: str, context_id: str) -> Dict[str, Any]:
        """Delete an isolated context and its jars. The default context
        rejects guest-side."""
        _validate_runtime_id(runtime_id)
        return self._j("DELETE", f"runtime/{runtime_id}/browser/{_q(browser_id)}/context/{_q(context_id)}")

    def export_storage(self, runtime_id: str, browser_id: str, context_id: str = "") -> Dict[str, Any]:
        """Export a context's cookies and local storage → ``{storage_state}``
        (Playwright-compatible ``cookies``/``origins`` shape). An empty
        ``context_id`` addresses the default context."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"context_id": context_id} if context_id else {}
        return self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/storage/export", body)

    def import_storage(
        self, runtime_id: str, browser_id: str, storage_state: Any, context_id: str = ""
    ) -> Dict[str, Any]:
        """Load cookies/origins into a context. ``storage_state`` may be the
        exported object or a pre-serialized JSON string; ``context_id``
        behaves as in :meth:`export_storage`."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"storage_state": storage_state}
        if context_id:
            body["context_id"] = context_id
        return self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/storage/import", body)

    # -- form + advanced verbs ---------------------------------------------------

    def select(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        option: str,
        target_id: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        """Pick a ``<select>`` option by value, label text, or index."""
        _validate_runtime_id(runtime_id)
        return self._action(
            runtime_id,
            browser_id,
            "select",
            _act(
                "select",
                target_id,
                target,
                settle,
                {"option": option},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    def check(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        target_id: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        """Check a checkbox/radio — a real click, only when state differs."""
        _validate_runtime_id(runtime_id)
        return self._action(
            runtime_id,
            browser_id,
            "check",
            _act(
                "check",
                target_id,
                target,
                settle,
                {},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    def uncheck(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        target_id: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        """Uncheck a checkbox — no-op when already unchecked."""
        _validate_runtime_id(runtime_id)
        return self._action(
            runtime_id,
            browser_id,
            "uncheck",
            _act(
                "uncheck",
                target_id,
                target,
                settle,
                {},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    def focus(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        target_id: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        """Move DOM focus onto an element."""
        _validate_runtime_id(runtime_id)
        return self._action(
            runtime_id,
            browser_id,
            "focus",
            _act(
                "focus",
                target_id,
                target,
                settle,
                {},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    def blur(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        target_id: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        """Remove DOM focus from an element."""
        _validate_runtime_id(runtime_id)
        return self._action(
            runtime_id,
            browser_id,
            "blur",
            _act(
                "blur",
                target_id,
                target,
                settle,
                {},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    def scroll_into_view(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        target_id: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        """Scroll an element into the viewport (nearest block/inline)."""
        _validate_runtime_id(runtime_id)
        return self._action(
            runtime_id,
            browser_id,
            "scroll_into_view",
            _act(
                "scroll_into_view",
                target_id,
                target,
                settle,
                {},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    def drag_to(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        drop_target: Any,
        target_id: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        """Drag ``target`` onto ``drop_target`` — stepped pointer move so
        intermediate ``dragover`` handlers fire."""
        _validate_runtime_id(runtime_id)
        return self._action(
            runtime_id,
            browser_id,
            "drag_to",
            _act(
                "drag_to",
                target_id,
                target,
                settle,
                {"drop_target": _target(drop_target)},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    def upload(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        paths: List[str],
        target_id: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        """Set files on a ``<input type=file>`` element. ``paths`` are guest
        paths — ship customer files first via the files API ``write``."""
        _validate_runtime_id(runtime_id)
        return self._action(
            runtime_id,
            browser_id,
            "upload",
            _act(
                "upload",
                target_id,
                target,
                settle,
                {"paths": list(paths)},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    # -- emulation, network, auth ------------------------------------------------

    def emulate(
        self,
        runtime_id: str,
        browser_id: str,
        target_id: str = "",
        viewport: Optional[Dict[str, Any]] = None,
        geolocation: Optional[Dict[str, Any]] = None,
        timezone: str = "",
        locale: str = "",
        user_agent: str = "",
        mobile: Optional[bool] = None,
        touch: Optional[bool] = None,
        color_scheme: str = "",
        context_id: str = "",
        clear: bool = False,
    ) -> Dict[str, Any]:
        """Apply emulation overrides to a target — ``viewport``
        ``{width, height, scale}``, ``geolocation`` ``{latitude, longitude,
        accuracy?}``, ``timezone`` (IANA), ``locale`` (also sets
        accept-language), ``user_agent``, ``mobile``, ``touch``,
        ``color_scheme`` (``light``/``dark``). Only the keys carried are
        overridden; overrides persist across target re-attach. ``clear``
        drops every override on the scope."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        if target_id:
            body["target_id"] = target_id
        if context_id:
            body["context_id"] = context_id
        if viewport is not None:
            if viewport.get("width"):
                body["width"] = viewport["width"]
            if viewport.get("height"):
                body["height"] = viewport["height"]
            if viewport.get("scale"):
                body["device_scale_factor"] = viewport["scale"]
        if geolocation is not None:
            if geolocation.get("latitude") is not None:
                body["geolocation_lat"] = geolocation["latitude"]
            if geolocation.get("longitude") is not None:
                body["geolocation_lon"] = geolocation["longitude"]
            if geolocation.get("accuracy") is not None:
                body["geolocation_accuracy"] = geolocation["accuracy"]
        for key, value in (
            ("timezone_id", timezone),
            ("locale", locale),
            ("user_agent", user_agent),
            ("color_scheme", color_scheme),
        ):
            if value:
                body[key] = value
        if mobile is not None:
            body["mobile"] = mobile
        if touch is not None:
            body["touch"] = touch
        if clear:
            body["clear"] = True
        return self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/emulate", body)

    def intercept(
        self, runtime_id: str, browser_id: str, rules: List[Dict[str, Any]], target_id: str = ""
    ) -> Dict[str, Any]:
        """Install request-interception rules — each ``{url_pattern,
        action: "continue"|"block"|"mock", resource_type?, mock_status?,
        mock_headers?, mock_body_b64?}``. Matching runs in the runtime; the
        network tap stays off while no rules exist → ``{rule_ids}``."""
        _validate_runtime_id(runtime_id)
        return self._j(
            "POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/intercept", {"target_id": target_id, "rules": rules}
        )

    def intercept_clear(
        self, runtime_id: str, browser_id: str, rule_ids: Optional[List[str]] = None, target_id: str = ""
    ) -> Dict[str, Any]:
        """Remove interception rules — ``rule_ids`` for specific rules, empty
        clears all."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        if rule_ids:
            body["rule_ids"] = rule_ids
        if target_id:
            body["target_id"] = target_id
        return self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/intercept/clear", body)

    def auth(
        self,
        runtime_id: str,
        browser_id: str,
        username: str = "",
        password: str = "",
        secret_ref: str = "",
        clear: bool = False,
        target_id: str = "",
    ) -> Dict[str, Any]:
        """Answer HTTP basic/digest challenges in-page. ``secret_ref``
        resolves the password server-side; ``clear`` disarms the handler."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        if username:
            body["username"] = username
        if secret_ref:
            body["secret_ref"] = secret_ref
        elif password:
            body["password"] = password
        if clear:
            body["clear"] = True
        if target_id:
            body["target_id"] = target_id
        return self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/auth", body)

    # -- extensions + CDP ------------------------------------------------------

    def extension_load(self, runtime_id: str, browser_id: str, path: str) -> Dict[str, Any]:
        """Hot-load an unpacked extension from a guest directory (must live
        under ``/workspace``) → ``{extension_id}``."""
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/extensions/load", {"path": path})

    def extension_unload(self, runtime_id: str, browser_id: str, extension_id: str) -> Dict[str, Any]:
        """Unload an extension by the id ``extension_load`` returned."""
        _validate_runtime_id(runtime_id)
        return self._j(
            "POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/extensions/unload", {"extension_id": extension_id}
        )

    def cdp_endpoint(self, runtime_id: str, browser_id: str, port: int = 0, token: str = "") -> Dict[str, Any]:
        """Start a tokened CDP WebSocket bridge → ``{port, path, token}`` —
        the attach point for external drivers. Raw protocol semantics: the
        bridge bypasses targeting/actionability."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        if port:
            body["port"] = port
        if token:
            body["token"] = token
        return self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/cdp_endpoint", body)

    def cdp_endpoint_stop(self, runtime_id: str, browser_id: str) -> Dict[str, Any]:
        """Tear down the CDP bridge."""
        _validate_runtime_id(runtime_id)
        return self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/cdp_endpoint/stop", {})

    # -- approvals --------------------------------------------------------------

    def approval_request(self, runtime_id: str, browser_id: str, message: str, timeout_ms: int = 0) -> Dict[str, Any]:
        """Ask an operator for approval — parks until resolved or
        ``timeout_ms`` lapses → ``{approval_id, resolved, approved?}``.
        Resolve from another call, or watch ``approval_request`` events."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"message": message}
        if timeout_ms:
            body["timeout_ms"] = timeout_ms
        return self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/approvals", body)

    def approval_resolve(
        self, runtime_id: str, browser_id: str, approval_id: str, approved: bool, note: str = ""
    ) -> Dict[str, Any]:
        """Resolve a pending approval — the parked ``approval_request`` wakes
        with the answer."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"approved": approved}
        if note:
            body["note"] = note
        return self._j(
            "POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/approvals/{_q(approval_id)}/resolve", body
        )

    # -- reads: content + cookies ------------------------------------------------

    def content(self, runtime_id: str, browser_id: str, target_id: str = "", format: str = "") -> Dict[str, Any]:
        """Serialized page content — rendered HTML by default, ``format``
        selects the extraction."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"target_id": target_id}
        if format:
            body["format"] = format
        return self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/content", body)

    def cookies(self, runtime_id: str, browser_id: str, context_id: str = "", url: str = "") -> Dict[str, Any]:
        """List the context's cookies — empty ``context_id`` is the default
        context."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        if context_id:
            body["context_id"] = context_id
        if url:
            body["url"] = url
        return self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/cookies", body)

    def set_cookie(
        self,
        runtime_id: str,
        browser_id: str,
        name: str,
        value: str,
        url: str = "",
        context_id: str = "",
        attrs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Set one cookie — ``url`` scopes it, ``attrs`` carries
        domain/path/secure/expiry fields."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"op": "set", "name": name, "value": value}
        if url:
            body["url"] = url
        if context_id:
            body["context_id"] = context_id
        if attrs:
            body["attrs"] = attrs
        return self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/cookies", body)

    def delete_cookie(
        self, runtime_id: str, browser_id: str, name: str, url: str = "", context_id: str = ""
    ) -> Dict[str, Any]:
        """Delete one cookie by name (``url`` scopes the match)."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"op": "delete", "name": name}
        if url:
            body["url"] = url
        if context_id:
            body["context_id"] = context_id
        return self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/cookies", body)

    def clear_cookies(self, runtime_id: str, browser_id: str, context_id: str = "") -> Dict[str, Any]:
        """Clear every cookie in the context."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"op": "clear"}
        if context_id:
            body["context_id"] = context_id
        return self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/cookies", body)

    # -- downloads, recording, profile, replay, fork -----------------------------

    def download_delete(
        self, runtime_id: str, browser_id: str, download_id: str, delete_file: bool = False
    ) -> Dict[str, Any]:
        """Drop a download record; ``delete_file`` also removes the guest
        file."""
        _validate_runtime_id(runtime_id)
        endpoint = f"runtime/{runtime_id}/browser/{_q(browser_id)}" f"/downloads/{_q(download_id)}"
        if delete_file:
            endpoint += "?delete_file=true"
        return self._j("DELETE", endpoint)

    def recording_start(
        self, runtime_id: str, browser_id: str, target_id: str, fps: int = 0, quality: int = 0
    ) -> Dict[str, Any]:
        """Start a per-target video recording (works headless) → recording
        handle."""
        _validate_runtime_id(runtime_id)
        return self._j(
            "POST",
            f"runtime/{runtime_id}/browser/{_q(browser_id)}/targets/{_q(target_id)}/recording/start",
            {k: v for k, v in (("fps", fps), ("quality", quality)) if v},
        )

    def recording_stop(self, runtime_id: str, browser_id: str, target_id: str) -> Dict[str, Any]:
        """Stop a target recording → sealed artifact metadata."""
        _validate_runtime_id(runtime_id)
        return self._j(
            "POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/targets/{_q(target_id)}/recording/stop", {}
        )

    def recording_export(self, runtime_id: str, browser_id: str, recording_id: str, dest_dir: str) -> Dict[str, Any]:
        """Copy a finished recording's artifacts into ``dest_dir`` (guest
        path under ``/workspace``)."""
        _validate_runtime_id(runtime_id)
        return self._j(
            "POST",
            f"runtime/{runtime_id}/browser/{_q(browser_id)}/recordings/export",
            {"recording_id": recording_id, "dest_dir": dest_dir},
        )

    def profile_export(self, runtime_id: str, browser_id: str, dest_path: str = "") -> Dict[str, Any]:
        """Quiesce and tar the browser's profile (cookies, storage, prefs —
        durable auth) → ``dest_path`` under ``/workspace``."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        if dest_path:
            body["dest_path"] = dest_path
        return self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/profile/export", body)

    def profile_import(self, runtime_id: str, browser_id: str, archive_path: str) -> Dict[str, Any]:
        """Respawn the browser against a previously exported profile tar."""
        _validate_runtime_id(runtime_id)
        return self._j(
            "POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/profile/import", {"archive_path": archive_path}
        )

    def replay(
        self,
        runtime_id: str,
        browser_id: str,
        steps: List[Dict[str, Any]],
        stop_on_fail: bool = False,
        step_timeout_ms: int = 0,
        target_id: str = "",
    ) -> Dict[str, Any]:
        """Replay recorded action steps with per-step effect checks —
        ``steps`` are ``{action, expect_url_contains?/expect_selector?/
        expect_eval?}`` entries; ``stop_on_fail`` halts the cohort on the
        first failed check; ``step_timeout_ms`` caps each step."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"steps": steps, "stop_on_fail": stop_on_fail}
        if step_timeout_ms:
            body["step_timeout_ms"] = step_timeout_ms
        if target_id:
            body["target_id"] = target_id
        return self._j(
            "POST",
            f"runtime/{runtime_id}/browser/{_q(browser_id)}/replay",
            body,
        )

    def fork(
        self, runtime_id: str, browser_id: str, count: int = 1, url: str = "", target_id: str = ""
    ) -> Dict[str, Any]:
        """Fork the page into a cohort of identical targets (1–8) for
        best-of-N runs → ``{target_ids: [...]}``."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"count": count}
        if url:
            body["url"] = url
        if target_id:
            body["target_id"] = target_id
        return self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/fork", body)


class AsyncRuntimeBrowserResource:
    """Async browser operations under ``client.runtime.browser``."""

    __slots__ = ("_rt", "_default")

    def __init__(self, runtimes: "AsyncRuntimes"):
        self._rt = runtimes
        self._default: Dict[str, str] = {}

    async def _ensure(self, runtime_id: str) -> str:
        bid = self._default.get(runtime_id)
        if not bid:
            bid = (await self.open(runtime_id))["browser_id"]
            self._default[runtime_id] = bid
        return bid

    async def goto(
        self, runtime_id: str, url: str, target_id: str = "", wait_until: str = "load", timeout_ms: int = 30_000
    ) -> Dict[str, Any]:
        """Auto-opens a browser if needed and navigates it — the simple path.
        If the remembered browser died, reopen and retry once."""
        _validate_runtime_id(runtime_id)
        from gravixlayer.types.exceptions import GravixLayerError

        bid = await self._ensure(runtime_id)
        try:
            return await self.navigate(
                runtime_id, bid, url, target_id=target_id, wait_until=wait_until, timeout_ms=timeout_ms
            )
        except GravixLayerError as e:
            if e.status != 404 or self._default.get(runtime_id) != bid:
                raise
            self._default.pop(runtime_id, None)
            return await self.navigate(
                runtime_id,
                await self._ensure(runtime_id),
                url,
                target_id=target_id,
                wait_until=wait_until,
                timeout_ms=timeout_ms,
            )

    async def _j(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None):
        r = await self._rt._make_agents_request(method, endpoint, data)
        return r.json()

    async def _action(self, runtime_id: str, browser_id: str, verb: str, body: Dict[str, Any]) -> Dict[str, Any]:
        return await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/actions/{verb}", body)

    async def open(
        self,
        runtime_id: str,
        engine: str = "chromium",
        headless: bool = False,
        profile_dir: str = "",
        args: Optional[List[str]] = None,
        url: str = "",
    ) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j(
            "POST", f"runtime/{runtime_id}/browser/open", _open_body(engine, headless, profile_dir, args, url)
        )

    async def close(self, runtime_id: str, browser_id: str) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        if self._default.get(runtime_id) == browser_id:
            self._default.pop(runtime_id, None)
        return await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/close")

    async def list(self, runtime_id: str) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j("GET", f"runtime/{runtime_id}/browser")

    async def status(self, runtime_id: str, browser_id: str) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j("GET", f"runtime/{runtime_id}/browser/{_q(browser_id)}/status")

    async def navigate(
        self,
        runtime_id: str,
        browser_id: str,
        url: str,
        target_id: str = "",
        wait_until: str = "load",
        timeout_ms: int = 30_000,
    ) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j(
            "POST",
            f"runtime/{runtime_id}/browser/{_q(browser_id)}/navigate",
            {"target_id": target_id, "url": url, "wait_until": wait_until, "timeout_ms": timeout_ms},
        )

    async def _command(self, runtime_id: str, browser_id: str, verb: str, target_id: str) -> Dict[str, Any]:
        return await self._j(
            "POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/{verb}", {"target_id": target_id, "verb": verb}
        )

    async def command(self, runtime_id: str, browser_id: str, verb: str, target_id: str = "") -> Dict[str, Any]:
        """Generic target verb — ``back``/``forward``/``reload``/``activate``.
        The named methods cover the same set; this is the escape hatch."""
        _validate_runtime_id(runtime_id)
        if verb not in _COMMAND_VERBS:
            raise ValueError(f"verb must be one of {sorted(_COMMAND_VERBS)}")
        return await self._command(runtime_id, browser_id, verb, target_id)

    async def activate(self, runtime_id: str, browser_id: str, target_id: str) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._command(runtime_id, browser_id, "activate", target_id)

    async def back(self, runtime_id: str, browser_id: str, target_id: str = "") -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._command(runtime_id, browser_id, "back", target_id)

    async def forward(self, runtime_id: str, browser_id: str, target_id: str = "") -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._command(runtime_id, browser_id, "forward", target_id)

    async def reload(self, runtime_id: str, browser_id: str, target_id: str = "") -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._command(runtime_id, browser_id, "reload", target_id)

    async def screenshot(
        self,
        runtime_id: str,
        browser_id: str,
        target_id: str = "",
        format: str = "png",
        full_page: bool = False,
        element: Any = None,
        quality: int = 0,
        wait_stable_ms: int = 0,
        timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j(
            "POST",
            f"runtime/{runtime_id}/browser/{_q(browser_id)}/screenshot",
            _shot_body(target_id, format, full_page, element, quality, wait_stable_ms, timeout_ms),
        )

    async def snapshot(
        self,
        runtime_id: str,
        browser_id: str,
        target_id: str = "",
        viewport_only: bool = True,
        diff: str = "",
        filter_role: str = "",
        filter_name: str = "",
    ) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j(
            "POST",
            f"runtime/{runtime_id}/browser/{_q(browser_id)}/snapshot",
            {
                "target_id": target_id,
                "viewport_only": viewport_only,
                "diff": diff,
                "filter_role": filter_role,
                "filter_name": filter_name,
            },
        )

    async def evaluate(
        self,
        runtime_id: str,
        browser_id: str,
        expression: str,
        target_id: str = "",
        await_promise: bool = True,
        timeout_ms: int = 30_000,
        world: str = "isolated",
    ) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j(
            "POST",
            f"runtime/{runtime_id}/browser/{_q(browser_id)}/evaluate",
            {
                "target_id": target_id,
                "expression": expression,
                "await_promise": await_promise,
                "timeout_ms": timeout_ms,
                "world": world,
            },
        )

    async def click(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        target_id: str = "",
        button: str = "left",
        click_count: int = 1,
        settle: bool = True,
        settle_timeout_ms: int = 0,
        force: bool = False,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._action(
            runtime_id,
            browser_id,
            "click",
            _act(
                "click",
                target_id,
                target,
                settle,
                {"button": button, "click_count": click_count},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    async def dblclick(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        target_id: str = "",
        button: str = "left",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._action(
            runtime_id,
            browser_id,
            "dblclick",
            _act(
                "dblclick",
                target_id,
                target,
                settle,
                {"button": button},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    async def hover(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        target_id: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._action(
            runtime_id,
            browser_id,
            "hover",
            _act(
                "hover",
                target_id,
                target,
                settle,
                {},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    async def fill(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        text: str = "",
        target_id: str = "",
        secret_ref: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        extra: Dict[str, Any] = {"secret_ref": secret_ref} if secret_ref else {"text": text}
        return await self._action(
            runtime_id,
            browser_id,
            "fill",
            _act(
                "fill",
                target_id,
                target,
                settle,
                extra,
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    async def type(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        text: str,
        target_id: str = "",
        delay_ms: int = 0,
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._action(
            runtime_id,
            browser_id,
            "type",
            _act(
                "type",
                target_id,
                target,
                settle,
                {"text": text, "delay_ms": delay_ms},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    async def press(
        self,
        runtime_id: str,
        browser_id: str,
        key: str,
        target: Any = None,
        target_id: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._action(
            runtime_id,
            browser_id,
            "press",
            _act(
                "press",
                target_id,
                target,
                settle,
                {"key": key},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    async def hotkey(
        self,
        runtime_id: str,
        browser_id: str,
        keys: List[str],
        target_id: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._action(
            runtime_id,
            browser_id,
            "hotkey",
            _act(
                "hotkey",
                target_id,
                None,
                settle,
                {"keys": keys},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    async def scroll(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any = None,
        target_id: str = "",
        dx: int = 0,
        dy: int = 0,
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._action(
            runtime_id,
            browser_id,
            "scroll",
            _act(
                "scroll",
                target_id,
                target,
                settle,
                {"dx": dx, "dy": dy},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    async def dialog(
        self,
        runtime_id: str,
        browser_id: str,
        accept: bool = True,
        prompt_text: str = "",
        auto_dismiss: bool = False,
        target_id: str = "",
    ) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        return await self._j(
            "POST",
            f"runtime/{runtime_id}/browser/{_q(browser_id)}/dialog",
            {"target_id": target_id, "accept": accept, "prompt_text": prompt_text, "auto_dismiss": auto_dismiss},
        )

    async def targets(
        self, runtime_id: str, browser_id: str, url: str = "", activate: bool = True, context_id: str = ""
    ) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"url": url, "activate": activate}
        if context_id:
            body["context_id"] = context_id
        return await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/targets", body)

    async def downloads(
        self, runtime_id: str, browser_id: str, wait_name: str = "", timeout_ms: int = 0
    ) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        if wait_name:
            body["wait_name"] = wait_name
            body["timeout_ms"] = timeout_ms or 30_000
        return await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/downloads", body)

    async def download(
        self, runtime_id: str, browser_id: str, download_id: str, meta_only: bool = False
    ) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        ep = f"runtime/{runtime_id}/browser/{_q(browser_id)}/downloads/{_q(download_id)}"
        if meta_only:
            ep += "?meta_only=true"
        return await self._j("GET", ep)

    async def pdf(
        self,
        runtime_id: str,
        browser_id: str,
        target_id: str,
        landscape: bool = False,
        print_background: bool = True,
        page_ranges: str = "",
        paper_width_in: float = 0.0,
        paper_height_in: float = 0.0,
        margins_in: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {
            "landscape": landscape,
            "print_background": print_background,
            "page_ranges": page_ranges,
            "paper_width_in": paper_width_in,
            "paper_height_in": paper_height_in,
        }
        if margins_in:
            for k in ("top", "bottom", "left", "right"):
                if k in margins_in:
                    body[f"margin_{k}_in"] = margins_in[k]
        return await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/targets/{_q(target_id)}/pdf", body)

    async def view(
        self,
        runtime_id: str,
        browser_id: str,
        target_id: str = "",
        fps: int = 0,
        quality: int = 0,
        role: str = "",
        rotate_token: bool = False,
    ) -> Dict[str, Any]:
        """Live view — returns the watch record. ``browser_url`` carries a
        fresh auth token and is what a human opens; every call mints one, so
        repeat calls always return a working link (each mint invalidates the
        previous token — already-open viewers keep their live sockets).
        ``rotate_token`` is accepted but no longer needed. ``role="watch"``
        mints a view-only link: ``view_token``/``watch_url`` carry a ``vt=``
        capability that sees frames but can never inject input. Headed
        browsers stream through the display's token-gated view where ``vt=``
        is required."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"target_id": target_id, "fps": fps, "quality": quality}
        if role:
            body["role"] = role
        if rotate_token:
            body["rotate_token"] = True
        from gravixlayer.resources.runtime_display import _with_watch_url

        return _with_watch_url(await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/view", body))

    # -- events, contexts, storage state --------------------------------------

    async def events(
        self, runtime_id: str, browser_id: str, since: int = 0, wait_ms: int = 0
    ) -> AsyncIterator[Dict[str, Any]]:
        """Async variant of the sync ``events`` — yields ``{seq, kind,
        data}`` until the long-poll page ends; chain by passing the last
        ``seq`` back as ``since``."""
        _validate_runtime_id(runtime_id)
        params: Dict[str, Any] = {}
        if since:
            params["since"] = since
        if wait_ms:
            params["wait_ms"] = wait_ms
        headers = {"Accept": "text/event-stream"}
        if since:
            headers["Last-Event-ID"] = str(since)
        response = await self._rt._make_agents_request(
            "GET", f"runtime/{runtime_id}/browser/{_q(browser_id)}/events", params=params, stream=True, headers=headers
        )
        try:
            async for frame in _aiter_event_frames(response.aiter_lines()):
                yield frame
        finally:
            await response.aclose()

    async def create_context(
        self, runtime_id: str, browser_id: str, proxy: str = "", storage_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Open an isolated browser context (separate cookie/storage jars)
        → ``{context_id}``. ``proxy`` is a proxy server URL."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        if proxy:
            body["proxy"] = proxy
        if storage_state is not None:
            body["storage_state"] = storage_state
        return await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/context", body)

    async def contexts(self, runtime_id: str, browser_id: str) -> Dict[str, Any]:
        """Caller-created contexts → ``{contexts: [...]}``."""
        _validate_runtime_id(runtime_id)
        return await self._j("GET", f"runtime/{runtime_id}/browser/{_q(browser_id)}/contexts")

    async def delete_context(self, runtime_id: str, browser_id: str, context_id: str) -> Dict[str, Any]:
        """Delete an isolated context and its jars."""
        _validate_runtime_id(runtime_id)
        return await self._j("DELETE", f"runtime/{runtime_id}/browser/{_q(browser_id)}/context/{_q(context_id)}")

    async def export_storage(self, runtime_id: str, browser_id: str, context_id: str = "") -> Dict[str, Any]:
        """Export a context's cookies and local storage → ``{storage_state}``."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"context_id": context_id} if context_id else {}
        return await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/storage/export", body)

    async def import_storage(
        self, runtime_id: str, browser_id: str, storage_state: Any, context_id: str = ""
    ) -> Dict[str, Any]:
        """Load cookies/origins into a context — object or JSON string."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"storage_state": storage_state}
        if context_id:
            body["context_id"] = context_id
        return await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/storage/import", body)

    # -- form + advanced verbs ---------------------------------------------------

    async def select(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        option: str,
        target_id: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        """Pick a ``<select>`` option by value, label text, or index."""
        _validate_runtime_id(runtime_id)
        return await self._action(
            runtime_id,
            browser_id,
            "select",
            _act(
                "select",
                target_id,
                target,
                settle,
                {"option": option},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    async def check(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        target_id: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        """Check a checkbox/radio — a real click, only when state differs."""
        _validate_runtime_id(runtime_id)
        return await self._action(
            runtime_id,
            browser_id,
            "check",
            _act(
                "check",
                target_id,
                target,
                settle,
                {},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    async def uncheck(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        target_id: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        """Uncheck a checkbox — no-op when already unchecked."""
        _validate_runtime_id(runtime_id)
        return await self._action(
            runtime_id,
            browser_id,
            "uncheck",
            _act(
                "uncheck",
                target_id,
                target,
                settle,
                {},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    async def focus(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        target_id: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        """Move DOM focus onto an element."""
        _validate_runtime_id(runtime_id)
        return await self._action(
            runtime_id,
            browser_id,
            "focus",
            _act(
                "focus",
                target_id,
                target,
                settle,
                {},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    async def blur(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        target_id: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        """Remove DOM focus from an element."""
        _validate_runtime_id(runtime_id)
        return await self._action(
            runtime_id,
            browser_id,
            "blur",
            _act(
                "blur",
                target_id,
                target,
                settle,
                {},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    async def scroll_into_view(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        target_id: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        """Scroll an element into the viewport (nearest block/inline)."""
        _validate_runtime_id(runtime_id)
        return await self._action(
            runtime_id,
            browser_id,
            "scroll_into_view",
            _act(
                "scroll_into_view",
                target_id,
                target,
                settle,
                {},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    async def drag_to(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        drop_target: Any,
        target_id: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        """Drag ``target`` onto ``drop_target`` — stepped pointer move so
        intermediate ``dragover`` handlers fire."""
        _validate_runtime_id(runtime_id)
        return await self._action(
            runtime_id,
            browser_id,
            "drag_to",
            _act(
                "drag_to",
                target_id,
                target,
                settle,
                {"drop_target": _target(drop_target)},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    async def upload(
        self,
        runtime_id: str,
        browser_id: str,
        target: Any,
        paths: List[str],
        target_id: str = "",
        settle: bool = True,
        force: bool = False,
        settle_timeout_ms: int = 0,
        target_timeout_ms: int = 0,
    ) -> Dict[str, Any]:
        """Set files on a ``<input type=file>`` element — ``paths`` are guest
        paths (ship files first via the files API ``write``)."""
        _validate_runtime_id(runtime_id)
        return await self._action(
            runtime_id,
            browser_id,
            "upload",
            _act(
                "upload",
                target_id,
                target,
                settle,
                {"paths": list(paths)},
                force=force,
                settle_timeout_ms=settle_timeout_ms,
                target_timeout_ms=target_timeout_ms,
            ),
        )

    # -- emulation, network, auth ------------------------------------------------

    async def emulate(
        self,
        runtime_id: str,
        browser_id: str,
        target_id: str = "",
        viewport: Optional[Dict[str, Any]] = None,
        geolocation: Optional[Dict[str, Any]] = None,
        timezone: str = "",
        locale: str = "",
        user_agent: str = "",
        mobile: Optional[bool] = None,
        touch: Optional[bool] = None,
        color_scheme: str = "",
        context_id: str = "",
        clear: bool = False,
    ) -> Dict[str, Any]:
        """Async mirror of :meth:`RuntimeBrowser.emulate`."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        if target_id:
            body["target_id"] = target_id
        if context_id:
            body["context_id"] = context_id
        if viewport is not None:
            if viewport.get("width"):
                body["width"] = viewport["width"]
            if viewport.get("height"):
                body["height"] = viewport["height"]
            if viewport.get("scale"):
                body["device_scale_factor"] = viewport["scale"]
        if geolocation is not None:
            if geolocation.get("latitude") is not None:
                body["geolocation_lat"] = geolocation["latitude"]
            if geolocation.get("longitude") is not None:
                body["geolocation_lon"] = geolocation["longitude"]
            if geolocation.get("accuracy") is not None:
                body["geolocation_accuracy"] = geolocation["accuracy"]
        for key, value in (
            ("timezone_id", timezone),
            ("locale", locale),
            ("user_agent", user_agent),
            ("color_scheme", color_scheme),
        ):
            if value:
                body[key] = value
        if mobile is not None:
            body["mobile"] = mobile
        if touch is not None:
            body["touch"] = touch
        if clear:
            body["clear"] = True
        return await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/emulate", body)

    async def intercept(
        self, runtime_id: str, browser_id: str, rules: List[Dict[str, Any]], target_id: str = ""
    ) -> Dict[str, Any]:
        """Install request-interception rules — ``{url_pattern, action:
        "continue"|"block"|"mock", ...}`` with caller-set ``id`` → ``{ok: true}``."""
        _validate_runtime_id(runtime_id)
        return await self._j(
            "POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/intercept", {"target_id": target_id, "rules": rules}
        )

    async def intercept_clear(
        self, runtime_id: str, browser_id: str, rule_ids: Optional[List[str]] = None, target_id: str = ""
    ) -> Dict[str, Any]:
        """Remove interception rules — empty clears all."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        if rule_ids:
            body["rule_ids"] = rule_ids
        if target_id:
            body["target_id"] = target_id
        return await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/intercept/clear", body)

    async def auth(
        self,
        runtime_id: str,
        browser_id: str,
        username: str = "",
        password: str = "",
        secret_ref: str = "",
        clear: bool = False,
        target_id: str = "",
    ) -> Dict[str, Any]:
        """Answer HTTP basic/digest challenges — ``secret_ref`` resolves the
        password server-side; ``clear`` disarms."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        if username:
            body["username"] = username
        if secret_ref:
            body["secret_ref"] = secret_ref
        elif password:
            body["password"] = password
        if clear:
            body["clear"] = True
        if target_id:
            body["target_id"] = target_id
        return await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/auth", body)

    # -- extensions + CDP ------------------------------------------------------

    async def extension_load(self, runtime_id: str, browser_id: str, path: str) -> Dict[str, Any]:
        """Hot-load an unpacked extension from a guest directory →
        ``{extension_id}``."""
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/extensions/load", {"path": path})

    async def extension_unload(self, runtime_id: str, browser_id: str, extension_id: str) -> Dict[str, Any]:
        """Unload an extension by id."""
        _validate_runtime_id(runtime_id)
        return await self._j(
            "POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/extensions/unload", {"extension_id": extension_id}
        )

    async def cdp_endpoint(self, runtime_id: str, browser_id: str, port: int = 0, token: str = "") -> Dict[str, Any]:
        """Start a tokened CDP WebSocket bridge → ``{port, path, token}`` —
        raw-protocol attach for external drivers."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        if port:
            body["port"] = port
        if token:
            body["token"] = token
        return await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/cdp_endpoint", body)

    async def cdp_endpoint_stop(self, runtime_id: str, browser_id: str) -> Dict[str, Any]:
        """Tear down the CDP bridge."""
        _validate_runtime_id(runtime_id)
        return await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/cdp_endpoint/stop", {})

    # -- approvals --------------------------------------------------------------

    async def approval_request(
        self, runtime_id: str, browser_id: str, message: str, timeout_ms: int = 0
    ) -> Dict[str, Any]:
        """Ask an operator for approval — parks until resolved or the
        timeout lapses → ``{approval_id, resolved, approved?}``."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"message": message}
        if timeout_ms:
            body["timeout_ms"] = timeout_ms
        return await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/approvals", body)

    async def approval_resolve(
        self, runtime_id: str, browser_id: str, approval_id: str, approved: bool, note: str = ""
    ) -> Dict[str, Any]:
        """Resolve a pending approval."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"approved": approved}
        if note:
            body["note"] = note
        return await self._j(
            "POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/approvals/{_q(approval_id)}/resolve", body
        )

    # -- reads: content + cookies ------------------------------------------------

    async def content(self, runtime_id: str, browser_id: str, target_id: str = "", format: str = "") -> Dict[str, Any]:
        """Serialized page content — rendered HTML by default."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"target_id": target_id}
        if format:
            body["format"] = format
        return await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/content", body)

    async def cookies(self, runtime_id: str, browser_id: str, context_id: str = "", url: str = "") -> Dict[str, Any]:
        """List the context's cookies."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        if context_id:
            body["context_id"] = context_id
        if url:
            body["url"] = url
        return await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/cookies", body)

    async def set_cookie(
        self,
        runtime_id: str,
        browser_id: str,
        name: str,
        value: str,
        url: str = "",
        context_id: str = "",
        attrs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Set one cookie — ``url`` scopes it, ``attrs`` carries
        domain/path/secure/expiry fields."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"op": "set", "name": name, "value": value}
        if url:
            body["url"] = url
        if context_id:
            body["context_id"] = context_id
        if attrs:
            body["attrs"] = attrs
        return await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/cookies", body)

    async def delete_cookie(
        self, runtime_id: str, browser_id: str, name: str, url: str = "", context_id: str = ""
    ) -> Dict[str, Any]:
        """Delete one cookie by name."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"op": "delete", "name": name}
        if url:
            body["url"] = url
        if context_id:
            body["context_id"] = context_id
        return await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/cookies", body)

    async def clear_cookies(self, runtime_id: str, browser_id: str, context_id: str = "") -> Dict[str, Any]:
        """Clear every cookie in the context."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"op": "clear"}
        if context_id:
            body["context_id"] = context_id
        return await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/cookies", body)

    # -- downloads, recording, profile, replay, fork -----------------------------

    async def download_delete(
        self, runtime_id: str, browser_id: str, download_id: str, delete_file: bool = False
    ) -> Dict[str, Any]:
        """Drop a download record; ``delete_file`` removes the guest file."""
        _validate_runtime_id(runtime_id)
        endpoint = f"runtime/{runtime_id}/browser/{_q(browser_id)}" f"/downloads/{_q(download_id)}"
        if delete_file:
            endpoint += "?delete_file=true"
        return await self._j("DELETE", endpoint)

    async def recording_start(
        self, runtime_id: str, browser_id: str, target_id: str, fps: int = 0, quality: int = 0
    ) -> Dict[str, Any]:
        """Start a per-target video recording (works headless)."""
        _validate_runtime_id(runtime_id)
        return await self._j(
            "POST",
            f"runtime/{runtime_id}/browser/{_q(browser_id)}/targets/{_q(target_id)}/recording/start",
            {k: v for k, v in (("fps", fps), ("quality", quality)) if v},
        )

    async def recording_stop(self, runtime_id: str, browser_id: str, target_id: str) -> Dict[str, Any]:
        """Stop a target recording → sealed artifact metadata."""
        _validate_runtime_id(runtime_id)
        return await self._j(
            "POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/targets/{_q(target_id)}/recording/stop", {}
        )

    async def recording_export(
        self, runtime_id: str, browser_id: str, recording_id: str, dest_dir: str
    ) -> Dict[str, Any]:
        """Copy a finished recording's artifacts into ``dest_dir``."""
        _validate_runtime_id(runtime_id)
        return await self._j(
            "POST",
            f"runtime/{runtime_id}/browser/{_q(browser_id)}/recordings/export",
            {"recording_id": recording_id, "dest_dir": dest_dir},
        )

    async def profile_export(self, runtime_id: str, browser_id: str, dest_path: str = "") -> Dict[str, Any]:
        """Quiesce and tar the browser's profile → ``dest_path``."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {}
        if dest_path:
            body["dest_path"] = dest_path
        return await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/profile/export", body)

    async def profile_import(self, runtime_id: str, browser_id: str, archive_path: str) -> Dict[str, Any]:
        """Respawn the browser against a previously exported profile tar."""
        _validate_runtime_id(runtime_id)
        return await self._j(
            "POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/profile/import", {"archive_path": archive_path}
        )

    async def replay(
        self,
        runtime_id: str,
        browser_id: str,
        steps: List[Dict[str, Any]],
        stop_on_fail: bool = False,
        step_timeout_ms: int = 0,
        target_id: str = "",
    ) -> Dict[str, Any]:
        """Replay recorded action steps with per-step effect checks."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"steps": steps, "stop_on_fail": stop_on_fail}
        if step_timeout_ms:
            body["step_timeout_ms"] = step_timeout_ms
        if target_id:
            body["target_id"] = target_id
        return await self._j(
            "POST",
            f"runtime/{runtime_id}/browser/{_q(browser_id)}/replay",
            body,
        )

    async def fork(
        self, runtime_id: str, browser_id: str, count: int = 1, url: str = "", target_id: str = ""
    ) -> Dict[str, Any]:
        """Fork the page into a cohort of identical targets (1–8)."""
        _validate_runtime_id(runtime_id)
        body: Dict[str, Any] = {"count": count}
        if url:
            body["url"] = url
        if target_id:
            body["target_id"] = target_id
        return await self._j("POST", f"runtime/{runtime_id}/browser/{_q(browser_id)}/fork", body)
