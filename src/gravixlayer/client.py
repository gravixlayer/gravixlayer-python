import os
import time
import random
import logging
from typing import Optional, Dict, Any

import httpx

from . import __version__
from ._resource_utils import build_list_endpoint
from ._request_utils import (
    RETRYABLE_STATUS,
    SUCCESS_STATUS,
    build_url,
    can_retry,
    next_retry_delay,
    prepare_request_kwargs,
)
from .resources.runtime import RuntimeResource
from .resources.templates import Templates
from .resources.agents import Agents
from .types.exceptions import (
    GravixLayerError,
    GravixLayerAuthenticationError,
    GravixLayerRateLimitError,
    GravixLayerServerError,
    GravixLayerBadRequestError,
    GravixLayerConnectionError,
)

class GravixLayer:
    """
    GravixLayer Python SDK Client

    Official Python client for the GravixLayer API. Provides cloud runtime
    environments and template management for AI workloads.

    Args:
        api_key: API key for authentication (or GRAVIXLAYER_API_KEY env var)
        base_url: Base URL for the API (or GRAVIXLAYER_BASE_URL env var, default: "https://api.gravixlayer.ai")
        cloud: Default cloud provider for runtime/template operations (default: "azure")
        region: Default region for runtime/template operations (default: "eastus2")
        timeout: Request timeout in seconds (default: 60.0)
        max_retries: Maximum retry attempts for transient failures (default: 3)
        headers: Additional HTTP headers to include in requests
        http2: Use HTTP/2 when True. Default is False (HTTP/1.1) for lower request
            latency on typical single-stream API usage; pass True for multiplexing
            or when profiling shows benefit.
        warmup_on_init: If True, call :meth:`warmup` at the end of construction so the
            first user request does not pay TCP+TLS+ALPN setup (adds one list-runtime GET).

    Example:
        >>> from gravixlayer import GravixLayer
        >>> client = GravixLayer(api_key="your-api-key", base_url="https://api.gravixlayer.ai")
        >>> runtime = client.runtime.create(template="python-base-v1")
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
        warmup_on_init: bool = False,
    ):
        self.api_key = api_key or os.environ.get("GRAVIXLAYER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key must be provided via 'api_key' argument or GRAVIXLAYER_API_KEY environment variable"
            )

        raw_url = base_url or os.environ.get("GRAVIXLAYER_BASE_URL", "https://api.gravixlayer.ai")
        self.base_url = raw_url.rstrip("/")

        if not (self.base_url.startswith("http://") or self.base_url.startswith("https://")):
            raise ValueError("Base URL must start with http:// or https://")

        self.cloud = cloud or os.environ.get("GRAVIXLAYER_CLOUD", "azure")
        self.region = region or os.environ.get("GRAVIXLAYER_REGION", "eastus2")
        self.timeout = timeout
        self.max_retries = max_retries
        self._retry_attempts = range(self.max_retries + 1)

        self._logger = logging.getLogger("gravixlayer")

        user_agent = f"gravixlayer-python/{__version__}"
        custom_headers = headers or {}

        self._service_urls = {
            svc: f"{self.base_url}/{svc}"
            for svc in ("v1/inference", "v1/agents", "v1/vectors", "v1/files", "v1/deployments")
        }

        self._http_client = httpx.Client(
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

        self.runtime = RuntimeResource(self)
        self.templates = Templates(self)
        self.agents = Agents(self)

        if warmup_on_init:
            self.warmup()

    def warmup(self) -> None:
        """Establish TCP, TLS, and application protocol (HTTP/2 or HTTP/1.1) to the API.

        Performs a minimal authenticated ``GET`` (runtime list, ``limit=1``) on the same
        connection pool used by all other calls. Use this before latency-sensitive work,
        especially when issuing **parallel** requests from multiple threads right after
        constructing the client: without warmup, each in-flight request can contend on
        cold connection setup (~50–150 ms over HTTPS is typical, dominated by TLS).

        This does not remove TLS for a brand-new process—it moves that cost to an
        explicit, idempotent step so measured requests reflect server-side latency.

        Raises:
            GravixLayerAuthenticationError: if the API returns 401.
            GravixLayerBadRequestError: on other 4xx responses.
            GravixLayerServerError: on 5xx responses.
        """
        endpoint = build_list_endpoint("runtime", limit=1, offset=0)
        url = build_url(endpoint, "v1/agents", self._service_urls, self.base_url)
        resp = self._http_client.get(url)
        if resp.status_code == 401:
            raise GravixLayerAuthenticationError("Authentication failed.")
        if resp.status_code in SUCCESS_STATUS:
            return
        if 400 <= resp.status_code < 500:
            raise GravixLayerBadRequestError(resp.text)
        if resp.status_code >= 500:
            raise GravixLayerServerError(resp.text)
        resp.raise_for_status()

    def close(self) -> None:
        """Close the underlying HTTP session and release connections."""
        self._http_client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _make_request(
        self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, stream: bool = False, **kwargs
    ) -> httpx.Response:
        _service = kwargs.pop("_service", "v1/inference")
        url = build_url(endpoint, _service, self._service_urls, self.base_url)
        prepare_request_kwargs(data, kwargs)

        last_exc: Optional[Exception] = None
        logger_warning = self._logger.warning
        sleep = time.sleep
        rand = random.random
        max_retries = self.max_retries
        can_retry_local = can_retry
        next_retry_delay_local = next_retry_delay

        for attempt in self._retry_attempts:
            try:
                if stream:
                    req = self._http_client.build_request(method, url, **kwargs)
                    resp = self._http_client.send(req, stream=True)
                else:
                    resp = self._http_client.request(method, url, **kwargs)

                status = resp.status_code

                if status in SUCCESS_STATUS:
                    return resp

                if status == 401:
                    raise GravixLayerAuthenticationError("Authentication failed.")

                if status == 429:
                    if can_retry_local(attempt, max_retries):
                        delay = next_retry_delay_local(
                            attempt,
                            rand,
                            resp.headers.get("Retry-After"),
                        )
                        logger_warning("Rate limited. Retrying in %.1fs...", delay)
                        sleep(delay)
                        continue
                    raise GravixLayerRateLimitError(resp.text)

                if status in RETRYABLE_STATUS and can_retry_local(attempt, max_retries):
                    delay = next_retry_delay_local(attempt, rand)
                    logger_warning("Server error %d. Retrying in %.1fs...", status, delay)
                    sleep(delay)
                    continue

                if 400 <= status < 500:
                    raise GravixLayerBadRequestError(resp.text)
                if status >= 500:
                    raise GravixLayerServerError(resp.text)

                resp.raise_for_status()

            except httpx.RequestError as exc:
                last_exc = exc
                if can_retry_local(attempt, max_retries):
                    delay = next_retry_delay_local(attempt, rand)
                    logger_warning("Connection error, retrying in %.1fs...", delay)
                    sleep(delay)
                    continue
                raise GravixLayerConnectionError(str(exc)) from exc

        raise GravixLayerError("Failed to complete request.") from last_exc
