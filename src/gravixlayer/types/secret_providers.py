"""Types for Identity Secret Providers API (/v1/identity/providers)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SecretInfo:
    """Masked secret pair (values are write-only and never returned in plaintext)."""

    id: str
    key: str
    value_set: bool = True
    masked: str = "••••••••"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "SecretInfo":
        return cls(
            id=data["id"],
            key=data["key"],
            value_set=bool(data.get("value_set", True)),
            masked=data.get("masked", "••••••••"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class SecretProvider:
    """Secret provider returned by the Identity API."""

    id: str
    name: str
    provider_type: str
    account_id: Optional[str] = None
    project_id: Optional[str] = None
    is_active: bool = True
    is_system: bool = False
    secret_count: int = 0
    secrets: List[SecretInfo] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "SecretProvider":
        secrets_raw = data.get("secrets") or []
        return cls(
            id=data["id"],
            name=data["name"],
            provider_type=data.get("provider_type", "api_key"),
            account_id=data.get("account_id"),
            project_id=data.get("project_id"),
            is_active=bool(data.get("is_active", True)),
            is_system=bool(data.get("is_system", False)),
            secret_count=int(data.get("secret_count", len(secrets_raw))),
            secrets=[SecretInfo.from_api(s) for s in secrets_raw],
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class SecretProviderList:
    """Paginated list of secret providers."""

    providers: List[SecretProvider]
    total: int = 0


@dataclass
class SecretList:
    """List of masked secrets for a provider."""

    secrets: List[SecretInfo]


@dataclass
class SuccessResponse:
    """Generic success envelope: {"success": true}."""

    success: bool = True


def _parse_provider(data: Dict[str, Any]) -> SecretProvider:
    return SecretProvider.from_api(data)


def _parse_secret(data: Dict[str, Any]) -> SecretInfo:
    return SecretInfo.from_api(data)
