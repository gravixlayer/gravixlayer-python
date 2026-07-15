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
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .._resource_utils import build_list_endpoint
from ..types.network_policies import (
    NetworkPolicy,
    NetworkPolicyList,
    NetworkPolicyRule,
    NetworkPolicyRuleList,
    SuccessResponse,
    _parse_policy,
    _parse_rule,
)


class NetworkPolicies:
    """Network policies resource at ``client.network_policies``.

    Create an egress policy with destination/port/protocol rules, attach it to
    a sandbox (runtime), and those rules control outbound network access.
    Maps to ``/v1/network-policies``.

    Example:
        >>> from gravixlayer import GravixLayer
        >>> client = GravixLayer()
        >>> policy = client.network_policies.create(
        ...     name="openai-only",
        ...     egress_mode="allowlist",
        ... )
        >>> client.network_policies.add_rule(
        ...     policy.id, destination="api.openai.com", port=443, protocol="tcp",
        ... )
        >>> client.network_policies.attach(policy.id, runtime_id)
        >>> runtime = client.runtime.create(
        ...     network_policy_ids=[policy.id],
        ... )
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
        project_id: Optional[str] = None,
    ) -> NetworkPolicy:
        """Create a network policy.

        Args:
            name: Display name for the policy.
            egress_mode: One of ``allowlist``, ``denylist``, ``allow_all``, ``deny_all``.
            description: Optional human-readable description.
            is_default: When True, mark this policy as the account/project default.
            project_id: Optional project scope (query param).
        """
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
        return _parse_policy(response.json()["policy"])

    def list(
        self,
        limit: int = 100,
        offset: int = 0,
        project_id: Optional[str] = None,
        search: Optional[str] = None,
    ) -> NetworkPolicyList:
        """List network policies."""
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

    def get(self, policy_id: str) -> NetworkPolicy:
        """Get a network policy by ID."""
        response = self._make_network_policy_request("GET", policy_id)
        return _parse_policy(response.json()["policy"])

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
        """Attach a network policy to a running (or any) sandbox/runtime.

        Rules take effect on the next apply (and at create if attached before
        create via ``runtime.create(network_policy_ids=...)``).
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
        """Detach a network policy from a sandbox/runtime."""
        endpoint = f"{policy_id}/attach/{runtime_id}"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = self._make_network_policy_request("DELETE", endpoint)
        data = response.json()
        return SuccessResponse(success=bool(data.get("success", True)))

    def list_for_runtime(self, runtime_id: str) -> NetworkPolicyList:
        """List network policies currently attached to a runtime."""
        response = self._make_network_policy_request(
            "GET", f"runtimes/{runtime_id}"
        )
        data = response.json()
        policies = [_parse_policy(p) for p in (data.get("policies") or [])]
        return NetworkPolicyList(policies=policies, total=len(policies))
