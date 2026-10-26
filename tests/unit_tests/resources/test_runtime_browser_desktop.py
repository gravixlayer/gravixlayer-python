"""
Tests for the computer-use planes: ``client.runtime.desktop`` (pixels + input)
and ``client.runtime.browser`` (semantic control).
"""

import base64
import json

import httpx
import pytest
from urllib.parse import parse_qs

from tests.utils import AGENTS_BASE, TEST_API_KEY, TEST_BASE_URL, VALID_UUID

from gravixlayer import AsyncGravixLayer, GravixLayer


SB = f"{AGENTS_BASE}/runtime"
BID = "b1"


# ===================================================================
# Sync — display plane
# ===================================================================


class TestSyncDisplay:
    def test_enable(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/enable").mock(
            return_value=httpx.Response(200, json={"enabled": True, "width": 1920})
        )
        r = client.runtime.desktop.enable(VALID_UUID, width=1920, height=1080)
        assert r["enabled"] is True
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["width"] == 1920 and body["height"] == 1080

    def test_status(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/display/status").mock(
            return_value=httpx.Response(200, json={"enabled": True})
        )
        assert client.runtime.desktop.status(VALID_UUID)["enabled"] is True

    def test_screenshot_wait_stable(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/screenshot").mock(
            return_value=httpx.Response(
                200, json={"data": base64.b64encode(b"PNG").decode(), "format": "png"}
            )
        )
        r = client.runtime.desktop.screenshot(
            VALID_UUID, format="png", wait_stable_ms=300, timeout_ms=5000
        )
        assert base64.b64decode(r["data"]) == b"PNG"
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["wait_stable_ms"] == 300 and body["timeout_ms"] == 5000

    def test_click(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/click").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.runtime.desktop.click(VALID_UUID, 100, 200, button="left")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["x"] == 100 and body["y"] == 200 and body["button"] == "left"

    def test_hotkey(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/keyboard/hotkey").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.runtime.desktop.hotkey(VALID_UUID, ["ctrl", "c"])
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["keys"] == ["ctrl", "c"]

    def test_view(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/view").mock(
            return_value=httpx.Response(200, json={"port": 9871})
        )
        assert client.runtime.desktop.view(VALID_UUID)["port"] == 9871

    def test_act(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/act").mock(
            return_value=httpx.Response(
                200,
                json={
                    "settled": True,
                    "rev": 42,
                    "screenshot": {"data": "UE5H", "format": "png", "rev": 42},
                },
            )
        )
        r = client.runtime.desktop.act(
            VALID_UUID,
            actions=[
                {"kind": "click", "mouse": {"x": 10, "y": 20, "button": "left"}},
                {"kind": "type", "key": {"text": "hi"}},
            ],
            settle_ms=200,
            timeout_ms=5000,
            observe={"format": "png", "if_rev": 41},
        )
        assert r["settled"] is True and r["rev"] == 42
        body = json.loads(mock_api.calls[-1].request.content)
        assert len(body["actions"]) == 2
        assert body["settle_ms"] == 200 and body["timeout_ms"] == 5000
        assert body["observe"]["if_rev"] == 41

    def test_screenshot_if_rev(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/screenshot").mock(
            return_value=httpx.Response(
                200, json={"data": "", "rev": 7, "unchanged": True}
            )
        )
        r = client.runtime.desktop.screenshot(VALID_UUID, if_rev=7)
        assert r["unchanged"] is True
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["if_rev"] == 7

    def test_resize(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/resize").mock(
            return_value=httpx.Response(200, json={"width": 1280, "height": 720})
        )
        r = client.runtime.desktop.resize(VALID_UUID, 1280, 720)
        assert r["width"] == 1280
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"width": 1280, "height": 720}

    def test_windows(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/display/windows").mock(
            return_value=httpx.Response(
                200,
                json={
                    "windows": [
                        {"id": 2097155, "title": "Terminal", "focused": True}
                    ],
                    "focused": 2097155,
                },
            )
        )
        r = client.runtime.desktop.windows(VALID_UUID, window_class="term")
        assert r["focused"] == 2097155
        assert "window_class=term" in str(mock_api.calls[-1].request.url)

    def test_windows_encodes_class_filter(self, client, mock_api):
        # A class containing query characters must not corrupt the URL —
        # "A&B" unencoded would inject a second parameter and silently
        # widen the filter. Assert on the decoded value so the exact
        # escape form (%20 vs +) stays an implementation detail.
        mock_api.get(f"{SB}/{VALID_UUID}/display/windows").mock(
            return_value=httpx.Response(200, json={"windows": [], "focused": 0})
        )
        client.runtime.desktop.windows(VALID_UUID, window_class="A&B +x")
        query = parse_qs(mock_api.calls[-1].request.url.query.decode())
        assert query["window_class"] == ["A&B +x"]
        assert list(query) == ["window_class"]  # no parameter injection

    def test_window_op(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/windows/op").mock(
            return_value=httpx.Response(200, json={"id": 1, "x": 10, "y": 20})
        )
        client.runtime.desktop.move_window(VALID_UUID, 1, 10, 20)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"id": 1, "op": "move", "x": 10, "y": 20}
        client.runtime.desktop.window_op(VALID_UUID, 1, "maximize")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"id": 1, "op": "maximize"}
        client.runtime.desktop.window_op(VALID_UUID, 1, "fullscreen")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"id": 1, "op": "fullscreen"}
        client.runtime.desktop.resize_window(VALID_UUID, 1, 400, 300)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"id": 1, "op": "resize", "w": 400, "h": 300}

    def test_apps_and_launch(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/display/apps").mock(
            return_value=httpx.Response(
                200,
                json={"apps": [{"id": "org.xterm", "name": "XTerm"}]},
            )
        )
        assert client.runtime.desktop.apps(VALID_UUID)["apps"][0]["name"] == "XTerm"
        mock_api.post(f"{SB}/{VALID_UUID}/display/apps/launch").mock(
            return_value=httpx.Response(
                200, json={"pid": 4242, "window_id": 2097155, "app": "org.xterm"}
            )
        )
        r = client.runtime.desktop.launch_app(
            VALID_UUID, "org.xterm", wait_window=True, timeout_ms=8000
        )
        assert r["pid"] == 4242 and r["window_id"] == 2097155
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["wait_window"] is True and body["timeout_ms"] == 8000

    def test_open(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/open").mock(
            return_value=httpx.Response(
                200,
                json={
                    "pid": 1,
                    "window_id": 0,
                    "app": "org.mozilla.firefox",
                    "mime": "text/html",
                },
            )
        )
        r = client.runtime.desktop.open(VALID_UUID, "https://example.com")
        assert r["mime"] == "text/html"
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["target"] == "https://example.com"

    def test_clipboard_image(self, client, mock_api):
        png = base64.b64encode(b"PNGBYTES").decode()
        mock_api.post(f"{SB}/{VALID_UUID}/display/clipboard").mock(
            return_value=httpx.Response(200, json={"text": "", "png": png})
        )
        assert client.runtime.desktop.clipboard_image(VALID_UUID) == b"PNGBYTES"
        client.runtime.desktop.set_clipboard_image(VALID_UUID, b"PNGBYTES")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"op": "set", "png": png}

    def test_view_window(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/view").mock(
            return_value=httpx.Response(200, json={"port": 9871})
        )
        client.runtime.desktop.view(VALID_UUID, window_id=2097155)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["window_id"] == 2097155


# ===================================================================
# Sync — browser plane
# ===================================================================


class TestSyncBrowser:
    def test_open_default_headed(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/open").mock(
            return_value=httpx.Response(
                200, json={"browser_id": BID, "engine": "chromium", "headless": False}
            )
        )
        r = client.runtime.browser.open(VALID_UUID)
        assert r["browser_id"] == BID
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["engine"] == "chromium" and body["headless"] is False

    def test_navigate_wait_until(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/navigate").mock(
            return_value=httpx.Response(200, json={"url": "https://x.io", "settled": True})
        )
        r = client.runtime.browser.navigate(VALID_UUID, BID, "https://x.io", wait_until="load")
        assert r["settled"] is True
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["url"] == "https://x.io" and body["wait_until"] == "load"

    def test_click_by_ref(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/actions/click").mock(
            return_value=httpx.Response(
                200, json={"ok": True, "navigated": False, "settled": True}
            )
        )
        r = client.runtime.browser.click(VALID_UUID, BID, "e3")
        assert r["ok"] is True
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["verb"] == "click"
        assert body["target"] == {"by": "ref", "value": "e3"}

    def test_click_by_coords(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/actions/click").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.runtime.browser.click(VALID_UUID, BID, (220, 340))
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["target"]["by"] == "coords"
        assert body["target"]["attrs"]["x"] == "220"

    def test_fill_secret_ref_never_serializes_secret(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/actions/fill").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.runtime.browser.fill(VALID_UUID, BID, "e7", secret_ref="ssv_abc")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["secret_ref"] == "ssv_abc"
        assert "text" not in body

    def test_snapshot_viewport_only(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/snapshot").mock(
            return_value=httpx.Response(
                200,
                json={
                    "url": "https://x.io",
                    "elements": [{"ref": "e1", "role": "button", "name": "Export"}],
                },
            )
        )
        r = client.runtime.browser.snapshot(VALID_UUID, BID)
        assert r["elements"][0]["ref"] == "e1"
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["viewport_only"] is True

    def test_evaluate(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/evaluate").mock(
            return_value=httpx.Response(200, json={"value": "42", "is_error": False})
        )
        r = client.runtime.browser.evaluate(VALID_UUID, BID, "document.title")
        assert r["value"] == "42"
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["expression"] == "document.title"

    def test_downloads_wait(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/downloads").mock(
            return_value=httpx.Response(
                200, json={"downloads": [{"id": "d1", "filename": "report.csv"}]}
            )
        )
        r = client.runtime.browser.downloads(VALID_UUID, BID, wait_name="report.csv")
        assert r["downloads"][0]["filename"] == "report.csv"
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["wait_name"] == "report.csv"

    def test_pdf(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/targets/t1/pdf").mock(
            return_value=httpx.Response(
                200, json={"data": base64.b64encode(b"%PDF").decode(), "format": "pdf"}
            )
        )
        r = client.runtime.browser.pdf(VALID_UUID, BID, "t1")
        assert base64.b64decode(r["data"]) == b"%PDF"

    def test_dialog_answers_by_default(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/dialog").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.runtime.browser.dialog(VALID_UUID, BID)
        body = json.loads(mock_api.calls[-1].request.content)
        # auto_dismiss=False → the call answers (accept+prompt_text) rather
        # than dismissing.
        assert body["auto_dismiss"] is False and body["accept"] is True

    def test_dialog_auto_dismiss_opt_in(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/dialog").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.runtime.browser.dialog(VALID_UUID, BID, auto_dismiss=True)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["auto_dismiss"] is True

    def test_screenshot_quality_kwarg(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/screenshot").mock(
            return_value=httpx.Response(200, json={"data": "", "format": "jpeg"})
        )
        client.runtime.browser.screenshot(VALID_UUID, BID, format="jpeg", quality=70)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["quality"] == 70 and body["format"] == "jpeg"


# ===================================================================
# Async — the same surface awaits identically
# ===================================================================


class TestAsyncBrowser:
    @pytest.mark.asyncio
    async def test_open_and_action(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/open").mock(
            return_value=httpx.Response(200, json={"browser_id": BID})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/actions/click").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            await client.runtime.browser.open(VALID_UUID)
            r = await client.runtime.browser.click(VALID_UUID, BID, "e3")
        assert r["ok"] is True
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["target"]["by"] == "ref"

    @pytest.mark.asyncio
    async def test_display_screenshot(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/screenshot").mock(
            return_value=httpx.Response(200, json={"data": "", "format": "png"})
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            await client.runtime.desktop.screenshot(VALID_UUID, wait_stable_ms=100)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["wait_stable_ms"] == 100

    @pytest.mark.asyncio
    async def test_display_act_and_windows(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/act").mock(
            return_value=httpx.Response(200, json={"settled": True, "rev": 3})
        )
        mock_api.get(f"{SB}/{VALID_UUID}/display/windows").mock(
            return_value=httpx.Response(
                200, json={"windows": [{"id": 5}], "focused": 5}
            )
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            r = await client.runtime.desktop.act(
                VALID_UUID,
                actions=[{"kind": "click", "mouse": {"x": 1, "y": 2}}],
            )
            assert r["settled"] is True and r["rev"] == 3
            w = await client.runtime.desktop.windows(VALID_UUID)
            assert w["focused"] == 5
            # Async path encodes the class filter too.
            await client.runtime.desktop.windows(VALID_UUID, window_class="x&y")
            assert "window_class=x%26y" in str(mock_api.calls[-1].request.url)

    @pytest.mark.asyncio
    async def test_display_open_launch_resize(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/open").mock(
            return_value=httpx.Response(200, json={"pid": 9, "app": "x", "mime": "m"})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/display/apps/launch").mock(
            return_value=httpx.Response(200, json={"pid": 8, "window_id": 4, "app": "a"})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/display/resize").mock(
            return_value=httpx.Response(200, json={"width": 800, "height": 600})
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            assert (await client.runtime.desktop.open(VALID_UUID, "f.pdf"))["pid"] == 9
            assert (await client.runtime.desktop.launch_app(
                VALID_UUID, "a", wait_window=True))["window_id"] == 4
            assert (await client.runtime.desktop.resize(
                VALID_UUID, 800, 600))["height"] == 600

    @pytest.mark.asyncio
    async def test_display_clipboard_image(self, mock_api):
        png = base64.b64encode(b"IMG").decode()
        mock_api.post(f"{SB}/{VALID_UUID}/display/clipboard").mock(
            return_value=httpx.Response(200, json={"png": png})
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            assert await client.runtime.desktop.clipboard_image(VALID_UUID) == b"IMG"


class TestGotoAndVerbs:
    def test_goto_opens_once_then_navigates(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/open").mock(
            return_value=httpx.Response(200, json={"browser_id": BID})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/navigate").mock(
            return_value=httpx.Response(200, json={"url": "https://x", "navigated": True})
        )
        with GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.runtime.browser.goto(VALID_UUID, "https://x")
            client.runtime.browser.goto(VALID_UUID, "https://y")
        # 1 open + 2 navigates — the browser is reused, not reopened
        assert len(mock_api.calls) == 3

    def test_dblclick_and_hover_verbs(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/actions/dblclick").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/actions/hover").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        with GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.runtime.browser.dblclick(VALID_UUID, BID, "e1")
            client.runtime.browser.hover(VALID_UUID, BID, (5, 5))
        d = json.loads(mock_api.calls[0].request.content)
        h = json.loads(mock_api.calls[1].request.content)
        assert d["verb"] == "dblclick" and h["verb"] == "hover"
        assert h["target"]["by"] == "coords" and h["target"]["attrs"]["x"] == "5"

    def test_close_drops_cached_default(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/open").mock(
            return_value=httpx.Response(200, json={"browser_id": BID})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/close").mock(
            return_value=httpx.Response(200, json={})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/navigate").mock(
            return_value=httpx.Response(200, json={"navigated": True})
        )
        with GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.runtime.browser.goto(VALID_UUID, "https://x")
            client.runtime.browser.close(VALID_UUID, BID)
            client.runtime.browser.goto(VALID_UUID, "https://y")
        # 2 opens — close cleared the cached default
        opens = [c for c in mock_api.calls if "/browser/open" in c.request.url.path]
        assert len(opens) == 2


class TestBoundHandles:
    """runtime.browser / runtime.desktop bound to the Runtime object."""

    def test_bound_browser_exists(self):
        from gravixlayer.types.runtime import Runtime
        r = Runtime(runtime_id=VALID_UUID, status="running")
        assert type(r.browser).__name__ == "RuntimeBrowserBound"

    def test_bound_display_exists(self):
        from gravixlayer.types.runtime import Runtime
        r = Runtime(runtime_id=VALID_UUID, status="running")
        assert type(r.desktop).__name__ == "RuntimeDesktopBound"

    def test_bound_scroll_sends_deltas(self, client, mock_api):
        """Bound scroll must forward dx/dy — and no pointer position when unset."""
        from gravixlayer.types.runtime import Runtime
        rt = Runtime(runtime_id=VALID_UUID, status="running")
        rt._client = client
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/scroll").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        rt.desktop.scroll(dy=-480)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["dy"] == -480 and body["dx"] == 0
        assert "x" not in body and "y" not in body

    def test_bound_scroll_positional_is_deltas(self, client, mock_api):
        """Positional args are deltas — same call shape as the TS bound view."""
        from gravixlayer.types.runtime import Runtime
        rt = Runtime(runtime_id=VALID_UUID, status="running")
        rt._client = client
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/scroll").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        rt.desktop.scroll(24, -480)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["dx"] == 24 and body["dy"] == -480

    def test_bound_scroll_position_still_forwards(self, client, mock_api):
        """x/y stay the optional pointer position."""
        from gravixlayer.types.runtime import Runtime
        rt = Runtime(runtime_id=VALID_UUID, status="running")
        rt._client = client
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/scroll").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        rt.desktop.scroll(x=100, y=200, dy=600)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["x"] == 100 and body["y"] == 200 and body["dy"] == 600

    def test_scroll_resource_sends_only_given_axes(self, client, mock_api):
        """The wire distinguishes 'unset' from 0 — an x=0 scroll position is
        real input, while an absent axis keeps the current pointer."""
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/scroll").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.runtime.desktop.scroll(VALID_UUID, dy=-480)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"dx": 0, "dy": -480}

        client.runtime.desktop.scroll(VALID_UUID, x=0, dy=-480)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"x": 0, "dx": 0, "dy": -480}

    def test_bound_browser_fill_positional_text(self, client, mock_api):
        """fill(bid, target, text) — text is positional, same as type()."""
        from gravixlayer.types.runtime import Runtime
        rt = Runtime(runtime_id=VALID_UUID, status="running")
        rt._client = client
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/actions/fill").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        rt.browser.fill(BID, "e7", "hunter2")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["verb"] == "fill" and body["text"] == "hunter2"
        assert "secret_ref" not in body

    def test_bound_browser_targets_open_tab(self, client, mock_api):
        """targets(url=…) opens a tab — the bound handle must forward it."""
        from gravixlayer.types.runtime import Runtime
        rt = Runtime(runtime_id=VALID_UUID, status="running")
        rt._client = client
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/targets").mock(
            return_value=httpx.Response(
                200, json={"targets": [{"target_id": "t9", "url": "https://x.io"}]}
            )
        )
        r = rt.browser.targets(BID, url="https://x.io", activate=False)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"url": "https://x.io", "activate": False}
        assert r["targets"][0]["target_id"] == "t9"

    def test_bound_browser_verbs_hit_command_routes(self, client, mock_api):
        """back/forward/reload/activate map onto the shared verb route."""
        from gravixlayer.types.runtime import Runtime
        rt = Runtime(runtime_id=VALID_UUID, status="running")
        rt._client = client
        for verb in ("back", "forward", "reload", "activate"):
            mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/{verb}").mock(
                return_value=httpx.Response(200, json={"target_id": "t1"})
            )
        rt.browser.back(BID)
        rt.browser.forward(BID)
        rt.browser.reload(BID)
        rt.browser.activate(BID, "t1")
        urls = [c.request.url.path for c in mock_api.calls[-4:]]
        assert urls == [
            f"/v1/agents/runtime/{VALID_UUID}/browser/{BID}/{v}"
            for v in ("back", "forward", "reload", "activate")
        ]
        assert json.loads(mock_api.calls[-1].request.content)["target_id"] == "t1"

    def test_browser_command_generic_verb(self, client, mock_api):
        """command(verb) hits the same route as the named verb methods."""
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/back").mock(
            return_value=httpx.Response(200, json={"target_id": "t1"})
        )
        client.runtime.browser.command(VALID_UUID, BID, "back", "t1")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"target_id": "t1", "verb": "back"}

    def test_browser_command_rejects_unknown_verb(self, client, mock_api):
        with pytest.raises(ValueError, match="verb must be one of"):
            client.runtime.browser.command(VALID_UUID, BID, "dematerialize")
        assert not mock_api.calls

    def test_bound_browser_command(self, client, mock_api):
        from gravixlayer.types.runtime import Runtime
        rt = Runtime(runtime_id=VALID_UUID, status="running")
        rt._client = client
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/forward").mock(
            return_value=httpx.Response(200, json={"target_id": "t2"})
        )
        rt.browser.command(BID, "forward")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"target_id": "", "verb": "forward"}

    def test_enable_omits_unset_geometry(self, client, mock_api):
        """Zero values defer to the platform default instead of pinning it."""
        mock_api.post(f"{SB}/{VALID_UUID}/display/enable").mock(
            return_value=httpx.Response(200, json={"enabled": True})
        )
        client.runtime.desktop.enable(VALID_UUID)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {}

        client.runtime.desktop.enable(VALID_UUID, width=2560, depth=30)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"width": 2560, "depth": 30}

    def test_view_rotate_token_flag(self, client, mock_api):
        """rotate_token mints a fresh watch URL on a repeat view call."""
        mock_api.post(f"{SB}/{VALID_UUID}/display/view").mock(
            return_value=httpx.Response(201, json={"url": "u", "browser_url": "b", "port": 1})
        )
        client.runtime.desktop.view(VALID_UUID, rotate_token=True)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["rotate_token"] is True


class TestWireParams:
    """Every wire field the fabric reads must be sendable from the SDK."""

    def test_evaluate_sends_world(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/b1/evaluate").mock(
            return_value=httpx.Response(200, json={"value": "2"})
        )
        client.runtime.browser.evaluate(VALID_UUID, BID, "1+1", world="main")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["world"] == "main"

    def test_action_sends_force_and_timeouts(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/b1/actions/click").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.runtime.browser.click(VALID_UUID, BID, "e3", force=True,
                                     target_timeout_ms=500)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["force"] is True
        assert body["target_timeout_ms"] == 500

    def test_download_meta_only(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/browser/b1/downloads/d9").mock(
            return_value=httpx.Response(200, json={"entry": {"id": "d9"}, "data": None})
        )
        client.runtime.browser.download(VALID_UUID, BID, "d9", meta_only=True)
        assert mock_api.calls[-1].request.url.path.endswith("/downloads/d9")
        assert b"meta_only=true" in mock_api.calls[-1].request.url.query

    def test_pdf_margins(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/b1/targets/t1/pdf").mock(
            return_value=httpx.Response(200, json={"data": ""})
        )
        client.runtime.browser.pdf(VALID_UUID, BID, "t1",
                                   margins_in={"top": 0.4, "left": 0.25})
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["margin_top_in"] == 0.4
        assert body["margin_left_in"] == 0.25

    def test_activate_route(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/b1/activate").mock(
            return_value=httpx.Response(200, json={"target_id": "t9"})
        )
        client.runtime.browser.activate(VALID_UUID, BID, "t9")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["target_id"] == "t9"

    def test_goto_retries_dead_browser(self, client, mock_api):
        """A remembered-but-dead browser → evict → reopen → navigate."""
        # first open returns b1; navigate on b1 404s; reopen returns b2; navigate ok
        mock_api.post(f"{SB}/{VALID_UUID}/browser/open").mock(
            side_effect=[
                httpx.Response(200, json={"browser_id": "b1"}),
                httpx.Response(200, json={"browser_id": "b2"}),
            ]
        )
        mock_api.post(f"{SB}/{VALID_UUID}/browser/b1/navigate").mock(
            return_value=httpx.Response(404, json={"error": "browser not found"})
        )
        nav2 = mock_api.post(f"{SB}/{VALID_UUID}/browser/b2/navigate").mock(
            return_value=httpx.Response(200, json={"url": "https://x", "navigated": True})
        )
        r = client.runtime.browser.goto(VALID_UUID, "https://x")
        assert r["navigated"] is True
        assert nav2.called

    def test_view_watch_role_composes_watch_url(self, client, mock_api):
        """role=watch goes on the wire; the minted vt capability lands on
        watch_url — a shared link can never arrive un-tokened."""
        mock_api.post(f"{SB}/{VALID_UUID}/browser/b1/view").mock(
            return_value=httpx.Response(201, json={
                "url": "https://x.service.example/",
                "browser_url": "https://x.service.example/_ws/auth?token=t",
                "port": 9871, "view_token": "vt-watch-1",
            })
        )
        r = client.runtime.browser.view(VALID_UUID, BID, role="watch")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["role"] == "watch"
        assert r["view_token"] == "vt-watch-1"
        assert r["watch_url"].endswith("token=t&vt=vt-watch-1")

    def test_view_default_omits_role(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/b1/view").mock(
            return_value=httpx.Response(201, json={
                "browser_url": "https://x.service.example/_ws/auth?token=t",
                "port": 9871, "view_token": "vt-ctl",
            })
        )
        r = client.runtime.browser.view(VALID_UUID, BID)
        body = json.loads(mock_api.calls[-1].request.content)
        assert "role" not in body
        # A control token still composes — headed feeds require vt=.
        assert r["watch_url"].endswith("vt=vt-ctl")

    def test_path_segments_are_encoded(self, client, mock_api):
        """Caller ids must never inject `/`, `?` or `#` into a route path."""
        mock_api.get(f"{SB}/{VALID_UUID}/browser/b%2F1/downloads/d%3F9").mock(
            return_value=httpx.Response(200, json={"entry": {"id": "d?9"}})
        )
        client.runtime.browser.download(VALID_UUID, "b/1", "d?9")
        raw = mock_api.calls[-1].request.url.raw_path.decode()
        assert raw.endswith("/browser/b%2F1/downloads/d%3F9"), raw
        assert "?" not in raw and raw.count("/downloads/") == 1


# ===================================================================
# CU1 — extended display + desktop session planes
# ===================================================================


class TestDisplayCU1:
    def test_enable_attach_mode(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/enable").mock(
            return_value=httpx.Response(200, json={"enabled": True, "attached": True})
        )
        r = client.runtime.desktop.enable(VALID_UUID, display=":1", mode="attach")
        assert r["attached"] is True
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["mode"] == "attach" and body["display"] == ":1"

    def test_info_and_position(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/display/info").mock(
            return_value=httpx.Response(200, json={"enabled": True, "dpi": 96, "attached": True})
        )
        mock_api.get(f"{SB}/{VALID_UUID}/display/position").mock(
            return_value=httpx.Response(200, json={"x": 41, "y": 88})
        )
        assert client.runtime.desktop.info(VALID_UUID)["attached"] is True
        assert client.runtime.desktop.position(VALID_UUID) == {"x": 41, "y": 88}

    def test_keys(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/display/keys").mock(
            return_value=httpx.Response(200, json={"keys": ["enter", "f5"]})
        )
        assert client.runtime.desktop.keys(VALID_UUID)["keys"] == ["enter", "f5"]

    def test_screenshot_fit_cursor_and_scale(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/screenshot").mock(
            return_value=httpx.Response(200, json={"data": "", "format": "webp", "scale": 0.5})
        )
        client.runtime.desktop.screenshot(
            VALID_UUID, format="webp", max_width=960, max_height=960, cursor=True
        )
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["format"] == "webp" and body["cursor"] is True
        assert body["max_width"] == 960 and body["max_height"] == 960

    def test_click_modifiers_count_space(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/click").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.runtime.desktop.click(
            VALID_UUID, 640, 360, click_count=2,
            modifiers=["ctrl"], coordinate_space="screenshot",
        )
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["click_count"] == 2
        assert body["modifiers"] == ["ctrl"]
        assert body["coordinate_space"] == "screenshot"

    def test_click_no_coords_keeps_pointer(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/click").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.runtime.desktop.click(VALID_UUID)
        body = json.loads(mock_api.calls[-1].request.content)
        assert "x" not in body and "y" not in body

    def test_down_up_drag(self, client, mock_api):
        for tail in ("down", "up", "drag"):
            mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/{tail}").mock(
                return_value=httpx.Response(200, json={"ok": True})
            )
        client.runtime.desktop.down(VALID_UUID, 10, 10, modifiers=["shift"])
        client.runtime.desktop.up(VALID_UUID)
        client.runtime.desktop.drag(VALID_UUID, 400, 300, x=10, y=10,
                                    steps=8, duration_ms=200)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["to_x"] == 400 and body["to_y"] == 300
        assert body["x"] == 10 and body["steps"] == 8 and body["duration_ms"] == 200

    def test_type_paste_mode(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/keyboard/type").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.runtime.desktop.type(VALID_UUID, "big block", mode="paste")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["text"] == "big block" and body["mode"] == "paste"

    def test_press_and_hotkey_modifiers(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/keyboard/press").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/display/keyboard/hotkey").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.runtime.desktop.press(VALID_UUID, "enter", modifiers=["ctrl"])
        assert json.loads(mock_api.calls[-1].request.content)["modifiers"] == ["ctrl"]
        client.runtime.desktop.hotkey(VALID_UUID, ["f4"], modifiers=["alt"])
        assert json.loads(mock_api.calls[-1].request.content)["modifiers"] == ["alt"]

    def test_clipboard_get_set(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/clipboard").mock(
            return_value=httpx.Response(200, json={"text": "hello"})
        )
        assert client.runtime.desktop.get_clipboard(VALID_UUID) == "hello"
        client.runtime.desktop.set_clipboard(VALID_UUID, "world")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"op": "set", "text": "world"}

    def test_view_role_and_stop(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/view").mock(
            return_value=httpx.Response(200, json={"url": "u", "view_token": "vt-1"})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/display/view/stop").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        r = client.runtime.desktop.view(VALID_UUID, role="watch")
        assert r["view_token"] == "vt-1"
        assert json.loads(mock_api.calls[-1].request.content)["role"] == "watch"
        client.runtime.desktop.stop_view(VALID_UUID)


class TestDesktopCU1:
    def test_status(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/desktop/status").mock(
            return_value=httpx.Response(200, json={
                "present": True, "display": ":1", "user": "agent",
                "components": [{"name": "display", "unit": "xvfb.service",
                                "state": "active", "sub_state": "running"}],
            })
        )
        s = client.runtime.desktop.components(VALID_UUID)
        assert s["present"] is True
        assert s["components"][0]["unit"] == "xvfb.service"

    def test_component_ops(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/desktop/component").mock(
            return_value=httpx.Response(200, json={"name": "session", "state": "active"})
        )
        client.runtime.desktop.restart_component(VALID_UUID, "session")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"name": "session", "op": "restart"}
        client.runtime.desktop.stop_component(VALID_UUID, "session")
        assert json.loads(mock_api.calls[-1].request.content)["op"] == "stop"

    def test_logs_pagination(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/desktop/logs").mock(
            return_value=httpx.Response(200, json={
                "entries": [{"timestamp": "t", "message": "m", "priority": 3}],
                "next_cursor": "c2", "truncated": True,
            })
        )
        page = client.runtime.desktop.logs(
            VALID_UUID, "display", cursor="c1", max_entries=100, priority="err")
        assert page["next_cursor"] == "c2"
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"name": "display", "cursor": "c1", "max": 100, "priority": "err"}


# ===================================================================
# Merged desktop surface — conveniences + session ops (sync + async)
# ===================================================================


class TestDesktopConveniences:
    """Simple mouse/keyboard conveniences wire to the display routes."""

    def test_left_click(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/click").mock(
            return_value=httpx.Response(200, json={})
        )
        client.runtime.desktop.left_click(VALID_UUID, x=10, y=20)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["button"] == "left" and body["x"] == 10 and body["y"] == 20

    def test_double_click(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/click").mock(
            return_value=httpx.Response(200, json={})
        )
        client.runtime.desktop.double_click(VALID_UUID, x=5, y=6)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["click_count"] == 2 and body["button"] == "left"

    def test_right_and_middle_click(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/click").mock(
            return_value=httpx.Response(200, json={})
        )
        client.runtime.desktop.right_click(VALID_UUID)
        client.runtime.desktop.middle_click(VALID_UUID)
        buttons = [
            json.loads(c.request.content)["button"] for c in mock_api.calls[-2:]
        ]
        assert buttons == ["right", "middle"]

    def test_mouse_press_and_release(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/down").mock(
            return_value=httpx.Response(200, json={})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/up").mock(
            return_value=httpx.Response(200, json={})
        )
        client.runtime.desktop.mouse_press(VALID_UUID, "right", x=1, y=2)
        down_body = json.loads(mock_api.calls[-1].request.content)
        assert down_body["button"] == "right" and down_body["x"] == 1
        client.runtime.desktop.mouse_release(VALID_UUID, "right", x=3, y=4)
        up_body = json.loads(mock_api.calls[-1].request.content)
        assert up_body["button"] == "right" and up_body["x"] == 3

    def test_move_mouse(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/move").mock(
            return_value=httpx.Response(200, json={})
        )
        client.runtime.desktop.move_mouse(VALID_UUID, 100, 200)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["x"] == 100 and body["y"] == 200

    def test_write_sends_keyboard_type(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/keyboard/type").mock(
            return_value=httpx.Response(200, json={})
        )
        client.runtime.desktop.write(VALID_UUID, "hi", delay_ms=5, mode="paste")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["text"] == "hi" and body["delay_ms"] == 5 and body["mode"] == "paste"


class TestAsyncDesktopConveniences:
    @pytest.mark.asyncio
    async def test_left_click_and_double(self, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/click").mock(
            return_value=httpx.Response(200, json={})
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            await client.runtime.desktop.left_click(VALID_UUID, x=1, y=2)
            await client.runtime.desktop.double_click(VALID_UUID, x=1, y=2)
        bodies = [json.loads(c.request.content) for c in mock_api.calls[-2:]]
        assert bodies[0]["button"] == "left" and bodies[1]["click_count"] == 2

    @pytest.mark.asyncio
    async def test_components_and_component_ops(self, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/desktop/status").mock(
            return_value=httpx.Response(200, json={"present": True, "components": []})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/desktop/component").mock(
            return_value=httpx.Response(200, json={"name": "session", "state": "active"})
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            s = await client.runtime.desktop.components(VALID_UUID)
            assert s["present"] is True
            await client.runtime.desktop.restart_component(VALID_UUID, "session")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"name": "session", "op": "restart"}


class TestBoundDesktopConveniences:
    """Bound ``rt.desktop`` forwards conveniences + session ops."""

    def _rt(self, client):
        from gravixlayer.types.runtime import Runtime
        rt = Runtime(runtime_id=VALID_UUID, status="running")
        rt._client = client
        return rt

    def test_bound_left_and_release(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/click").mock(
            return_value=httpx.Response(200, json={})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/up").mock(
            return_value=httpx.Response(200, json={})
        )
        rt = self._rt(client)
        rt.desktop.left_click(x=9, y=9)
        assert json.loads(mock_api.calls[-1].request.content)["x"] == 9
        rt.desktop.mouse_release("left", x=4, y=4)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["x"] == 4 and body["y"] == 4

    def test_bound_write_and_components(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/keyboard/type").mock(
            return_value=httpx.Response(200, json={})
        )
        mock_api.get(f"{SB}/{VALID_UUID}/desktop/status").mock(
            return_value=httpx.Response(200, json={"present": True, "components": []})
        )
        rt = self._rt(client)
        rt.desktop.write("go")
        assert json.loads(mock_api.calls[-1].request.content)["text"] == "go"
        assert rt.desktop.components()["present"] is True

    def test_bound_remaining_conveniences(self, client, mock_api):
        for _ in range(6):
            mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/click").mock(
                return_value=httpx.Response(200, json={})
            )
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/down").mock(
            return_value=httpx.Response(200, json={})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/move").mock(
            return_value=httpx.Response(200, json={})
        )
        rt = self._rt(client)
        rt.desktop.double_click()
        rt.desktop.right_click()
        rt.desktop.middle_click()
        rt.desktop.mouse_press("middle", x=7)
        rt.desktop.move_mouse(50, 60)
        urls = [c.request.url.path for c in mock_api.calls[-5:]]
        assert urls[-2].endswith("mouse/down") and urls[-1].endswith("mouse/move")
        assert json.loads(mock_api.calls[-2].request.content)["button"] == "middle"

    def test_bound_component_ops_and_logs(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/desktop/component").mock(
            return_value=httpx.Response(200, json={"name": "display", "state": "active"})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/desktop/logs").mock(
            return_value=httpx.Response(200, json={"entries": [], "next_cursor": ""})
        )
        rt = self._rt(client)
        rt.desktop.start_component("display")
        rt.desktop.restart_component("display")
        rt.desktop.logs("display", max_entries=10)
        ops = [json.loads(c.request.content)["op"] for c in mock_api.calls[:2]]
        assert ops == ["start", "restart"]
        assert json.loads(mock_api.calls[-1].request.content)["max"] == 10


class TestBoundDesktopMirror:
    """Bound ``rt.desktop`` mirrors the resource signature minus ``runtime_id``
    — every named param reaches the wire, positionally or by keyword."""

    def _rt(self, client):
        from gravixlayer.types.runtime import Runtime
        rt = Runtime(runtime_id=VALID_UUID, status="running")
        rt._client = client
        return rt

    def _body(self, mock_api):
        return json.loads(mock_api.calls[-1].request.content)

    def test_enable_positional_geometry(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/enable").mock(
            return_value=httpx.Response(200, json={"enabled": True})
        )
        self._rt(client).desktop.enable(1920, 1080, 24, "sway", ":0", "attach")
        b = self._body(mock_api)
        assert (b["width"], b["height"], b["depth"]) == (1920, 1080, 24)
        assert b["wm"] == "sway" and b["display"] == ":0" and b["mode"] == "attach"

    def test_screenshot_positional(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/screenshot").mock(
            return_value=httpx.Response(200, json={"png": ""})
        )
        self._rt(client).desktop.screenshot("jpeg", {"x": 1, "y": 2, "w": 3, "h": 4}, 80)
        b = self._body(mock_api)
        assert b["format"] == "jpeg" and b["region"]["w"] == 3 and b["quality"] == 80

    def test_click_positional_count_and_modifiers(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/click").mock(
            return_value=httpx.Response(200, json={})
        )
        self._rt(client).desktop.click(10, 20, "left", 2, ["shift"], "display")
        b = self._body(mock_api)
        assert (b["x"], b["y"], b["button"], b["click_count"]) == (10, 20, "left", 2)
        assert b["modifiers"] == ["shift"] and b["coordinate_space"] == "display"

    def test_down_positional_modifiers(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/down").mock(
            return_value=httpx.Response(200, json={})
        )
        self._rt(client).desktop.down(10, 20, "left", ["ctrl"])
        b = self._body(mock_api)
        assert b["modifiers"] == ["ctrl"]

    def test_up_positional_xy(self, client, mock_api):
        """``up`` takes x/y — the param order that broke ``mouse_release``."""
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/up").mock(
            return_value=httpx.Response(200, json={})
        )
        self._rt(client).desktop.up("left", 10, 20)
        b = self._body(mock_api)
        assert b["button"] == "left" and b["x"] == 10 and b["y"] == 20

    def test_drag_positional(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/drag").mock(
            return_value=httpx.Response(200, json={})
        )
        self._rt(client).desktop.drag(200, 200, 100, 100, "left", 3, 250)
        b = self._body(mock_api)
        assert (b["to_x"], b["to_y"], b["x"], b["y"]) == (200, 200, 100, 100)
        assert b["steps"] == 3 and b["duration_ms"] == 250

    def test_move_positional_space(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/move").mock(
            return_value=httpx.Response(200, json={})
        )
        self._rt(client).desktop.move(10, 20, "display")
        assert self._body(mock_api)["coordinate_space"] == "display"

    def test_type_positional_mode(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/keyboard/type").mock(
            return_value=httpx.Response(200, json={})
        )
        self._rt(client).desktop.type("hi", 5, "paste")
        b = self._body(mock_api)
        assert b["text"] == "hi" and b["delay_ms"] == 5 and b["mode"] == "paste"

    def test_press_and_hotkey_modifiers(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/keyboard/press").mock(
            return_value=httpx.Response(200, json={})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/display/keyboard/hotkey").mock(
            return_value=httpx.Response(200, json={})
        )
        rt = self._rt(client)
        rt.desktop.press("enter", ["shift"])
        rt.desktop.hotkey(["ctrl", "c"], ["alt"])
        assert json.loads(mock_api.calls[-2].request.content)["modifiers"] == ["shift"]
        hb = json.loads(mock_api.calls[-1].request.content)
        assert hb["keys"] == ["ctrl", "c"] and hb["modifiers"] == ["alt"]

    def test_view_positional(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/view").mock(
            return_value=httpx.Response(200, json={"url": "u"})
        )
        self._rt(client).desktop.view(10, 60, True, "control", 7)
        b = self._body(mock_api)
        assert b["fps"] == 10 and b["quality"] == 60 and b["rotate_token"] is True
        assert b["role"] == "control" and b["window_id"] == 7

    def test_act_positional(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/act").mock(
            return_value=httpx.Response(200, json={"settled": True})
        )
        self._rt(client).desktop.act([{"kind": "wait", "ms": 5}], 100, 5000,
                                     {"format": "jpeg"})
        b = self._body(mock_api)
        assert b["settle_ms"] == 100 and b["timeout_ms"] == 5000
        assert b["observe"]["format"] == "jpeg"

    def test_window_op_positional(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/windows/op").mock(
            return_value=httpx.Response(200, json={"id": 7})
        )
        self._rt(client).desktop.window_op(7, "move", 10, 20, 300, 200)
        b = self._body(mock_api)
        assert (b["id"], b["op"], b["x"], b["y"], b["w"], b["h"]) == \
            (7, "move", 10, 20, 300, 200)

    def test_launch_app_positional(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/apps/launch").mock(
            return_value=httpx.Response(200, json={"pid": 1})
        )
        self._rt(client).desktop.launch_app("calc", "uri://x", True, 500)
        b = self._body(mock_api)
        assert b["app"] == "calc" and b["uri"] == "uri://x"
        assert b["wait_window"] is True and b["timeout_ms"] == 500

    def test_open_positional(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/open").mock(
            return_value=httpx.Response(200, json={"pid": 1})
        )
        self._rt(client).desktop.open("https://x", True, 500)
        b = self._body(mock_api)
        assert b["target"] == "https://x" and b["wait_window"] is True
        assert b["timeout_ms"] == 500

    def test_logs_positional(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/desktop/logs").mock(
            return_value=httpx.Response(200, json={"entries": []})
        )
        self._rt(client).desktop.logs("display", "cur1", 50, "err")
        b = self._body(mock_api)
        assert b["cursor"] == "cur1" and b["max"] == 50 and b["priority"] == "err"

    def test_goto_positional_navigate_opts(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/open").mock(
            return_value=httpx.Response(200, json={"browser_id": BID})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/navigate").mock(
            return_value=httpx.Response(200, json={"url": "u", "navigated": True})
        )
        self._rt(client).browser.goto("https://x", "t1", "commit", 5000)
        b = json.loads(mock_api.calls[-1].request.content)
        assert b["target_id"] == "t1" and b["wait_until"] == "commit"
        assert b["timeout_ms"] == 5000


# ===================================================================
# Desktop — accessibility plane (CU3)
# ===================================================================


class TestDesktopA11y:
    def test_a11y_snapshot_defaults(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/a11y/snapshot").mock(
            return_value=httpx.Response(
                200, json={"rev": 3, "elements": [{"ref": "d1"}], "truncated": False}
            )
        )
        r = client.runtime.desktop.a11y_snapshot(VALID_UUID)
        assert r["rev"] == 3 and r["elements"][0]["ref"] == "d1"
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {}

    def test_a11y_snapshot_filters_and_diff(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/a11y/snapshot").mock(
            return_value=httpx.Response(200, json={"rev": 4, "elements": []})
        )
        client.runtime.desktop.a11y_snapshot(
            VALID_UUID, scope="app", app="files", pid=12, max_depth=8,
            limit=100, visible_only=False, roles=["push button"],
            name="Save", diff=True, rev=3,
        )
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["scope"] == "app" and body["app"] == "files"
        assert body["pid"] == 12 and body["max_depth"] == 8
        assert body["limit"] == 100 and body["visible_only"] is False
        assert body["roles"] == ["push button"] and body["name"] == "Save"
        assert body["diff"] is True and body["rev"] == 3

    def test_a11y_find(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/a11y/find").mock(
            return_value=httpx.Response(
                200, json={"elements": [{"ref": "d9", "role": "push button"}], "rev": 2}
            )
        )
        r = client.runtime.desktop.a11y_find(
            VALID_UUID, role="push button", name="save", ref="d2", max=5
        )
        assert r["elements"][0]["ref"] == "d9"
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"role": "push button", "name": "save", "ref": "d2", "max": 5}

    def test_a11y_action_invoke(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/a11y/action").mock(
            return_value=httpx.Response(200, json={"ok": True, "settled": True, "rev": 5})
        )
        r = client.runtime.desktop.a11y_action(
            VALID_UUID, "invoke", "d9", action="press", timeout_ms=800
        )
        assert r["ok"] is True and r["rev"] == 5
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"op": "invoke", "ref": "d9", "action": "press",
                        "timeout_ms": 800}

    def test_a11y_action_set_value(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/a11y/action").mock(
            return_value=httpx.Response(200, json={"ok": True, "settled": True, "rev": 6})
        )
        client.runtime.desktop.a11y_action(
            VALID_UUID, "set_value", "d3", text="hello", value=1.5
        )
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["text"] == "hello" and body["value"] == 1.5


# ===================================================================
# Desktop — recordings + takeover (CU4)
# ===================================================================


class TestDesktopRecording:
    def test_start_recording_selectors(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/recordings").mock(
            return_value=httpx.Response(
                200, json={"rec_id": "r1", "path": "/tmp/r.mp4",
                           "trajectory_path": "/tmp/r.jsonl", "status": "recording"}
            )
        )
        r = client.runtime.desktop.start_recording(
            VALID_UUID, include=["video", "input"], label="e2e", window_id=7
        )
        assert r["rec_id"] == "r1" and r["path"].endswith(".mp4")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"include": ["video", "input"], "label": "e2e",
                        "window_id": 7}

    def test_start_recording_empty_body(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/recordings").mock(
            return_value=httpx.Response(200, json={"rec_id": "r2"})
        )
        client.runtime.desktop.start_recording(VALID_UUID)
        assert json.loads(mock_api.calls[-1].request.content) == {}

    def test_recordings_list_get(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/display/recordings").mock(
            return_value=httpx.Response(200, json={"recordings": [{"rec_id": "r1"}]})
        )
        assert client.runtime.desktop.recordings(VALID_UUID)["recordings"][0]["rec_id"] == "r1"
        mock_api.get(f"{SB}/{VALID_UUID}/display/recordings/r1").mock(
            return_value=httpx.Response(200, json={"rec_id": "r1", "bytes": 10})
        )
        assert client.runtime.desktop.recording(VALID_UUID, "r1")["bytes"] == 10

    def test_stop_mark_delete(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/recordings/r1/stop").mock(
            return_value=httpx.Response(200, json={"status": "stopped"})
        )
        assert client.runtime.desktop.stop_recording(VALID_UUID, "r1")["status"] == "stopped"
        mock_api.post(f"{SB}/{VALID_UUID}/display/recordings/r1/mark").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.runtime.desktop.mark_recording(VALID_UUID, "r1", "midpoint")
        assert json.loads(mock_api.calls[-1].request.content) == {"label": "midpoint"}
        mock_api.delete(f"{SB}/{VALID_UUID}/display/recordings/r1").mock(
            return_value=httpx.Response(200, json={"deleted": True})
        )
        assert client.runtime.desktop.delete_recording(VALID_UUID, "r1")["deleted"] is True

    def test_set_control_mode(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/view/control").mock(
            return_value=httpx.Response(200, json={"mode": "human"})
        )
        r = client.runtime.desktop.set_control_mode(VALID_UUID, "human")
        assert r["mode"] == "human"
        assert json.loads(mock_api.calls[-1].request.content) == {"mode": "human"}


# ===================================================================
# Browser — events SSE, contexts, storage state
# ===================================================================


SSE_PAGE = (
    ": ka\n"
    "\n"
    "id: 41\n"
    "event: navigated\n"
    'data: {"url": "https://example.com", "seq": 41}\n'
    "\n"
    "id: 42\n"
    "event: console\n"
    'data: {"text": "hi", "seq": 42}\n'
    "\n"
)


class TestBrowserEvents:
    def test_events_parse_frames(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/browser/{BID}/events").mock(
            return_value=httpx.Response(
                200, text=SSE_PAGE, headers={"content-type": "text/event-stream"}
            )
        )
        frames = list(client.runtime.browser.events(VALID_UUID, BID))
        assert [f["seq"] for f in frames] == [41, 42]
        assert frames[0]["kind"] == "navigated"
        assert frames[0]["data"]["url"] == "https://example.com"
        assert mock_api.calls[-1].request.headers["Accept"] == "text/event-stream"

    def test_events_resume_params(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/browser/{BID}/events").mock(
            return_value=httpx.Response(
                200, text=": ka\n\n", headers={"content-type": "text/event-stream"}
            )
        )
        frames = list(client.runtime.browser.events(VALID_UUID, BID, since=41, wait_ms=8000))
        assert frames == []
        req = mock_api.calls[-1].request
        assert req.headers["Last-Event-ID"] == "41"
        assert "since=41" in str(req.url) and "wait_ms=8000" in str(req.url)


class TestBrowserContextsStorage:
    def test_context_create_list_delete(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/context").mock(
            return_value=httpx.Response(200, json={"context_id": "c1"})
        )
        r = client.runtime.browser.create_context(VALID_UUID, BID)
        assert r["context_id"] == "c1"
        assert json.loads(mock_api.calls[-1].request.content) == {}

        mock_api.get(f"{SB}/{VALID_UUID}/browser/{BID}/contexts").mock(
            return_value=httpx.Response(200, json={"contexts": [{"context_id": "c1"}]})
        )
        assert client.runtime.browser.contexts(VALID_UUID, BID)["contexts"][0]["context_id"] == "c1"

        mock_api.delete(f"{SB}/{VALID_UUID}/browser/{BID}/context/c1").mock(
            return_value=httpx.Response(200, json={"deleted": True})
        )
        assert client.runtime.browser.delete_context(VALID_UUID, BID, "c1")["deleted"] is True

    def test_context_create_seeded(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/context").mock(
            return_value=httpx.Response(200, json={"context_id": "c2"})
        )
        state = {"cookies": [], "origins": []}
        client.runtime.browser.create_context(
            VALID_UUID, BID, proxy="http://p:8080", storage_state=state
        )
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["proxy"] == "http://p:8080" and body["storage_state"] == state

    def test_targets_in_context(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/targets").mock(
            return_value=httpx.Response(200, json={"target_id": "t9"})
        )
        client.runtime.browser.targets(VALID_UUID, BID, url="https://x", context_id="c1")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["context_id"] == "c1" and body["url"] == "https://x"

    def test_storage_export_import(self, client, mock_api):
        state = {"cookies": [{"name": "NID"}], "origins": []}
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/storage/export").mock(
            return_value=httpx.Response(200, json={"storage_state": state})
        )
        r = client.runtime.browser.export_storage(VALID_UUID, BID, context_id="c1")
        assert r["storage_state"]["cookies"][0]["name"] == "NID"
        assert json.loads(mock_api.calls[-1].request.content) == {"context_id": "c1"}

        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/storage/import").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.runtime.browser.import_storage(VALID_UUID, BID, state)
        assert json.loads(mock_api.calls[-1].request.content) == {"storage_state": state}


# ===================================================================
# Async mirrors — a11y, recording, events, contexts, storage
# ===================================================================


class TestAsyncNewPlanes:
    @pytest.mark.asyncio
    async def test_a11y_and_recording(self, mock_api):
        from gravixlayer import AsyncGravixLayer

        mock_api.post(f"{SB}/{VALID_UUID}/display/a11y/action").mock(
            return_value=httpx.Response(200, json={"ok": True, "rev": 2})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/display/recordings").mock(
            return_value=httpx.Response(200, json={"rec_id": "r1"})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/display/recordings/r1/stop").mock(
            return_value=httpx.Response(200, json={"status": "stopped"})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/display/view/control").mock(
            return_value=httpx.Response(200, json={"mode": "shared"})
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as c:
            assert (await c.runtime.desktop.a11y_action(VALID_UUID, "focus", "d1"))["ok"] is True
            assert (await c.runtime.desktop.start_recording(VALID_UUID))["rec_id"] == "r1"
            assert (await c.runtime.desktop.stop_recording(VALID_UUID, "r1"))["status"] == "stopped"
            assert (await c.runtime.desktop.set_control_mode(VALID_UUID, "shared"))["mode"] == "shared"

    @pytest.mark.asyncio
    async def test_events_and_storage(self, mock_api):
        from gravixlayer import AsyncGravixLayer

        mock_api.get(f"{SB}/{VALID_UUID}/browser/{BID}/events").mock(
            return_value=httpx.Response(
                200, text=SSE_PAGE, headers={"content-type": "text/event-stream"}
            )
        )
        state = {"cookies": [], "origins": []}
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/storage/export").mock(
            return_value=httpx.Response(200, json={"storage_state": state})
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as c:
            frames = [f async for f in c.runtime.browser.events(VALID_UUID, BID)]
            assert [f["seq"] for f in frames] == [41, 42]
            assert frames[1]["kind"] == "console"
            assert (await c.runtime.browser.export_storage(VALID_UUID, BID))["storage_state"] == state
