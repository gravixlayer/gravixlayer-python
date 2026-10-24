"""
Tests for the computer-use planes: ``client.runtime.display`` (pixels + input)
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
        r = client.runtime.display.enable(VALID_UUID, width=1920, height=1080)
        assert r["enabled"] is True
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["width"] == 1920 and body["height"] == 1080

    def test_status(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/display/status").mock(
            return_value=httpx.Response(200, json={"enabled": True})
        )
        assert client.runtime.display.status(VALID_UUID)["enabled"] is True

    def test_screenshot_wait_stable(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/screenshot").mock(
            return_value=httpx.Response(
                200, json={"data": base64.b64encode(b"PNG").decode(), "format": "png"}
            )
        )
        r = client.runtime.display.screenshot(
            VALID_UUID, format="png", wait_stable_ms=300, timeout_ms=5000
        )
        assert base64.b64decode(r["data"]) == b"PNG"
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["wait_stable_ms"] == 300 and body["timeout_ms"] == 5000

    def test_click(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/click").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.runtime.display.click(VALID_UUID, 100, 200, button="left")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["x"] == 100 and body["y"] == 200 and body["button"] == "left"

    def test_hotkey(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/keyboard/hotkey").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.runtime.display.hotkey(VALID_UUID, ["ctrl", "c"])
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["keys"] == ["ctrl", "c"]

    def test_view(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/view").mock(
            return_value=httpx.Response(200, json={"port": 9871})
        )
        assert client.runtime.display.view(VALID_UUID)["port"] == 9871

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
        r = client.runtime.display.act(
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
        r = client.runtime.display.screenshot(VALID_UUID, if_rev=7)
        assert r["unchanged"] is True
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["if_rev"] == 7

    def test_resize(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/resize").mock(
            return_value=httpx.Response(200, json={"width": 1280, "height": 720})
        )
        r = client.runtime.display.resize(VALID_UUID, 1280, 720)
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
        r = client.runtime.display.windows(VALID_UUID, window_class="term")
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
        client.runtime.display.windows(VALID_UUID, window_class="A&B +x")
        query = parse_qs(mock_api.calls[-1].request.url.query.decode())
        assert query["window_class"] == ["A&B +x"]
        assert list(query) == ["window_class"]  # no parameter injection

    def test_window_op(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/windows/op").mock(
            return_value=httpx.Response(200, json={"id": 1, "x": 10, "y": 20})
        )
        client.runtime.display.move_window(VALID_UUID, 1, 10, 20)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"id": 1, "op": "move", "x": 10, "y": 20}
        client.runtime.display.window_op(VALID_UUID, 1, "maximize")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"id": 1, "op": "maximize"}
        client.runtime.display.window_op(VALID_UUID, 1, "fullscreen")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"id": 1, "op": "fullscreen"}
        client.runtime.display.resize_window(VALID_UUID, 1, 400, 300)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"id": 1, "op": "resize", "w": 400, "h": 300}

    def test_apps_and_launch(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/display/apps").mock(
            return_value=httpx.Response(
                200,
                json={"apps": [{"id": "org.xterm", "name": "XTerm"}]},
            )
        )
        assert client.runtime.display.apps(VALID_UUID)["apps"][0]["name"] == "XTerm"
        mock_api.post(f"{SB}/{VALID_UUID}/display/apps/launch").mock(
            return_value=httpx.Response(
                200, json={"pid": 4242, "window_id": 2097155, "app": "org.xterm"}
            )
        )
        r = client.runtime.display.launch_app(
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
        r = client.runtime.display.open(VALID_UUID, "https://example.com")
        assert r["mime"] == "text/html"
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["target"] == "https://example.com"

    def test_clipboard_image(self, client, mock_api):
        png = base64.b64encode(b"PNGBYTES").decode()
        mock_api.post(f"{SB}/{VALID_UUID}/display/clipboard").mock(
            return_value=httpx.Response(200, json={"text": "", "png": png})
        )
        assert client.runtime.display.clipboard_image(VALID_UUID) == b"PNGBYTES"
        client.runtime.display.set_clipboard_image(VALID_UUID, b"PNGBYTES")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"op": "set", "png": png}

    def test_view_window(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/view").mock(
            return_value=httpx.Response(200, json={"port": 9871})
        )
        client.runtime.display.view(VALID_UUID, window_id=2097155)
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
            await client.runtime.display.screenshot(VALID_UUID, wait_stable_ms=100)
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
            r = await client.runtime.display.act(
                VALID_UUID,
                actions=[{"kind": "click", "mouse": {"x": 1, "y": 2}}],
            )
            assert r["settled"] is True and r["rev"] == 3
            w = await client.runtime.display.windows(VALID_UUID)
            assert w["focused"] == 5
            # Async path encodes the class filter too.
            await client.runtime.display.windows(VALID_UUID, window_class="x&y")
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
            assert (await client.runtime.display.open(VALID_UUID, "f.pdf"))["pid"] == 9
            assert (await client.runtime.display.launch_app(
                VALID_UUID, "a", wait_window=True))["window_id"] == 4
            assert (await client.runtime.display.resize(
                VALID_UUID, 800, 600))["height"] == 600

    @pytest.mark.asyncio
    async def test_display_clipboard_image(self, mock_api):
        png = base64.b64encode(b"IMG").decode()
        mock_api.post(f"{SB}/{VALID_UUID}/display/clipboard").mock(
            return_value=httpx.Response(200, json={"png": png})
        )
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            assert await client.runtime.display.clipboard_image(VALID_UUID) == b"IMG"


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
    """runtime.browser / runtime.display bound to the Runtime object."""

    def test_bound_browser_exists(self):
        from gravixlayer.types.runtime import Runtime
        r = Runtime(runtime_id=VALID_UUID, status="running")
        assert type(r.browser).__name__ == "RuntimeBrowserBound"

    def test_bound_display_exists(self):
        from gravixlayer.types.runtime import Runtime
        r = Runtime(runtime_id=VALID_UUID, status="running")
        assert type(r.display).__name__ == "RuntimeDisplayBound"

    def test_bound_scroll_sends_deltas(self, client, mock_api):
        """Bound scroll must forward dx/dy — and no pointer position when unset."""
        from gravixlayer.types.runtime import Runtime
        rt = Runtime(runtime_id=VALID_UUID, status="running")
        rt._client = client
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/scroll").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        rt.display.scroll(dy=-480)
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
        rt.display.scroll(24, -480)
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
        rt.display.scroll(x=100, y=200, dy=600)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["x"] == 100 and body["y"] == 200 and body["dy"] == 600

    def test_scroll_resource_sends_only_given_axes(self, client, mock_api):
        """The wire distinguishes 'unset' from 0 — an x=0 scroll position is
        real input, while an absent axis keeps the current pointer."""
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/scroll").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.runtime.display.scroll(VALID_UUID, dy=-480)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"dx": 0, "dy": -480}

        client.runtime.display.scroll(VALID_UUID, x=0, dy=-480)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"x": 0, "dx": 0, "dy": -480}

    def test_enable_omits_unset_geometry(self, client, mock_api):
        """Zero values defer to the platform default instead of pinning it."""
        mock_api.post(f"{SB}/{VALID_UUID}/display/enable").mock(
            return_value=httpx.Response(200, json={"enabled": True})
        )
        client.runtime.display.enable(VALID_UUID)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {}

        client.runtime.display.enable(VALID_UUID, width=2560, depth=30)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"width": 2560, "depth": 30}

    def test_view_rotate_token_flag(self, client, mock_api):
        """rotate_token mints a fresh watch URL on a repeat view call."""
        mock_api.post(f"{SB}/{VALID_UUID}/display/view").mock(
            return_value=httpx.Response(201, json={"url": "u", "browser_url": "b", "port": 1})
        )
        client.runtime.display.view(VALID_UUID, rotate_token=True)
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
        r = client.runtime.display.enable(VALID_UUID, display=":1", mode="attach")
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
        assert client.runtime.display.info(VALID_UUID)["attached"] is True
        assert client.runtime.display.position(VALID_UUID) == {"x": 41, "y": 88}

    def test_keys(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/display/keys").mock(
            return_value=httpx.Response(200, json={"keys": ["enter", "f5"]})
        )
        assert client.runtime.display.keys(VALID_UUID)["keys"] == ["enter", "f5"]

    def test_screenshot_fit_cursor_and_scale(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/screenshot").mock(
            return_value=httpx.Response(200, json={"data": "", "format": "webp", "scale": 0.5})
        )
        client.runtime.display.screenshot(
            VALID_UUID, format="webp", max_width=960, max_height=960, cursor=True
        )
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["format"] == "webp" and body["cursor"] is True
        assert body["max_width"] == 960 and body["max_height"] == 960

    def test_click_modifiers_count_space(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/click").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.runtime.display.click(
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
        client.runtime.display.click(VALID_UUID)
        body = json.loads(mock_api.calls[-1].request.content)
        assert "x" not in body and "y" not in body

    def test_down_up_drag(self, client, mock_api):
        for tail in ("down", "up", "drag"):
            mock_api.post(f"{SB}/{VALID_UUID}/display/mouse/{tail}").mock(
                return_value=httpx.Response(200, json={"ok": True})
            )
        client.runtime.display.down(VALID_UUID, 10, 10, modifiers=["shift"])
        client.runtime.display.up(VALID_UUID)
        client.runtime.display.drag(VALID_UUID, 400, 300, x=10, y=10,
                                    steps=8, duration_ms=200)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["to_x"] == 400 and body["to_y"] == 300
        assert body["x"] == 10 and body["steps"] == 8 and body["duration_ms"] == 200

    def test_type_paste_mode(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/keyboard/type").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.runtime.display.type(VALID_UUID, "big block", mode="paste")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["text"] == "big block" and body["mode"] == "paste"

    def test_press_and_hotkey_modifiers(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/keyboard/press").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/display/keyboard/hotkey").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.runtime.display.press(VALID_UUID, "enter", modifiers=["ctrl"])
        assert json.loads(mock_api.calls[-1].request.content)["modifiers"] == ["ctrl"]
        client.runtime.display.hotkey(VALID_UUID, ["f4"], modifiers=["alt"])
        assert json.loads(mock_api.calls[-1].request.content)["modifiers"] == ["alt"]

    def test_clipboard_get_set(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/clipboard").mock(
            return_value=httpx.Response(200, json={"text": "hello"})
        )
        assert client.runtime.display.get_clipboard(VALID_UUID) == "hello"
        client.runtime.display.set_clipboard(VALID_UUID, "world")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"op": "set", "text": "world"}

    def test_view_role_and_stop(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/display/view").mock(
            return_value=httpx.Response(200, json={"url": "u", "view_token": "vt-1"})
        )
        mock_api.post(f"{SB}/{VALID_UUID}/display/view/stop").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        r = client.runtime.display.view(VALID_UUID, role="watch")
        assert r["view_token"] == "vt-1"
        assert json.loads(mock_api.calls[-1].request.content)["role"] == "watch"
        client.runtime.display.stop_view(VALID_UUID)


class TestDesktopCU1:
    def test_status(self, client, mock_api):
        mock_api.get(f"{SB}/{VALID_UUID}/desktop/status").mock(
            return_value=httpx.Response(200, json={
                "present": True, "display": ":1", "user": "agent",
                "components": [{"name": "display", "unit": "xvfb.service",
                                "state": "active", "sub_state": "running"}],
            })
        )
        s = client.runtime.desktop.status(VALID_UUID)
        assert s["present"] is True
        assert s["components"][0]["unit"] == "xvfb.service"

    def test_component_ops(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/desktop/component").mock(
            return_value=httpx.Response(200, json={"name": "session", "state": "active"})
        )
        client.runtime.desktop.restart(VALID_UUID, "session")
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"name": "session", "op": "restart"}
        client.runtime.desktop.stop(VALID_UUID, "session")
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
