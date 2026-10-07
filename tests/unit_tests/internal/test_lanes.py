"""Unit tests for the parallel HTTP/2 lane transport (``gravixlayer._lanes``)."""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

import httpx
import pytest

from gravixlayer._lanes import (
    H2_LANES,
    H2_LANE_DEPTH,
    AsyncLanesTransport,
    LanesTransport,
    warm_dns,
)

API = "https://api.gravixlayer.test"


def _request(method: str = "GET", url: str = f"{API}/v1/agents") -> httpx.Request:
    return httpx.Request(method, url)


class _OkSyncTransport(httpx.BaseTransport):
    """Serves a canned response and records the requests it handled."""

    def __init__(self, calls: List[httpx.Request], extensions=None) -> None:
        self.calls = calls
        self._extensions = extensions or {}

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        return httpx.Response(200, json={"ok": True}, extensions=dict(self._extensions))

    def close(self) -> None:
        pass


class _OkAsyncTransport(httpx.AsyncBaseTransport):
    def __init__(self, calls: List[httpx.Request], extensions=None) -> None:
        self.calls = calls
        self._extensions = extensions or {}

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        return httpx.Response(200, json={"ok": True}, extensions=dict(self._extensions))

    async def aclose(self) -> None:
        pass


class _GateSyncTransport(_OkSyncTransport):
    """Holds the request open until the gate releases it."""

    def __init__(self, calls: List[httpx.Request], gate: threading.Event) -> None:
        super().__init__(calls)
        self._gate = gate

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        self._gate.wait(timeout=5)
        return httpx.Response(200, json={"ok": True})


class _GateAsyncTransport(_OkAsyncTransport):
    def __init__(self, calls: List[httpx.Request], gate: asyncio.Event) -> None:
        super().__init__(calls)
        self._gate = gate

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        await self._gate.wait()
        return httpx.Response(200, json={"ok": True})


class _FailConnectSync(httpx.BaseTransport):
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unreachable", request=request)

    def close(self) -> None:
        pass


class _FailConnectAsync(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unreachable", request=request)

    async def aclose(self) -> None:
        pass


class _FailMidflightSync(httpx.BaseTransport):
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        raise httpx.ReadError("connection dropped", request=request)

    def close(self) -> None:
        pass


def _sync_lanes(lane_factory, fallback=None) -> LanesTransport:
    return LanesTransport(lane_factory=lane_factory, fallback=fallback)


def _async_lanes(lane_factory, fallback=None) -> AsyncLanesTransport:
    return AsyncLanesTransport(lane_factory=lane_factory, fallback=fallback)


class TestSyncLanes:
    def test_sequential_requests_share_one_lane(self):
        calls: List[httpx.Request] = []
        transport = _sync_lanes(lambda: _OkSyncTransport(calls))
        for _ in range(3):
            resp = transport.handle_request(_request())
            resp.read()
        pool = transport._pools[next(iter(transport._pools))]
        assert len(pool.lanes) == 1
        assert len(calls) == 3
        transport.close()

    def test_burst_fills_the_whole_pool(self):
        calls: List[httpx.Request] = []
        gate = threading.Event()
        lane_calls: List[List[httpx.Request]] = []

        def factory():
            seen: List[httpx.Request] = []
            lane_calls.append(seen)
            return _GateSyncTransport(seen, gate)

        transport = _sync_lanes(factory)
        with ThreadPoolExecutor(max_workers=H2_LANE_DEPTH + 2) as executor:
            futures = [
                executor.submit(transport.handle_request, _request())
                for _ in range(H2_LANE_DEPTH + 2)
            ]
            gate.wait(0.2)
            gate.set()
            for future in futures:
                future.result().read()

        pool = transport._pools[next(iter(transport._pools))]
        assert len(pool.lanes) == H2_LANES
        # The burst spread: the deep lane carried the first requests, and the
        # lanes opened by the burst carried the rest.
        assert sum(len(c) for c in lane_calls) == H2_LANE_DEPTH + 2
        assert len(lane_calls) == H2_LANES
        transport.close()

    def test_connect_failure_redials_on_a_live_lane(self):
        calls: List[httpx.Request] = []
        built = {"n": 0}

        def factory():
            built["n"] += 1
            if built["n"] == 1:
                return _FailConnectSync()
            return _OkSyncTransport(calls)

        transport = _sync_lanes(factory)
        resp = transport.handle_request(_request())
        resp.read()
        assert len(calls) == 1
        # The dead lane was dropped, not kept in the pool.
        pool = transport._pools[next(iter(transport._pools))]
        assert len(pool.lanes) == 1
        assert pool.lanes[0].transport.calls is calls
        transport.close()

    def test_midflight_failure_never_replays(self):
        transport = _sync_lanes(lambda: _FailMidflightSync())
        with pytest.raises(httpx.ReadError):
            transport.handle_request(_request(method="POST"))
        pool = transport._pools[next(iter(transport._pools))]
        assert pool.lanes == []
        transport.close()

    def test_http1_origin_learns_and_falls_back(self):
        lane_calls: List[httpx.Request] = []
        fallback_calls: List[httpx.Request] = []
        transport = _sync_lanes(
            lambda: _OkSyncTransport(lane_calls, {"http_version": b"HTTP/1.1"}),
            fallback=_OkSyncTransport(fallback_calls),
        )
        resp = transport.handle_request(_request())
        resp.read()
        assert len(lane_calls) == 1
        resp = transport.handle_request(_request())
        resp.read()
        # The origin now routes through the shared HTTP/1.1 pool.
        assert len(fallback_calls) == 1
        transport.close()

    def test_cleartext_origin_uses_fallback_directly(self):
        lane_calls: List[httpx.Request] = []
        fallback_calls: List[httpx.Request] = []
        transport = _sync_lanes(
            lambda: _OkSyncTransport(lane_calls),
            fallback=_OkSyncTransport(fallback_calls),
        )
        resp = transport.handle_request(_request(url="http://api.test/v1/x"))
        resp.read()
        assert len(fallback_calls) == 1
        assert not transport._pools
        transport.close()

    def test_inflight_held_until_stream_closes(self):
        class _Streaming(httpx.BaseTransport):
            def handle_request(self, request: httpx.Request) -> httpx.Response:
                return httpx.Response(200, stream=httpx.ByteStream(b"body"))

            def close(self) -> None:
                pass

        transport = _sync_lanes(lambda: _Streaming())
        resp = transport.handle_request(_request())
        pool = transport._pools[next(iter(transport._pools))]
        lane = pool.lanes[0]
        assert lane.inflight == 1
        resp.read()
        resp.close()
        assert lane.inflight == 0
        transport.close()

    def test_ensure_pool_fills_without_requests(self):
        transport = _sync_lanes(lambda: _OkSyncTransport([]))
        transport.ensure_pool(httpx.URL(f"{API}/x"))
        pool = transport._pools[next(iter(transport._pools))]
        assert len(pool.lanes) == H2_LANES
        transport.close()

    def test_close_drains_every_lane_and_is_idempotent(self):
        transport = _sync_lanes(lambda: _OkSyncTransport([]))
        transport.ensure_pool(httpx.URL(f"{API}/x"))
        closed = []
        pool = transport._pools[next(iter(transport._pools))]
        for lane in pool.lanes:
            closed.append(lane.transport)
            lane.transport.close = lambda *a, _t=lane.transport, **k: closed.append(_t)
        transport.close()
        transport.close()
        assert transport._pools == {}

    def test_requests_after_close_raise(self):
        transport = _sync_lanes(lambda: _OkSyncTransport([]))
        transport.close()
        with pytest.raises(RuntimeError):
            transport.handle_request(_request())

    def test_timeout_keeps_the_lane(self):
        class _Slow(httpx.BaseTransport):
            def handle_request(self, request: httpx.Request) -> httpx.Response:
                raise httpx.ReadTimeout("slow", request=request)

            def close(self) -> None:
                pass

        transport = _sync_lanes(lambda: _Slow())
        with pytest.raises(httpx.ReadTimeout):
            transport.handle_request(_request())
        pool = transport._pools[next(iter(transport._pools))]
        # A timeout is not a dead connection: the lane stays in the pool.
        assert len(pool.lanes) == 1
        assert pool.lanes[0].inflight == 0
        transport.close()

    def test_dead_origin_redials_once_then_raises(self):
        transport = _sync_lanes(lambda: _FailConnectSync())
        with pytest.raises(httpx.ConnectError):
            transport.handle_request(_request())
        pool = transport._pools[next(iter(transport._pools))]
        assert pool.lanes == []
        transport.close()

    def test_ensure_pool_skips_cleartext(self):
        transport = _sync_lanes(lambda: _OkSyncTransport([]))
        transport.ensure_pool(httpx.URL("http://api.test/x"))
        assert not transport._pools
        transport.close()


class TestAsyncLanes:
    async def test_sequential_requests_share_one_lane(self):
        calls: List[httpx.Request] = []
        transport = _async_lanes(lambda: _OkAsyncTransport(calls))
        for _ in range(3):
            resp = await transport.handle_async_request(_request())
            await resp.aread()
        pool = transport._pools[next(iter(transport._pools))]
        assert len(pool.lanes) == 1
        await transport.aclose()

    async def test_burst_fills_the_whole_pool(self):
        gate = asyncio.Event()
        lane_calls: List[List[httpx.Request]] = []

        def factory():
            seen: List[httpx.Request] = []
            lane_calls.append(seen)
            return _GateAsyncTransport(seen, gate)

        transport = _async_lanes(factory)
        tasks = [
            asyncio.create_task(transport.handle_async_request(_request()))
            for _ in range(H2_LANE_DEPTH + 2)
        ]
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        gate.set()
        for task in tasks:
            resp = await task
            await resp.aread()

        pool = transport._pools[next(iter(transport._pools))]
        assert len(pool.lanes) == H2_LANES
        assert sum(len(c) for c in lane_calls) == H2_LANE_DEPTH + 2
        assert len(lane_calls) == H2_LANES
        await transport.aclose()

    async def test_connect_failure_redials_on_a_live_lane(self):
        calls: List[httpx.Request] = []
        built = {"n": 0}

        def factory():
            built["n"] += 1
            if built["n"] == 1:
                return _FailConnectAsync()
            return _OkAsyncTransport(calls)

        transport = _async_lanes(factory)
        resp = await transport.handle_async_request(_request())
        await resp.aread()
        assert len(calls) == 1
        pool = transport._pools[next(iter(transport._pools))]
        assert len(pool.lanes) == 1
        await transport.aclose()

    async def test_midflight_failure_never_replays(self):
        class _FailMid(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                raise httpx.ReadError("dropped", request=request)

            async def aclose(self) -> None:
                pass

        transport = _async_lanes(lambda: _FailMid())
        with pytest.raises(httpx.ReadError):
            await transport.handle_async_request(_request(method="POST"))
        await transport.aclose()

    async def test_http1_origin_learns_and_falls_back(self):
        lane_calls: List[httpx.Request] = []
        fallback_calls: List[httpx.Request] = []
        transport = _async_lanes(
            lambda: _OkAsyncTransport(lane_calls, {"http_version": b"HTTP/1.1"}),
            fallback=_OkAsyncTransport(fallback_calls),
        )
        resp = await transport.handle_async_request(_request())
        await resp.aread()
        resp = await transport.handle_async_request(_request())
        await resp.aread()
        assert len(lane_calls) == 1
        assert len(fallback_calls) == 1
        await transport.aclose()

    async def test_inflight_held_until_stream_closes(self):
        class _Body(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b"body"

            async def aclose(self) -> None:
                pass

        class _Streaming(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                return httpx.Response(200, stream=_Body())

            async def aclose(self) -> None:
                pass

        transport = _async_lanes(lambda: _Streaming())
        resp = await transport.handle_async_request(_request())
        pool = transport._pools[next(iter(transport._pools))]
        assert pool.lanes[0].inflight == 1
        await resp.aread()
        await resp.aclose()
        assert pool.lanes[0].inflight == 0
        await transport.aclose()

    async def test_ensure_pool_fills_without_requests(self):
        transport = _async_lanes(lambda: _OkAsyncTransport([]))
        transport.ensure_pool(httpx.URL(f"{API}/x"))
        pool = transport._pools[next(iter(transport._pools))]
        assert len(pool.lanes) == H2_LANES
        await transport.aclose()

    async def test_aclose_drains_every_lane_and_is_idempotent(self):
        transport = _async_lanes(lambda: _OkAsyncTransport([]))
        transport.ensure_pool(httpx.URL(f"{API}/x"))
        await transport.aclose()
        await transport.aclose()
        assert transport._pools == {}

    async def test_requests_after_aclose_raise(self):
        transport = _async_lanes(lambda: _OkAsyncTransport([]))
        await transport.aclose()
        with pytest.raises(RuntimeError):
            await transport.handle_async_request(_request())

    async def test_cleartext_origin_uses_fallback_directly(self):
        fallback_calls: List[httpx.Request] = []
        transport = _async_lanes(
            lambda: _OkAsyncTransport([]),
            fallback=_OkAsyncTransport(fallback_calls),
        )
        resp = await transport.handle_async_request(
            _request(url="http://api.test/v1/x")
        )
        await resp.aread()
        assert len(fallback_calls) == 1
        assert not transport._pools
        await transport.aclose()

    async def test_ensure_pool_skips_h1_only_and_cleartext(self):
        fallback_calls: List[httpx.Request] = []
        transport = _async_lanes(
            lambda: _OkAsyncTransport([], {"http_version": b"HTTP/1.1"}),
            fallback=_OkAsyncTransport(fallback_calls),
        )
        resp = await transport.handle_async_request(_request())
        await resp.aread()
        # The origin learned HTTP/1.1: ensure_pool must not grow lanes for it.
        transport.ensure_pool(httpx.URL(f"{API}/x"))
        pool = transport._pools[next(iter(transport._pools))]
        assert len(pool.lanes) == 1
        # And cleartext origins never get lanes at all.
        transport.ensure_pool(httpx.URL("http://api.test/x"))
        assert len(transport._pools) == 1
        await transport.aclose()


def test_warm_dns_fires_and_forgets():
    # The daemon thread resolves in the background; any outcome is fine —
    # the point is it never blocks and never raises into the caller.
    warm_dns("api.gravixlayer.test.invalid")


class TestProxyGate:
    def test_env_proxy_uses_plain_transport(self, monkeypatch):
        from gravixlayer import GravixLayer
        from gravixlayer._lanes import LanesTransport
        from tests.utils import TEST_API_KEY, TEST_BASE_URL

        monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:8080")
        client = GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        assert not isinstance(client._http_client._transport, LanesTransport)
        client.close()

    def test_no_proxy_env_keeps_lanes(self, monkeypatch):
        from gravixlayer import GravixLayer
        from gravixlayer._lanes import LanesTransport
        from tests.utils import TEST_API_KEY, TEST_BASE_URL

        for name in (
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
            "http_proxy", "https_proxy", "all_proxy",
        ):
            monkeypatch.delenv(name, raising=False)
        client = GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        assert isinstance(client._http_client._transport, LanesTransport)
        client.close()


class TestWarmupThroughLanes:
    def test_sync_warmup_warms_every_lane(self, mock_api):
        from gravixlayer import GravixLayer
        from tests.utils import TEST_API_KEY, TEST_BASE_URL

        route = mock_api.get(f"{TEST_BASE_URL}/v1/agents/runtime").mock(
            return_value=httpx.Response(200, json={"runtimes": [], "total": 0})
        )
        client = GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        client.warmup()
        assert route.call_count == H2_LANES
        client.close()

    async def test_async_warmup_warms_every_lane(self, mock_api):
        from gravixlayer import AsyncGravixLayer
        from tests.utils import TEST_API_KEY, TEST_BASE_URL

        route = mock_api.get(f"{TEST_BASE_URL}/v1/agents/runtime").mock(
            return_value=httpx.Response(200, json={"runtimes": [], "total": 0})
        )
        client = AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        await client.warmup()
        assert route.call_count == H2_LANES
        await client.aclose()
