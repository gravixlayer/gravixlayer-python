"""
Tests for RuntimeServiceHandle / AsyncRuntimeServiceHandle (mocked HTTP).

Covers: token header, path joining, verb helpers, and keeping requests (and
the service token) on the service's own origin.
"""

import httpx
import pytest

from gravixlayer.resources.async_runtime_service import AsyncRuntimeServiceHandle
from gravixlayer.resources.runtime_service import RuntimeServiceHandle
from gravixlayer.types.runtime import RuntimeWebService

SERVICE = "https://svc-1.service.example.test/"
TOKEN_HEADER = "X-Gravix-Web-Service-Token"

OFF_ORIGIN_PATHS = [
    "https://attacker.example/collect",
    "http:attacker.example/collect",
    "https://svc-1.service.example.test:8443/x",
    "http://svc-1.service.example.test/x",
]


def _info(is_public=False):
    return RuntimeWebService.from_api(
        {
            "runtime_id": "rt-1",
            "port": 8080,
            "web_url": SERVICE,
            "token": "svc-token",
            "is_public": is_public,
        }
    )


class TestRuntimeServiceHandle:
    def test_sends_the_token_to_the_joined_path(self, mock_api):
        route = mock_api.get(f"{SERVICE}api/health").mock(return_value=httpx.Response(200))
        with RuntimeServiceHandle(_info()) as handle:
            assert handle.get("/api/health", headers={"X-Extra": "1"}).status_code == 200
        request = route.calls.last.request
        assert request.headers[TOKEN_HEADER] == "svc-token"
        assert request.headers["X-Extra"] == "1"

    def test_public_service_sends_no_token(self, mock_api):
        route = mock_api.get(SERVICE).mock(return_value=httpx.Response(200))
        with RuntimeServiceHandle(_info(is_public=True)) as handle:
            handle.get("")
        assert TOKEN_HEADER not in route.calls.last.request.headers

    @pytest.mark.parametrize("path", ["//attacker.example/x", f"{SERVICE}x"])
    def test_paths_that_stay_on_the_service_keep_the_token(self, mock_api, path):
        route = mock_api.route(host="svc-1.service.example.test").mock(return_value=httpx.Response(200))
        with RuntimeServiceHandle(_info()) as handle:
            handle.get(path)
        request = route.calls.last.request
        assert request.url.host == "svc-1.service.example.test"
        assert request.headers[TOKEN_HEADER] == "svc-token"

    @pytest.mark.parametrize("path", OFF_ORIGIN_PATHS)
    def test_rejects_a_path_on_another_origin(self, mock_api, path):
        with RuntimeServiceHandle(_info()) as handle:
            with pytest.raises(ValueError, match="service's origin"):
                handle.get(path)
        assert mock_api.calls.call_count == 0

    def test_verb_helpers(self, mock_api):
        route = mock_api.route(host="svc-1.service.example.test").mock(return_value=httpx.Response(204))
        handle = RuntimeServiceHandle(_info())
        for call in (handle.post, handle.put, handle.patch, handle.delete):
            call("/items")
        handle.close()
        assert [c.request.method for c in route.calls] == ["POST", "PUT", "PATCH", "DELETE"]
        assert (handle.web_url, handle.url, handle.browser_url, handle.service_url) == (SERVICE,) * 4
        assert (handle.token, handle.port, handle.expires_at, handle.is_public) == ("svc-token", 8080, "", False)


class TestAsyncRuntimeServiceHandle:
    @pytest.mark.asyncio
    async def test_sends_the_token_and_verb_helpers(self, mock_api):
        route = mock_api.route(host="svc-1.service.example.test").mock(return_value=httpx.Response(200))
        async with AsyncRuntimeServiceHandle(_info()) as handle:
            for call in (handle.get, handle.post, handle.put, handle.patch, handle.delete):
                await call("/items", headers={"X-Extra": "1"})
        assert [c.request.method for c in route.calls] == ["GET", "POST", "PUT", "PATCH", "DELETE"]
        assert all(c.request.headers[TOKEN_HEADER] == "svc-token" for c in route.calls)
        assert all(c.request.headers["X-Extra"] == "1" for c in route.calls)
        assert str(route.calls.last.request.url) == f"{SERVICE}items"
        assert (handle.web_url, handle.url, handle.browser_url, handle.service_url) == (SERVICE,) * 4
        assert (handle.token, handle.port) == ("svc-token", 8080)

    @pytest.mark.asyncio
    async def test_public_service_sends_no_token(self, mock_api):
        route = mock_api.get(SERVICE).mock(return_value=httpx.Response(200))
        async with AsyncRuntimeServiceHandle(_info(is_public=True)) as handle:
            await handle.get("")
        assert TOKEN_HEADER not in route.calls.last.request.headers

    @pytest.mark.asyncio
    @pytest.mark.parametrize("path", OFF_ORIGIN_PATHS)
    async def test_rejects_a_path_on_another_origin(self, mock_api, path):
        async with AsyncRuntimeServiceHandle(_info()) as handle:
            with pytest.raises(ValueError, match="service's origin"):
                await handle.get(path)
        assert mock_api.calls.call_count == 0
