"""
Runtime web service resource — public HTTPS access to guest HTTP ports
via *.service.gravixlayer.ai (CellProxy → CellRouter).
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional
from urllib.parse import urljoin

import httpx

from ..types.runtime import RuntimeWebService, _validate_runtime_id


class RuntimeServiceHandle:
    """HTTP client bound to one runtime web service."""

    def __init__(self, info: RuntimeWebService):
        self._info = info
        self._client = httpx.Client(timeout=60.0)

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

    @property
    def expires_at(self) -> str:
        return self._info.expires_at

    @property
    def is_public(self) -> bool:
        return self._info.is_public

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

    def request(self, method: str, path: str = "/", **kwargs: Any) -> httpx.Response:
        headers = self._headers(kwargs.pop("headers", None))
        return self._client.request(method, self._url(path), headers=headers, **kwargs)

    def get(self, path: str = "/", **kwargs: Any) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str = "/", **kwargs: Any) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str = "/", **kwargs: Any) -> httpx.Response:
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str = "/", **kwargs: Any) -> httpx.Response:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str = "/", **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", path, **kwargs)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "RuntimeServiceHandle":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class RuntimeServiceResource:
    """``client.runtime.service`` — open web services and call guest HTTP APIs."""

    def __init__(self, runtimes: Any):
        self._runtimes = runtimes

    def __call__(
        self,
        runtime_id: str,
        port: int,
        *,
        expires_in_seconds: int = 3600,
        is_public: bool = False,
        rotate_token: bool = False,
    ) -> RuntimeServiceHandle:
        info = self.web_url(
            runtime_id,
            port,
            expires_in_seconds=expires_in_seconds,
            is_public=is_public,
            rotate_token=rotate_token,
        )
        return RuntimeServiceHandle(info)

    def web_url(
        self,
        runtime_id: str,
        port: int,
        *,
        expires_in_seconds: int = 3600,
        is_public: bool = False,
        rotate_token: bool = False,
    ) -> RuntimeWebService:
        """Open (or refresh) an HTTPS web service for a guest port."""
        _validate_runtime_id(runtime_id)
        if port < 1 or port > 65535:
            raise ValueError("port must be in 1..=65535")
        response = self._runtimes._make_agents_request(
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

    def list(self, runtime_id: str) -> list[RuntimeWebService]:
        _validate_runtime_id(runtime_id)
        response = self._runtimes._make_agents_request(
            "GET", f"runtime/{runtime_id}/services"
        )
        data = response.json()
        items = data.get("services") or []
        return [RuntimeWebService.from_api(item) for item in items]

    def revoke(self, runtime_id: str, port: int) -> None:
        _validate_runtime_id(runtime_id)
        self._runtimes._make_agents_request(
            "DELETE", f"runtime/{runtime_id}/services/{port}"
        )
