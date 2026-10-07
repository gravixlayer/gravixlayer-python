import os
import time
import random
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any

import httpx

from . import __version__
from ._lanes import H2_LANES, LanesTransport, env_proxy_configured, warm_dns
from ._resource_utils import build_list_endpoint
from ._request_utils import (
    HTTP_LIMITS,
    REPLAYABLE_METHODS,
    RETRYABLE_STATUS,
    SUCCESS_STATUS,
    ApiKeyAuth,
    build_url,
    can_retry,
    next_retry_delay,
    prepare_request_kwargs,
    response_text,
    split_authorization,
)
from .resources.runtime import RuntimeResource
from .resources.templates import Templates
from .resources.snapshots import Snapshots
from .resources.agents import Agents
from .resources.identity import Identity
from .resources.network_policies import NetworkPolicies
from . import telemetry
from .types.exceptions import (
    GravixLayerError,
    GravixLayerConnectionError,
    error_from_response,
)

class GravixLayer:
    """
    GravixLayer Python SDK Client

    Official Python client for the GravixLayer API. Provides cloud runtime
    environments and template management for AI workloads.

    Args:
        api_key: API key for authentication (or GRAVIXLAYER_API_KEY env var)
        base_url: Base URL for the API (or GRAVIXLAYER_BASE_URL env var, default: "https://api.gravixlayer.ai")
        cloud: Default cloud for runtime/template operations (default: "aws")
        region: Default region for runtime/template operations (default: "us-east-1")
        timeout: Request timeout in seconds (default: 60.0)
        max_retries: Maximum retry attempts for transient failures (default: 3)
        headers: Additional HTTP headers to include in requests
        http2: Use HTTP/2 when True (the default). HTTPS requests run over a
            small pool of parallel HTTP/2 connections — opened lazily and filled
            once a burst is proven — so concurrent calls spread across
            connections instead of serializing on one. Pass ``False`` for a
            plain HTTP/1.1 pool.
        warmup_on_init: If True, call :meth:`warmup` at the end of construction so the
            first user request does not pay TCP+TLS+ALPN setup (adds one GET per
            transport lane).

    Example:
        >>> from gravixlayer import GravixLayer
        >>> client = GravixLayer()  # defaults to cloud="aws", region="us-east-1"
        >>> sandbox = client.runtime.create()  # defaults to template="base-small"
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

        self.cloud = cloud or os.environ.get("GRAVIXLAYER_CLOUD", "aws")
        self.region = region or os.environ.get("GRAVIXLAYER_REGION", "us-east-1")
        self.timeout = timeout
        self.max_retries = max_retries
        self._retry_attempts = range(self.max_retries + 1)

        # Activate client tracing when GRAVIXLAYER_ENABLE_TELEMETRY is set (or a
        # prior enable_telemetry / configure_otel call). A bare GravixLayer() never
        # starts a background exporter without the flag.
        telemetry.maybe_configure_from_env()

        self._logger = logging.getLogger("gravixlayer")

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
            self._transport: httpx.BaseTransport = LanesTransport(fallback_limits=HTTP_LIMITS)
            self._http_client = httpx.Client(
                timeout=self.timeout,
                headers={
                    "User-Agent": user_agent,
                    **custom_headers,
                },
                auth=ApiKeyAuth(authorization, self.base_url),
                transport=self._transport,
            )
        else:
            self._http_client = httpx.Client(
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

        self.runtime = RuntimeResource(self)
        self.templates = Templates(self)
        self.snapshots = Snapshots(self)
        self.agents = Agents(self)
        self.identity = Identity(self)
        self.network_policies = NetworkPolicies(self)

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
        if isinstance(self._transport, LanesTransport):
            # Fill the lane pool, then drive one request per lane so every
            # connection's handshake finishes before real traffic arrives.
            self._transport.ensure_pool(httpx.URL(url))
            with ThreadPoolExecutor(max_workers=H2_LANES) as pool:
                responses = list(pool.map(self._http_client.get, [url] * H2_LANES))
            for resp in responses:
                if not resp.is_success:
                    raise error_from_response(resp.status_code, resp.text, resp.headers)
            return
        resp = self._http_client.get(url)
        if resp.status_code in SUCCESS_STATUS:
            return
        if not resp.is_success:
            raise error_from_response(resp.status_code, resp.text, resp.headers)

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

        if not telemetry._spans_active():
            return self._send_with_retries(method, url, stream, kwargs)

        with telemetry.client_span(method, url) as span:
            headers = dict(kwargs.get("headers") or {})
            telemetry.inject(headers)
            kwargs["headers"] = headers
            resp = self._send_with_retries(method, url, stream, kwargs)
            if span is not None:
                span.set_attribute("http.response.status_code", resp.status_code)
            return resp

    def _send_with_retries(
        self, method: str, url: str, stream: bool, kwargs: Dict[str, Any]
    ) -> httpx.Response:
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

                body = response_text(resp)
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
                    raise error_from_response(status, body, resp.headers)

                if (
                    status in RETRYABLE_STATUS
                    and method in REPLAYABLE_METHODS
                    and can_retry_local(attempt, max_retries)
                ):
                    delay = next_retry_delay_local(attempt, rand)
                    logger_warning("Server error %d. Retrying in %.1fs...", status, delay)
                    sleep(delay)
                    continue

                if status >= 400 or not resp.is_success:
                    raise error_from_response(status, body, resp.headers)

            except httpx.RequestError as exc:
                last_exc = exc
                if method in REPLAYABLE_METHODS and can_retry_local(attempt, max_retries):
                    delay = next_retry_delay_local(attempt, rand)
                    logger_warning("Connection error, retrying in %.1fs...", delay)
                    sleep(delay)
                    continue
                raise GravixLayerConnectionError(str(exc)) from exc

        raise GravixLayerError("Failed to complete request.") from last_exc
