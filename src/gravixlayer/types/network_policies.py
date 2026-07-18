"""Types for Network Policies API (/v1/network-policies)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

# Exact egress-mode strings accepted by the Gravix Layer API.
EGRESS_MODE_DENY_ALL = "deny_all"
EGRESS_MODE_ALLOW_ALL = "allow_all"
EGRESS_MODE_ALLOWLIST = "allowlist"
EGRESS_MODE_DENYLIST = "denylist"

EGRESS_MODES = (
    EGRESS_MODE_DENY_ALL,
    EGRESS_MODE_ALLOW_ALL,
    EGRESS_MODE_ALLOWLIST,
    EGRESS_MODE_DENYLIST,
)

PROTOCOL_TCP = "tcp"
PROTOCOL_UDP = "udp"
PROTOCOL_ANY = "any"

PROTOCOLS = (PROTOCOL_TCP, PROTOCOL_UDP, PROTOCOL_ANY)

# Display name of the auto-attached, non-user-managed fail-closed default.
SYSTEM_DEFAULT_POLICY_NAME = "System Default"


@dataclass
class NetworkPolicyRule:
    """Single destination/port/protocol egress rule."""

    id: str
    policy_id: str
    destination: str
    port: int = 0
    protocol: str = PROTOCOL_TCP
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
            protocol=data.get("protocol", PROTOCOL_TCP),
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
    # Populated when ``get(..., include_rules=True)`` or ``create(..., rules=...)``.
    rules: Optional[List[NetworkPolicyRule]] = field(default=None)

    @property
    def is_system_default(self) -> bool:
        """True for the auto-managed empty-allowlist System Default policy."""
        return (self.is_system and self.is_default) or self.name == SYSTEM_DEFAULT_POLICY_NAME

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "NetworkPolicy":
        rules_raw = data.get("rules")
        rules: Optional[List[NetworkPolicyRule]] = None
        if isinstance(rules_raw, list):
            rules = [NetworkPolicyRule.from_api(r) for r in rules_raw]
        return cls(
            id=data["id"],
            name=data["name"],
            egress_mode=data.get("egress_mode", EGRESS_MODE_ALLOWLIST),
            account_id=data.get("account_id"),
            project_id=data.get("project_id"),
            description=data.get("description"),
            is_default=bool(data.get("is_default", False)),
            is_system=bool(data.get("is_system", False)),
            is_active=bool(data.get("is_active", True)),
            rule_count=int(data.get("rule_count", 0)),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            rules=rules,
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


def _is_system_default_policy(policy: NetworkPolicy) -> bool:
    return policy.is_system_default


def _normalize_rule_inputs(
    rules: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Validate and normalize rule dicts for ``create(..., rules=...)``.

    Each item must include ``destination``. Optional: ``port`` (default 0),
    ``protocol`` (default ``tcp``), ``description``.
    """
    normalized: List[Dict[str, Any]] = []
    for i, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise TypeError(f"rules[{i}] must be a dict, got {type(rule).__name__}")
        dest = rule.get("destination")
        if not dest or not isinstance(dest, str) or not dest.strip():
            raise ValueError(f"rules[{i}].destination is required")
        port = rule.get("port", 0)
        if port is None:
            port = 0
        if not isinstance(port, int) or port < 0 or port > 65535:
            raise ValueError(f"rules[{i}].port must be an int in 0–65535 (got {port!r})")
        protocol = str(rule.get("protocol") or PROTOCOL_TCP).lower()
        if protocol not in PROTOCOLS:
            raise ValueError(
                f"rules[{i}].protocol must be one of {PROTOCOLS}, got {protocol!r}"
            )
        item: Dict[str, Any] = {
            "destination": dest.strip(),
            "port": port,
            "protocol": protocol,
        }
        if rule.get("description") is not None:
            item["description"] = rule["description"]
        normalized.append(item)
    return normalized
