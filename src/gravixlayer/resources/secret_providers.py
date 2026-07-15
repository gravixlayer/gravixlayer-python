"""
Secret Providers resource for the synchronous GravixLayer client.

Maps to Identity API:
    POST   /v1/identity/providers
    GET    /v1/identity/providers
    GET    /v1/identity/providers/:id
    PATCH  /v1/identity/providers/:id
    DELETE /v1/identity/providers/:id
    POST   /v1/identity/providers/:id/secrets
    GET    /v1/identity/providers/:id/secrets
    PATCH  /v1/identity/providers/:id/secrets/:secret_id
    DELETE /v1/identity/providers/:id/secrets/:secret_id
    POST   /v1/identity/providers/:id/attach
    DELETE /v1/identity/providers/:id/attach/:runtime_id
    GET    /v1/identity/runtimes/:runtime_id/providers
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


class Providers:
    """Identity providers resource at ``client.identity.providers``.

    Create a provider with key/value secrets, attach it to a sandbox (runtime),
    and those secrets become environment variables at execution time.
    Maps to ``/v1/identity/providers``.

    Example:
        >>> from gravixlayer import GravixLayer
        >>> client = GravixLayer()
        >>> provider = client.identity.providers.create(
        ...     name="OpenAI",
        ...     provider_type="openai",
        ...     secrets=[{"key": "OPENAI_API_KEY", "value": "sk-..."}],
        ... )
        >>> client.identity.providers.attach(provider.id, runtime_id)
        >>> runtime = client.runtime.create(
        ...     providers=[provider.id],
        ... )
    """

    def __init__(self, client):
        self.client = client

    def _make_identity_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        return self.client._make_request(
            method, endpoint, data, _service="v1/identity", **kwargs
        )

    # -- Provider CRUD -------------------------------------------------------

    def create(
        self,
        name: str,
        provider_type: str = "custom",
        secrets: Optional[List[Dict[str, str]]] = None,
        project_id: Optional[str] = None,
    ) -> SecretProvider:
        """Create a secret provider with optional initial key/value pairs.

        Args:
            name: Display name for the provider.
            provider_type: Type label (openai, anthropic, google, azure, aws, custom).
            secrets: Optional list of ``{"key": "...", "value": "..."}`` pairs.
            project_id: Optional project scope (query param).
        """
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
        response = self._make_identity_request("POST", endpoint, body)
        return _parse_provider(response.json()["provider"])

    def list(
        self,
        limit: int = 100,
        offset: int = 0,
        project_id: Optional[str] = None,
        search: Optional[str] = None,
    ) -> SecretProviderList:
        """List secret providers (masked; no secret values)."""
        endpoint = build_list_endpoint(
            "providers",
            limit=limit,
            offset=offset,
            extra_params={"project_id": project_id, "search": search},
        )
        response = self._make_identity_request("GET", endpoint)
        data = response.json()
        providers = [_parse_provider(p) for p in (data.get("providers") or [])]
        return SecretProviderList(providers=providers, total=int(data.get("total", 0)))

    def get(self, provider_id: str) -> SecretProvider:
        """Get a provider including its masked secrets."""
        response = self._make_identity_request(
            "GET", f"providers/{provider_id}"
        )
        return _parse_provider(response.json()["provider"])

    def update(
        self,
        provider_id: str,
        name: Optional[str] = None,
        provider_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        project_id: Optional[str] = None,
    ) -> SecretProvider:
        """Update provider metadata (name, type, enabled/disabled)."""
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
        response = self._make_identity_request("PATCH", endpoint, body)
        return _parse_provider(response.json()["provider"])

    def delete(self, provider_id: str, project_id: Optional[str] = None) -> SuccessResponse:
        """Soft-delete a provider and detach it from all runtimes."""
        endpoint = f"providers/{provider_id}"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = self._make_identity_request("DELETE", endpoint)
        data = response.json()
        return SuccessResponse(success=bool(data.get("success", True)))

    # -- Secrets -------------------------------------------------------------

    def add_secret(
        self,
        provider_id: str,
        key: str,
        value: str,
        project_id: Optional[str] = None,
    ) -> SecretInfo:
        """Add or upsert a key/value secret on a provider."""
        endpoint = f"providers/{provider_id}/secrets"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = self._make_identity_request(
            "POST", endpoint, {"key": key, "value": value}
        )
        return _parse_secret(response.json()["secret"])

    def list_secrets(self, provider_id: str) -> SecretList:
        """List masked secrets for a provider."""
        response = self._make_identity_request(
            "GET", f"providers/{provider_id}/secrets"
        )
        data = response.json()
        return SecretList(
            secrets=[_parse_secret(s) for s in (data.get("secrets") or [])]
        )

    def update_secret(
        self,
        provider_id: str,
        secret_id: str,
        key: Optional[str] = None,
        value: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> SecretInfo:
        """Update a secret's key and/or replace its value."""
        body: Dict[str, Any] = {}
        if key is not None:
            body["key"] = key
        if value is not None:
            body["value"] = value
        endpoint = f"providers/{provider_id}/secrets/{secret_id}"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = self._make_identity_request("PATCH", endpoint, body)
        return _parse_secret(response.json()["secret"])

    def delete_secret(
        self,
        provider_id: str,
        secret_id: str,
        project_id: Optional[str] = None,
    ) -> SuccessResponse:
        """Delete a secret pair from a provider."""
        endpoint = f"providers/{provider_id}/secrets/{secret_id}"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = self._make_identity_request("DELETE", endpoint)
        data = response.json()
        return SuccessResponse(success=bool(data.get("success", True)))

    # -- Attach / detach -----------------------------------------------------

    def attach(
        self,
        provider_id: str,
        runtime_id: str,
        project_id: Optional[str] = None,
    ) -> SuccessResponse:
        """Attach a provider to a running (or any) sandbox/runtime.

        Secrets take effect on the next code/command execution (and at create
        if attached before create via ``runtime.create(providers=...)``).
        """
        endpoint = f"providers/{provider_id}/attach"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = self._make_identity_request(
            "POST", endpoint, {"runtime_id": runtime_id}
        )
        data = response.json()
        return SuccessResponse(success=bool(data.get("success", True)))

    def detach(
        self,
        provider_id: str,
        runtime_id: str,
        project_id: Optional[str] = None,
    ) -> SuccessResponse:
        """Detach a provider from a sandbox/runtime."""
        endpoint = f"providers/{provider_id}/attach/{runtime_id}"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = self._make_identity_request("DELETE", endpoint)
        data = response.json()
        return SuccessResponse(success=bool(data.get("success", True)))

    def list_for_runtime(self, runtime_id: str) -> SecretProviderList:
        """List providers currently attached to a runtime."""
        response = self._make_identity_request(
            "GET", f"runtimes/{runtime_id}/providers"
        )
        data = response.json()
        providers = [_parse_provider(p) for p in (data.get("providers") or [])]
        return SecretProviderList(providers=providers, total=len(providers))
