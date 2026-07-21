"""
Async runtime web service resource.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional
from urllib.parse import urljoin

import httpx

from ..types.runtime import RuntimeWebService, _validate_runtime_id


class AsyncRuntimeServiceHandle:
    """Async bound handle for one runtime + port web service."""

    def __init__(self, info: RuntimeWebService):
        self._info = info
        self._client = httpx.AsyncClient(timeout=60.0)

    @property
    def web_url(self) -> str:
        return self._info.web_url

    @property
    def url(self) -> str:
        return self._info.url

    @property
    def browser_url(self) -> str:
        return self._info.browser_url

    @property
    def service_url(self) -> str:
        return self._info.service_url

    @property
    def token(self) -> Optional[str]:
        return self._info.token

    @property
    def port(self) -> int:
        return self._info.port

    def _headers(self, extra: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self._info.token and not self._info.is_public:
            headers["X-Gravix-Web-Service-Token"] = self._info.token
        if extra:
            headers.update(dict(extra))
        return headers

    def _url(self, path: str) -> str:
        base = self._info.service_url
        if not path:
            return base
        return urljoin(base, path.lstrip("/"))

    async def request(self, method: str, path: str = "/", **kwargs: Any) -> httpx.Response:
        headers = self._headers(kwargs.pop("headers", None))
        return await self._client.request(method, self._url(path), headers=headers, **kwargs)

    async def get(self, path: str = "/", **kwargs: Any) -> httpx.Response:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str = "/", **kwargs: Any) -> httpx.Response:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str = "/", **kwargs: Any) -> httpx.Response:
        return await self.request("PUT", path, **kwargs)

    async def patch(self, path: str = "/", **kwargs: Any) -> httpx.Response:
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str = "/", **kwargs: Any) -> httpx.Response:
        return await self.request("DELETE", path, **kwargs)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncRuntimeServiceHandle":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()


class AsyncRuntimeServiceResource:
    """``client.runtime.service`` (async)."""

    def __init__(self, runtimes: Any):
        self._runtimes = runtimes

    async def __call__(
        self,
        runtime_id: str,
        port: int,
        *,
        expires_in_seconds: int = 3600,
        is_public: bool = False,
    ) -> AsyncRuntimeServiceHandle:
        info = await self.web_url(
            runtime_id,
            port,
            expires_in_seconds=expires_in_seconds,
            is_public=is_public,
        )
        return AsyncRuntimeServiceHandle(info)

    async def web_url(
        self,
        runtime_id: str,
        port: int,
        *,
        expires_in_seconds: int = 3600,
        is_public: bool = False,
        rotate_token: bool = False,
    ) -> RuntimeWebService:
        _validate_runtime_id(runtime_id)
        if port < 1 or port > 65535:
            raise ValueError("port must be in 1..=65535")
        response = await self._runtimes._make_agents_request(
            "POST",
            f"runtime/{runtime_id}/services",
            {
                "port": port,
                "expires_in_seconds": expires_in_seconds,
                "is_public": is_public,
                "rotate_token": rotate_token,
            },
        )
        return RuntimeWebService.from_api(response.json())

    async def list(self, runtime_id: str) -> list[RuntimeWebService]:
        _validate_runtime_id(runtime_id)
        response = await self._runtimes._make_agents_request(
            "GET", f"runtime/{runtime_id}/services"
        )
        data = response.json()
        items = data.get("services") or []
        return [RuntimeWebService.from_api(item) for item in items]

    async def revoke(self, runtime_id: str, port: int) -> None:
        _validate_runtime_id(runtime_id)
        await self._runtimes._make_agents_request(
            "DELETE", f"runtime/{runtime_id}/services/{port}"
        )
