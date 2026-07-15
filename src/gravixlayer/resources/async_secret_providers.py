"""
Secret Providers resource for the asynchronous GravixLayer client.

Same endpoints as :mod:`gravixlayer.resources.secret_providers`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .._resource_utils import build_list_endpoint
from ..types.secret_providers import (
    SecretInfo,
    SecretList,
    SecretProvider,
    SecretProviderList,
    SuccessResponse,
    _parse_provider,
    _parse_secret,
)


class AsyncProviders:
    """Async Secret Providers resource at ``client.providers``."""

    def __init__(self, client):
        self.client = client

    async def _make_identity_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        return await self.client._make_request(
            method, endpoint, data, _service="v1/identity", **kwargs
        )

    async def create(
        self,
        name: str,
        provider_type: str = "custom",
        secrets: Optional[List[Dict[str, str]]] = None,
        project_id: Optional[str] = None,
    ) -> SecretProvider:
        body: Dict[str, Any] = {
            "name": name,
            "provider_type": provider_type,
        }
        if secrets:
            body["secrets"] = [
                {"key": s["key"], "value": s["value"]} for s in secrets
            ]
        endpoint = "providers"
        if project_id:
            endpoint = f"providers?project_id={project_id}"
        response = await self._make_identity_request("POST", endpoint, body)
        return _parse_provider(response.json()["provider"])

    async def list(
        self,
        limit: int = 100,
        offset: int = 0,
        project_id: Optional[str] = None,
        search: Optional[str] = None,
    ) -> SecretProviderList:
        endpoint = build_list_endpoint(
            "providers",
            limit=limit,
            offset=offset,
            extra_params={"project_id": project_id, "search": search},
        )
        response = await self._make_identity_request("GET", endpoint)
        data = response.json()
        providers = [_parse_provider(p) for p in (data.get("providers") or [])]
        return SecretProviderList(providers=providers, total=int(data.get("total", 0)))

    async def get(self, provider_id: str) -> SecretProvider:
        response = await self._make_identity_request(
            "GET", f"providers/{provider_id}"
        )
        return _parse_provider(response.json()["provider"])

    async def update(
        self,
        provider_id: str,
        name: Optional[str] = None,
        provider_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        project_id: Optional[str] = None,
    ) -> SecretProvider:
        body: Dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if provider_type is not None:
            body["provider_type"] = provider_type
        if is_active is not None:
            body["is_active"] = is_active
        endpoint = f"providers/{provider_id}"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = await self._make_identity_request("PATCH", endpoint, body)
        return _parse_provider(response.json()["provider"])

    async def delete(
        self, provider_id: str, project_id: Optional[str] = None
    ) -> SuccessResponse:
        endpoint = f"providers/{provider_id}"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = await self._make_identity_request("DELETE", endpoint)
        data = response.json()
        return SuccessResponse(success=bool(data.get("success", True)))

    async def add_secret(
        self,
        provider_id: str,
        key: str,
        value: str,
        project_id: Optional[str] = None,
    ) -> SecretInfo:
        endpoint = f"providers/{provider_id}/secrets"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = await self._make_identity_request(
            "POST", endpoint, {"key": key, "value": value}
        )
        return _parse_secret(response.json()["secret"])

    async def list_secrets(self, provider_id: str) -> SecretList:
        response = await self._make_identity_request(
            "GET", f"providers/{provider_id}/secrets"
        )
        data = response.json()
        return SecretList(
            secrets=[_parse_secret(s) for s in (data.get("secrets") or [])]
        )

    async def update_secret(
        self,
        provider_id: str,
        secret_id: str,
        key: Optional[str] = None,
        value: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> SecretInfo:
        body: Dict[str, Any] = {}
        if key is not None:
            body["key"] = key
        if value is not None:
            body["value"] = value
        endpoint = f"providers/{provider_id}/secrets/{secret_id}"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = await self._make_identity_request("PATCH", endpoint, body)
        return _parse_secret(response.json()["secret"])

    async def delete_secret(
        self,
        provider_id: str,
        secret_id: str,
        project_id: Optional[str] = None,
    ) -> SuccessResponse:
        endpoint = f"providers/{provider_id}/secrets/{secret_id}"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = await self._make_identity_request("DELETE", endpoint)
        data = response.json()
        return SuccessResponse(success=bool(data.get("success", True)))

    async def attach(
        self,
        provider_id: str,
        runtime_id: str,
        project_id: Optional[str] = None,
    ) -> SuccessResponse:
        endpoint = f"providers/{provider_id}/attach"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = await self._make_identity_request(
            "POST", endpoint, {"runtime_id": runtime_id}
        )
        data = response.json()
        return SuccessResponse(success=bool(data.get("success", True)))

    async def detach(
        self,
        provider_id: str,
        runtime_id: str,
        project_id: Optional[str] = None,
    ) -> SuccessResponse:
        endpoint = f"providers/{provider_id}/attach/{runtime_id}"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = await self._make_identity_request("DELETE", endpoint)
        data = response.json()
        return SuccessResponse(success=bool(data.get("success", True)))

    async def list_for_runtime(self, runtime_id: str) -> SecretProviderList:
        response = await self._make_identity_request(
            "GET", f"runtimes/{runtime_id}/providers"
        )
        data = response.json()
        providers = [_parse_provider(p) for p in (data.get("providers") or [])]
        return SecretProviderList(providers=providers, total=len(providers))
