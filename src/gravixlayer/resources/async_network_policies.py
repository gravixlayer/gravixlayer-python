"""
Network Policies resource for the asynchronous GravixLayer client.

Same endpoints and semantics as :mod:`gravixlayer.resources.network_policies`.
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


class AsyncNetworkPolicies:
    """Async network policies resource at ``client.network_policies``."""

    def __init__(self, client):
        self.client = client

    async def _make_network_policy_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        return await self.client._make_request(
            method, endpoint, data, _service="v1/network-policies", **kwargs
        )

    async def create(
        self,
        name: str,
        egress_mode: str = "allowlist",
        description: Optional[str] = None,
        is_default: bool = False,
        rules: Optional[Sequence[Dict[str, Any]]] = None,
        project_id: Optional[str] = None,
    ) -> NetworkPolicy:
        """Create a network policy, optionally with initial egress rules."""
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
        response = await self._make_network_policy_request("POST", endpoint, body)
        policy = _parse_policy(response.json()["policy"])

        if not normalized_rules:
            return policy

        created_rules: List[NetworkPolicyRule] = []
        try:
            for rule in normalized_rules:
                created_rules.append(
                    await self.add_rule(
                        policy.id,
                        destination=rule["destination"],
                        port=rule["port"],
                        protocol=rule["protocol"],
                        description=rule.get("description"),
                        project_id=project_id,
                    )
                )
        except Exception as rule_err:
            try:
                await self.delete(policy.id, project_id=project_id)
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

    async def list(
        self,
        limit: int = 100,
        offset: int = 0,
        project_id: Optional[str] = None,
        search: Optional[str] = None,
    ) -> NetworkPolicyList:
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
        response = await self._make_network_policy_request("GET", endpoint)
        data = response.json()
        policies = [_parse_policy(p) for p in (data.get("policies") or [])]
        return NetworkPolicyList(policies=policies, total=int(data.get("total", 0)))

    async def get(
        self,
        policy_id: str,
        *,
        include_rules: bool = False,
    ) -> NetworkPolicy:
        response = await self._make_network_policy_request("GET", policy_id)
        policy = _parse_policy(response.json()["policy"])
        if include_rules:
            rule_list = await self.list_rules(policy_id)
            policy.rules = rule_list.rules
            policy.rule_count = len(rule_list.rules)
        return policy

    async def update(
        self,
        policy_id: str,
        name: Optional[str] = None,
        egress_mode: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_default: Optional[bool] = None,
        project_id: Optional[str] = None,
    ) -> NetworkPolicy:
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
        response = await self._make_network_policy_request("PATCH", endpoint, body)
        return _parse_policy(response.json()["policy"])

    async def delete(
        self, policy_id: str, project_id: Optional[str] = None
    ) -> SuccessResponse:
        endpoint = policy_id
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = await self._make_network_policy_request("DELETE", endpoint)
        data = response.json()
        return SuccessResponse(success=bool(data.get("success", True)))

    async def add_rule(
        self,
        policy_id: str,
        destination: str,
        port: int = 0,
        protocol: str = "tcp",
        description: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> NetworkPolicyRule:
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
        response = await self._make_network_policy_request("POST", endpoint, body)
        return _parse_rule(response.json()["rule"])

    async def list_rules(self, policy_id: str) -> NetworkPolicyRuleList:
        response = await self._make_network_policy_request(
            "GET", f"{policy_id}/rules"
        )
        data = response.json()
        return NetworkPolicyRuleList(
            rules=[_parse_rule(r) for r in (data.get("rules") or [])]
        )

    async def update_rule(
        self,
        policy_id: str,
        rule_id: str,
        destination: Optional[str] = None,
        port: Optional[int] = None,
        protocol: Optional[str] = None,
        description: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> NetworkPolicyRule:
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
        response = await self._make_network_policy_request("PATCH", endpoint, body)
        return _parse_rule(response.json()["rule"])

    async def delete_rule(
        self,
        policy_id: str,
        rule_id: str,
        project_id: Optional[str] = None,
    ) -> SuccessResponse:
        endpoint = f"{policy_id}/rules/{rule_id}"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = await self._make_network_policy_request("DELETE", endpoint)
        data = response.json()
        return SuccessResponse(success=bool(data.get("success", True)))

    async def attach(
        self,
        policy_id: str,
        runtime_id: str,
        project_id: Optional[str] = None,
    ) -> SuccessResponse:
        endpoint = f"{policy_id}/attach"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = await self._make_network_policy_request(
            "POST", endpoint, {"runtime_id": runtime_id}
        )
        data = response.json()
        return SuccessResponse(success=bool(data.get("success", True)))

    async def detach(
        self,
        policy_id: str,
        runtime_id: str,
        project_id: Optional[str] = None,
    ) -> SuccessResponse:
        endpoint = f"{policy_id}/attach/{runtime_id}"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = await self._make_network_policy_request("DELETE", endpoint)
        data = response.json()
        return SuccessResponse(success=bool(data.get("success", True)))

    async def list_for_runtime(
        self,
        runtime_id: str,
        *,
        include_system: bool = False,
    ) -> NetworkPolicyList:
        response = await self._make_network_policy_request(
            "GET", f"runtimes/{runtime_id}"
        )
        data = response.json()
        policies = [_parse_policy(p) for p in (data.get("policies") or [])]
        if not include_system:
            policies = [p for p in policies if not _is_system_default_policy(p)]
        return NetworkPolicyList(policies=policies, total=len(policies))
