"""
Tests for the computer-use planes: ``client.runtime.display`` (pixels + input)
and ``client.runtime.browser`` (semantic control).
"""

import base64
import json

import httpx
import pytest

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

    def test_dialog_default_auto_dismiss(self, client, mock_api):
        mock_api.post(f"{SB}/{VALID_UUID}/browser/{BID}/dialog").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.runtime.browser.dialog(VALID_UUID, BID)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["auto_dismiss"] is True and body["accept"] is True


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
