"""
Tests for GravixLayer sync and async client scaffolding.

Covers: initialization, auth, URL normalization, retry logic, error handling,
context managers, headers, and resource attributes.
"""

import os
import pytest
import httpx
import respx

from conftest import TEST_API_KEY, TEST_BASE_URL, AGENTS_BASE, VALID_UUID, make_runtime_response

from gravixlayer import GravixLayer, AsyncGravixLayer
from gravixlayer.types.exceptions import (
    GravixLayerError,
    GravixLayerAuthenticationError,
    GravixLayerRateLimitError,
    GravixLayerServerError,
    GravixLayerBadRequestError,
    GravixLayerConnectionError,
)


# ===================================================================
# Sync Client — Initialization
# ===================================================================


class TestSyncClientInit:
    def test_requires_api_key(self):
        env = os.environ.copy()
        env.pop("GRAVIXLAYER_API_KEY", None)
        with pytest.raises(ValueError, match="API key must be provided"):
            GravixLayer(api_key=None, base_url=TEST_BASE_URL)

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("GRAVIXLAYER_API_KEY", "env-key")
        client = GravixLayer(base_url=TEST_BASE_URL)
        assert client.api_key == "env-key"
        client.close()

    def test_explicit_api_key_overrides_env(self, monkeypatch):
        monkeypatch.setenv("GRAVIXLAYER_API_KEY", "env-key")
        client = GravixLayer(api_key="explicit-key", base_url=TEST_BASE_URL)
        assert client.api_key == "explicit-key"
        client.close()

    def test_default_base_url(self, monkeypatch):
        monkeypatch.delenv("GRAVIXLAYER_BASE_URL", raising=False)
        client = GravixLayer(api_key=TEST_API_KEY)
        assert client.base_url == "https://api.gravixlayer.com"
        client.close()

    def test_base_url_from_env(self, monkeypatch):
        monkeypatch.setenv("GRAVIXLAYER_API_KEY", TEST_API_KEY)
        monkeypatch.setenv("GRAVIXLAYER_BASE_URL", "https://custom.api.com")
        client = GravixLayer()
        assert client.base_url == "https://custom.api.com"
        client.close()

    def test_base_url_invalid_scheme(self):
        with pytest.raises(ValueError, match="must start with http"):
            GravixLayer(api_key=TEST_API_KEY, base_url="ftp://invalid.com")

    def test_base_url_strips_service_paths(self):
        client = GravixLayer(api_key=TEST_API_KEY, base_url="https://api.example.com/v1/inference")
        assert client.base_url == "https://api.example.com"
        client.close()

        client2 = GravixLayer(api_key=TEST_API_KEY, base_url="https://api.example.com/v1/agents")
        assert client2.base_url == "https://api.example.com"
        client2.close()

    def test_base_url_strips_trailing_slash(self):
        client = GravixLayer(api_key=TEST_API_KEY, base_url="https://api.example.com/")
        assert not client.base_url.endswith("/")
        client.close()

    def test_cloud_region_defaults(self):
        client = GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        assert client.cloud == "azure"
        assert client.region == "eastus2"
        client.close()

    def test_cloud_region_from_env(self, monkeypatch):
        monkeypatch.setenv("GRAVIXLAYER_CLOUD", "aws")
        monkeypatch.setenv("GRAVIXLAYER_REGION", "us-west-2")
        client = GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        assert client.cloud == "aws"
        assert client.region == "us-west-2"
        client.close()

    def test_custom_timeout(self):
        client = GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL, timeout=120.0)
        assert client.timeout == 120.0
        client.close()

    def test_custom_max_retries(self):
        client = GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL, max_retries=5)
        assert client.max_retries == 5
        client.close()

    def test_has_runtimes_resource(self):
        client = GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        assert hasattr(client, "runtime")
        client.close()

    def test_has_templates_resource(self):
        client = GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        assert hasattr(client, "templates")
        client.close()

    def test_user_agent_header_contains_version(self):
        client = GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        assert client.user_agent.startswith("gravixlayer-python/")
        client.close()

    def test_custom_user_agent(self):
        client = GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL, user_agent="my-app/1.0")
        assert client.user_agent == "my-app/1.0"
        client.close()

    def test_custom_headers_merged(self):
        custom = {"X-Custom": "value"}
        client = GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL, headers=custom)
        assert client.custom_headers == custom
        client.close()


# ===================================================================
# Sync Client — Context Manager
# ===================================================================


class TestSyncClientContextManager:
    def test_context_manager(self):
        with GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            assert client.api_key == TEST_API_KEY

    def test_close_is_idempotent(self):
        client = GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        client.close()
        client.close()  # should not raise


# ===================================================================
# Sync Client — _make_request and Error Handling
# ===================================================================


class TestSyncClientRequest:
    def test_401_raises_auth_error(self, client, mock_api):
        mock_api.get(f"{AGENTS_BASE}/runtimes/{VALID_UUID}").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        with pytest.raises(GravixLayerAuthenticationError):
            client.runtime.get(VALID_UUID)

    def test_429_raises_rate_limit_after_retries(self, mock_api):
        c = GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL, max_retries=0)
        mock_api.get(f"{AGENTS_BASE}/runtimes/{VALID_UUID}").mock(
            return_value=httpx.Response(429, text="Too Many Requests")
        )
        with pytest.raises(GravixLayerRateLimitError):
            c.runtime.get(VALID_UUID)
        c.close()

    def test_400_raises_bad_request(self, client, mock_api):
        mock_api.post(f"{AGENTS_BASE}/runtimes").mock(
            return_value=httpx.Response(400, text="Bad Request")
        )
        with pytest.raises(GravixLayerBadRequestError):
            client.runtime.create()

    def test_500_raises_server_error_after_retries(self, mock_api):
        c = GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL, max_retries=0)
        mock_api.post(f"{AGENTS_BASE}/runtimes").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        with pytest.raises(GravixLayerServerError):
            c.runtime.create()
        c.close()

    def test_connection_error_raises_after_retries(self, mock_api):
        c = GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL, max_retries=0)
        mock_api.get(f"{AGENTS_BASE}/runtimes/{VALID_UUID}").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        with pytest.raises(GravixLayerConnectionError):
            c.runtime.get(VALID_UUID)
        c.close()

    def test_successful_request_returns_response(self, client, mock_api):
        mock_api.get(f"{AGENTS_BASE}/runtimes/{VALID_UUID}").mock(
            return_value=httpx.Response(200, json=make_runtime_response())
        )
        rt = client.runtime.get(VALID_UUID)
        assert rt.runtime_id == VALID_UUID
        assert rt.status == "running"

    def test_absolute_url_endpoint(self, client, mock_api):
        abs_url = "https://other.api.com/custom"
        mock_api.get(abs_url).mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        resp = client._make_request("GET", abs_url)
        assert resp.json() == {"ok": True}


# ===================================================================
# Async Client — Initialization
# ===================================================================


class TestAsyncClientInit:
    def test_requires_api_key(self):
        with pytest.raises(ValueError, match="API key must be provided"):
            AsyncGravixLayer(api_key=None, base_url=TEST_BASE_URL)

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("GRAVIXLAYER_API_KEY", "env-key")
        c = AsyncGravixLayer(base_url=TEST_BASE_URL)
        assert c.api_key == "env-key"

    def test_base_url_strips_service_paths(self):
        c = AsyncGravixLayer(api_key=TEST_API_KEY, base_url="https://api.example.com/v1/files")
        assert c.base_url == "https://api.example.com"

    def test_base_url_invalid_scheme(self):
        with pytest.raises(ValueError, match="must start with http"):
            AsyncGravixLayer(api_key=TEST_API_KEY, base_url="ftp://bad.com")

    def test_has_runtimes_and_templates(self):
        c = AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        assert hasattr(c, "runtime")
        assert hasattr(c, "templates")

    def test_user_agent_contains_version(self):
        c = AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        assert "gravixlayer-python/" in c.user_agent


# ===================================================================
# Async Client — Context Manager
# ===================================================================


class TestAsyncClientContextManager:
    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            assert client.api_key == TEST_API_KEY


# ===================================================================
# Async Client — Error Handling
# ===================================================================


class TestAsyncClientErrors:
    @pytest.mark.asyncio
    async def test_401_raises_auth_error(self, mock_api):
        async with AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            mock_api.get(f"{AGENTS_BASE}/runtimes/{VALID_UUID}").mock(
                return_value=httpx.Response(401, json={"error": "Unauthorized"})
            )
            with pytest.raises(GravixLayerAuthenticationError):
                await client.runtime.get(VALID_UUID)

    @pytest.mark.asyncio
    async def test_429_raises_rate_limit(self, mock_api):
        client = AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL, max_retries=0)
        mock_api.get(f"{AGENTS_BASE}/runtimes/{VALID_UUID}").mock(
            return_value=httpx.Response(429, text="Too Many Requests")
        )
        with pytest.raises(GravixLayerRateLimitError):
            await client.runtime.get(VALID_UUID)
        await client.aclose()

    @pytest.mark.asyncio
    async def test_500_raises_server_error(self, mock_api):
        client = AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL, max_retries=0)
        mock_api.post(f"{AGENTS_BASE}/runtimes").mock(
            return_value=httpx.Response(500, text="Server Error")
        )
        with pytest.raises(GravixLayerServerError):
            await client.runtime.create()
        await client.aclose()

    @pytest.mark.asyncio
    async def test_connection_error(self, mock_api):
        client = AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL, max_retries=0)
        mock_api.get(f"{AGENTS_BASE}/runtimes/{VALID_UUID}").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        with pytest.raises(GravixLayerConnectionError):
            await client.runtime.get(VALID_UUID)
        await client.aclose()


# ===================================================================
# Exception Hierarchy
# ===================================================================


class TestExceptionHierarchy:
    def test_all_exceptions_inherit_base(self):
        assert issubclass(GravixLayerAuthenticationError, GravixLayerError)
        assert issubclass(GravixLayerRateLimitError, GravixLayerError)
        assert issubclass(GravixLayerServerError, GravixLayerError)
        assert issubclass(GravixLayerBadRequestError, GravixLayerError)
        assert issubclass(GravixLayerConnectionError, GravixLayerError)

    def test_base_inherits_exception(self):
        assert issubclass(GravixLayerError, Exception)

    def test_exception_message(self):
        err = GravixLayerAuthenticationError("auth failed")
        assert str(err) == "auth failed"
