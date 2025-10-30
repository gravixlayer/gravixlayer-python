

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
from .resources.sandbox import SandboxResource
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
    GravixLayer Python SDK Client
    
    Official Python client for the GravixLayer API. Provides a familiar interface
    compatible with popular AI SDKs for easy migration and integration.
    
    Example:
        >>> from gravixlayer import GravixLayer
        >>> client = GravixLayer(api_key="your-api-key")
        >>> response = client.chat.completions.create(
        ...     model="mistralai/mistral-nemo-instruct-2407",
        ...     messages=[{"role": "user", "content": "Hello!"}]
        ... )
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
        organization: Optional[str] = None,  
        project: Optional[str] = None,       
        **kwargs 
    ):
        self.api_key = api_key or os.environ.get("GRAVIXLAYER_API_KEY")
        self.base_url = base_url or os.environ.get(
            "GRAVIXLAYER_BASE_URL", "https://api.gravixlayer.com/v1/inference")

        self.organization = organization
        self.project = project

        # Validate URL scheme - support both HTTP and HTTPS
        if not (self.base_url.startswith("http://") or self.base_url.startswith("https://")):
            raise ValueError("Base URL must start with http:// or https://")
        self.timeout = timeout
        self.max_retries = max_retries
        self.custom_headers = headers or {}
        self.logger = logger or logging.getLogger("gravixlayer")
        self.logger.setLevel(logging.INFO)
        if not self.logger.hasHandlers():
            logging.basicConfig(level=logging.INFO)
        self.user_agent = user_agent or "gravixlayer-python/0.0.45"
        if not self.api_key:
            raise ValueError(
                "API key must be provided via 'api_key' argument or GRAVIXLAYER_API_KEY environment variable"
            )
        self.chat = ChatResource(self)
        self.embeddings = Embeddings(self)
        self.completions = Completions(self)
        self.deployments = Deployments(self)
        self.accelerators = Accelerators(self)
        self.files = Files(self)
        self.vectors = VectorDatabase(self)
        self.sandbox = SandboxResource(self)
        
        # Memory is now a factory method - requires parameters
        # Users must call client.memory(...) with required parameters
    
    def memory(
        self,
        embedding_model: str,
        inference_model: str,
        index_name: str,
        cloud_provider: str,
        region: str,
        delete_protection: bool = False
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
            delete_protection=delete_protection
        )

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
