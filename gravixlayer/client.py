

import os
import requests
import logging
from typing import Optional, Dict, Any, Type
from .resources.chat.completions import ChatCompletions
from .resources.embeddings import Embeddings
from .resources.completions import Completions
from .resources.deployments import Deployments
from .resources.accelerators import Accelerators
from .resources.files import Files
from .resources.vectors.main import VectorDatabase
from .types.exceptions import (
    GravixLayerError,
    GravixLayerAuthenticationError,
    GravixLayerRateLimitError,
    GravixLayerServerError,
    GravixLayerBadRequestError,
    GravixLayerConnectionError
)


class GravixLayer:
    """
 

    Provides the same interface as popular AI SDKs for easy migration.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        headers: Optional[Dict[str, str]] = None,
        logger: Optional[Type[logging.Logger]] = None,
        user_agent: Optional[str] = None,
        organization: Optional[str] = None,  # For compatibility
        project: Optional[str] = None,       # For compatibility
        **kwargs  # Accept any additional parameters for compatibility
    ):
        self.api_key = api_key or os.environ.get("GRAVIXLAYER_API_KEY")
        self.base_url = base_url or os.environ.get(
            "GRAVIXLAYER_BASE_URL", "https://api.gravixlayer.com/v1/inference")

        # Store compatibility parameters (can be used for future features)
        self.organization = organization
        self.project = project

        # Validate URL scheme - support both HTTP and HTTPS
        if not (self.base_url.startswith("http://") or self.base_url.startswith("https://")):
            raise ValueError("Base URL must use HTTP or HTTPS protocol")

        # Allow both http and https; require explicit scheme for clarity
        if not (self.base_url.startswith("http://") or self.base_url.startswith("https://")):
            raise ValueError("Base URL must start with http:// or https://")
        self.timeout = timeout
        self.max_retries = max_retries
        self.custom_headers = headers or {}
        self.logger = logger or logging.getLogger("gravixlayer")
        self.logger.setLevel(logging.INFO)
        if not self.logger.hasHandlers():
            logging.basicConfig(level=logging.INFO)
        self.user_agent = user_agent or f"gravixlayer-python/0.0.22"
        if not self.api_key:
            raise ValueError(
                "API key must be provided via argument or GRAVIXLAYER_API_KEY environment variable")
        self.chat = ChatResource(self)
        self.embeddings = Embeddings(self)
        self.completions = Completions(self)
        self.deployments = Deployments(self)
        self.accelerators = Accelerators(self)
        self.files = Files(self)
        self.vectors = VectorDatabase(self)
        
        # Initialize memory resource
        from .resources.memory import Memory
        self.memory = Memory(self)

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        **kwargs
    ) -> requests.Response:
        # Handle full URLs (for vector database endpoints)
        if endpoint and (endpoint.startswith('http://') or endpoint.startswith('https://')):
            url = endpoint
        else:
            url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}" if endpoint else self.base_url
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": self.user_agent,
            **self.custom_headers,
        }
        
        # Don't set Content-Type for file uploads (let requests handle it)
        if 'files' not in kwargs:
            headers["Content-Type"] = "application/json"
        
        for attempt in range(self.max_retries + 1):
            try:
                # Use different parameters based on request type
                request_kwargs = {
                    'method': method,
                    'url': url,
                    'headers': headers,
                    'timeout': self.timeout,
                    'stream': stream,
                    **kwargs
                }
                
                # For file uploads, use 'data' and 'files' parameters
                if 'files' in kwargs:
                    request_kwargs['data'] = data
                else:
                    request_kwargs['json'] = data
                
                resp = requests.request(**request_kwargs)
                # Accept both 200 (OK) and 201 (Created) as successful responses
                if resp.status_code in [200, 201]:
                    return resp
                elif resp.status_code == 401:
                    raise GravixLayerAuthenticationError(
                        "Authentication failed.")
                elif resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    self.logger.warning(
                        f"Rate limit exceeded. Retrying in {retry_after or 2**attempt}s...")
                    if attempt < self.max_retries:
                        import time
                        time.sleep(float(retry_after)
                                   if retry_after else (2 ** attempt))
                        continue
                    raise GravixLayerRateLimitError(resp.text)
                elif resp.status_code in [502, 503, 504] and attempt < self.max_retries:
                    self.logger.warning(
                        f"Server error: {resp.status_code}. Retrying...")
                    import time
                    time.sleep(2 ** attempt)
                    continue
                elif 400 <= resp.status_code < 500:
                    raise GravixLayerBadRequestError(resp.text)
                elif 500 <= resp.status_code < 600:
                    raise GravixLayerServerError(resp.text)
                else:
                    resp.raise_for_status()
            except requests.RequestException as e:
                if attempt == self.max_retries:
                    raise GravixLayerConnectionError(str(e)) from e
                self.logger.warning("Transient connection error, retrying...")
                import time
                time.sleep(2 ** attempt)
        raise GravixLayerError("Failed to complete request.")

    def _handle_error_response(self, response):
        """Handle error responses from API calls"""
        if response.status_code == 401:
            raise GravixLayerAuthenticationError("Authentication failed.")
        elif response.status_code == 429:
            raise GravixLayerRateLimitError(response.text)
        elif 400 <= response.status_code < 500:
            raise GravixLayerBadRequestError(response.text)
        elif 500 <= response.status_code < 600:
            raise GravixLayerServerError(response.text)
        else:
            response.raise_for_status()


class ChatResource:
    def __init__(self, client: GravixLayer):
        self.client = client
        # Initialize completions directly on this resource
        self.completions = ChatCompletions(client)
