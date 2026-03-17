import os
import time
import random
import logging
from typing import Optional, Dict, Any, Type
from urllib.parse import urlparse, urlunparse

import httpx

from .resources.runtime import RuntimeResource
from .resources.templates import Templates
from .types.exceptions import (
    GravixLayerError,
    GravixLayerAuthenticationError,
    GravixLayerRateLimitError,
    GravixLayerServerError,
    GravixLayerBadRequestError,
    GravixLayerConnectionError,
)

_KNOWN_SERVICE_PATHS = ("/v1/inference", "/v1/agents", "/v1/vectors", "/v1/files", "/v1/deployments")

_POOL_CONNECTIONS = 10
_POOL_MAXSIZE = 20


class GravixLayer:
    """
    GravixLayer Python SDK Client

    Official Python client for the GravixLayer API. Provides cloud runtime
    environments and template management for AI workloads.

    Args:
        api_key: API key for authentication (or GRAVIXLAYER_API_KEY env var)
        base_url: Base URL for the API (or GRAVIXLAYER_BASE_URL env var)
        cloud: Default cloud provider for runtime/template operations (default: "azure")
        region: Default region for runtime/template operations (default: "eastus2")
        timeout: Request timeout in seconds (default: 60.0)
        max_retries: Maximum retry attempts for transient failures (default: 3)
        headers: Additional HTTP headers to include in requests
        organization: Organization identifier
        project: Project identifier

    Example:
        >>> from gravixlayer import GravixLayer
        >>> client = GravixLayer(
        ...     api_key="your-api-key",
        ...     cloud="azure",
        ...     region="eastus2",
        ... )
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
        logger: Optional[Type[logging.Logger]] = None,
        user_agent: Optional[str] = None,
        organization: Optional[str] = None,
        project: Optional[str] = None,
        **kwargs,
    ):
        self.api_key = api_key or os.environ.get("GRAVIXLAYER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key must be provided via 'api_key' argument or GRAVIXLAYER_API_KEY environment variable"
            )

        raw_url = base_url or os.environ.get("GRAVIXLAYER_BASE_URL", "https://api.gravixlayer.com")

        parsed = urlparse(raw_url.rstrip("/"))
        path = parsed.path
        for prefix in _KNOWN_SERVICE_PATHS:
            if path == prefix or path.startswith(prefix + "/"):
                path = ""
                break
        self.base_url = urlunparse((parsed.scheme, parsed.netloc, path.rstrip("/"), "", "", ""))

        if not (self.base_url.startswith("http://") or self.base_url.startswith("https://")):
            raise ValueError("Base URL must start with http:// or https://")

        self.cloud = cloud or os.environ.get("GRAVIXLAYER_CLOUD", "azure")
        self.region = region or os.environ.get("GRAVIXLAYER_REGION", "eastus2")
        self.organization = organization
        self.project = project
        self.timeout = timeout
        self.max_retries = max_retries
        self.custom_headers = headers or {}

        self.logger = logger or logging.getLogger("gravixlayer")
        if not self.logger.handlers:
            self.logger.addHandler(logging.NullHandler())

        from . import __version__
        self.user_agent = user_agent or f"gravixlayer-python/{__version__}"

        self._base_url_stripped = self.base_url.rstrip("/")
        self._service_urls = {
            svc: f"{self._base_url_stripped}/{svc}"
            for svc in ("v1/inference", "v1/agents", "v1/vectors", "v1/files", "v1/deployments")
        }

        self._http_client = httpx.Client(
            http2=True,
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": self.user_agent,
                **self.custom_headers,
            },
            limits=httpx.Limits(
                max_connections=_POOL_MAXSIZE,
                max_keepalive_connections=_POOL_CONNECTIONS,
            ),
        )

        self.runtime = RuntimeResource(self)
        self.templates = Templates(self)

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

        last_exc: Optional[Exception] = None

        request_kwargs: Dict[str, Any] = {
            "headers": headers,
            **kwargs,
        }
        if has_files:
            request_kwargs["data"] = data
        else:
            request_kwargs["json"] = data

        for attempt in range(self.max_retries + 1):
            try:
                if stream:
                    req = self._http_client.build_request(method, url, **request_kwargs)
                    resp = self._http_client.send(req, stream=True)
                else:
                    resp = self._http_client.request(method, url, **request_kwargs)

                if resp.status_code in (200, 201, 202, 204, 207):
                    return resp

                if resp.status_code == 401:
                    raise GravixLayerAuthenticationError("Authentication failed.")

                if resp.status_code == 429:
                    if attempt < self.max_retries:
                        retry_after = resp.headers.get("Retry-After")
                        delay = float(retry_after) if retry_after else (2 ** attempt + random.uniform(0, 1))
                        self.logger.warning("Rate limited. Retrying in %.1fs...", delay)
                        time.sleep(delay)
                        continue
                    raise GravixLayerRateLimitError(resp.text)

                if resp.status_code in (502, 503, 504) and attempt < self.max_retries:
                    delay = 2 ** attempt + random.uniform(0, 1)
                    self.logger.warning("Server error %d. Retrying in %.1fs...", resp.status_code, delay)
                    time.sleep(delay)
                    continue

                if 400 <= resp.status_code < 500:
                    raise GravixLayerBadRequestError(resp.text)
                if 500 <= resp.status_code < 600:
                    raise GravixLayerServerError(resp.text)

                resp.raise_for_status()

            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    delay = 2 ** attempt + random.uniform(0, 1)
                    self.logger.warning("Connection error, retrying in %.1fs...", delay)
                    time.sleep(delay)
                    continue
                raise GravixLayerConnectionError(str(exc)) from exc

        raise GravixLayerError("Failed to complete request.") from last_exc
