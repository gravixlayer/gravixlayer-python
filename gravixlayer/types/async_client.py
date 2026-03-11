import os
import httpx
import logging
import asyncio
import json
import random
from urllib.parse import urlparse, urlunparse
from typing import Optional, Dict, Any, List, Union, AsyncIterator


def _get_sdk_version() -> str:
    """Get the SDK version from the package module (cached at import time)."""
    try:
        from .. import __version__
        return __version__
    except Exception:
        return "unknown"


from ..types.chat import (
    ChatCompletion,
    ChatCompletionChoice,
    ChatCompletionMessage,
    ChatCompletionUsage,
    ChatCompletionDelta,
    FunctionCall,
    ToolCall,
)
from ..types.exceptions import (
    GravixLayerError,
    GravixLayerAuthenticationError,
    GravixLayerRateLimitError,
    GravixLayerServerError,
    GravixLayerBadRequestError,
    GravixLayerConnectionError,
)
from ..resources.async_embeddings import AsyncEmbeddings
from ..resources.async_completions import AsyncCompletions
from ..resources.vectors.async_main import AsyncVectorDatabase
from ..resources.async_sandbox import AsyncSandboxResource
from ..resources.async_templates import AsyncTemplates


class AsyncChatResource:
    def __init__(self, client):
        self.client = client
        self.completions = AsyncChatCompletions(client)


class AsyncChatCompletions:
    def __init__(self, client):
        self.client = client

    def create(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        stop: Optional[Union[str, List[str]]] = None,
        stream: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        **kwargs,
    ) -> Union[ChatCompletion, AsyncIterator[ChatCompletion]]:
        # Convert message objects to dictionaries if needed
        serialized_messages = []
        for msg in messages:
            if hasattr(msg, "__dict__"):
                # Convert dataclass to dict
                msg_dict = {
                    "role": msg.role,  # type: ignore[attr-defined]
                    "content": msg.content  # type: ignore[attr-defined]
                }
                if hasattr(msg, "name") and msg.name:
                    msg_dict["name"] = msg.name
                if hasattr(msg, "tool_call_id") and msg.tool_call_id:
                    msg_dict["tool_call_id"] = msg.tool_call_id
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    msg_dict["tool_calls"] = []
                    for tool_call in msg.tool_calls:
                        tool_call_dict = {
                            "id": tool_call.id,
                            "type": tool_call.type,
                            "function": {"name": tool_call.function.name, "arguments": tool_call.function.arguments},
                        }
                        msg_dict["tool_calls"].append(tool_call_dict)
                serialized_messages.append(msg_dict)
            else:
                # Already a dictionary
                serialized_messages.append(msg)

        data = {"model": model, "messages": serialized_messages, "stream": stream}
        if temperature is not None:
            data["temperature"] = temperature
        if max_tokens is not None:
            data["max_tokens"] = max_tokens
        if top_p is not None:
            data["top_p"] = top_p
        if frequency_penalty is not None:
            data["frequency_penalty"] = frequency_penalty
        if presence_penalty is not None:
            data["presence_penalty"] = presence_penalty
        if stop is not None:
            data["stop"] = stop
        if tools is not None:
            data["tools"] = tools
        if tool_choice is not None:
            data["tool_choice"] = tool_choice
        data.update(kwargs)

        # Fix: Return the async generator directly, don't await it here
        if stream:
            return self._create_stream(data)
        else:
            # For non-streaming, return the coroutine to be awaited
            return self._create_non_stream(data)

    async def _create_non_stream(self, data: Dict[str, Any]) -> ChatCompletion:
        resp = await self.client._make_request("POST", "chat/completions", data)
        return self._parse_response(resp.json())

    async def _create_stream(self, data: Dict[str, Any]) -> AsyncIterator[ChatCompletion]:
        """Async generator for streaming responses"""
        resp = await self.client._make_request("POST", "chat/completions", data, stream=True)

        async for line in resp.aiter_lines():
            if not line:
                continue
            line = line.strip()

            # Handle SSE format
            if line.startswith("data: "):
                line = line[6:]  # Remove "data: " prefix

            # Skip empty lines and [DONE] marker
            if not line or line == "[DONE]":
                continue

            try:
                chunk_data = json.loads(line)
                parsed_chunk = self._parse_response(chunk_data, is_stream=True)

                # Only yield if we have valid choices
                if parsed_chunk.choices:
                    yield parsed_chunk

            except json.JSONDecodeError:
                # Skip malformed JSON
                continue
            except Exception:
                # Skip other errors
                continue

    def _parse_response(self, resp_data: Dict[str, Any], is_stream: bool = False) -> ChatCompletion:
        choices = []

        # Handle different response formats
        if "choices" in resp_data and resp_data["choices"]:
            for choice_data in resp_data["choices"]:
                if is_stream:
                    # For streaming, create delta object
                    delta_content = None
                    delta_role = None
                    delta_tool_calls = None

                    if "delta" in choice_data:
                        delta = choice_data["delta"]
                        delta_content = delta.get("content")
                        delta_role = delta.get("role")

                        # Parse tool calls in delta
                        if "tool_calls" in delta and delta["tool_calls"]:
                            delta_tool_calls = []
                            for tool_call_data in delta["tool_calls"]:
                                function_data = tool_call_data.get("function", {})
                                function_call = FunctionCall(
                                    name=function_data.get("name", ""), arguments=function_data.get("arguments", "{}")
                                )
                                tool_call = ToolCall(
                                    id=tool_call_data.get("id", ""),
                                    type=tool_call_data.get("type", "function"),
                                    function=function_call,
                                )
                                delta_tool_calls.append(tool_call)

                    elif "message" in choice_data:
                        # Fallback: treat message as delta
                        message = choice_data["message"]
                        delta_content = message.get("content")
                        delta_role = message.get("role")

                    # Create delta object
                    delta_obj = ChatCompletionDelta(role=delta_role, content=delta_content, tool_calls=delta_tool_calls)

                    msg = ChatCompletionMessage(
                        role=delta_role or "assistant", content=delta_content or "", tool_calls=delta_tool_calls
                    )

                    choices.append(
                        ChatCompletionChoice(
                            index=choice_data.get("index", 0),
                            message=msg,
                            delta=delta_obj,
                            finish_reason=choice_data.get("finish_reason"),
                        )
                    )
                else:
                    # For non-streaming, use message object
                    message_data = choice_data.get("message", {})

                    # Parse tool calls if present
                    tool_calls = None
                    if "tool_calls" in message_data and message_data["tool_calls"]:
                        tool_calls = []
                        for tool_call_data in message_data["tool_calls"]:
                            function_data = tool_call_data.get("function", {})
                            function_call = FunctionCall(
                                name=function_data.get("name", ""), arguments=function_data.get("arguments", "{}")
                            )
                            tool_call = ToolCall(
                                id=tool_call_data.get("id", ""),
                                type=tool_call_data.get("type", "function"),
                                function=function_call,
                            )
                            tool_calls.append(tool_call)

                    msg = ChatCompletionMessage(
                        role=message_data.get("role", "assistant"),
                        content=message_data.get("content"),
                        tool_calls=tool_calls,
                        tool_call_id=message_data.get("tool_call_id"),
                    )
                    choices.append(
                        ChatCompletionChoice(
                            index=choice_data.get("index", 0),
                            message=msg,
                            finish_reason=choice_data.get("finish_reason"),
                        )
                    )

        # Fallback: create a single choice if no choices found
        if not choices:
            content = ""
            if isinstance(resp_data, str):
                content = resp_data
            elif "content" in resp_data:
                content = resp_data["content"]

            if is_stream:
                delta_obj = ChatCompletionDelta(content=content)
                msg = ChatCompletionMessage(role="assistant", content=content)
                choices = [ChatCompletionChoice(index=0, message=msg, delta=delta_obj, finish_reason=None)]
            else:
                msg = ChatCompletionMessage(role="assistant", content=content)
                choices = [ChatCompletionChoice(index=0, message=msg, finish_reason="stop")]

        # Parse usage if available
        usage = None
        if "usage" in resp_data:
            usage = ChatCompletionUsage(
                prompt_tokens=resp_data["usage"].get("prompt_tokens", 0),
                completion_tokens=resp_data["usage"].get("completion_tokens", 0),
                total_tokens=resp_data["usage"].get("total_tokens", 0),
            )

        import time

        return ChatCompletion(
            id=resp_data.get("id", f"chatcmpl-{hash(str(resp_data))}"),
            object="chat.completion" if not is_stream else "chat.completion.chunk",
            created=resp_data.get("created", int(time.time())),
            model=resp_data.get("model", "unknown"),
            choices=choices,
            usage=usage,
        )


class AsyncGravixLayer:
    """Async client for GravixLayer.

    Reuses a single httpx.AsyncClient across all requests for
    connection pooling and performance. Use as an async context manager
    or call ``await client.aclose()`` when done.
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

        # Normalize base_url to just the origin (scheme + host)
        _known = ("/v1/inference", "/v1/agents", "/v1/vectors", "/v1/files", "/v1/deployments")
        parsed = urlparse(raw_url.rstrip("/"))
        path = parsed.path
        for prefix in _known:
            if path == prefix or path.startswith(prefix + "/"):
                path = ""
                break
        self.base_url = urlunparse((parsed.scheme, parsed.netloc, path.rstrip("/"), "", "", ""))

        # Validate URL scheme
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

        # Pre-compute stripped base URL and service URL map for fast path construction
        self._base_url_stripped = self.base_url.rstrip("/")
        self._service_urls = {
            svc: f"{self._base_url_stripped}/{svc}"
            for svc in ("v1/inference", "v1/agents", "v1/vectors", "v1/files", "v1/deployments")
        }

        # Persistent HTTP client with default auth/UA headers for connection reuse
        self._default_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": self.user_agent,
            **self.custom_headers,
        }
        self._http_client = httpx.AsyncClient(
            timeout=self.timeout,
            headers=self._default_headers,
        )

        # Create the proper resource structure
        self.chat = AsyncChatResource(self)
        self.embeddings = AsyncEmbeddings(self)
        self.completions = AsyncCompletions(self)
        self.vectors = AsyncVectorDatabase(self)
        self.sandbox = AsyncSandboxResource(self)
        self.templates = AsyncTemplates(self)

    async def aclose(self) -> None:
        """Close the underlying HTTP client and release connections."""
        await self._http_client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()

    async def memory(
        self,
        embedding_model: str,
        inference_model: str,
        index_name: str,
        cloud_provider: str,
        region: str,
        delete_protection: bool = False,
    ):
        """
        Create an async memory instance with required configuration

        Args:
            embedding_model: Model for text embeddings (required)
            inference_model: Model for memory inference (required)
            index_name: Name of the memory index (required)
            cloud_provider: Cloud provider (AWS, GCP, Azure) (required)
            region: Cloud region (required)
            delete_protection: Enable delete protection (default: False)

        Returns:
            ExternalCompatibilityLayer: Configured async memory instance
        """
        from ..resources.memory import ExternalCompatibilityLayer

        return ExternalCompatibilityLayer(
            self,
            embedding_model=embedding_model,
            inference_model=inference_model,
            index_name=index_name,
            cloud_provider=cloud_provider,
            region=region,
            delete_protection=delete_protection,
        )

    async def _make_request(
        self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, stream: bool = False, **kwargs
    ) -> httpx.Response:
        # Pop the service path from kwargs (default: inference)
        _service = kwargs.pop("_service", "v1/inference")

        # Handle full URLs (for legacy code)
        if endpoint and (endpoint.startswith("http://") or endpoint.startswith("https://")):
            url = endpoint
        else:
            if _service:
                service_base = self._service_urls.get(_service) or f"{self._base_url_stripped}/{_service}"
            else:
                service_base = self._base_url_stripped
            url = f"{service_base}/{endpoint.lstrip('/')}" if endpoint else service_base

        # Only Content-Type varies per-request; auth/UA are on the session
        has_files = "files" in kwargs
        headers = {"Content-Type": "application/json"} if not has_files else {}

        for attempt in range(self.max_retries + 1):
            try:
                # Build request kwargs — files use form data, others use JSON
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

                # Accept all successful status codes (200-207)
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
