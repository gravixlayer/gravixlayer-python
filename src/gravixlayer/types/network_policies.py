"""Types for Network Policies API (/v1/network-policies)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class NetworkPolicyRule:
    """Single destination/port/protocol egress rule."""

    id: str
    policy_id: str
    destination: str
    port: int = 0
    protocol: str = "tcp"
    account_id: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "NetworkPolicyRule":
        return cls(
            id=data["id"],
            policy_id=data["policy_id"],
            destination=data["destination"],
            port=int(data.get("port", 0)),
            protocol=data.get("protocol", "tcp"),
            account_id=data.get("account_id"),
            description=data.get("description"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class NetworkPolicy:
    """Network policy returned by the Network Policies API."""

    id: str
    name: str
    egress_mode: str
    account_id: Optional[str] = None
    project_id: Optional[str] = None
    description: Optional[str] = None
    is_default: bool = False
    is_system: bool = False
    is_active: bool = True
    rule_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "NetworkPolicy":
        return cls(
            id=data["id"],
            name=data["name"],
            egress_mode=data.get("egress_mode", "allowlist"),
            account_id=data.get("account_id"),
            project_id=data.get("project_id"),
            description=data.get("description"),
            is_default=bool(data.get("is_default", False)),
            is_system=bool(data.get("is_system", False)),
            is_active=bool(data.get("is_active", True)),
            rule_count=int(data.get("rule_count", 0)),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class NetworkPolicyList:
    """Paginated list of network policies."""

    policies: List[NetworkPolicy]
    total: int = 0


@dataclass
class NetworkPolicyRuleList:
    """List of rules for a network policy."""

    rules: List[NetworkPolicyRule]


@dataclass
class SuccessResponse:
    """Generic success envelope: {"success": true}."""

    success: bool = True


def _parse_policy(data: Dict[str, Any]) -> NetworkPolicy:
    return NetworkPolicy.from_api(data)


def _parse_rule(data: Dict[str, Any]) -> NetworkPolicyRule:
    return NetworkPolicyRule.from_api(data)
