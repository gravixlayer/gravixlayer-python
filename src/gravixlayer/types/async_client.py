import os
import httpx
import logging
import asyncio
import random
from typing import Optional, Dict, Any

from .. import __version__
from .._lanes import AsyncLanesTransport, H2_LANES, env_proxy_configured, warm_dns
from .._resource_utils import build_list_endpoint
from .._request_utils import (
    HTTP_LIMITS,
    REPLAYABLE_METHODS,
    RETRYABLE_STATUS,
    SUCCESS_STATUS,
    ApiKeyAuth,
    aresponse_text,
    build_url,
    can_retry,
    next_retry_delay,
    prepare_request_kwargs,
    split_authorization,
)
from ..types.exceptions import (
    GravixLayerError,
    GravixLayerConnectionError,
    error_from_response,
)
from ..resources.async_runtime import AsyncRuntimeResource
from ..resources.async_templates import AsyncTemplates
from ..resources.async_snapshots import AsyncSnapshots
from ..resources.async_agents import AsyncAgents
from ..resources.async_identity import AsyncIdentity
from ..resources.async_network_policies import AsyncNetworkPolicies
from .. import telemetry

class AsyncGravixLayer:
    """Async client for GravixLayer.

    Provides cloud runtime environments and template management for
    AI workloads. Reuses a single httpx.AsyncClient across all requests
    for connection pooling and performance.

    Use as an async context manager or call ``await client.aclose()`` when done.
    For minimal first-request latency after process start, ``await client.warmup()``
    once during startup (same idea as :meth:`gravixlayer.GravixLayer.warmup`).

    Transport defaults to **HTTP/2** (``http2=True``): HTTPS requests run over a
    small pool of parallel HTTP/2 connections — opened lazily and filled once a
    burst is proven — so concurrent calls spread across connections instead of
    serializing on one. Pass ``http2=False`` for a plain HTTP/1.1 pool.

    Example:
        >>> async with AsyncGravixLayer() as client:  # defaults to cloud="aws", region="us-east-1"
        ...     sandbox = await client.runtime.create()  # defaults to template="base-small"
        ...     result = await client.runtime.run_code(sandbox.runtime_id, "print('hello')")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        cloud: Optional[str] = None,
        region: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        headers: Optional[Dict[str, str]] = None,
        http2: bool = True,
    ):
        self.api_key = api_key or os.environ.get("GRAVIXLAYER_API_KEY")
        if not self.api_key:
            raise ValueError("API key must be provided via argument or GRAVIXLAYER_API_KEY environment variable")

        raw_url = base_url or os.environ.get("GRAVIXLAYER_BASE_URL", "https://api.gravixlayer.ai")
        self.base_url = raw_url.rstrip("/")

        if not (self.base_url.startswith("http://") or self.base_url.startswith("https://")):
            raise ValueError("Base URL must start with http:// or https://")

        self.cloud = cloud or os.environ.get("GRAVIXLAYER_CLOUD", "aws")
        self.region = region or os.environ.get("GRAVIXLAYER_REGION", "us-east-1")
        self.timeout = timeout
        self.max_retries = max_retries
        self._retry_attempts = range(self.max_retries + 1)

        # Activate client tracing when GRAVIXLAYER_ENABLE_TELEMETRY is set (or a
        # prior enable_telemetry / configure_otel call). A bare client never
        # starts a background exporter without the flag.
        telemetry.maybe_configure_from_env()

        self._logger = logging.getLogger("gravixlayer-async")

        user_agent = f"gravixlayer-python/{__version__}"
        authorization, custom_headers = split_authorization(self.api_key, headers)

        self._service_urls = {
            svc: f"{self.base_url}/{svc}"
            for svc in (
                "v1/inference",
                "v1/agents",
                "v1/vectors",
                "v1/files",
                "v1/deployments",
                "v1/identity",
                "v1/network-policies",
            )
        }

        # Over HTTPS the default transport spreads bursts across parallel
        # HTTP/2 lanes; the plain HTTP/1.1 pool is unchanged for ``http2=False``.
        # When a proxy is set in the environment the client builds its own
        # transports so proxy mounts still apply — lanes connect directly.
        if http2 and not env_proxy_configured():
            self._transport: httpx.AsyncBaseTransport = AsyncLanesTransport(
                fallback_limits=HTTP_LIMITS
            )
            self._http_client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "User-Agent": user_agent,
                    **custom_headers,
                },
                auth=ApiKeyAuth(authorization, self.base_url),
                transport=self._transport,
            )
        else:
            self._http_client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "User-Agent": user_agent,
                    **custom_headers,
                },
                auth=ApiKeyAuth(authorization, self.base_url),
                http2=http2,
                limits=HTTP_LIMITS,
            )
            self._transport = self._http_client._transport

        # The hostname lookup warms on a daemon thread while the client
        # finishes constructing, so the first request's connect skips it.
        url = httpx.URL(self.base_url)
        if url.host:
            warm_dns(url.host)

        self.runtime = AsyncRuntimeResource(self)
        self.templates = AsyncTemplates(self)
        self.snapshots = AsyncSnapshots(self)
        self.agents = AsyncAgents(self)
        self.identity = AsyncIdentity(self)
        self.network_policies = AsyncNetworkPolicies(self)

    async def warmup(self) -> None:
        """Same as :meth:`gravixlayer.GravixLayer.warmup` but async.

        Call during application startup (e.g. FastAPI ``lifespan``) before handling
        traffic so the first user-facing request does not pay cold TLS connect.
        """
        endpoint = build_list_endpoint("runtime", limit=1, offset=0)
        url = build_url(endpoint, "v1/agents", self._service_urls, self.base_url)
        if isinstance(self._transport, AsyncLanesTransport):
            # Fill the lane pool, then drive one request per lane so every
            # connection's handshake finishes before real traffic arrives.
            self._transport.ensure_pool(httpx.URL(url))
            responses = await asyncio.gather(
                *(self._http_client.get(url) for _ in range(H2_LANES))
            )
            for resp in responses:
                if not resp.is_success:
                    raise error_from_response(resp.status_code, resp.text, resp.headers)
            return
        resp = await self._http_client.get(url)
        if resp.status_code in SUCCESS_STATUS:
            return
        if not resp.is_success:
            raise error_from_response(resp.status_code, resp.text, resp.headers)

    async def aclose(self) -> None:
        """Close the underlying HTTP client and release connections."""
        await self._http_client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()

    async def _make_request(
        self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, stream: bool = False, **kwargs
    ) -> httpx.Response:
        _service = kwargs.pop("_service", "v1/inference")
        url = build_url(endpoint, _service, self._service_urls, self.base_url)
        prepare_request_kwargs(data, kwargs)

        if not telemetry._spans_active():
            return await self._send_with_retries(method, url, stream, kwargs)

        with telemetry.client_span(method, url) as span:
            headers = dict(kwargs.get("headers") or {})
            telemetry.inject(headers)
            kwargs["headers"] = headers
            resp = await self._send_with_retries(method, url, stream, kwargs)
            if span is not None:
                span.set_attribute("http.response.status_code", resp.status_code)
            return resp

    async def _send_with_retries(
        self, method: str, url: str, stream: bool, kwargs: Dict[str, Any]
    ) -> httpx.Response:
        last_exc: Optional[Exception] = None
        logger_warning = self._logger.warning
        sleep = asyncio.sleep
        rand = random.random
        max_retries = self.max_retries
        can_retry_local = can_retry
        next_retry_delay_local = next_retry_delay

        for attempt in self._retry_attempts:
            try:
                if stream:
                    req = self._http_client.build_request(method, url, **kwargs)
                    resp = await self._http_client.send(req, stream=True)
                else:
                    resp = await self._http_client.request(method, url, **kwargs)
                status = resp.status_code

                if status in SUCCESS_STATUS:
                    return resp

                body = await aresponse_text(resp)
                if status == 429:
                    if can_retry_local(attempt, max_retries):
                        await sleep(next_retry_delay_local(attempt, rand, resp.headers.get("Retry-After")))
                        continue
                    raise error_from_response(status, body, resp.headers)

                if (
                    status in RETRYABLE_STATUS
                    and method in REPLAYABLE_METHODS
                    and can_retry_local(attempt, max_retries)
                ):
                    logger_warning("Server error %d. Retrying...", status)
                    await sleep(next_retry_delay_local(attempt, rand))
                    continue

                if status >= 400 or not resp.is_success:
                    raise error_from_response(status, body, resp.headers)

            except httpx.RequestError as exc:
                last_exc = exc
                if method in REPLAYABLE_METHODS and can_retry_local(attempt, max_retries):
                    await sleep(next_retry_delay_local(attempt, rand))
                    continue
                raise GravixLayerConnectionError(str(exc)) from exc

        raise GravixLayerError("Failed to complete request.") from last_exc
