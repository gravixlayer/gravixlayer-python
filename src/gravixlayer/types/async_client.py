import os
import httpx
import logging
import asyncio
import random
from typing import Optional, Dict, Any

from .. import __version__
from .._resource_utils import build_list_endpoint
from .._request_utils import (
    RETRYABLE_STATUS,
    SUCCESS_STATUS,
    build_url,
    can_retry,
    next_retry_delay,
    prepare_request_kwargs,
)
from ..types.exceptions import (
    GravixLayerError,
    GravixLayerAuthenticationError,
    GravixLayerRateLimitError,
    GravixLayerServerError,
    GravixLayerBadRequestError,
    GravixLayerConnectionError,
)
from ..resources.async_runtime import AsyncRuntimeResource
from ..resources.async_templates import AsyncTemplates
from ..resources.async_agents import AsyncAgents

class AsyncGravixLayer:
    """Async client for GravixLayer.

    Provides cloud runtime environments and template management for
    AI workloads. Reuses a single httpx.AsyncClient across all requests
    for connection pooling and performance.

    Use as an async context manager or call ``await client.aclose()`` when done.
    For minimal first-request latency after process start, ``await client.warmup()``
    once during startup (same idea as :meth:`gravixlayer.GravixLayer.warmup`).

    Transport defaults to **HTTP/1.1** (``http2=False``). Pass ``http2=True`` to use
    HTTP/2 (ALPN ``h2``) when you want multiplexing or your measurements favor it.

    Example:
        >>> async with AsyncGravixLayer(api_key="...") as client:
        ...     runtime = await client.runtime.create(template="python-3.14-base-small")
        ...     result = await client.runtime.run_code(runtime.id, "print('hello')")
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
        http2: bool = False,
    ):
        self.api_key = api_key or os.environ.get("GRAVIXLAYER_API_KEY")
        if not self.api_key:
            raise ValueError("API key must be provided via argument or GRAVIXLAYER_API_KEY environment variable")

        raw_url = base_url or os.environ.get("GRAVIXLAYER_BASE_URL", "https://api.gravixlayer.ai")
        self.base_url = raw_url.rstrip("/")

        if not (self.base_url.startswith("http://") or self.base_url.startswith("https://")):
            raise ValueError("Base URL must start with http:// or https://")

        self.cloud = cloud or os.environ.get("GRAVIXLAYER_CLOUD", "azure")
        self.region = region or os.environ.get("GRAVIXLAYER_REGION", "eastus2")
        self.timeout = timeout
        self.max_retries = max_retries
        self._retry_attempts = range(self.max_retries + 1)

        self._logger = logging.getLogger("gravixlayer-async")

        user_agent = f"gravixlayer-python/{__version__}"
        custom_headers = headers or {}

        self._service_urls = {
            svc: f"{self.base_url}/{svc}"
            for svc in ("v1/inference", "v1/agents", "v1/vectors", "v1/files", "v1/deployments")
        }

        self._http_client = httpx.AsyncClient(
            http2=http2,
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": user_agent,
                **custom_headers,
            },
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
            ),
        )

        self.runtime = AsyncRuntimeResource(self)
        self.templates = AsyncTemplates(self)
        self.agents = AsyncAgents(self)

    async def warmup(self) -> None:
        """Same as :meth:`gravixlayer.GravixLayer.warmup` but async.

        Call during application startup (e.g. FastAPI ``lifespan``) before handling
        traffic so the first user-facing request does not pay cold TLS connect.
        """
        endpoint = build_list_endpoint("runtime", limit=1, offset=0)
        url = build_url(endpoint, "v1/agents", self._service_urls, self.base_url)
        resp = await self._http_client.get(url)
        if resp.status_code == 401:
            raise GravixLayerAuthenticationError("Authentication failed.")
        if resp.status_code in SUCCESS_STATUS:
            return
        if 400 <= resp.status_code < 500:
            raise GravixLayerBadRequestError(resp.text)
        if resp.status_code >= 500:
            raise GravixLayerServerError(resp.text)
        resp.raise_for_status()

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

        last_exc: Optional[Exception] = None
        logger_warning = self._logger.warning
        sleep = asyncio.sleep
        rand = random.random
        max_retries = self.max_retries
        can_retry_local = can_retry
        next_retry_delay_local = next_retry_delay

        for attempt in self._retry_attempts:
            try:
                resp = await self._http_client.request(method, url, **kwargs)
                status = resp.status_code

                if status in SUCCESS_STATUS:
                    return resp

                if status == 401:
                    raise GravixLayerAuthenticationError("Authentication failed.")

                if status == 429:
                    if can_retry_local(attempt, max_retries):
                        await sleep(next_retry_delay_local(attempt, rand, resp.headers.get("Retry-After")))
                        continue
                    raise GravixLayerRateLimitError(resp.text)

                if status in RETRYABLE_STATUS and can_retry_local(attempt, max_retries):
                    logger_warning("Server error %d. Retrying...", status)
                    await sleep(next_retry_delay_local(attempt, rand))
                    continue

                if 400 <= status < 500:
                    raise GravixLayerBadRequestError(resp.text)
                if status >= 500:
                    raise GravixLayerServerError(resp.text)

                resp.raise_for_status()

            except httpx.RequestError as exc:
                last_exc = exc
                if can_retry_local(attempt, max_retries):
                    await sleep(next_retry_delay_local(attempt, rand))
                    continue
                raise GravixLayerConnectionError(str(exc)) from exc

        raise GravixLayerError("Failed to complete request.") from last_exc
