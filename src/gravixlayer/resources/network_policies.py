"""
Network Policies resource for the synchronous GravixLayer client.

Maps to Network Policies API:
    POST   /v1/network-policies
    GET    /v1/network-policies
    GET    /v1/network-policies/:id
    PATCH  /v1/network-policies/:id
    DELETE /v1/network-policies/:id
    POST   /v1/network-policies/:id/rules
    GET    /v1/network-policies/:id/rules
    PATCH  /v1/network-policies/:id/rules/:rule_id
    DELETE /v1/network-policies/:id/rules/:rule_id
    POST   /v1/network-policies/:id/attach
    DELETE /v1/network-policies/:id/attach/:runtime_id
    GET    /v1/network-policies/runtimes/:runtime_id

Egress modes (most-restrictive-wins when multiple policies are attached):
    deny_all > allowlist > denylist > allow_all

The System Default policy (empty allowlist) is auto-attached at runtime create
and hidden from list/list_for_runtime by default — it is a fail-closed fallback
only, not a user-managed policy.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .._resource_utils import build_list_endpoint
from ..types.network_policies import (
    EGRESS_MODES,
    NetworkPolicy,
    NetworkPolicyList,
    NetworkPolicyRule,
    NetworkPolicyRuleList,
    PROTOCOLS,
    SuccessResponse,
    _is_system_default_policy,
    _normalize_rule_inputs,
    _parse_policy,
    _parse_rule,
)


class NetworkPolicies:
    """Network policies resource at ``client.network_policies``.

    Full lifecycle: create (optionally with rules) → list/get/update/delete →
    add/update/delete rules → attach/detach → list_for_runtime.
    Also attach at create via ``runtime.create(network_policy_ids=[...])``.

    Example:
        >>> from gravixlayer import GravixLayer
        >>> client = GravixLayer()
        >>> policy = client.network_policies.create(
        ...     name="openai-only",
        ...     egress_mode="allowlist",
        ...     rules=[{"destination": "api.openai.com", "port": 443, "protocol": "tcp"}],
        ... )
        >>> runtime = client.runtime.create(network_policy_ids=[policy.id])
        >>> client.network_policies.attach(policy.id, other_runtime_id)
        >>> attached = client.network_policies.list_for_runtime(runtime.runtime_id)
    """

    def __init__(self, client):
        self.client = client

    def _make_network_policy_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        return self.client._make_request(
            method, endpoint, data, _service="v1/network-policies", **kwargs
        )

    # -- Policy CRUD ---------------------------------------------------------

    def create(
        self,
        name: str,
        egress_mode: str = "allowlist",
        description: Optional[str] = None,
        is_default: bool = False,
        rules: Optional[Sequence[Dict[str, Any]]] = None,
        project_id: Optional[str] = None,
    ) -> NetworkPolicy:
        """Create a network policy, optionally with initial egress rules.

        Args:
            name: Display name for the policy.
            egress_mode: One of ``allowlist``, ``denylist``, ``allow_all``, ``deny_all``.
            description: Optional human-readable description.
            is_default: When True, mark this policy as the account/project default.
            rules: Optional list of rule dicts
                ``{"destination", "port"?, "protocol"?, "description"?}``.
                Added after create; on any rule failure the policy is rolled back
                (deleted) so callers never get a half-configured policy.
            project_id: Optional project scope (query param).
        """
        if egress_mode not in EGRESS_MODES:
            raise ValueError(
                f"egress_mode must be one of {EGRESS_MODES}, got {egress_mode!r}"
            )
        normalized_rules = _normalize_rule_inputs(rules) if rules else []

        body: Dict[str, Any] = {
            "name": name,
            "egress_mode": egress_mode,
            "is_default": is_default,
        }
        if description is not None:
            body["description"] = description
        endpoint = ""
        if project_id:
            endpoint = f"?project_id={project_id}"
        response = self._make_network_policy_request("POST", endpoint, body)
        policy = _parse_policy(response.json()["policy"])

        if not normalized_rules:
            return policy

        created_rules: List[NetworkPolicyRule] = []
        try:
            for rule in normalized_rules:
                created_rules.append(
                    self.add_rule(
                        policy.id,
                        destination=rule["destination"],
                        port=rule["port"],
                        protocol=rule["protocol"],
                        description=rule.get("description"),
                        project_id=project_id,
                    )
                )
        except Exception as rule_err:
            # Best-effort rollback so we never leave a half-configured policy.
            try:
                self.delete(policy.id, project_id=project_id)
            except Exception:
                raise RuntimeError(
                    f"Failed to add rules ({rule_err}); policy {policy.id} was "
                    "created but could not be rolled back — delete it and retry."
                ) from rule_err
            raise RuntimeError(
                f"Failed to add rules; policy creation was rolled back. {rule_err}"
            ) from rule_err

        policy.rules = created_rules
        policy.rule_count = len(created_rules)
        return policy

    def list(
        self,
        limit: int = 100,
        offset: int = 0,
        project_id: Optional[str] = None,
        search: Optional[str] = None,
    ) -> NetworkPolicyList:
        """List network policies (System Default is excluded by the API)."""
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        if offset < 0:
            raise ValueError("offset must be >= 0")
        endpoint = build_list_endpoint(
            "",
            limit=limit,
            offset=offset,
            extra_params={"project_id": project_id, "search": search},
        )
        response = self._make_network_policy_request("GET", endpoint)
        data = response.json()
        policies = [_parse_policy(p) for p in (data.get("policies") or [])]
        return NetworkPolicyList(policies=policies, total=int(data.get("total", 0)))

    def get(
        self,
        policy_id: str,
        *,
        include_rules: bool = False,
    ) -> NetworkPolicy:
        """Get a network policy by ID.

        Args:
            policy_id: Policy UUID.
            include_rules: When True, also fetch ``GET .../rules`` and set
                ``policy.rules``.
        """
        response = self._make_network_policy_request("GET", policy_id)
        policy = _parse_policy(response.json()["policy"])
        if include_rules:
            rule_list = self.list_rules(policy_id)
            policy.rules = rule_list.rules
            policy.rule_count = len(rule_list.rules)
        return policy

    def update(
        self,
        policy_id: str,
        name: Optional[str] = None,
        egress_mode: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_default: Optional[bool] = None,
        project_id: Optional[str] = None,
    ) -> NetworkPolicy:
        """Update policy metadata (name, mode, description, enabled/disabled, default)."""
        if egress_mode is not None and egress_mode not in EGRESS_MODES:
            raise ValueError(
                f"egress_mode must be one of {EGRESS_MODES}, got {egress_mode!r}"
            )
        body: Dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if egress_mode is not None:
            body["egress_mode"] = egress_mode
        if description is not None:
            body["description"] = description
        if is_active is not None:
            body["is_active"] = is_active
        if is_default is not None:
            body["is_default"] = is_default
        endpoint = policy_id
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = self._make_network_policy_request("PATCH", endpoint, body)
        return _parse_policy(response.json()["policy"])

    def delete(self, policy_id: str, project_id: Optional[str] = None) -> SuccessResponse:
        """Soft-delete a network policy and detach it from all runtimes."""
        endpoint = policy_id
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = self._make_network_policy_request("DELETE", endpoint)
        data = response.json()
        return SuccessResponse(success=bool(data.get("success", True)))

    # -- Rules ---------------------------------------------------------------

    def add_rule(
        self,
        policy_id: str,
        destination: str,
        port: int = 0,
        protocol: str = "tcp",
        description: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> NetworkPolicyRule:
        """Add a destination/port/protocol rule to a policy.

        Args:
            policy_id: Policy UUID.
            destination: Hostname, IP, or CIDR (e.g. ``api.openai.com``).
            port: Destination port; ``0`` means any port.
            protocol: ``tcp``, ``udp``, or ``any``.
            description: Optional rule description.
            project_id: Optional project scope (query param).
        """
        protocol = protocol.lower()
        if protocol not in PROTOCOLS:
            raise ValueError(f"protocol must be one of {PROTOCOLS}, got {protocol!r}")
        if not isinstance(port, int) or port < 0 or port > 65535:
            raise ValueError(f"port must be an int in 0–65535 (got {port!r})")
        body: Dict[str, Any] = {
            "destination": destination,
            "port": port,
            "protocol": protocol,
        }
        if description is not None:
            body["description"] = description
        endpoint = f"{policy_id}/rules"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = self._make_network_policy_request("POST", endpoint, body)
        return _parse_rule(response.json()["rule"])

    def list_rules(self, policy_id: str) -> NetworkPolicyRuleList:
        """List rules for a network policy."""
        response = self._make_network_policy_request("GET", f"{policy_id}/rules")
        data = response.json()
        return NetworkPolicyRuleList(
            rules=[_parse_rule(r) for r in (data.get("rules") or [])]
        )

    def update_rule(
        self,
        policy_id: str,
        rule_id: str,
        destination: Optional[str] = None,
        port: Optional[int] = None,
        protocol: Optional[str] = None,
        description: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> NetworkPolicyRule:
        """Update a rule's destination, port, protocol, and/or description."""
        if protocol is not None:
            protocol = protocol.lower()
            if protocol not in PROTOCOLS:
                raise ValueError(
                    f"protocol must be one of {PROTOCOLS}, got {protocol!r}"
                )
        if port is not None and (not isinstance(port, int) or port < 0 or port > 65535):
            raise ValueError(f"port must be an int in 0–65535 (got {port!r})")
        body: Dict[str, Any] = {}
        if destination is not None:
            body["destination"] = destination
        if port is not None:
            body["port"] = port
        if protocol is not None:
            body["protocol"] = protocol
        if description is not None:
            body["description"] = description
        endpoint = f"{policy_id}/rules/{rule_id}"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = self._make_network_policy_request("PATCH", endpoint, body)
        return _parse_rule(response.json()["rule"])

    def delete_rule(
        self,
        policy_id: str,
        rule_id: str,
        project_id: Optional[str] = None,
    ) -> SuccessResponse:
        """Delete a rule from a network policy."""
        endpoint = f"{policy_id}/rules/{rule_id}"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = self._make_network_policy_request("DELETE", endpoint)
        data = response.json()
        return SuccessResponse(success=bool(data.get("success", True)))

    # -- Attach / detach -----------------------------------------------------

    def attach(
        self,
        policy_id: str,
        runtime_id: str,
        project_id: Optional[str] = None,
    ) -> SuccessResponse:
        """Attach a network policy to a sandbox/runtime.

        Multiple policies may be attached; the platform compiles them with
        most-restrictive-wins precedence (``deny_all`` > ``allowlist`` >
        ``denylist`` > ``allow_all``). Prefer create-time attach via
        ``runtime.create(network_policy_ids=...)`` when creating the runtime.
        """
        endpoint = f"{policy_id}/attach"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = self._make_network_policy_request(
            "POST", endpoint, {"runtime_id": runtime_id}
        )
        data = response.json()
        return SuccessResponse(success=bool(data.get("success", True)))

    def detach(
        self,
        policy_id: str,
        runtime_id: str,
        project_id: Optional[str] = None,
    ) -> SuccessResponse:
        """Detach a network policy from a sandbox/runtime.

        The System Default policy cannot be detached (API returns 403).
        """
        endpoint = f"{policy_id}/attach/{runtime_id}"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = self._make_network_policy_request("DELETE", endpoint)
        data = response.json()
        return SuccessResponse(success=bool(data.get("success", True)))

    def list_for_runtime(
        self,
        runtime_id: str,
        *,
        include_system: bool = False,
    ) -> NetworkPolicyList:
        """List network policies currently attached to a runtime.

        Args:
            runtime_id: Runtime UUID.
            include_system: When False (default), hide the auto-managed System
                Default policy. Pass True to see every attachment including the
                fail-closed baseline.
        """
        response = self._make_network_policy_request(
            "GET", f"runtimes/{runtime_id}"
        )
        data = response.json()
        policies = [_parse_policy(p) for p in (data.get("policies") or [])]
        if not include_system:
            policies = [p for p in policies if not _is_system_default_policy(p)]
        return NetworkPolicyList(policies=policies, total=len(policies))
