import os
import httpx
import logging
from typing import Optional, Dict, Any
from gravixlayer.resources.chat.completions import ChatCompletions

class AsyncGravixLayer:
    """
    Async client for GravixLayer
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        headers: Optional[Dict[str, str]] = None,
        logger: Optional[logging.Logger] = None,
        user_agent: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("GRAVIXLAYER_API_KEY")
        self.base_url = base_url or "https://api.gravixlayer.com/v1/inference"
        if not self.base_url.startswith("https://"):
            raise ValueError("Base URL must use HTTPS for security reasons.")
        self.timeout = timeout
        self.max_retries = max_retries
        self.custom_headers = headers or {}
        self.logger = logger or logging.getLogger("gravixlayer-async")
        self.user_agent = user_agent or f"gravixlayer-python/0.0.2"
        if not self.api_key:
            raise ValueError("API key must be provided via argument or GRAVIXLAYER_API_KEY environment variable")
        self.chat = ChatCompletions(self)

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        **kwargs
    ) -> httpx.Response:
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}" if endpoint else self.base_url
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": self.user_agent,
            **self.custom_headers,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    resp = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        json=data,
                        **kwargs,
                    )
                    if resp.status_code == 200:
                        return resp
                    # TODO: map errors as in sync client (add equivalent exception handling)
                except httpx.RequestError as e:
                    if attempt == self.max_retries:
                        raise e
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
        raise Exception("Failed async request")
