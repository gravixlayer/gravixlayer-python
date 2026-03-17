import os
import httpx
import logging
import asyncio
import random
from urllib.parse import urlparse, urlunparse
from typing import Optional, Dict, Any


def _get_sdk_version() -> str:
    try:
        from .. import __version__
        return __version__
    except Exception:
        return "unknown"


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


class AsyncGravixLayer:
    """Async client for GravixLayer.

    Provides cloud runtime environments and template management for
    AI workloads. Reuses a single httpx.AsyncClient across all requests
    for connection pooling and performance.

    Use as an async context manager or call ``await client.aclose()`` when done.

    Example:
        >>> async with AsyncGravixLayer(api_key="...") as client:
        ...     runtime = await client.runtime.create(template="python-base-v1")
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
        logger: Optional[logging.Logger] = None,
        user_agent: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("GRAVIXLAYER_API_KEY")
        raw_url = base_url or os.environ.get("GRAVIXLAYER_BASE_URL", "https://api.gravixlayer.com")

        _known = ("/v1/inference", "/v1/agents", "/v1/vectors", "/v1/files", "/v1/deployments")
        parsed = urlparse(raw_url.rstrip("/"))
        path = parsed.path
        for prefix in _known:
            if path == prefix or path.startswith(prefix + "/"):
                path = ""
                break
        self.base_url = urlunparse((parsed.scheme, parsed.netloc, path.rstrip("/"), "", "", ""))

        if not (self.base_url.startswith("http://") or self.base_url.startswith("https://")):
            raise ValueError("Base URL must start with http:// or https://")

        self.cloud = cloud or os.environ.get("GRAVIXLAYER_CLOUD", "azure")
        self.region = region or os.environ.get("GRAVIXLAYER_REGION", "eastus2")
        self.timeout = timeout
        self.max_retries = max_retries
        self.custom_headers = headers or {}
        self.logger = logger or logging.getLogger("gravixlayer-async")
        self.user_agent = user_agent or f"gravixlayer-python/{_get_sdk_version()}"
        if not self.api_key:
            raise ValueError("API key must be provided via argument or GRAVIXLAYER_API_KEY environment variable")

        self._base_url_stripped = self.base_url.rstrip("/")
        self._service_urls = {
            svc: f"{self._base_url_stripped}/{svc}"
            for svc in ("v1/inference", "v1/agents", "v1/vectors", "v1/files", "v1/deployments")
        }

        self._default_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": self.user_agent,
            **self.custom_headers,
        }
        self._http_client = httpx.AsyncClient(
            http2=True,
            timeout=self.timeout,
            headers=self._default_headers,
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
            ),
        )

        self.runtime = AsyncRuntimeResource(self)
        self.templates = AsyncTemplates(self)

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

        if endpoint and (endpoint.startswith("http://") or endpoint.startswith("https://")):
            url = endpoint
        else:
            if _service:
                service_base = self._service_urls.get(_service) or f"{self._base_url_stripped}/{_service}"
            else:
                service_base = self._base_url_stripped
            url = f"{service_base}/{endpoint.lstrip('/')}" if endpoint else service_base

        has_files = "files" in kwargs
        headers = {"Content-Type": "application/json"} if not has_files else {}

        for attempt in range(self.max_retries + 1):
            try:
                request_kwargs: Dict[str, Any] = {
                    "method": method,
                    "url": url,
                    "headers": headers,
                    **kwargs,
                }
                if has_files:
                    request_kwargs["data"] = data
                else:
                    request_kwargs["json"] = data

                resp = await self._http_client.request(**request_kwargs)

                if 200 <= resp.status_code <= 207:
                    return resp
                elif resp.status_code == 401:
                    raise GravixLayerAuthenticationError("Authentication failed.")
                elif resp.status_code == 429:
                    if attempt < self.max_retries:
                        await asyncio.sleep(2**attempt + random.uniform(0, 1))
                        continue
                    raise GravixLayerRateLimitError(resp.text)
                elif resp.status_code in [502, 503, 504] and attempt < self.max_retries:
                    self.logger.warning(f"Server error: {resp.status_code}. Retrying...")
                    await asyncio.sleep(2**attempt + random.uniform(0, 1))
                    continue
                elif 400 <= resp.status_code < 500:
                    raise GravixLayerBadRequestError(resp.text)
                elif 500 <= resp.status_code < 600:
                    raise GravixLayerServerError(resp.text)
                else:
                    resp.raise_for_status()

            except httpx.RequestError as e:
                if attempt == self.max_retries:
                    raise GravixLayerConnectionError(str(e)) from e
                await asyncio.sleep(2**attempt + random.uniform(0, 1))

        raise GravixLayerError("Failed async request")
