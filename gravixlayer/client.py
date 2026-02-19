import os
import time
import logging
from typing import Optional, Dict, Any, Type
from urllib.parse import urlparse, urlunparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .resources.chat.completions import ChatCompletions
from .resources.embeddings import Embeddings
from .resources.completions import Completions
from .resources.deployments import Deployments
from .resources.accelerators import Accelerators
from .resources.files import Files
from .resources.vectors.main import VectorDatabase
from .resources.sandbox import SandboxResource
from .resources.templates import Templates
from .types.exceptions import (
    GravixLayerError,
    GravixLayerAuthenticationError,
    GravixLayerRateLimitError,
    GravixLayerServerError,
    GravixLayerBadRequestError,
    GravixLayerConnectionError,
)

# Known API service path prefixes — stripped during base_url normalization
_KNOWN_SERVICE_PATHS = ("/v1/inference", "/v1/agents", "/v1/vectors", "/v1/files", "/v1/deployments")

# Connection pool sizing — reuse TCP connections across requests
_POOL_CONNECTIONS = 10
_POOL_MAXSIZE = 20


class GravixLayer:
    """
    GravixLayer Python SDK Client

    Official Python client for the GravixLayer API. Provides a familiar interface
    compatible with popular AI SDKs for easy migration and integration.

    Args:
        api_key: API key for authentication (or GRAVIXLAYER_API_KEY env var)
        base_url: Base URL for the API (or GRAVIXLAYER_BASE_URL env var)
        cloud: Default cloud provider for sandbox/template operations (default: "azure")
        region: Default region for sandbox/template operations (default: "eastus2")
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
        >>> # cloud and region are used as defaults for sandbox/template calls
        >>> sandbox = client.sandbox.sandboxes.create(template="python-base-v1")
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

        # Normalize base_url to just the origin (scheme + host).
        # This allows users to pass any variant:
        #   https://api.gravixlayer.com
        #   https://api.gravixlayer.com/v1/inference   (legacy default)
        #   https://api.gravixlayer.com/v1/agents
        # All are normalised to https://api.gravixlayer.com
        parsed = urlparse(raw_url.rstrip("/"))
        path = parsed.path
        for prefix in _KNOWN_SERVICE_PATHS:
            if path == prefix or path.startswith(prefix + "/"):
                path = ""
                break
        self.base_url = urlunparse((parsed.scheme, parsed.netloc, path.rstrip("/"), "", "", ""))

        # Validate URL scheme
        if not (self.base_url.startswith("http://") or self.base_url.startswith("https://")):
            raise ValueError("Base URL must start with http:// or https://")

        self.cloud = cloud or os.environ.get("GRAVIXLAYER_CLOUD", "azure")
        self.region = region or os.environ.get("GRAVIXLAYER_REGION", "eastus2")
        self.organization = organization
        self.project = project
        self.timeout = timeout
        self.max_retries = max_retries
        self.custom_headers = headers or {}

        # Logger — never call basicConfig; let the caller configure logging
        self.logger = logger or logging.getLogger("gravixlayer")
        if not self.logger.handlers:
            self.logger.addHandler(logging.NullHandler())

        # User-agent auto-tracks the installed version
        from . import __version__
        self.user_agent = user_agent or f"gravixlayer-python/{__version__}"

        # Pre-compute stripped base URL and service URL map for fast path construction
        self._base_url_stripped = self.base_url.rstrip("/")
        self._service_urls = {
            svc: f"{self._base_url_stripped}/{svc}"
            for svc in ("v1/inference", "v1/agents", "v1/vectors", "v1/files", "v1/deployments")
        }

        # Persistent HTTP session with connection pooling and keep-alive
        self._session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=_POOL_CONNECTIONS,
            pool_maxsize=_POOL_MAXSIZE,
            max_retries=Retry(total=0),  # We handle retries ourselves
        )
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

        # Set persistent headers on the session — avoids re-creating per request
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": self.user_agent,
        })
        if self.custom_headers:
            self._session.headers.update(self.custom_headers)

        self.chat = ChatResource(self)
        self.embeddings = Embeddings(self)
        self.completions = Completions(self)
        self.deployments = Deployments(self)
        self.accelerators = Accelerators(self)
        self.files = Files(self)
        self.vectors = VectorDatabase(self)
        self.sandbox = SandboxResource(self)
        self.templates = Templates(self)

    def memory(
        self,
        embedding_model: str,
        inference_model: str,
        index_name: str,
        cloud_provider: str,
        region: str,
        delete_protection: bool = False,
    ):
        """
        Create a memory instance with required configuration.

        Args:
            embedding_model (str): Model for text embeddings
            inference_model (str): Model for memory inference
            index_name (str): Name of the memory index
            cloud_provider (str): Cloud provider (AWS, GCP, Azure)
            region (str): Cloud region
            delete_protection (bool): Enable delete protection (default: False)

        Returns:
            SyncExternalMemory: Configured memory instance

        Example:
            >>> memory = client.memory(
            ...     embedding_model="microsoft/multilingual-e5-large",
            ...     inference_model="mistralai/mistral-nemo-instruct-2407",
            ...     index_name="user-memories",
            ...     cloud_provider="AWS",
            ...     region="us-east-1"
            ... )
        """
        from .resources.memory.sync_external_memory import SyncExternalMemory

        return SyncExternalMemory(
            self,
            embedding_model=embedding_model,
            inference_model=inference_model,
            index_name=index_name,
            cloud_provider=cloud_provider,
            region=region,
            delete_protection=delete_protection,
        )

    def _make_request(
        self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, stream: bool = False, **kwargs
    ) -> requests.Response:
        _service = kwargs.pop("_service", "v1/inference")

        # Handle full URLs (for legacy code that may still pass them)
        if endpoint and (endpoint.startswith("http://") or endpoint.startswith("https://")):
            url = endpoint
        else:
            if _service:
                service_base = self._service_urls.get(_service) or f"{self._base_url_stripped}/{_service}"
            else:
                service_base = self._base_url_stripped
            url = f"{service_base}/{endpoint.lstrip('/')}" if endpoint else service_base

        # Per-request headers — only Content-Type varies (session holds auth + UA)
        has_files = "files" in kwargs
        headers = {"Content-Type": "application/json"} if not has_files else {}

        last_exc: Optional[Exception] = None

        # Build request kwargs once — reused across retry attempts
        request_kwargs: Dict[str, Any] = {
            "method": method,
            "url": url,
            "headers": headers,
            "timeout": self.timeout,
            "stream": stream,
            **kwargs,
        }

        if has_files:
            request_kwargs["data"] = data
        else:
            request_kwargs["json"] = data

        for attempt in range(self.max_retries + 1):
            try:
                resp = self._session.request(**request_kwargs)

                if resp.status_code in (200, 201, 202, 204, 207):
                    return resp

                if resp.status_code == 401:
                    raise GravixLayerAuthenticationError("Authentication failed.")

                if resp.status_code == 429:
                    if attempt < self.max_retries:
                        retry_after = resp.headers.get("Retry-After")
                        delay = float(retry_after) if retry_after else (2 ** attempt)
                        self.logger.warning("Rate limited. Retrying in %.1fs...", delay)
                        time.sleep(delay)
                        continue
                    raise GravixLayerRateLimitError(resp.text)

                if resp.status_code in (502, 503, 504) and attempt < self.max_retries:
                    delay = 2 ** attempt
                    self.logger.warning("Server error %d. Retrying in %ds...", resp.status_code, delay)
                    time.sleep(delay)
                    continue

                if 400 <= resp.status_code < 500:
                    raise GravixLayerBadRequestError(resp.text)
                if 500 <= resp.status_code < 600:
                    raise GravixLayerServerError(resp.text)

                resp.raise_for_status()

            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    delay = 2 ** attempt
                    self.logger.warning("Connection error, retrying in %ds...", delay)
                    time.sleep(delay)
                    continue
                raise GravixLayerConnectionError(str(exc)) from exc

        raise GravixLayerError("Failed to complete request.") from last_exc


class ChatResource:
    def __init__(self, client: GravixLayer):
        self.client = client
        # Initialize completions directly on this resource
        self.completions = ChatCompletions(client)
